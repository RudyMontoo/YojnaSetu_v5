package com.yojnasetu.gateway.credit;

import net.lingala.zip4j.io.outputstream.ZipOutputStream;
import net.lingala.zip4j.model.ZipParameters;
import net.lingala.zip4j.model.enums.EncryptionMethod;
import org.junit.jupiter.api.Test;
import org.w3c.dom.Document;
import org.w3c.dom.Element;

import javax.xml.crypto.dsig.CanonicalizationMethod;
import javax.xml.crypto.dsig.DigestMethod;
import javax.xml.crypto.dsig.Reference;
import javax.xml.crypto.dsig.SignatureMethod;
import javax.xml.crypto.dsig.SignedInfo;
import javax.xml.crypto.dsig.Transform;
import javax.xml.crypto.dsig.XMLSignature;
import javax.xml.crypto.dsig.XMLSignatureFactory;
import javax.xml.crypto.dsig.dom.DOMSignContext;
import javax.xml.crypto.dsig.spec.TransformParameterSpec;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.transform.OutputKeys;
import javax.xml.transform.Transformer;
import javax.xml.transform.TransformerFactory;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.stream.StreamResult;
import java.io.ByteArrayOutputStream;
import java.io.StringWriter;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.util.Collections;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Builds a genuine, correctly password-protected, genuinely-signed offline
 * eKYC fixture in every test — not a canned byte array — so what's proven
 * here is the real decrypt-then-parse-then-verify pipeline, not a stub that
 * agrees with itself. The one thing NOT tested is against an actual UIDAI
 * file, which this environment has no access to; that gap is real and is
 * called out in AadhaarOfflineEkycService's own javadoc.
 */
class AadhaarOfflineEkycExtractorTest {

    private static final String SHARE_CODE = "1234";

    // ------------------------------------------------------------ fixtures

    private static byte[] buildZip(byte[] xmlBytes, String password) throws Exception {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        ZipParameters params = new ZipParameters();
        params.setEncryptFiles(true);
        params.setEncryptionMethod(EncryptionMethod.ZIP_STANDARD);
        params.setFileNameInZip("offline_ekyc.xml");
        try (ZipOutputStream zos = new ZipOutputStream(baos, password.toCharArray())) {
            zos.putNextEntry(params);
            zos.write(xmlBytes);
            zos.closeEntry();
        }
        return baos.toByteArray();
    }

    private static Document buildXml(String name, String dob, String uid, boolean withPhoto) throws Exception {
        DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();
        dbf.setNamespaceAware(true);
        Document doc = dbf.newDocumentBuilder().newDocument();

        Element root = doc.createElement("OfflinePaperlessKyc");
        root.setAttribute("referenceId", "9999999999999999999999999");
        doc.appendChild(root);

        Element uidData = doc.createElement("UidData");
        uidData.setAttribute("uid", uid);
        root.appendChild(uidData);

        Element poi = doc.createElement("Poi");
        poi.setAttribute("name", name);
        poi.setAttribute("dob", dob);
        poi.setAttribute("gender", "M");
        poi.setAttribute("co", "S/O Rajesh Kumar");
        uidData.appendChild(poi);

        Element poa = doc.createElement("Poa");
        poa.setAttribute("house", "12");
        poa.setAttribute("street", "MG Road");
        poa.setAttribute("vtc", "Ranchi");
        poa.setAttribute("dist", "Ranchi");
        poa.setAttribute("state", "Jharkhand");
        poa.setAttribute("pc", "834001");
        poa.setAttribute("country", "India");
        uidData.appendChild(poa);

        if (withPhoto) {
            Element pht = doc.createElement("Pht");
            pht.setTextContent(java.util.Base64.getEncoder().encodeToString(
                    new byte[]{(byte) 0xFF, (byte) 0xD8, (byte) 0xFF, 0x01, 0x02, 0x03}));
            uidData.appendChild(pht);
        }

        return doc;
    }

