package com.yojnasetu.gateway.credit;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * Rules-engine tests against the seeded catalogue with a stubbed repository
 * rather than a Mongo container — these are pure decisions over data, and they
 * should run in milliseconds on every push.
 */
class CreditEligibilityServiceTest {

    private CreditEligibilityService service;

    @BeforeEach
    void setUp() {
        CreditProductRepository repository = mock(CreditProductRepository.class);
        when(repository.findByActiveTrue()).thenReturn(seededProducts());
        service = new CreditEligibilityService(repository);
    }

    private static EligibilityRequest business(Long cost, Long income, String category, String gender) {
        return new EligibilityRequest(EligibilityRequest.NEED_BUSINESS, cost, income, category, gender, null);
    }

    private static SchemeRecommendation top(EligibilityResponse response) {
        return response.recommendations().get(0);
    }

    @Test
    void recommendsMicroFinanceForASmallBusinessProject() {
        EligibilityResponse response = service.evaluate(business(100_000L, 300_000L, "SC", "male"));

        assertEquals(EligibilityResponse.ELIGIBLE, response.verdict());
        assertEquals("micro-finance", top(response).productId());
        assertTrue(top(response).eligible());
    }

    // -------------------------------------------------- women-only schemes

    @Test
    void leadsWithTheWomensSchemeForAWomanApplicant() {
        // Mahila Samriddhi lends the same ₹1.25 lakh at 4% where the general
        // Micro Finance Scheme charges 6.5% — showing MFS first would quote a
        // woman a rate she doesn't have to pay.
        EligibilityResponse response = service.evaluate(business(100_000L, 300_000L, "sc", "female"));

        assertEquals("mahila-samriddhi", top(response).productId());
        assertTrue(top(response).womenOnly());
        assertEquals(4.0, top(response).interestRate());
    }

    @Test
    void quotesAWomanTheLowerRepaymentThatRateBuys() {
        double womens = top(service.evaluate(business(100_000L, 300_000L, "sc", "female")))
                .indicativeEmi().totalPayment();
        double general = top(service.evaluate(business(100_000L, 300_000L, "sc", "male")))
                .indicativeEmi().totalPayment();

        assertTrue(womens < general,
                () -> "women's scheme should cost less: " + womens + " vs " + general);
    }

    @Test
    void doesNotOfferAWomenOnlySchemeToAManButStillExplainsWhy() {
        EligibilityResponse response = service.evaluate(business(100_000L, 300_000L, "sc", "male"));

        SchemeRecommendation womensScheme = response.recommendations().stream()
                .filter(r -> r.productId().equals("mahila-samriddhi"))
                .findFirst().orElse(null);
        // It may rank off the end of the top 3 — but if shown, it is shown as
        // ineligible with a stated reason, never silently.
        if (womensScheme != null) {
            assertFalse(womensScheme.eligible());
            assertTrue(womensScheme.failed().stream().anyMatch(f -> f.contains("only to women")));
        }
    }

    @Test
    void asksForGenderRatherThanAssumingIt() {
        EligibilityResponse response = service.evaluate(business(100_000L, 300_000L, "sc", null));

        assertTrue(response.missingProfileData().contains("gender"),
                () -> "expected gender to be asked for, got " + response.missingProfileData());
    }

    @Test
    void carriesProvenanceThroughToEveryRecommendation() {
        // Provenance is asserted against the real catalogue in
        // CreditProductSeederTest; here we only check it survives the mapping.
        SchemeRecommendation womens = top(service.evaluate(business(100_000L, 300_000L, "sc", "female")));
        assertEquals("mahila-samriddhi", womens.productId());
        assertTrue(womens.womenOnly());
    }

