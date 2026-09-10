package com.yojnasetu.gateway.credit;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

/**
 * The specific things a citizen can agree to.
 *
 * DPDP-2023 requires consent to be purpose-specific, informed and revocable.
 * A single "consentGivenAt" timestamp on a profile — which is what this module
 * inherited — satisfies none of those: it cannot say what was agreed to, it
 * cannot be withdrawn for one purpose while kept for another, and it cannot
 * answer the question that actually matters at a branch counter, which is
 * "did this person agree to us sending their income certificate to a bank?".
 *
 * Each purpose carries the plain-language statement the citizen was shown.
 * That text is stored on the consent record itself, so if the wording changes
 * later we can still say what a given person actually agreed to rather than
 * what the current version happens to say.
 */
public enum ConsentPurpose {

    /** Storing profile details at all — the closest analogue to the old flag. */
    PROFILE_STORAGE("profile_storage",
            "I agree that Yojna Sarthi may store my personal and family details to check "
                    + "which schemes I qualify for."),

    /** Running the eligibility engine over declared income and category. */
    CREDIT_ELIGIBILITY("credit_eligibility",
            "I agree that my income, category and project details may be used to check my "
                    + "eligibility for concessional credit schemes."),

    /**
     * Sending the application and its documents to the chosen Channel Partner.
     * This is the consequential one: it is the point at which a citizen's caste
     * and income certificates leave this platform for a bank.
     */
    PARTNER_SHARING("partner_sharing",
            "I agree that my application and the documents I upload may be shared with the "
                    + "Channel Partner branch I have chosen, so that they can process my loan."),

    /** A rep opening and checking uploaded documents. */
    DOCUMENT_VERIFICATION("document_verification",
            "I agree that the documents I upload may be opened and checked by the branch "
                    + "representative handling my application."),

    /** Planned — see VerificationMode. Declared so the record shape is right. */
    DIGILOCKER_FETCH("digilocker_fetch",
            "I agree that Yojna Sarthi may fetch my issued documents from DigiLocker."),

    /** Planned. */
    ACCOUNT_AGGREGATOR_FETCH("account_aggregator_fetch",
            "I agree that my bank statement information may be fetched through an Account "
                    + "Aggregator to verify my income.");

    private final String wireName;
    private final String statement;

    ConsentPurpose(String wireName, String statement) {
        this.wireName = wireName;
        this.statement = statement;
    }

    @JsonValue
    public String wireName() {
        return wireName;
    }

    /** Exactly what the citizen is asked to agree to. Show this, verbatim. */
    public String statement() {
        return statement;
    }

    @JsonCreator
    public static ConsentPurpose fromWire(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        String normalised = value.trim().toLowerCase().replace('-', '_');
        for (ConsentPurpose purpose : values()) {
            if (purpose.wireName.equals(normalised)) {
                return purpose;
            }
        }
        throw new IllegalArgumentException("Unknown consent purpose '" + value + "'");
    }
}
