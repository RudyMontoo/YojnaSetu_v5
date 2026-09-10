package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.credit.CreditApplicationService.Failure;
import com.yojnasetu.gateway.credit.CreditApplicationService.TransitionException;
import com.yojnasetu.gateway.security.FieldEncryptionService;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.Base64;
import java.util.List;

/**
 * Storage and retrieval of loan documents.
 *
 * The file type is decided by looking at the bytes, never by trusting the
 * browser's Content-Type or the filename. Both are attacker-controlled, and
 * this codebase already takes that stance for profile photos by making
 * ImageIO decode real pixels. The same reasoning applies more strongly here,
 * because these files are handed to a branch rep who will open them.
 */
@Service
public class LoanDocumentService {

    /**
     * Sized for how citizens actually submit these: a phone photo of a
     * certificate, which on a mid-range Android is routinely 2–5MB and on a
     * high-megapixel one more. The earlier 4MB cap would have rejected a real
     * share of them with advice — "photograph it at a lower resolution" — that
     * is useless to someone who does not know how to change camera settings.
     *
     * Encrypting the bytes directly costs 33% overhead rather than the 78% of
     * base64-then-encrypt, which puts the hard ceiling at ~12MB raw against
     * MongoDB's 16MB document limit. 8MB leaves real headroom under that.
     *
     * The browser should still downscale before upload — a certificate is
     * legible at ~2000px and pushing 8MB up a rural 4G link is a bad
     * experience even when it succeeds. This limit is the backstop, not the
     * plan.
     */
    public static final int MAX_DOCUMENT_BYTES = 8 * 1024 * 1024;

    /** Enough for a scanned booklet; beyond it something is wrong. */
    public static final int MAX_DOCUMENTS_PER_APPLICATION = 20;

    private static final String PDF = "application/pdf";
    private static final String JPEG = "image/jpeg";
    private static final String PNG = "image/png";

    private final LoanDocumentRepository documents;
    private final FieldEncryptionService encryption;

    public LoanDocumentService(LoanDocumentRepository documents, FieldEncryptionService encryption) {
        this.documents = documents;
        this.encryption = encryption;
    }

    /**
     * Identifies a file from its leading bytes.
     *
     * @return the real content type, or null if it is not something we accept
     */
    public static String sniffContentType(byte[] bytes) {
        if (bytes == null || bytes.length < 8) {
            return null;
        }
        // %PDF-
        if (bytes[0] == 0x25 && bytes[1] == 0x50 && bytes[2] == 0x44 && bytes[3] == 0x46
                && bytes[4] == 0x2D) {
            return PDF;
        }
        // JPEG: FF D8 FF
        if ((bytes[0] & 0xFF) == 0xFF && (bytes[1] & 0xFF) == 0xD8 && (bytes[2] & 0xFF) == 0xFF) {
            return JPEG;
        }
        // PNG: 89 50 4E 47 0D 0A 1A 0A
        if ((bytes[0] & 0xFF) == 0x89 && bytes[1] == 0x50 && bytes[2] == 0x4E && bytes[3] == 0x47
                && bytes[4] == 0x0D && bytes[5] == 0x0A && bytes[6] == 0x1A && bytes[7] == 0x0A) {
            return PNG;
        }
        return null;
    }

    /**
     * Strips any path from an uploaded filename and bounds its length.
     *
     * A browser can send "../../etc/passwd" or a 4KB name. We never write
     * these to disk, so this is about what a rep sees rather than traversal,
     * but a filename is untrusted text and is treated as such.
     */
    public static String sanitiseFilename(String raw) {
        if (raw == null || raw.isBlank()) {
            return "document";
        }
        String name = raw.replace('\\', '/');
        name = name.substring(name.lastIndexOf('/') + 1);
        name = name.replaceAll("[\\p{Cntrl}]", "").trim();
        if (name.isBlank()) {
            return "document";
        }
        return name.length() > 120 ? name.substring(0, 120) : name;
    }

    public LoanDocument store(CreditApplication application, byte[] bytes, String rawFilename,
                              String documentType, String uploadedByUserId, String uploadedByRole) {

        if (bytes == null || bytes.length == 0) {
            throw new TransitionException(Failure.BAD_REQUEST, "No file received");
        }
        if (bytes.length > MAX_DOCUMENT_BYTES) {
            throw new TransitionException(Failure.BAD_REQUEST,
                    "Document is larger than " + (MAX_DOCUMENT_BYTES / (1024 * 1024))
                            + "MB — please photograph it at a lower resolution");
        }
        if (application.getStatus().isTerminal()) {
            // Uploading to a closed file would look like it did something.
            throw new TransitionException(Failure.CONFLICT,
                    "This application is closed (" + application.getStatus().wireName()
                            + ") and no longer accepts documents");
        }
        if (documents.countByApplicationId(application.getId()) >= MAX_DOCUMENTS_PER_APPLICATION) {
            throw new TransitionException(Failure.CONFLICT,
                    "This application already has " + MAX_DOCUMENTS_PER_APPLICATION + " documents");
        }

        String contentType = sniffContentType(bytes);
        if (contentType == null) {
            throw new TransitionException(Failure.BAD_REQUEST,
                    "Only PDF, JPEG and PNG files are accepted. Please upload a photo or scan.");
        }

        LoanDocument document = new LoanDocument();
        document.setApplicationId(application.getId());
        document.setUserId(application.getUserId());
        document.setDocumentType(documentType == null || documentType.isBlank()
                ? "Unspecified" : documentType.trim());
        document.setFilename(sanitiseFilename(rawFilename));
        document.setContentType(contentType);
        document.setSizeBytes(bytes.length);
        document.setContent(encryption.encryptBytes(bytes));
        document.setUploadedAt(LocalDateTime.now());
        document.setUploadedByUserId(uploadedByUserId);
        document.setUploadedByRole(uploadedByRole);

        return documents.save(document);
    }

    /** Metadata only — {@code content} is cleared so a listing can never leak a file. */
    public List<LoanDocument> listFor(String applicationId) {
        return documents.findByApplicationIdOrderByUploadedAtDesc(applicationId).stream()
                .peek(d -> d.setContent(null))
                .toList();
    }

    /** The decrypted bytes, for a caller that has already passed an access check. */
    public byte[] contentOf(LoanDocument document) {
        byte[] bytes = encryption.decryptBytes(document.getContent());
        if (bytes == null) {
            throw new TransitionException(Failure.NOT_FOUND, "Document content is unavailable");
        }
        return bytes;
    }

    public LoanDocument requireDocument(String documentId) {
        return documents.findById(documentId)
                .orElseThrow(() -> new TransitionException(Failure.NOT_FOUND, "Document not found"));
    }

    public void delete(LoanDocument document) {
        documents.delete(document);
    }
}
