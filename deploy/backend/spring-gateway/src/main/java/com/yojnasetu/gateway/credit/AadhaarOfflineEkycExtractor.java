package com.yojnasetu.gateway.credit;

import net.lingala.zip4j.exception.ZipException;
import net.lingala.zip4j.io.inputstream.ZipInputStream;
import net.lingala.zip4j.model.LocalFileHeader;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

import javax.xml.crypto.dsig.XMLSignatureFactory;
import javax.xml.crypto.dsig.dom.DOMValidateContext;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.security.PublicKey;

import java.util.Base64;

/**
 * Reads a UIDAI offline eKYC download — the ZIP a resident gets from
 * resident.uidai.gov.in, protected with a 4-digit share code THEY chose — and
 * extracts identity data without any network call, live OTP, or DigiLocker
 * account.
 *
 * This exists because DigiLocker and live Aadhaar OTP both assume things a
 * large share of this scheme's applicants cannot reliably do: their own
 * DigiLocker account, a phone number that still matches Aadhaar, working
 * connectivity at the exact moment of verification. Offline eKYC needs none of
 * that at verification time — the file is downloaded once, at a CSC if
 * necessary, and can be read here whenever, online or off. UIDAI's own
 * signature is what makes the data trustworthy without a live check.
 *
 * Three things this class is careful about, because the input is fully
 * untrusted and the output is someone's identity document:
 *
 *   1. XXE. This parses XML from a citizen upload. DTD processing is
 *      disabled outright — UIDAI's file never has or needs a DOCTYPE, so
 *      there is no legitimate case this breaks, only an attack surface it
 *      closes.
 *   2. The signature is checked against OUR configured trust anchor, never
 *      against whatever certificate the file itself claims to carry. A
 *      KeyInfo block inside untrusted XML is a claim, not a fact — the only
 *      question worth asking is "does this validate against the UIDAI
 *      certificate we ourselves loaded", and that is the only question this
 *      asks. No certificate configured means no possible "yes" — see
 *      {@link ExtractedKyc#signatureVerified()}.
 *   3. The UID is masked defensively even though UIDAI already ships it
 *      pre-masked in this file format. If that ever changes upstream, this
 *      class still never persists more than the last 4 digits.
 */
public final class AadhaarOfflineEkycExtractor {

    private AadhaarOfflineEkycExtractor() {
    }

    public enum Reason {
        WRONG_SHARE_CODE,
        NOT_A_VALID_FILE,
        MISSING_REQUIRED_FIELDS,
    }

    public static class ExtractionException extends RuntimeException {
        private final Reason reason;

        public ExtractionException(Reason reason, String message) {
            super(message);
            this.reason = reason;
        }

        public Reason reason() {
            return reason;
        }
    }

    public record Address(String house, String street, String landmark, String locality,
                          String vtc, String subDistrict, String district, String state,
                          String pinCode, String postOffice, String country) {

        /** For display — a rep or citizen reading this back should see one readable line. */
        public String oneLine() {
            return java.util.stream.Stream.of(house, street, landmark, locality, vtc,
                            postOffice, subDistrict, district, state, pinCode, country)
                    .filter(s -> s != null && !s.isBlank())
                    .reduce((a, b) -> a + ", " + b)
                    .orElse("");
        }

        boolean isEmpty() {
            return oneLine().isBlank();
        }
    }

    public record ExtractedKyc(
            String referenceId,
            /** Last 4 digits only, e.g. "xxxxxxxx1234" — never the full number. */
            String maskedUid,
            String name,
            String dob,
            String gender,
            String careOf,
            Address address,
            /** Raw JPEG bytes, or null if the file carried no photo or it didn't decode. Caller encrypts before storing. */
            byte[] photo,
            boolean signaturePresent,
            /** True only if a signature was present AND validated against the configured UIDAI certificate. */
            boolean signatureVerified) {
    }