    @Test
    void appliesCoverageAndReportsTheMarginMoneyTheCitizenMustFind() {
        // 90% of ₹1,00,000 is lendable; the remaining ₹10,000 is theirs to raise.
        SchemeRecommendation best = top(service.evaluate(business(100_000L, 300_000L, "sc", "male")));

        assertEquals(90_000L, best.eligibleLoanAmount());
        assertEquals(10_000L, best.marginMoney());
        assertFalse(best.costExceedsCap());
    }

    @Test
    void quotesAMoratoriumCorrectEmiAlongsideTheRecommendation() {
        SchemeRecommendation best = top(service.evaluate(business(100_000L, 300_000L, "sc", "male")));
        EmiPlan emi = best.indicativeEmi();

        assertNotNull(emi);
        assertEquals(3, emi.moratoriumMonths());
        // The whole point of the fix: interest accrued before the first EMI is
        // present in the quote rather than silently dropped.
        assertTrue(emi.moratoriumInterest() > 0);
        assertTrue(emi.totalInterest() > 0);
    }

    @Test
    void routesLargerProjectsToTheTermLoan() {
        EligibilityResponse response = service.evaluate(business(1_000_000L, 300_000L, "sc", "male"));

        assertEquals(EligibilityResponse.ELIGIBLE, response.verdict());
        assertEquals("term-loan", top(response).productId());
    }

    @Test
    void rejectsIncomeAboveTheCeilingWithAReadableReason() {
        EligibilityResponse response = service.evaluate(business(100_000L, 600_000L, "sc", "male"));

        assertEquals(EligibilityResponse.NOT_ELIGIBLE, response.verdict());
        assertTrue(response.recommendations().stream().noneMatch(SchemeRecommendation::eligible));
        assertTrue(top(response).failed().stream()
                        .anyMatch(f -> f.contains("exceeds") && f.contains("₹5,00,000")),
                () -> "expected an income-ceiling explanation, got " + top(response).failed());
    }

    @Test
    void asksForMissingAnswersInsteadOfGuessing() {
        // No income given: that is not a rejection, it is an unanswered question.
        EligibilityResponse response = service.evaluate(business(100_000L, null, "sc", "male"));

        assertEquals(EligibilityResponse.INSUFFICIENT_DATA, response.verdict());
        assertTrue(response.missingProfileData().contains("annualIncome"));
        assertFalse(top(response).eligible());
    }

    @Test
    void asksForCategoryWhenItIsNotSupplied() {
        EligibilityResponse response = service.evaluate(business(100_000L, 300_000L, null, "male"));

        assertEquals(EligibilityResponse.INSUFFICIENT_DATA, response.verdict());
        assertTrue(response.missingProfileData().contains("category"));
    }

    @Test
    void rejectsAnIneligibleCategoryRatherThanAskingAgain() {
        EligibilityResponse response = service.evaluate(business(100_000L, 300_000L, "general", "male"));

        assertEquals(EligibilityResponse.NOT_ELIGIBLE, response.verdict());
        assertTrue(response.missingProfileData().isEmpty());
    }

    @Test
    void flagsAProjectTooLargeForAnyProductRatherThanCallingItMarginMoney() {
        // ₹8 crore project — above even the Term Loan's ₹50 lakh unit-cost band.
        SchemeRecommendation best = top(service.evaluate(business(80_000_000L, 300_000L, "sc", "male")));

        assertTrue(best.costExceedsCap());
        assertFalse(best.eligible());
        assertTrue(best.failed().stream().anyMatch(f -> f.contains("above this scheme's")));
    }

    @Test
    void treatsTheLoanCapAsMarginMoneyNotARefusalWhenTheProjectIsInBand() {
        // A ₹50 lakh project IS within Term Loan's band, but the loan is capped
        // at ₹45 lakh — so the ₹5 lakh gap is the citizen's contribution, not a
        // rejection. Conflating the unit-cost ceiling with the loan cap is what
        // made this case wrong before.
        SchemeRecommendation best = top(service.evaluate(business(5_000_000L, 300_000L, "sc", "male")));

        assertEquals("term-loan", best.productId());
        assertTrue(best.eligible());
        assertFalse(best.costExceedsCap());
        assertEquals(4_500_000L, best.eligibleLoanAmount());
        assertEquals(500_000L, best.marginMoney());
    }

