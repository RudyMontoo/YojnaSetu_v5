package com.yojnasetu.gateway.credit;

import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.CompoundIndex;
import org.springframework.data.mongodb.core.index.CompoundIndexes;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;

/**
 * A document a citizen uploaded against a loan application.
 *
 * These are among the most sensitive things this platform holds — a caste
 * certificate names someone's caste, an income certificate their earnings —
 * so {@link #content} is stored encrypted with the same AES-256-GCM service
 * that protects profile fields, and is never returned by a list call. Reading
 * one back is a separate, audited request.
 *
 * Stored in Mongo as encrypted base64 rather than GridFS. That is a
 * deliberate limit, not an oversight: it keeps documents inside the same
 * encryption and backup story as the rest of the record, at the cost of a hard
 * ceiling on size. Certificates are well under it; anything genuinely large
 * would need GridFS and its own key handling.
 */
@Document(collection = "loan_documents")
@CompoundIndexes({
        @CompoundIndex(name = "application_docs", def = "{'applicationId': 1, 'uploadedAt': -1}")
})
@Data
@NoArgsConstructor
public class LoanDocument {

    @Id
    private String id;

    private String applicationId;

    /** The citizen who owns the application — the ownership check keys on this. */
    private String userId;

    /**
     * What this is meant to be, matching the wording a branch rep used when
     * asking (see {@code CreditApplication.missingDocuments}), so a rep can
     * see which request an upload answers.
     */
    private String documentType;

    /** Sanitised original filename, kept only so a rep sees something familiar. */
    private String filename;

    /** Determined by inspecting the bytes, never from the Content-Type header. */
    private String contentType;

    /** Size of the ORIGINAL file, before base64 and encryption inflate it. */
    private long sizeBytes;

    /** Encrypted base64 of the file. Never included in a list response. */
    private String content;

    private LocalDateTime uploadedAt;

    /** Who uploaded — a citizen, or a helper acting for them. */
    private String uploadedByUserId;
    private String uploadedByRole;
}
