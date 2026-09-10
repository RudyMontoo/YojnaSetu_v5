package com.yojnasetu.gateway.credit;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

/**
 * What kind of person is helping, and therefore what they are allowed to do.
 *
 * The portal was built for one kind of helper: a representative at the lending
 * branch. That is not who reaches most of this scheme's applicants. Field
 * evidence on digital financial inclusion in India is consistent — people with
 * low digital literacy, feature phones, or patchy connectivity complete these
 * journeys through a trusted local intermediary, usually a CSC village-level
 * entrepreneur, an SHG or NGO worker, or a field agent. A system that only
 * issues accounts to bank staff simply has no seat for the people who actually
 * sit next to the applicant.
 *
 * The distinction that matters is NOT seniority, it is authority over the
 * money. A branch representative works for the lender and can record credit
 * decisions. A CSC operator, an NGO worker and a field agent do not work for
 * the lender: they help a citizen assemble and submit a file. Letting them
 * mark an application SANCTIONED or REJECTED would hand a credit decision to
 * someone with no mandate to make it, and would let a helper close a file the
 * lender never saw. So {@link #canRecordDecisions()} is false for all three,
 * and it is enforced server-side rather than by hiding buttons.
 *
 * Every helper type can still do the thing they exist to do — see the file
 * they are assisting on and upload documents for it — because that is the
 * inclusion problem being solved.
 */
public enum RepType {

    /**
     * Staff at the lending Channel Partner branch (bank, SCA, RRB, NBFC-MFI,
     * cooperative). The only type that may record a credit decision.
     */
    BANK_BRANCH("bank_branch", "Branch representative", true),

    /** Common Service Centre village-level entrepreneur. Assists, does not decide. */
    CSC("csc", "CSC operator", false),

    /** Self-Help Group or NGO field worker. Assists, does not decide. */
    NGO_SHG("ngo_shg", "NGO / SHG worker", false),

    /** The platform's own field agent. Assists, does not decide. */
    FIELD_AGENT("field_agent", "Field agent", false);

    private final String wireName;
    private final String label;
    private final boolean canRecordDecisions;

    RepType(String wireName, String label, boolean canRecordDecisions) {
        this.wireName = wireName;
        this.label = label;
        this.canRecordDecisions = canRecordDecisions;
    }

    @JsonValue
    public String wireName() {
        return wireName;
    }

    /** Human-readable, for a citizen's "who helped you" list. */
    public String label() {
        return label;
    }

    /**
     * Whether this helper may move an application through the credit lifecycle.
     * True only for the lender's own staff — see the class comment for why this
     * is a hard server-side line and not a UI affordance.
     */
    public boolean canRecordDecisions() {
        return canRecordDecisions;
    }

    /** Assist-only helpers work on behalf of a citizen, not a lending branch. */
    public boolean isAssistOnly() {
        return !canRecordDecisions;
    }

    @JsonCreator
    public static RepType fromWire(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        String normalised = value.trim().toLowerCase().replace('-', '_');
        for (RepType type : values()) {
            if (type.wireName.equals(normalised)) {
                return type;
            }
        }
        throw new IllegalArgumentException("Unknown repType '" + value + "'");
    }
}
