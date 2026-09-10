package com.yojnasetu.gateway.credit;

import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;

/**
 * Identity data extracted from a UIDAI offline eKYC file — see
 * {@link AadhaarOfflineEkycExtractor} for how, and its class javadoc for why
 * this path exists at all.
 *
 * {@link #signatureVerified} is the one field everything else defers to. It is
 * false whenever no UIDAI certificate is configured (this platform's current
 * reality) and true only when a genuine signature validated against that
 * certificate — same honesty rule as {@code VerificationMode.isAvailable()}
 * and {@code CreditProduct.figuresVerified} elsewhere in this module: an
 * unverified record is still stored and still useful (it is no worse evidence
 * than a photocopy a citizen hands across a counter), but it must never be
 * presented to anyone as more certain than it is.
 *
 * The photo, if present, is encrypted the same way {@code LoanDocument}
 * encrypts a scan — same {@code FieldEncryptionService}, same reasoning: this
 * is a picture of someone's face attached to their government identity number.
 */
@Document(collection = "aadhaar_ekyc_records")
@Data
@NoArgsConstructor
public class AadhaarEkycRecord {

    @Id
    private String id;

    @Indexed
    private String applicationId;

    @Indexed
    private String citizenId;

    private String referenceId;

    /** Always exactly "xxxxxxxx" + last 4 digits — see the extractor's masking rule. */
    private String maskedUid;

    private String name;
    private String dob;
    private String gender;
    private String careOf;
    private String addressOneLine;

    /** Base64 of the AES-GCM ciphertext, or null if the file carried no photo. */
    private String encryptedPhoto;

    private boolean signaturePresent;
    private boolean signatureVerified;

    private LocalDateTime extractedAt;
    private String uploadedByUserId;
    private String uploadedByRole;
}