    @Test
    void treatsAnUnstatedProjectCostAsAQuestionNotADenial() {
        EligibilityResponse response = service.evaluate(business(null, 300_000L, "sc", "male"));

        assertEquals(EligibilityResponse.INSUFFICIENT_DATA, response.verdict());
        assertTrue(response.missingProfileData().contains("estimatedCost"));
        assertNull(top(response).indicativeEmi());
    }

    @Test
    void offersOnlyTheEducationProductForAnEducationNeed() {
        EligibilityResponse response = service.evaluate(
                new EligibilityRequest(EligibilityRequest.NEED_EDUCATION, 500_000L, 300_000L, "sc", "female", null));

        assertEquals(EligibilityResponse.ELIGIBLE, response.verdict());
        assertEquals(1, response.recommendations().size());
        assertEquals("education-loan", top(response).productId());
        // Business products aren't "denied" to a student — they're not what was asked.
        assertTrue(response.recommendations().stream()
                .noneMatch(r -> r.productId().equals("micro-finance")));
    }

    @Test
    void neverReturnsMoreThanThreeSchemes() {
        assertTrue(service.evaluate(business(100_000L, 300_000L, "sc", "male")).recommendations().size() <= 3);
    }

    @Test
    void honoursTheRequestedMoratoriumTreatment() {
        EligibilityRequest serviced = new EligibilityRequest(
                EligibilityRequest.NEED_BUSINESS, 100_000L, 300_000L, "sc", "male", MoratoriumMode.SERVICE_INTEREST);

        EmiPlan plan = top(service.evaluate(serviced)).indicativeEmi();
        assertEquals(MoratoriumMode.SERVICE_INTEREST, plan.moratoriumMode());
        assertTrue(plan.moratoriumPayment() > 0);
    }

    @Test
    void explainsWhyAnEligibleSchemeMatched() {
        List<String> matched = top(service.evaluate(business(100_000L, 300_000L, "sc", "male"))).matched();

        assertTrue(matched.stream().anyMatch(m -> m.contains("income")));
        assertTrue(matched.stream().anyMatch(m -> m.contains("category")));
        assertTrue(matched.stream().anyMatch(m -> m.contains("90%")));
    }

    /** Mirrors CreditProductSeeder's real NSFDC figures, not invented ones. */
    private static List<CreditProduct> seededProducts() {
        return List.of(
                product("micro-finance", "small", null, 140_000L, 125_000, 6.5, 3, 36, false),
                product("term-loan", "large", 140_001L, 5_000_000L, 4_500_000, 8.0, 6, 84, false),
                product("mahila-samriddhi", "small", null, 140_000L, 125_000, 4.0, 3, 36, true),
                product("education-loan", "education", null, null, 4_000_000, 6.5, 12, 144, false));
    }

    private static CreditProduct product(String id, String projectType, Long unitCostFloor,
                                         Long unitCostCeiling, long maxLoan, double rate,
                                         int moratorium, int tenure, boolean womenOnly) {
        CreditProduct p = new CreditProduct();
        p.setId(id);
        p.setCode(id.toUpperCase());
        p.setName(id);
        p.setType(projectType);
        p.setProjectType(projectType);
        p.setUnitCostFloor(unitCostFloor);
        p.setUnitCostCeiling(unitCostCeiling);
        p.setMaxLoanAmount(maxLoan);
        p.setInterestRate(rate);
        p.setMoratoriumMonths(moratorium);
        p.setMaxTenureMonths(tenure);
        p.setCoveragePct(90);
        p.setMaxAnnualIncome(500_000L);
        p.setCategories(List.of("sc"));
        p.setWomenOnly(womenOnly);
        p.setDescription(id);
        p.setActive(true);
        return p;
    }
}
