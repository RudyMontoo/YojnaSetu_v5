package com.yojnasetu.gateway.credit;

import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;

/**
 * A citizen's application to become an assist-only helper — a CSC operator,
 * an NGO/SHG worker, or a field agent.
 *
 * Mirrors {@code HelperApplication}'s shape and privacy stance deliberately:
 * this is the same real gap that model already exists to close for the
 * general-scheme helper role, just missing on the credit side. Every
 * {@code BranchRep} account for an assist-only {@link RepType} was, before
 * this, admin-issued with no path for the CSC operator or NGO worker
 * themselves to ever ask for one — which meant the only way to actually get
 * an account was to already know someone with database access. That defeats
 * the entire point of the assisted-access model: the helpers who reach a
 * scheme's real applicants are precisely the ones with no institutional
 * relationship to whoever runs this platform.
 *
 * {@link RepType#BANK_BRANCH} is deliberately NOT an option here. A branch
 * representative is appointed by the lending Channel Partner, not
 * self-applied — see {@code BranchRepApplicationService#apply} for the
 * enforcement, not just this comment.
 *
 * KYC is stored privacy-safe, same as {@code HelperApplication}: only the
 * Aadhaar hash + masked display form, never the raw UID or a document image.
 */
@Document(collection = "branch_rep_applications")
@Data
@NoArgsConstructor
public class BranchRepApplication {

    @Id
    private String id;

    /** Applicant's userId — the citizen account this application was filed from. */
    @Indexed
    private String userId;

    // PII encrypted at rest (same FieldEncryptionService every other citizen
    // PII field in this codebase uses), decrypted only for an admin reviewer.
    private String fullName;
    private String phone;

    /** SHA-256(aadhaar + salt) — never the raw UID. */
    private String aadhaarHash;
    /** Display only, e.g. "XXXX-XXXX-1234". */
    private String aadhaarMasked;
    /** Whether the typed Aadhaar passed the Verhoeff checksum. */
    private boolean aadhaarVerified;

    /** PAN in canonical form (ABCDE1234F), encrypted at rest. */
    private String pan;

    /** Which kind of assist-only helper — CSC, NGO_SHG, or FIELD_AGENT only. */
    private RepType repType;

    /** CSC code, NGO/SHG name, or district — what {@link BranchRep#getOrganisation()} becomes on approval. */
    private String organisation;

    /** Free text backing the claim — a CSC registration number, an NGO's registration, etc. */
    private String workProofDetail;

    /** pending | approved | rejected */
    @Indexed
    private String status = "pending";

    /** Admin userId who reviewed it. */
    private String reviewedBy;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
