package com.yojnasetu.gateway.credit;

import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * Matches a citizen's answers against the credit_products catalogue and
 * explains the result criterion by criterion.
 *
 * Two rules govern the output:
 *
 * 1. Never guess. A criterion the citizen hasn't answered yields
 *    {@code insufficient_data} and a request for that exact field — not a
 *    default value silently substituted, and not a rejection.
 * 2. Never quote a number without its consequences. A recommendation carries
 *    the margin money the citizen must find and a moratorium-correct EMI, so
 *    "you're eligible for ₹1.4 lakh" never reaches them stripped of what it
 *    actually costs.
 *
 * Rules live here rather than in the browser because the income ceiling is an
 * eligibility gate: enforced client-side it is one devtools edit away from
 * being bypassed.
 */
@Service
public class CreditEligibilityService {

    /** Cap on how many products to hand back, per the PRD's "1–3 schemes". */
    private static final int MAX_RECOMMENDATIONS = 3;

    private final CreditProductRepository repository;

    public CreditEligibilityService(CreditProductRepository repository) {
        this.repository = repository;
    }

    public EligibilityResponse evaluate(EligibilityRequest request) {
        List<CreditProduct> applicable = repository.findByActiveTrue().stream()
                .filter(p -> suits(p, request))
                .toList();

        if (applicable.isEmpty()) {
            return new EligibilityResponse(
                    EligibilityResponse.NOT_ELIGIBLE, List.of(), List.of(),
                    "No concessional credit product in this catalogue covers that kind of need.");
        }

        List<SchemeRecommendation> assessed = applicable.stream()
                .map(p -> assess(p, request))
                .sorted(rankBestFirst())
                .toList();

        // Union across EVERY assessed product, not just the ones we display.
        // A product that can't be assessed ranks below the eligible ones and
        // falls outside the top three — so collecting these after the cut-off
        // silently drops the question. That is how an unanswered `gender`
        // stopped being asked, hiding the 4% women's scheme from women who
        // qualified for it while the response still said "eligible".
        Set<String> missing = new LinkedHashSet<>();
        assessed.forEach(r -> missing.addAll(r.missingProfileData()));

        List<SchemeRecommendation> shown = assessed.stream()
                .limit(MAX_RECOMMENDATIONS)
                .toList();

        String verdict;
        if (shown.stream().anyMatch(SchemeRecommendation::eligible)) {
            verdict = EligibilityResponse.ELIGIBLE;
        } else if (!missing.isEmpty()) {
            verdict = EligibilityResponse.INSUFFICIENT_DATA;
        } else {
            verdict = EligibilityResponse.NOT_ELIGIBLE;
        }

        return new EligibilityResponse(verdict, shown, List.copyOf(missing),
                noteFor(verdict, !missing.isEmpty()));
    }

    /**
     * Whether this product funds the kind of thing the citizen is asking about.
     * A mismatch here is not a rejection — an education loan isn't "denied" to
     * someone opening a tea stall, it simply isn't what they asked for — so
     * these products are filtered out rather than reported as failures.
     */
    private static boolean suits(CreditProduct product, EligibilityRequest request) {
        return request.isEducation()
                ? "education".equals(product.getProjectType())
                : !"education".equals(product.getProjectType());
    }

    private SchemeRecommendation assess(CreditProduct product, EligibilityRequest request) {
        List<String> matched = new ArrayList<>();
        List<String> failed = new ArrayList<>();
        List<String> missing = new ArrayList<>();

        checkCategory(product, request, matched, failed, missing);
        checkGender(product, request, matched, failed, missing);
        checkIncome(product, request, matched, failed, missing);

        Long loanAmount = null;
        Long marginMoney = null;
        boolean costExceedsCap = false;
        EmiPlan emi = null;

        Long cost = request.estimatedCost();
        if (cost == null || cost <= 0) {
            missing.add("estimatedCost");
        } else {
            // Two separate constraints, and conflating them is the bug this
            // module previously shipped: the scheme only covers projects within
            // its unit-cost band, AND the loan itself is capped independently.
            Long ceiling = product.getUnitCostCeiling();
            Long floor = product.getUnitCostFloor();

            long coveredByLoan = Math.round(cost * (product.getCoveragePct() / 100.0));
            loanAmount = Math.min(coveredByLoan, product.getMaxLoanAmount());
            marginMoney = cost - loanAmount;
            costExceedsCap = ceiling != null && cost > ceiling;

            if (costExceedsCap) {
                failed.add("project cost " + inr(cost) + " is above this scheme's "
                        + inr(ceiling) + " limit");
            } else if (floor != null && cost < floor) {
                failed.add("project cost " + inr(cost) + " is below this scheme's "
                        + inr(floor) + " starting point");
            } else if (coveredByLoan > product.getMaxLoanAmount()) {
                // Within the band, but the loan cap bites — the citizen funds
                // the difference, so this is margin money rather than a refusal.
                matched.add("this scheme lends at most " + inr(product.getMaxLoanAmount())
                        + ", so it can fund " + inr(loanAmount) + " of your " + inr(cost) + " project");
            } else {
                matched.add("project cost " + inr(cost) + " is fundable — this scheme covers "
                        + product.getCoveragePct() + "%, so it can lend " + inr(loanAmount));
            }

            // Quote the EMI whenever an amount is computable, even on a failing
            // product: seeing the repayment is often what tells a citizen the
            // neighbouring scheme is the one they actually want.
            if (loanAmount > 0) {
                emi = EmiCalculator.calculate(loanAmount, product.getInterestRate(),
                        product.getMaxTenureMonths(), product.getMoratoriumMonths(),
                        request.modeOrDefault());
            }
        }

        boolean eligible = failed.isEmpty() && missing.isEmpty();
        return new SchemeRecommendation(
                product.getId(), product.getCode(), product.getName(), product.getType(),
                product.getUnitCostFloor(), product.getUnitCostCeiling(), product.getMaxLoanAmount(),
                product.getInterestRate(), product.getMoratoriumMonths(), product.getMaxTenureMonths(),
                product.getCoveragePct(), product.isWomenOnly(),
                product.getDescription(), product.getSourceNote(), product.getSourceUrl(),
                product.isFiguresVerified(),
                eligible, List.copyOf(matched), List.copyOf(failed), List.copyOf(missing),
                loanAmount, marginMoney, costExceedsCap, emi);
    }

