package com.yojnasetu.gateway.credit;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

/**
 * Why a branch rep moved an application to a negative state.
 *
 * A code rather than free text, for two reasons: a citizen's status screen can
 * render it in their own language, and "rejected — reason: (blank)" stops being
 * possible. Reps can still attach a free-text note; the code is what the UI and
 * any later analysis rely on.
 */
public enum ReasonCode {

    INCOME_ABOVE_CEILING("income_above_ceiling", "Declared family income is above the scheme's ceiling."),
    CATEGORY_NOT_ELIGIBLE("category_not_eligible", "Applicant's category is not covered by this scheme."),
    DOCUMENTS_INCOMPLETE("documents_incomplete", "One or more required documents were not provided."),
    DOCUMENTS_ILLEGIBLE("documents_illegible", "Documents were provided but could not be read."),
    DOCUMENTS_MISMATCH("documents_mismatch", "Details on the documents do not match the application."),
    PROJECT_NOT_VIABLE("project_not_viable", "The proposed project was not assessed as viable."),
    EXISTING_LOAN_DEFAULT("existing_loan_default", "An existing loan is in default."),
    DUPLICATE_APPLICATION("duplicate_application", "An application for this scheme already exists."),
    PARTNER_FUNDS_EXHAUSTED("partner_funds_exhausted", "This partner has no funds available under the scheme right now."),
    APPLICANT_WITHDREW("applicant_withdrew", "The applicant asked to withdraw."),
    OTHER("other", "See the accompanying note.");

    private final String wireName;
    private final String description;

    ReasonCode(String wireName, String description) {
        this.wireName = wireName;
        this.description = description;
    }

    @JsonValue
    public String wireName() {
        return wireName;
    }

    public String description() {
        return description;
    }

    @JsonCreator
    public static ReasonCode fromWire(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        String normalised = value.trim().toLowerCase().replace('-', '_');
        for (ReasonCode code : values()) {
            if (code.wireName.equals(normalised)) {
                return code;
            }
        }
        throw new IllegalArgumentException("Unknown reasonCode '" + value + "'");
    }
}
