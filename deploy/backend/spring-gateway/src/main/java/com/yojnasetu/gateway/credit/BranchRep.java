package com.yojnasetu.gateway.credit;

import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;

/**
 * Someone who helps work a loan file: a branch representative at the lending
 * partner, or — since {@link RepType} was added — a CSC operator, an NGO/SHG
 * worker, or a field agent.
 *
 * Follows the same shape as {@code Helper}: its own collection, an
 * admin-issued login id and password rather than OTP, and the document id used
 * as the JWT subject. Helpers are staff, not citizens of the platform, so they
 * do not belong in {@code users}.
 *
 * The class and collection are still named for the branch rep this started as.
 * Renaming both would mean migrating a live collection for a cosmetic gain, so
 * the name stays and {@link #repType} carries the real distinction.
 *
 * {@link #partnerId} is the join that was missing. An application records the
 * BRANCH a citizen chose; without this field there was no way to get from that
 * branch to a person, so every SLA reminder addressed to "the rep" reached
 * nobody. One branch may have several reps and all of them are told. It is
 * meaningful only for {@link RepType#BANK_BRANCH}: an assist-only helper is
 * attached to a citizen's application by that citizen's own authorization
 * ({@code AssistAuthorization}), not by belonging to a lending branch.
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
     * What kind of helper this is, and therefore whether they may record credit
     * decisions. Defaults to {@link RepType#BANK_BRANCH} so that every account
     * written before this field existed keeps behaving exactly as it did — the
     * alternative, a null default, would silently strip working branch reps of
     * the ability to action their own queue on the next deploy.
     */
    private RepType repType = RepType.BANK_BRANCH;

    /**
     * The branch this rep works at, matching
     * {@code CreditApplication.assignedPartnerId}. Only meaningful for
     * {@link RepType#BANK_BRANCH}; assist-only helpers reach an application
     * through the citizen's own authorization instead.
     */
    @Indexed
    private String partnerId;

    /**
     * Where an assist-only helper operates — a CSC code, an NGO or SHG name, a
     * district. Display only, so a citizen reviewing who helped them sees
     * something they recognise rather than an opaque id.
     */
    private String organisation;

    /** Denormalized for display in a queue header. */
    private String partnerName;

    private boolean active = true;

    /** Admin-issued passwords are temporary by default, as for helpers. */
    private boolean mustResetPassword = true;

    private LocalDateTime createdAt;
    private LocalDateTime lastLoginAt;

    /**
     * Hand-written so the default survives however the document was stored.
     * Lombok's generated getter would return whatever the mapper put in the
     * field, and whether Spring Data leaves a field initializer alone for a
     * property the document doesn't carry is a framework detail this shouldn't
     * bet on — a null here would read as "no known type", which callers would
     * have to treat as untrusted, locking existing branch reps out of their own
     * queue. Every account that predates {@link RepType} is a branch rep, so
     * that is what an absent value means.
     */
    public RepType getRepType() {
        return repType == null ? RepType.BANK_BRANCH : repType;
    }

    /** True for CSC, NGO/SHG and field-agent helpers — see {@link RepType}. */
    public boolean isAssistOnly() {
        return getRepType().isAssistOnly();
    }
}
