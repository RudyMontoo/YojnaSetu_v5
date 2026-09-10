package com.yojnasetu.gateway.credit;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Worked examples deliberately mirror frontend/src/lib/emiCalculator.test.js —
 * the two implementations must agree, and testing them against the same numbers
 * is what makes a divergence show up as a failure rather than as two plausible
 * figures on two screens.
 */
class EmiCalculatorTest {

    // Micro Finance Scheme's real seeded parameters.
    private static final long PRINCIPAL = 140_000;
    private static final double RATE = 6.5;
    private static final int TENURE = 36;
    private static final int MORATORIUM = 3;

    private static void near(double expected, double actual) {
        near(expected, actual, 0.01);
    }

    private static void near(double expected, double actual, double tolerance) {
        assertTrue(Math.abs(expected - actual) < tolerance,
                () -> "expected ~" + expected + " but was " + actual);
    }

    @Test
    void matchesTheStandardFormulaWithoutAMoratorium() {
        EmiPlan plan = EmiCalculator.calculate(100_000, 12, 12, 0, MoratoriumMode.CAPITALISE);
        double r = 0.01;
        double f = Math.pow(1 + r, 12);
        near((100_000 * r * f) / (f - 1), plan.emi());
        assertEquals(12, plan.schedule().size());
    }

    @Test
    void treatsAZeroRateAsAStraightPrincipalSplit() {
        EmiPlan plan = EmiCalculator.calculate(120_000, 0, 12, 6, MoratoriumMode.CAPITALISE);
        near(10_000, plan.emi());
        near(0, plan.totalInterest());
        near(0, plan.moratoriumInterest());
    }

    @Test
    void capitalisesAccruedInterestIntoThePrincipal() {
        EmiPlan plan = EmiCalculator.calculate(PRINCIPAL, RATE, TENURE, MORATORIUM, MoratoriumMode.CAPITALISE);
        near(142_287.35, plan.financedPrincipal(), 0.05);
        near(2_287.35, plan.moratoriumInterest(), 0.05);
        near(0, plan.moratoriumPayment());
    }

    @Test
    void aMoratoriumAlwaysCostsMoreThanNone() {
        // The regression that shipped in the frontend: a moratorium was shown in
        // the UI but never entered the arithmetic, so this came out equal.
        EmiPlan with = EmiCalculator.calculate(PRINCIPAL, RATE, TENURE, MORATORIUM, MoratoriumMode.CAPITALISE);
        EmiPlan without = EmiCalculator.calculate(PRINCIPAL, RATE, TENURE, 0, MoratoriumMode.CAPITALISE);
        assertTrue(with.totalInterest() > without.totalInterest());
        assertTrue(with.emi() > without.emi());
    }

    @Test
    void servicingInterestLeavesThePrincipalAloneAndCostsLessOverall() {
        EmiPlan serviced = EmiCalculator.calculate(PRINCIPAL, RATE, TENURE, MORATORIUM, MoratoriumMode.SERVICE_INTEREST);
        EmiPlan capitalised = EmiCalculator.calculate(PRINCIPAL, RATE, TENURE, MORATORIUM, MoratoriumMode.CAPITALISE);

        near(PRINCIPAL, serviced.financedPrincipal());
        near(PRINCIPAL * (RATE / 12 / 100) * MORATORIUM, serviced.moratoriumPayment());
        near(EmiCalculator.calculate(PRINCIPAL, RATE, TENURE, 0, MoratoriumMode.CAPITALISE).emi(), serviced.emi());
        assertTrue(serviced.totalPayment() < capitalised.totalPayment());
    }

    @ParameterizedTest
    @EnumSource(MoratoriumMode.class)
    void scheduleSpansTheWholeLoanLifeWithAbsoluteMonthNumbers(MoratoriumMode mode) {
        List<EmiPlan.ScheduleRow> rows =
                EmiCalculator.calculate(PRINCIPAL, RATE, TENURE, MORATORIUM, mode).schedule();

        assertEquals(MORATORIUM + TENURE, rows.size());
        for (int i = 0; i < rows.size(); i++) {
            assertEquals(i + 1, rows.get(i).month());
            EmiPlan.Phase expected = i < MORATORIUM ? EmiPlan.Phase.MORATORIUM : EmiPlan.Phase.REPAYMENT;
            assertEquals(expected, rows.get(i).phase());
        }
    }

    @ParameterizedTest
    @EnumSource(MoratoriumMode.class)
    void amortisesToZeroAndReconcilesInterest(MoratoriumMode mode) {
        EmiPlan plan = EmiCalculator.calculate(PRINCIPAL, RATE, TENURE, MORATORIUM, mode);

        near(0, plan.schedule().get(plan.schedule().size() - 1).balance());

        // Row-level interest must add up to the headline figure — an identity
        // that holds in both modes and catches most arithmetic drift.
        double summed = plan.schedule().stream()
                .mapToDouble(EmiPlan.ScheduleRow::interestComponent)
                .sum();
        near(plan.totalInterest(), summed, 0.02);
    }

    @Test
    void noEmiIsDueDuringACapitalisedMoratorium() {
        EmiPlan plan = EmiCalculator.calculate(PRINCIPAL, RATE, TENURE, MORATORIUM, MoratoriumMode.CAPITALISE);
        plan.schedule().stream()
                .filter(r -> r.phase() == EmiPlan.Phase.MORATORIUM)
                .forEach(r -> {
                    near(0, r.emi());
                    near(0, r.principalComponent());
                    assertTrue(r.interestComponent() > 0);
                });
    }

    @Test
    void educationLoanAccruesTwelveMonthsBeforeTheFirstEmi() {
        EmiPlan plan = EmiCalculator.calculate(2_000_000, 6.5, 120, 12, MoratoriumMode.CAPITALISE);
        near(2_000_000 * Math.pow(1 + 0.065 / 12, 12), plan.financedPrincipal(), 0.05);
        assertTrue(plan.moratoriumInterest() > 130_000);
        assertEquals(12, plan.schedule().stream()
                .filter(r -> r.phase() == EmiPlan.Phase.MORATORIUM).count());
    }

    @Test
    void defaultsToCapitalisingWhenNoModeIsGiven() {
        EmiPlan explicit = EmiCalculator.calculate(PRINCIPAL, RATE, TENURE, MORATORIUM, MoratoriumMode.CAPITALISE);
        EmiPlan defaulted = EmiCalculator.calculate(PRINCIPAL, RATE, TENURE, MORATORIUM, null);
        near(explicit.emi(), defaulted.emi());
        assertEquals(MoratoriumMode.CAPITALISE, defaulted.moratoriumMode());
    }
}
