package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.credit.CreditApplicationService.Failure;
import com.yojnasetu.gateway.credit.CreditApplicationService.TransitionException;
import com.yojnasetu.gateway.security.FieldEncryptionService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class LoanDocumentServiceTest {

    private LoanDocumentRepository repository;
    private LoanDocumentService service;

    /**
     * The real cipher on a throwaway key, not a stub. Encryption is the point
     * of storing these files this way, so the round-trip is worth exercising
     * for real rather than asserting against a fake that always agrees.
     */
    private static final FieldEncryptionService CIPHER = new FieldEncryptionService(
            Base64.getEncoder().encodeToString(new byte[32]));

    @BeforeEach
    void setUp() {
        repository = mock(LoanDocumentRepository.class);
        when(repository.save(any(LoanDocument.class))).thenAnswer(inv -> inv.getArgument(0));
        when(repository.countByApplicationId(anyString())).thenReturn(0L);
        service = new LoanDocumentService(repository, CIPHER);
    }

    private static CreditApplication application(CreditApplicationStatus status) {
        CreditApplication a = new CreditApplication();
        a.setId("app-1");
        a.setUserId("citizen-1");
        a.setStatus(status);
        return a;
    }

    private static byte[] pdf() {
        byte[] bytes = new byte[64];
        System.arraycopy("%PDF-1.7".getBytes(StandardCharsets.US_ASCII), 0, bytes, 0, 8);
        return bytes;
    }

    private static byte[] jpeg() {
        byte[] bytes = new byte[64];
        bytes[0] = (byte) 0xFF; bytes[1] = (byte) 0xD8; bytes[2] = (byte) 0xFF;
        return bytes;
    }

    private static byte[] png() {
        byte[] bytes = new byte[64];
        byte[] magic = {(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A};
        System.arraycopy(magic, 0, bytes, 0, magic.length);
        return bytes;
    }

    // -------------------------------------------------------- content type

    @Test
    void identifiesTheAcceptedFormatsFromTheirBytes() {
        assertEquals("application/pdf", LoanDocumentService.sniffContentType(pdf()));
        assertEquals("image/jpeg", LoanDocumentService.sniffContentType(jpeg()));
        assertEquals("image/png", LoanDocumentService.sniffContentType(png()));
    }

    @Test
    void refusesAFileThatMerelyClaimsToBeADocument() {
        // The whole reason for sniffing: an executable renamed proof.pdf is
        // handed to a branch rep who will open it.
        byte[] executable = new byte[64];
        executable[0] = 0x4D; executable[1] = 0x5A; // MZ

        TransitionException thrown = assertThrows(TransitionException.class,
                () -> service.store(application(CreditApplicationStatus.DRAFT), executable,
                        "income-proof.pdf", "Income proof", "citizen-1", "CITIZEN"));

        assertEquals(Failure.BAD_REQUEST, thrown.failure());
        assertTrue(thrown.getMessage().contains("PDF, JPEG and PNG"));
    }

    @Test
    void rejectsAFileTooShortToIdentify() {
        assertNull(LoanDocumentService.sniffContentType(new byte[]{0x25, 0x50}));
        assertNull(LoanDocumentService.sniffContentType(null));
    }

    // ----------------------------------------------------------- filenames

    @ParameterizedTest
    @ValueSource(strings = {
            "../../etc/passwd",
            "..\\..\\windows\\system32\\config",
            "/absolute/path/proof.pdf",
    })
    void stripsAnyPathFromAnUploadedFilename(String raw) {
        String clean = LoanDocumentService.sanitiseFilename(raw);
        assertTrue(!clean.contains("/") && !clean.contains("\\"),
                () -> "path survived sanitisation: " + clean);
    }

    @Test
    void boundsAnAbsurdFilename() {
        assertTrue(LoanDocumentService.sanitiseFilename("x".repeat(5000)).length() <= 120);
    }

    @Test
    void fallsBackToAUsableNameWhenThereIsNone() {
        assertEquals("document", LoanDocumentService.sanitiseFilename(null));
        assertEquals("document", LoanDocumentService.sanitiseFilename("   "));
        assertEquals("document", LoanDocumentService.sanitiseFilename("/"));
    }

    // -------------------------------------------------------------- limits

    @Test
    void refusesAFileOverTheSizeCeiling() {
        byte[] huge = new byte[LoanDocumentService.MAX_DOCUMENT_BYTES + 1];
        System.arraycopy(pdf(), 0, huge, 0, 8);

        TransitionException thrown = assertThrows(TransitionException.class,
                () -> service.store(application(CreditApplicationStatus.DRAFT), huge,
                        "big.pdf", "Income proof", "citizen-1", "CITIZEN"));
        assertEquals(Failure.BAD_REQUEST, thrown.failure());
        // The advice a citizen can act on, not just a limit.
        assertTrue(thrown.getMessage().contains("lower resolution"));
    }

    @Test
    void refusesAnEmptyUpload() {
        assertEquals(Failure.BAD_REQUEST, assertThrows(TransitionException.class,
                () -> service.store(application(CreditApplicationStatus.DRAFT), new byte[0],
                        "empty.pdf", "x", "citizen-1", "CITIZEN")).failure());
    }

    @Test
    void refusesToAcceptDocumentsForAClosedApplication() {
        // Accepting one would look like it achieved something.
        TransitionException thrown = assertThrows(TransitionException.class,
                () -> service.store(application(CreditApplicationStatus.REJECTED), pdf(),
                        "proof.pdf", "Income proof", "citizen-1", "CITIZEN"));
        assertEquals(Failure.CONFLICT, thrown.failure());
    }

    @Test
    void stopsAtTheDocumentCountCeiling() {
        when(repository.countByApplicationId("app-1"))
                .thenReturn((long) LoanDocumentService.MAX_DOCUMENTS_PER_APPLICATION);

        assertEquals(Failure.CONFLICT, assertThrows(TransitionException.class,
                () -> service.store(application(CreditApplicationStatus.MISSING_DOCS), pdf(),
                        "proof.pdf", "Income proof", "citizen-1", "CITIZEN")).failure());
    }

    @Test
    void acceptsDocumentsWhileMoreHaveBeenAskedFor() {
        // The state a citizen is actually in when uploading.
        LoanDocument stored = service.store(application(CreditApplicationStatus.MISSING_DOCS),
                jpeg(), "caste.jpg", "Caste certificate", "citizen-1", "CITIZEN");
        assertEquals("image/jpeg", stored.getContentType());
    }

    // ------------------------------------------------------------- storage

    @Test
    void storesContentEncryptedAndReadsItBackIntact() {
        byte[] original = pdf();
        LoanDocument stored = service.store(application(CreditApplicationStatus.DRAFT), original,
                "proof.pdf", "Income proof", "citizen-1", "CITIZEN");

        String plainBase64 = Base64.getEncoder().encodeToString(original);
        assertNotEquals(plainBase64, stored.getContent(), "content must not be stored in the clear");
        assertArrayEquals(original, service.contentOf(stored));
    }

    @Test
    void storesWithoutDoubleEncodingTheFile() {
        // The file was previously base64-encoded and then handed to encrypt(),
        // which base64s again — 78% overhead instead of 33%. Against MongoDB's
        // 16MB document limit that is the difference between a 9MB and a 12MB
        // ceiling for a stored file, and it silently halved the headroom.
        int raw = 90_000;
        byte[] bytes = new byte[raw];
        System.arraycopy(pdf(), 0, bytes, 0, 8);

        LoanDocument stored = service.store(application(CreditApplicationStatus.DRAFT), bytes,
                "proof.pdf", "Income proof", "citizen-1", "CITIZEN");

        double overhead = (double) stored.getContent().length() / raw;
        assertTrue(overhead < 1.40,
                () -> "expected ~1.34x (single base64), got " + overhead
                        + "x — the file is being encoded twice again");
        // And it still round-trips.
        assertArrayEquals(bytes, service.contentOf(stored));
    }

    @Test
    void recordsTheOriginalSizeNotTheEncodedOne() {
        LoanDocument stored = service.store(application(CreditApplicationStatus.DRAFT), pdf(),
                "proof.pdf", "Income proof", "citizen-1", "CITIZEN");
        // base64 inflates by ~33%; the figure shown to a citizen is the file's.
        assertEquals(64, stored.getSizeBytes());
    }

    @Test
    void labelsAnUnspecifiedDocumentRatherThanLeavingItBlank() {
        LoanDocument stored = service.store(application(CreditApplicationStatus.DRAFT), pdf(),
                "proof.pdf", "  ", "citizen-1", "CITIZEN");
        assertEquals("Unspecified", stored.getDocumentType());
    }

    @Test
    void neverReturnsContentInAListing() {
        LoanDocument withContent = new LoanDocument();
        withContent.setId("d-1");
        withContent.setContent(CIPHER.encrypt("secret"));
        when(repository.findByApplicationIdOrderByUploadedAtDesc("app-1"))
                .thenReturn(List.of(withContent));

        // A listing is rendered in a browser; a download is separately audited.
        assertNull(service.listFor("app-1").get(0).getContent());
    }

    @Test
    void reportsAMissingDocumentAsNotFound() {
        when(repository.findById("gone")).thenReturn(java.util.Optional.empty());
        assertEquals(Failure.NOT_FOUND,
                assertThrows(TransitionException.class, () -> service.requireDocument("gone")).failure());
    }
}
