package com.yojnasetu.gateway.credit;

import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;

/**
 * A Channel Partner branch representative — the person who actually works a
 * loan file.
 *
 * Follows the same shape as {@code Helper}: its own collection, an
 * admin-issued login id and password rather than OTP, and the document id used
 * as the JWT subject. Reps are staff at a partner institution, not citizens of
 * the platform, so they do not belong in {@code users}.
 *
 * {@link #partnerId} is the join that was missing. An application records the
 * BRANCH a citizen chose; without this field there was no way to get from that
 * branch to a person, so every SLA reminder addressed to "the rep" reached
 * nobody. One branch may have several reps and all of them are told.
 */
@Document(collection = "branch_reps")
@Data
@NoArgsConstructor
public class BranchRep {

    @Id
    private String id;

    /** Admin-issued login identifier, e.g. "BOB-CP-014". */
    @Indexed(unique = true)
    private String repId;

    private String passwordHash;

    private String name;

    // Contact details live here so notifications can reach a rep the same way
    // they reach a citizen — see NotificationService's recipient resolution.
    private String phone;
    private String email;

    /**
     * The branch this rep works at, matching
     * {@code CreditApplication.assignedPartnerId}.
     */
    @Indexed
    private String partnerId;

    /** Denormalized for display in a queue header. */
    private String partnerName;

    private boolean active = true;

    /** Admin-issued passwords are temporary by default, as for helpers. */
    private boolean mustResetPassword = true;

    private LocalDateTime createdAt;
    private LocalDateTime lastLoginAt;
}