    /** Signs the document in place (enveloped signature over the whole root). */
    private static void sign(Document doc, KeyPair signingKey) throws Exception {
        XMLSignatureFactory sigFactory = XMLSignatureFactory.getInstance("DOM");
        Reference ref = sigFactory.newReference("", sigFactory.newDigestMethod(DigestMethod.SHA256, null),
                Collections.singletonList(sigFactory.newTransform(
                        Transform.ENVELOPED, (TransformParameterSpec) null)),
                null, null);
        SignedInfo signedInfo = sigFactory.newSignedInfo(
                sigFactory.newCanonicalizationMethod(CanonicalizationMethod.INCLUSIVE, (javax.xml.crypto.dsig.spec.C14NMethodParameterSpec) null),
                sigFactory.newSignatureMethod(SignatureMethod.RSA_SHA256, null),
                Collections.singletonList(ref));
        XMLSignature signature = sigFactory.newXMLSignature(signedInfo, null);
        DOMSignContext signContext = new DOMSignContext(signingKey.getPrivate(), doc.getDocumentElement());
        signature.sign(signContext);
    }

    private static byte[] toBytes(Document doc) throws Exception {
        Transformer transformer = TransformerFactory.newInstance().newTransformer();
        transformer.setOutputProperty(OutputKeys.OMIT_XML_DECLARATION, "no");
        StringWriter writer = new StringWriter();
        transformer.transform(new DOMSource(doc), new StreamResult(writer));
        return writer.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8);
    }

    private static KeyPair rsaKeyPair() throws Exception {
        KeyPairGenerator kpg = KeyPairGenerator.getInstance("RSA");
        kpg.initialize(2048);
        return kpg.generateKeyPair();
    }

    // -------------------------------------------------------------- tests

    @Test
    void extractsTheDemographicFieldsFromAGenuineZip() throws Exception {
        Document doc = buildXml("RAM KUMAR", "01-01-1990", "xxxxxxxx1234", false);
        byte[] zip = buildZip(toBytes(doc), SHARE_CODE);

        var kyc = AadhaarOfflineEkycExtractor.extract(zip, SHARE_CODE, null);

        assertEquals("RAM KUMAR", kyc.name());
        assertEquals("01-01-1990", kyc.dob());
        assertEquals("M", kyc.gender());
        assertEquals("S/O Rajesh Kumar", kyc.careOf());
        assertTrue(kyc.address().oneLine().contains("Ranchi"));
        assertTrue(kyc.address().oneLine().contains("Jharkhand"));
    }

    @Test
    void refusesTheWrongShareCodeCleanlyRatherThanCorruptedData() throws Exception {
        Document doc = buildXml("RAM KUMAR", "01-01-1990", "xxxxxxxx1234", false);
        byte[] zip = buildZip(toBytes(doc), SHARE_CODE);

        var e = assertThrows(AadhaarOfflineEkycExtractor.ExtractionException.class,
                () -> AadhaarOfflineEkycExtractor.extract(zip, "0000", null));

        assertEquals(AadhaarOfflineEkycExtractor.Reason.WRONG_SHARE_CODE, e.reason());
    }

    @Test
    void refusesNotAZipAtAll() {
        var e = assertThrows(AadhaarOfflineEkycExtractor.ExtractionException.class,
                () -> AadhaarOfflineEkycExtractor.extract("not a zip file".getBytes(), SHARE_CODE, null));

        assertEquals(AadhaarOfflineEkycExtractor.Reason.NOT_A_VALID_FILE, e.reason());
    }

    @Test
    void refusesAnEmptyUpload() {
        var e = assertThrows(AadhaarOfflineEkycExtractor.ExtractionException.class,
                () -> AadhaarOfflineEkycExtractor.extract(new byte[0], SHARE_CODE, null));
        assertEquals(AadhaarOfflineEkycExtractor.Reason.NOT_A_VALID_FILE, e.reason());
    }

    @Test
    void refusesAMissingShareCode() throws Exception {
        Document doc = buildXml("RAM KUMAR", "01-01-1990", "xxxxxxxx1234", false);
        byte[] zip = buildZip(toBytes(doc), SHARE_CODE);

        var e = assertThrows(AadhaarOfflineEkycExtractor.ExtractionException.class,
                () -> AadhaarOfflineEkycExtractor.extract(zip, "", null));
        assertEquals(AadhaarOfflineEkycExtractor.Reason.WRONG_SHARE_CODE, e.reason());
    }

    @Test
    void refusesXmlWithNoNameAsNotARealFile() throws Exception {
        DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();
        Document doc = dbf.newDocumentBuilder().newDocument();
        Element root = doc.createElement("SomethingElse");
        doc.appendChild(root);
        byte[] zip = buildZip(toBytes(doc), SHARE_CODE);

        var e = assertThrows(AadhaarOfflineEkycExtractor.ExtractionException.class,
                () -> AadhaarOfflineEkycExtractor.extract(zip, SHARE_CODE, null));
        assertEquals(AadhaarOfflineEkycExtractor.Reason.MISSING_REQUIRED_FIELDS, e.reason());
    }

    @Test
    void refusesMalformedXmlInsideAnOtherwiseValidZip() throws Exception {
        byte[] zip = buildZip("<not-even-closed".getBytes(), SHARE_CODE);

        var e = assertThrows(AadhaarOfflineEkycExtractor.ExtractionException.class,
                () -> AadhaarOfflineEkycExtractor.extract(zip, SHARE_CODE, null));
        assertEquals(AadhaarOfflineEkycExtractor.Reason.NOT_A_VALID_FILE, e.reason());
    }

    @Test
    void refusesADoctypeDeclarationInsteadOfProcessingIt() throws Exception {
        // XXE: a DOCTYPE has no legitimate place in this file format. Proving
        // this is refused (not silently expanded) is the point of the test,
        // not the specific error it comes back as.
        String malicious = "<?xml version=\"1.0\"?><!DOCTYPE OfflinePaperlessKyc [<!ENTITY x \"pwned\">]>"
                + "<OfflinePaperlessKyc><UidData uid=\"xxxxxxxx1234\"><Poi name=\"&x;\" dob=\"01-01-1990\"/>"
                + "</UidData></OfflinePaperlessKyc>";
        byte[] zip = buildZip(malicious.getBytes(java.nio.charset.StandardCharsets.UTF_8), SHARE_CODE);

        var e = assertThrows(AadhaarOfflineEkycExtractor.ExtractionException.class,
                () -> AadhaarOfflineEkycExtractor.extract(zip, SHARE_CODE, null));
        assertEquals(AadhaarOfflineEkycExtractor.Reason.NOT_A_VALID_FILE, e.reason());
    }

    @Test
    void masksTheUidToTheLastFourDigitsEvenIfTheSourceIsFullyUnmasked() throws Exception {
        // Defensive re-masking: even if a file (real or crafted) carried a full
        // 12-digit uid, this must never persist more than the last 4.
        Document doc = buildXml("RAM KUMAR", "01-01-1990", "234567891234", false);
        byte[] zip = buildZip(toBytes(doc), SHARE_CODE);

        var kyc = AadhaarOfflineEkycExtractor.extract(zip, SHARE_CODE, null);

        assertEquals("xxxxxxxx1234", kyc.maskedUid());
    }

    @Test
    void decodesAnEmbeddedPhotoWhenPresent() throws Exception {
        Document doc = buildXml("RAM KUMAR", "01-01-1990", "xxxxxxxx1234", true);
        byte[] zip = buildZip(toBytes(doc), SHARE_CODE);

        var kyc = AadhaarOfflineEkycExtractor.extract(zip, SHARE_CODE, null);

        assertArrayEquals(new byte[]{(byte) 0xFF, (byte) 0xD8, (byte) 0xFF, 0x01, 0x02, 0x03}, kyc.photo());
    }

    @Test
    void hasNoPhotoFieldWhenTheFileCarriesNone() throws Exception {
        Document doc = buildXml("RAM KUMAR", "01-01-1990", "xxxxxxxx1234", false);
        byte[] zip = buildZip(toBytes(doc), SHARE_CODE);

        assertNull(AadhaarOfflineEkycExtractor.extract(zip, SHARE_CODE, null).photo());
    }

    @Test
    void reportsUnsignedFilesHonestly() throws Exception {
        Document doc = buildXml("RAM KUMAR", "01-01-1990", "xxxxxxxx1234", false);
        byte[] zip = buildZip(toBytes(doc), SHARE_CODE);

        var kyc = AadhaarOfflineEkycExtractor.extract(zip, SHARE_CODE, rsaKeyPair().getPublic());

        assertFalse(kyc.signaturePresent());
        assertFalse(kyc.signatureVerified());
    }

    @Test
    void aGenuineSignatureValidatesAgainstTheMatchingPublicKey() throws Exception {
        KeyPair signer = rsaKeyPair();
        Document doc = buildXml("RAM KUMAR", "01-01-1990", "xxxxxxxx1234", false);
        sign(doc, signer);
        byte[] zip = buildZip(toBytes(doc), SHARE_CODE);

        var kyc = AadhaarOfflineEkycExtractor.extract(zip, SHARE_CODE, signer.getPublic());

        assertTrue(kyc.signaturePresent());
        assertTrue(kyc.signatureVerified(), "a real, matching signature must validate");
    }

    @Test
    void aRealSignatureIsNotVerifiedWithNoTrustedKeyConfigured() throws Exception {
        // The honesty rule this whole feature depends on: no certificate
        // configured must never read as "verified" just because the document
        // happens to carry SOME signature.
        KeyPair signer = rsaKeyPair();
        Document doc = buildXml("RAM KUMAR", "01-01-1990", "xxxxxxxx1234", false);
        sign(doc, signer);
        byte[] zip = buildZip(toBytes(doc), SHARE_CODE);

        var kyc = AadhaarOfflineEkycExtractor.extract(zip, SHARE_CODE, null);

        assertTrue(kyc.signaturePresent());
        assertFalse(kyc.signatureVerified());
    }

    @Test
    void aSignatureFromTheWrongKeyDoesNotValidate() throws Exception {
        // Proves this checks against OUR trust anchor, not "is there a
        // signature that verifies against ANY key" — signing with one keypair
        // and trusting a different one must fail closed.
        KeyPair signer = rsaKeyPair();
        KeyPair impostor = rsaKeyPair();
        Document doc = buildXml("RAM KUMAR", "01-01-1990", "xxxxxxxx1234", false);
        sign(doc, signer);
        byte[] zip = buildZip(toBytes(doc), SHARE_CODE);

        var kyc = AadhaarOfflineEkycExtractor.extract(zip, SHARE_CODE, impostor.getPublic());

        assertTrue(kyc.signaturePresent());
        assertFalse(kyc.signatureVerified());
    }

    @Test
    void aTamperedDocumentDoesNotValidateEvenWithTheRightKeyConfigured() throws Exception {
        // The classic signature-wrapping-adjacent check: signing genuinely
        // happened, but the payload was altered after signing.
        KeyPair signer = rsaKeyPair();
        Document doc = buildXml("RAM KUMAR", "01-01-1990", "xxxxxxxx1234", false);
        sign(doc, signer);
        // Tamper: flip the name after signing, directly on the signed DOM.
        Element uidData = (Element) doc.getDocumentElement().getElementsByTagName("UidData").item(0);
        Element poi = (Element) uidData.getElementsByTagName("Poi").item(0);
        poi.setAttribute("name", "SOMEONE ELSE");
        byte[] zip = buildZip(toBytes(doc), SHARE_CODE);

        var kyc = AadhaarOfflineEkycExtractor.extract(zip, SHARE_CODE, signer.getPublic());

        assertFalse(kyc.signatureVerified(), "a tampered document must not validate even against the right key");
    }
}
