package com.yojnasetu.gateway.credit;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

import java.util.EnumSet;
import java.util.Map;
import java.util.Set;

/**
 * The lifecycle of a concessional-credit application, and — importantly — which
 * moves between those states are legal.
 *
 * The welfare-tracking {@code Application} model validates only that a status
 * string is in a known set, which accepts {@code disbursed -> draft}. A loan
 * file cannot work that way: the status history is what a citizen is shown as
 * their progress and what a branch rep answers for, so the transitions are
 * enumerated here and anything else is refused.
 */
public enum CreditApplicationStatus {

    /** Started but not yet handed to a partner. Only the citizen sees it. */
    DRAFT("draft"),

    /** Citizen has submitted; awaiting pickup by the assigned Channel Partner. */
    SUBMITTED("submitted"),

    /** A branch rep is checking the documents. */
    UNDER_VERIFICATION("under_verification"),

    /** Verification paused — named documents are missing or unreadable. */
    MISSING_DOCS("missing_docs"),

    /** Verified and forwarded to the sanctioning authority. */
    FORWARDED("forwarded"),

    /** Loan approved; funds not yet released. */
    SANCTIONED("sanctioned"),

    /** Terminal. Carries a reason code. */
    REJECTED("rejected"),

    /** Terminal. Money has reached the citizen's account. */
    DISBURSED("disbursed");

    private static final Map<CreditApplicationStatus, Set<CreditApplicationStatus>> ALLOWED = Map.of(
            DRAFT, EnumSet.of(SUBMITTED),
            SUBMITTED, EnumSet.of(UNDER_VERIFICATION, REJECTED),
            UNDER_VERIFICATION, EnumSet.of(MISSING_DOCS, FORWARDED, REJECTED),
            // Returning to verification is the whole point of missing_docs — a
            // citizen who supplies what was asked for continues, they don't restart.
            MISSING_DOCS, EnumSet.of(UNDER_VERIFICATION, REJECTED),
            FORWARDED, EnumSet.of(SANCTIONED, REJECTED),
            // A sanction can still fall through before the money moves.
            SANCTIONED, EnumSet.of(DISBURSED, REJECTED),
            REJECTED, EnumSet.noneOf(CreditApplicationStatus.class),
            DISBURSED, EnumSet.noneOf(CreditApplicationStatus.class));

    private final String wireName;

    CreditApplicationStatus(String wireName) {
        this.wireName = wireName;
    }

    @JsonValue
    public String wireName() {
        return wireName;
    }

    @JsonCreator
    public static CreditApplicationStatus fromWire(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        String normalised = value.trim().toLowerCase().replace('-', '_');
        for (CreditApplicationStatus status : values()) {
            if (status.wireName.equals(normalised)) {
                return status;
            }
        }
        throw new IllegalArgumentException("Unknown status '" + value + "'");
    }

    public Set<CreditApplicationStatus> allowedNext() {
        return ALLOWED.get(this);
    }

    public boolean canMoveTo(CreditApplicationStatus next) {
        return next != null && allowedNext().contains(next);
    }

    /** No further movement is possible — the file is closed. */
    public boolean isTerminal() {
        return allowedNext().isEmpty();
    }

    /**
     * Whether this status still occupies the citizen's "one live application per
     * scheme" slot. A rejected applicant must be able to fix their documents and
     * apply again; a citizen with a file already in flight should not open a second.
     */
    public boolean isActive() {
        return !isTerminal();
    }
}