    public static ExtractedKyc extract(byte[] zipBytes, String shareCode, PublicKey trustedUidaiKey) {
        if (zipBytes == null || zipBytes.length == 0) {
            throw new ExtractionException(Reason.NOT_A_VALID_FILE, "No file received");
        }
        if (shareCode == null || shareCode.isBlank()) {
            throw new ExtractionException(Reason.WRONG_SHARE_CODE, "Share code is required");
        }

        byte[] xmlBytes = readXmlEntry(zipBytes, shareCode);
        Document doc = parseXml(xmlBytes);
        return toExtractedKyc(doc, trustedUidaiKey);
    }

    // ------------------------------------------------------------- unzip

    private static byte[] readXmlEntry(byte[] zipBytes, String shareCode) {
        try (ZipInputStream zis = new ZipInputStream(new ByteArrayInputStream(zipBytes), shareCode.toCharArray())) {
            LocalFileHeader entry;
            while ((entry = zis.getNextEntry()) != null) {
                if (!entry.getFileName().toLowerCase().endsWith(".xml")) {
                    continue;
                }
                ByteArrayOutputStream out = new ByteArrayOutputStream();
                zis.transferTo(out);
                return out.toByteArray();
            }
        } catch (ZipException e) {
            // Zip4j's message for a wrong password varies by the encryption
            // method UIDAI used across format revisions (legacy ZipCrypto vs
            // AES). Rather than pattern-match message text, which breaks
            // silently on a library upgrade, any failure to read an encrypted
            // entry is reported as a wrong share code — by far the most likely
            // real cause, and the one the citizen can actually act on.
            throw new ExtractionException(Reason.WRONG_SHARE_CODE,
                    "Could not open this file with that share code. Check the 4-digit code and try again.");
        } catch (IOException e) {
            throw new ExtractionException(Reason.NOT_A_VALID_FILE,
                    "This doesn't look like a UIDAI offline eKYC download.");
        }
        throw new ExtractionException(Reason.NOT_A_VALID_FILE,
                "No XML data found inside this file.");
    }

    // -------------------------------------------------------------- parse

    private static Document parseXml(byte[] xmlBytes) {
        try {
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            // XXE hardening. This format never has or needs a DOCTYPE — closing
            // this leaves no legitimate case broken, only an attack surface shut.
            factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            factory.setXIncludeAware(false);
            factory.setExpandEntityReferences(false);
            factory.setNamespaceAware(true);
            DocumentBuilder builder = factory.newDocumentBuilder();
            return builder.parse(new ByteArrayInputStream(xmlBytes));
        } catch (Exception e) {
            throw new ExtractionException(Reason.NOT_A_VALID_FILE,
                    "This doesn't look like a valid UIDAI offline eKYC XML.");
        }
    }

    private static ExtractedKyc toExtractedKyc(Document doc, PublicKey trustedUidaiKey) {
        Element root = doc.getDocumentElement();

        Element uidData = firstChildNamed(root, "UidData");
        Element poi = uidData == null ? null : firstChildNamed(uidData, "Poi");
        Element poa = uidData == null ? null : firstChildNamed(uidData, "Poa");
        Element pht = uidData == null ? null : firstChildNamed(uidData, "Pht");

        String name = poi == null ? null : attr(poi, "name");
        if (name == null || name.isBlank()) {
            throw new ExtractionException(Reason.MISSING_REQUIRED_FIELDS,
                    "This file doesn't contain a name — it may not be a real offline eKYC download.");
        }

        String referenceId = attr(root, "referenceId");
        String rawUid = uidData == null ? null : attr(uidData, "uid");

        Address address = poa == null ? null : new Address(
                attr(poa, "house"), attr(poa, "street"), attr(poa, "lm"), attr(poa, "loc"),
                attr(poa, "vtc"), attr(poa, "subdist"), attr(poa, "dist"), attr(poa, "state"),
                attr(poa, "pc"), attr(poa, "po"), attr(poa, "country"));

        byte[] photo = null;
        if (pht != null) {
            String base64 = pht.getTextContent();
            if (base64 != null && !base64.isBlank()) {
                try {
                    photo = Base64.getDecoder().decode(base64.trim());
                } catch (IllegalArgumentException ignored) {
                    // A bad photo blob is not a reason to reject an otherwise
                    // legitimate identity record — the demographic data still
                    // stands on its own.
                }
            }
        }

        boolean signaturePresent = findSignatureElement(doc) != null;
        boolean signatureVerified = signaturePresent && trustedUidaiKey != null
                && verifySignature(doc, trustedUidaiKey);

        return new ExtractedKyc(
                referenceId,
                maskUid(rawUid),
                name,
                poi == null ? null : attr(poi, "dob"),
                poi == null ? null : attr(poi, "gender"),
                poi == null ? attr(poa, "co") : attr(poi, "co"),
                (address == null || address.isEmpty()) ? null : address,
                photo,
                signaturePresent,
                signatureVerified);
    }

