package com.yojnasetu.gateway.credit;

/**
 * What a citizen tells us in the guided eligibility flow. Every field is
 * nullable on purpose: an unanswered question is a distinct state from a
 * question answered badly, and the response says which applies rather than
 * assuming a default and quietly producing a wrong verdict.
 *
 * @param need           {@code business} or {@code education}
 * @param estimatedCost  total project or course cost in rupees
 * @param annualIncome   annual family income in rupees
 * @param category       social category, e.g. {@code sc}
 * @param gender         {@code female}, {@code male} or {@code other}. Needed
 *                       because NSFDC's women-only schemes carry a materially
 *                       lower rate (4% against 6.5%) — without it we cannot
 *                       tell whether a woman is being shown her best option
 * @param moratoriumMode which moratorium treatment to quote (defaults to CAPITALISE)
 */
public record EligibilityRequest(
        String need,
        Long estimatedCost,
        Long annualIncome,
        String category,
        String gender,
        MoratoriumMode moratoriumMode) {

    public static final String NEED_BUSINESS = "business";
    public static final String NEED_EDUCATION = "education";
    public static final String GENDER_FEMALE = "female";

    public boolean isEducation() {
        return NEED_EDUCATION.equalsIgnoreCase(need);
    }

    /** Null when unstated — a question to ask, not an assumption to make. */
    public Boolean isFemale() {
        if (gender == null || gender.isBlank()) {
            return null;
        }
        return GENDER_FEMALE.equalsIgnoreCase(gender.trim());
    }

    public MoratoriumMode modeOrDefault() {
        return moratoriumMode == null ? MoratoriumMode.CAPITALISE : moratoriumMode;
    }
}
