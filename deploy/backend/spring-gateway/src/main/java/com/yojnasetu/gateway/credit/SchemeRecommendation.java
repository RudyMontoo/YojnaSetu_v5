package com.yojnasetu.gateway.credit;

import java.util.List;

/**
 * One product assessed against one citizen's answers, with the reasoning left
 * visible. {@code matched} and {@code failed} are written to be read back to a
 * citizen verbatim — "annual family income ₹3,00,000 is within the ₹5,00,000
 * limit" — so a rejection is explainable rather than an opaque no.
 *
 * @param eligibleLoanAmount what this product would actually lend against the
 *                           stated cost, after applying coveragePct and the cap
 * @param marginMoney        the citizen's own contribution — cost minus the loan.
 *                           Surfacing this is the point: it is the most common
 *                           practical reason an otherwise-eligible application stalls
 * @param costExceedsCap     true when the project is simply too large for this
 *                           product, so the shortfall isn't mistaken for margin money
 * @param indicativeEmi      a full quote at this product's maximum tenure, or null
 *                           when the cost isn't known yet
 */
public record SchemeRecommendation(
        String productId,
        String code,
        String name,
        String type,
        Long unitCostFloor,
        Long unitCostCeiling,
        long maxLoanAmount,
        double interestRate,
        int moratoriumMonths,
        int maxTenureMonths,
        int coveragePct,
        boolean womenOnly,
        String description,
        String sourceNote,
        String sourceUrl,
        boolean figuresVerified,
        boolean eligible,
        List<String> matched,
        List<String> failed,
        List<String> missingProfileData,
        Long eligibleLoanAmount,
        Long marginMoney,
        boolean costExceedsCap,
        EmiPlan indicativeEmi) {
}