    private static void checkCategory(CreditProduct product, EligibilityRequest request,
                                      List<String> matched, List<String> failed, List<String> missing) {
        List<String> required = product.getCategories();
        if (required == null || required.isEmpty()) {
            return; // no category restriction to check
        }
        String category = request.category() == null ? null : request.category().trim().toLowerCase();
        if (category == null || category.isEmpty()) {
            missing.add("category");
        } else if (required.contains(category)) {
            matched.add("category '" + category + "' is eligible for this scheme");
        } else {
            failed.add("this scheme is for " + String.join("/", required)
                    + " applicants; your category is '" + category + "'");
        }
    }

    /**
     * Women-only schemes exist to give women a lower rate, so an unstated
     * gender is asked for rather than assumed — guessing wrong here either
     * hides a 4% scheme from someone entitled to it, or offers it to someone
     * who isn't.
     */
    private static void checkGender(CreditProduct product, EligibilityRequest request,
                                    List<String> matched, List<String> failed, List<String> missing) {
        if (!product.isWomenOnly()) {
            return;
        }
        Boolean female = request.isFemale();
        if (female == null) {
            missing.add("gender");
        } else if (female) {
            matched.add("this scheme is reserved for women, at a concessional "
                    + product.getInterestRate() + "% rate");
        } else {
            failed.add("this scheme is open only to women applicants");
        }
    }

    private static void checkIncome(CreditProduct product, EligibilityRequest request,
                                    List<String> matched, List<String> failed, List<String> missing) {
        Long income = request.annualIncome();
        if (income == null) {
            missing.add("annualIncome");
        } else if (income > product.getMaxAnnualIncome()) {
            failed.add("annual family income " + inr(income) + " exceeds the "
                    + inr(product.getMaxAnnualIncome()) + " ceiling for concessional credit");
        } else {
            matched.add("annual family income " + inr(income) + " is within the "
                    + inr(product.getMaxAnnualIncome()) + " limit");
        }
    }

    /**
     * Eligible products first; among those, the one needing the least margin
     * money, then the one that costs least to repay overall.
     *
     * Margin money outranks cost deliberately — an applicant who cannot raise
     * their own share cannot take the loan at any price. Total repayment then
     * outranks the headline rate because two schemes at the same rate can
     * differ by tens of thousands once tenure and moratorium differ: Udyam
     * Nidhi and
     * Aajeevika both quote 15%, but on a ₹90,000 loan Udyam Nidhi costs
     * ₹16,764 more over its longer term.
     */
    private static Comparator<SchemeRecommendation> rankBestFirst() {
        return Comparator
                .comparing(SchemeRecommendation::eligible, Comparator.reverseOrder())
                .thenComparing(r -> r.marginMoney() == null ? Long.MAX_VALUE : r.marginMoney())
                .thenComparingDouble(r -> r.indicativeEmi() == null
                        ? Double.MAX_VALUE
                        : r.indicativeEmi().totalPayment())
                .thenComparingDouble(SchemeRecommendation::interestRate);
    }

    private static String noteFor(String verdict, boolean hasUnansweredQuestions) {
        if (EligibilityResponse.ELIGIBLE.equals(verdict) && hasUnansweredQuestions) {
            // Eligible, but something unanswered could still unlock a better
            // scheme — a woman who hasn't stated her gender is being quoted
            // 6.5% when 4% is available to her.
            return "You already qualify for the schemes below. Answering the fields in "
                    + "missingProfileData may find you one with a lower interest rate.";
        }
        return switch (verdict) {
            case EligibilityResponse.ELIGIBLE ->
                    "Eligibility here is indicative. The Channel Partner branch makes the final "
                            + "decision and may ask for documents this check doesn't cover.";
            case EligibilityResponse.INSUFFICIENT_DATA ->
                    "Answer the fields listed in missingProfileData and this can be assessed properly.";
            default ->
                    "Based on what you've told us, these schemes don't fit. A CSC or Channel "
                            + "Partner branch can check whether another programme does.";
        };
    }

    private static String inr(long amount) {
        return Rupees.format(amount);
    }
}
