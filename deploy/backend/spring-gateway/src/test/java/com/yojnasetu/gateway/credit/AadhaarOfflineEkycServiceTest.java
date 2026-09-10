package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.security.FieldEncryptionService;
import net.lingala.zip4j.io.outputstream.ZipOutputStream;
import net.lingala.zip4j.model.ZipParameters;
import net.lingala.zip4j.model.enums.EncryptionMethod;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.w3c.dom.Document;
import org.w3c.dom.Element;

import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.transform.OutputKeys;
import javax.xml.transform.Transformer;
import javax.xml.transform.TransformerFactory;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.stream.StreamResult;
import java.io.ByteArrayOutputStream;
import java.io.StringWriter;
import java.util.Base64;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class AadhaarOfflineEkycServiceTest {

    private static final String SHARE_CODE = "1234";

    /** The real cipher on a throwaway key — same pattern LoanDocumentServiceTest uses. */
    private static final FieldEncryptionService CIPHER =
            new FieldEncryptionService(Base64.getEncoder().encodeToString(new byte[32]));

    private AadhaarEkycRepository repository;
    private AadhaarOfflineEkycService service;

    @BeforeEach
    void setUp() {
        repository = mock(AadhaarEkycRepository.class);
        when(repository.save(any(AadhaarEkycRecord.class))).thenAnswer(inv -> inv.getArgument(0));
        // No cert path configured — the default, honest "unverified" state.
        service = new AadhaarOfflineEkycService(repository, CIPHER, "");
    }

    private static CreditApplication application() {
        CreditApplication a = new CreditApplication();
        a.setId("app-1");
        a.setUserId("citizen-1");
        a.setStatus(CreditApplicationStatus.SUBMITTED);
        return a;
    }

    private static byte[] validZip(boolean withPhoto) throws Exception {
        DocumentBuilderFactory dbf = DocumentBuilderFactory.newInstance();
        dbf.setNamespaceAware(true);
        Document doc = dbf.newDocumentBuilder().newDocument();
        Element root = doc.createElement("OfflinePaperlessKyc");
        doc.appendChild(root);
        Element uidData = doc.createElement("UidData");
        uidData.setAttribute("uid", "xxxxxxxx1234");
        root.appendChild(uidData);
        Element poi = doc.createElement("Poi");
        poi.setAttribute("name", "RAM KUMAR");
        poi.setAttribute("dob", "01-01-1990");
        uidData.appendChild(poi);
        if (withPhoto) {
            Element pht = doc.createElement("Pht");
            pht.setTextContent(Base64.getEncoder().encodeToString(new byte[]{1, 2, 3, 4}));
            uidData.appendChild(pht);
        }

        Transformer transformer = TransformerFactory.newInstance().newTransformer();
        transformer.setOutputProperty(OutputKeys.OMIT_XML_DECLARATION, "no");
        StringWriter writer = new StringWriter();
        transformer.transform(new DOMSource(doc), new StreamResult(writer));
        byte[] xmlBytes = writer.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8);

        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        ZipParameters params = new ZipParameters();
        params.setEncryptFiles(true);
        params.setEncryptionMethod(EncryptionMethod.ZIP_STANDARD);
        params.setFileNameInZip("offline_ekyc.xml");
        try (ZipOutputStream zos = new ZipOutputStream(baos, SHARE_CODE.toCharArray())) {
            zos.putNextEntry(params);
            zos.write(xmlBytes);
            zos.closeEntry();
        }
        return baos.toByteArray();
    }

    @Test
    void extractsAndStoresARecord() throws Exception {
        AadhaarEkycRecord record = service.extractAndStore(
                application(), validZip(false), SHARE_CODE, "citizen-1", "CITIZEN");

        assertEquals("app-1", record.getApplicationId());
        assertEquals("citizen-1", record.getCitizenId());
        assertEquals("RAM KUMAR", record.getName());
        assertEquals("xxxxxxxx1234", record.getMaskedUid());
    }

    @Test
    void withNoCertConfiguredEveryRecordIsHonestlyUnverified() throws Exception {
        assertFalse(service.verificationAvailable());

        AadhaarEkycRecord record = service.extractAndStore(
                application(), validZip(false), SHARE_CODE, "citizen-1", "CITIZEN");

        assertFalse(record.isSignatureVerified());
    }

    @Test
    void encryptsThePhotoRatherThanStoringItRaw() throws Exception {
        AadhaarEkycRecord record = service.extractAndStore(
                application(), validZip(true), SHARE_CODE, "citizen-1", "CITIZEN");

        assertTrue(record.getEncryptedPhoto() != null && !record.getEncryptedPhoto().isEmpty());
        // The ciphertext must not be the plaintext bytes reinterpreted as text.
        assertFalse(record.getEncryptedPhoto().contains(
                Base64.getEncoder().encodeToString(new byte[]{1, 2, 3, 4})));
    }

    @Test
    void thePhotoRoundTripsThroughRealEncryption() throws Exception {
        AadhaarEkycRecord record = service.extractAndStore(
                application(), validZip(true), SHARE_CODE, "citizen-1", "CITIZEN");

        assertArrayEquals(new byte[]{1, 2, 3, 4}, service.photoOf(record));
    }

    @Test
    void hasNoPhotoToServeWhenTheFileCarriedNone() throws Exception {
        AadhaarEkycRecord record = service.extractAndStore(
                application(), validZip(false), SHARE_CODE, "citizen-1", "CITIZEN");

        assertThrows(CreditApplicationService.TransitionException.class, () -> service.photoOf(record));
    }

    @Test
    void listingNeverLeaksTheEncryptedPhoto() throws Exception {
        service.extractAndStore(application(), validZip(true), SHARE_CODE, "citizen-1", "CITIZEN");
        AadhaarEkycRecord withPhoto = new AadhaarEkycRecord();
        withPhoto.setApplicationId("app-1");
        withPhoto.setEncryptedPhoto("some-ciphertext");
        when(repository.findByApplicationIdOrderByExtractedAtDesc("app-1")).thenReturn(List.of(withPhoto));

        List<AadhaarEkycRecord> listed = service.listFor("app-1");

        assertNull(listed.get(0).getEncryptedPhoto());
    }

    @Test
    void refusesAFileLargerThanTheLimit() {
        byte[] tooLarge = new byte[9 * 1024 * 1024];
        var e = assertThrows(CreditApplicationService.TransitionException.class,
                () -> service.extractAndStore(application(), tooLarge, SHARE_CODE, "citizen-1", "CITIZEN"));
        assertEquals(CreditApplicationService.Failure.BAD_REQUEST, e.failure());
    }

    @Test
    void refusesUploadingToATerminalApplication() throws Exception {
        CreditApplication app = application();
        app.setStatus(CreditApplicationStatus.DISBURSED);

        var e = assertThrows(CreditApplicationService.TransitionException.class,
                () -> service.extractAndStore(app, validZip(false), SHARE_CODE, "citizen-1", "CITIZEN"));
        assertEquals(CreditApplicationService.Failure.CONFLICT, e.failure());
    }

    @Test
    void wrapsAnExtractionFailureAsABadRequestNeverAServerError() {
        var e = assertThrows(CreditApplicationService.TransitionException.class,
                () -> service.extractAndStore(application(), "not a zip".getBytes(), SHARE_CODE,
                        "citizen-1", "CITIZEN"));
        assertEquals(CreditApplicationService.Failure.BAD_REQUEST, e.failure());
    }

    @Test
    void requireRecordRefusesAnUnknownIdRatherThanReturningNull() {
        when(repository.findById("nope")).thenReturn(Optional.empty());
        var e = assertThrows(CreditApplicationService.TransitionException.class,
                () -> service.requireRecord("nope"));
        assertEquals(CreditApplicationService.Failure.NOT_FOUND, e.failure());
    }

    @Test
    void aMisconfiguredCertPathDegradesToUnverifiedRatherThanFailingBoot() {
        // Same reasoning as PincodeGeocoder degrading over a third-party outage
        // — a bad path to an optional feature must not take the app down.
        AadhaarOfflineEkycService withBadPath =
                new AadhaarOfflineEkycService(repository, CIPHER, "/nonexistent/path/to/cert.pem");

        assertFalse(withBadPath.verificationAvailable());
    }
}
