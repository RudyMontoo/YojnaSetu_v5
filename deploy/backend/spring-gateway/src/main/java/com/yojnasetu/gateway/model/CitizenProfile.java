package com.yojnasetu.gateway.model;

import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.CompoundIndex;
import org.springframework.data.mongodb.core.index.CompoundIndexes;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;
import java.util.List;

/**
 * Per CLAUDE.md's `citizen_profiles` collection, including the v5.0 pension
 * fields from day one (this ADR-001 rewrite lands after the v5.0 doc, so
 * there's no reason to build the pre-pension shape and migrate later).
 *
 * name/dob/phone are stored ENCRYPTED (AES-256-GCM via FieldEncryptionService)
 * — callers must encrypt before save and decrypt after read. This class does
 * not encrypt itself; CitizenProfileService owns that, same separation
 * PRANJAL_HANDOFF.md specified ("use this service in CitizenProfileService,
 * never in the controller directly").
 */
@Document(collection = "citizen_profiles")
@CompoundIndexes({
        @CompoundIndex(name = "state_1_category_1_isBpl_1", def = "{'state': 1, 'category': 1, 'isBpl': 1}")
})
@Data
@NoArgsConstructor
public class CitizenProfile {

    @Id
    private String id;

    // Name matches ai_service's already-created index on this shared collection.
    @Indexed(name = "userId_1", unique = true)
    private String userId;

    // AES-256-GCM encrypted at rest — decrypt after read, encrypt before write
    private String name;
    private String dob;
    private String phone;

    private String gender; // male | female | other
    private Long annualIncome;
    private String category; // general | obc | sc | st
    private String occupation; // farmer | student | daily_wage | self_employed | unemployed
    private Boolean isBpl;
    private Boolean isDisabled;
    private Integer disabilityPct;

    @Indexed
    private String state; // 2-char code: UP, MH, RJ...
    private String district;
    private Boolean isRural;
    private Integer familySize;
    private Boolean hasLand;
    private Double landAreaAcres;

    /** SHA-256(aadhaar + server salt) — NEVER the raw UID. */
    private String aadhaarHash;
    private List<String> verifiedDocs;
    private Integer profileCompleteness = 0;

    // ── v5.0 pension fields ──────────────────────────────────────────────────
    private Boolean pensionEnrolled = false;
    private String pensionType; // SPARSH | NSAP | state | null
    private String ppoNumberHash; // SHA-256, same treatment as aadhaarHash
    private String bankIfsc;
    private String aadhaarSeedingStatus = "unknown"; // active | conflict | unknown
    private Double biometricDegradeScore; // 0-1, from Agent 11 history
    private LocalDateTime lastDlcSubmission;
    private String lastDlcPramaanId;

    private LocalDateTime consentGivenAt;
    private LocalDateTime updatedAt;
}
