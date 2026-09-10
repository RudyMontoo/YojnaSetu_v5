package com.yojnasetu.gateway.credit;

import java.util.List;

/**
 * The answer to "what can I get, and why".
 *
 * The three-way verdict is deliberate and mirrors the shape the Python welfare
 * engine already uses: "we can't tell yet because you haven't told us X" is a
 * different answer from "no", and collapsing the two either turns an
 * answerable question into a rejection or invents a yes we can't justify.
 *
 * @param verdict             {@code eligible}, {@code not_eligible} or {@code insufficient_data}
 * @param missingProfileData  fields to ask for to resolve an insufficient_data verdict
 */
public record EligibilityResponse(
        String verdict,
        List<SchemeRecommendation> recommendations,
        List<String> missingProfileData,
        String note) {

    public static final String ELIGIBLE = "eligible";
    public static final String NOT_ELIGIBLE = "not_eligible";
    public static final String INSUFFICIENT_DATA = "insufficient_data";
}
