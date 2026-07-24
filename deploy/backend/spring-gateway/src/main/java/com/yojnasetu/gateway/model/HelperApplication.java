package com.yojnasetu.gateway.model;

import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;

/**
 * A citizen's application to become a CSC helper. KYC is stored PRIVACY-SAFE:
 * only the Aadhaar HASH (SHA-256 + salt) and a masked display form are kept —
 * never the raw UID or a document image (same DPDP stance as citizen_profiles).
 * An admin reviews the application and, on approval, the applicant's user role
 * is promoted to CSC_OPERATOR.
 */
@Document(collection = "helper_applications")
@Data
@NoArgsConstructor
public class HelperApplication {

    @Id
    private String id;

    /** Applicant's userId. */
    @Indexed
    private String userId;

    private String fullName;
    private String phone;

    /** SHA-256(aadhaar + salt) — never the raw UID. */
    private String aadhaarHash;
    /** Display only, e.g. "XXXX-XXXX-1234". */
    private String aadhaarMasked;
    /** Whether the typed Aadhaar passed the Verhoeff checksum. */
    private boolean aadhaarVerified;

    /** PAN in canonical form (ABCDE1234F). */
    private String pan;

    /** Proof of work: csc_operator | ngo | panchayat | bank_mitra | other */
    private String workProofType;
    /** Free text — org name / role / anything that backs the claim. */
    private String workProofDetail;

    /** pending | approved | rejected */
    @Indexed
    private String status = "pending";

    /** Admin userId who reviewed it. */
    private String reviewedBy;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