    private static Element findSignatureElement(Document doc) {
        NodeList sigs = doc.getElementsByTagNameNS("http://www.w3.org/2000/09/xmldsig#", "Signature");
        return sigs.getLength() == 0 ? null : (Element) sigs.item(0);
    }

    /**
     * Validated against the certificate WE configured, ignoring whatever
     * KeyInfo the document itself carries — see the class javadoc. A
     * malformed or unparseable signature is reported as unverified, never
     * thrown: an invalid signature is a fact about the data, not a system
     * failure.
     */
    private static boolean verifySignature(Document doc, PublicKey trustedUidaiKey) {
        try {
            Element signatureNode = findSignatureElement(doc);
            if (signatureNode == null) {
                return false;
            }
            XMLSignatureFactory factory = XMLSignatureFactory.getInstance("DOM");
            DOMValidateContext context = new DOMValidateContext(new FixedKeySelector(trustedUidaiKey), signatureNode);
            javax.xml.crypto.dsig.XMLSignature signature = factory.unmarshalXMLSignature(context);
            return signature.validate(context);
        } catch (Exception e) {
            return false;
        }
    }

    /**
     * Defensive re-masking. UIDAI's own offline eKYC XML already ships the
     * {@code uid} attribute pre-masked to the last 4 digits — this is a second
     * line of defence, not the primary one, for exactly the case where that
     * assumption stops holding (a format change, a different generator, a
     * hand-crafted test file). Never returns more than 4 trailing digits.
     */
    private static String maskUid(String rawUid) {
        if (rawUid == null || rawUid.isBlank()) {
            return null;
        }
        String digitsOnly = rawUid.replaceAll("[^0-9]", "");
        String last4 = digitsOnly.length() >= 4
                ? digitsOnly.substring(digitsOnly.length() - 4)
                : digitsOnly;
        return "x".repeat(8) + last4;
    }

    private static Element firstChildNamed(Element parent, String localName) {
        NodeList children = parent.getChildNodes();
        for (int i = 0; i < children.getLength(); i++) {
            Node child = children.item(i);
            if (child.getNodeType() == Node.ELEMENT_NODE && localName.equals(child.getLocalName())) {
                return (Element) child;
            }
        }
        return null;
    }

    private static String attr(Element element, String name) {
        if (element == null || !element.hasAttribute(name)) {
            return null;
        }
        String value = element.getAttribute(name);
        return value.isBlank() ? null : value.trim();
    }

    /**
     * Ignores whatever key the document's own KeyInfo claims and always
     * resolves to the certificate WE configured — the whole point being that
     * a signature only counts as verified against a trust anchor we chose,
     * never against a key the untrusted input supplied about itself.
     */
    private static final class FixedKeySelector extends javax.xml.crypto.KeySelector {
        private final PublicKey key;

        FixedKeySelector(PublicKey key) {
            this.key = key;
        }

        @Override
        public javax.xml.crypto.KeySelectorResult select(javax.xml.crypto.dsig.keyinfo.KeyInfo keyInfo,
                                                          Purpose purpose,
                                                          javax.xml.crypto.AlgorithmMethod method,
                                                          javax.xml.crypto.XMLCryptoContext context) {
            return () -> key;
        }
    }
}
