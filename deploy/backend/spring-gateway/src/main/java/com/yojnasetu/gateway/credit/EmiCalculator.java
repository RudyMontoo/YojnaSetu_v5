package com.yojnasetu.gateway.credit;

import java.util.ArrayList;
import java.util.List;

/**
 * Server-authoritative reducing-balance EMI math with moratorium handling.
 *
 * The browser runs the same arithmetic (frontend/src/lib/emiCalculator.js) so
 * sliders stay responsive, but this is the copy of record: anything persisted
 * onto an application, or shown as a figure a citizen is asked to agree to, is
 * quoted from here. The two implementations are kept deliberately identical in
 * structure so a discrepancy is easy to spot; both are covered by tests using
 * the same worked examples.
 *
 * Rates are held as doubles rather than BigDecimal. The EMI formula is
 * inherently a floating-point exponentiation, and every figure crossing the API
 * boundary is rounded to whole rupees, so the precision that BigDecimal buys
 * would be discarded at the edge anyway.
 */
public final class EmiCalculator {

    private EmiCalculator() {
    }

    /**
     * @param principal       amount actually disbursed, in rupees
     * @param annualRatePct   annual interest rate, e.g. 6.5 for 6.5%
     * @param tenureMonths    repayment months, counted AFTER the moratorium
     * @param moratoriumMonths months before the first EMI falls due (0 for none)
     */
    public static EmiPlan calculate(double principal,
                                    double annualRatePct,
                                    int tenureMonths,
                                    int moratoriumMonths,
                                    MoratoriumMode mode) {

        double p = Math.max(0, principal);
        int n = Math.max(1, tenureMonths);
        int m = Math.max(0, moratoriumMonths);
        double monthlyRate = annualRatePct / 12 / 100;
        MoratoriumMode effectiveMode = mode == null ? MoratoriumMode.CAPITALISE : mode;
        boolean servicing = effectiveMode == MoratoriumMode.SERVICE_INTEREST;

        // What the EMI is actually computed against. Under capitalisation the
        // moratorium's accrued interest joins the principal; under
        // interest-servicing it has already been paid, so principal is untouched.
        double financedPrincipal = servicing ? p : p * Math.pow(1 + monthlyRate, m);

        double moratoriumInterest = servicing
                ? p * monthlyRate * m
                : financedPrincipal - p;
        double moratoriumPayment = servicing ? moratoriumInterest : 0;

        double emi;
        if (monthlyRate == 0) {
            emi = financedPrincipal / n;
        } else {
            double factor = Math.pow(1 + monthlyRate, n);
            emi = (financedPrincipal * monthlyRate * factor) / (factor - 1);
        }

        double totalPayment = moratoriumPayment + emi * n;

        return new EmiPlan(
                emi,
                totalPayment,
                totalPayment - p,
                moratoriumInterest,
                moratoriumPayment,
                financedPrincipal,
                m,
                effectiveMode,
                buildSchedule(p, financedPrincipal, monthlyRate, emi, n, m, servicing));
    }

    private static List<EmiPlan.ScheduleRow> buildSchedule(double principal,
                                                           double financedPrincipal,
                                                           double monthlyRate,
                                                           double emi,
                                                           int n,
                                                           int m,
                                                           boolean servicing) {
        List<EmiPlan.ScheduleRow> rows = new ArrayList<>(m + n);
        double balance = principal;

        for (int month = 1; month <= m; month++) {
            double interest = balance * monthlyRate;
            if (!servicing) {
                balance += interest; // capitalised into the principal
            }
            rows.add(new EmiPlan.ScheduleRow(
                    month,
                    EmiPlan.Phase.MORATORIUM,
                    servicing ? interest : 0,
                    0,
                    interest,
                    balance));
        }

        balance = financedPrincipal;
        for (int i = 1; i <= n; i++) {
            double interest = balance * monthlyRate;
            double principalComponent = emi - interest;
            balance = Math.max(0, balance - principalComponent);
            rows.add(new EmiPlan.ScheduleRow(
                    m + i,
                    EmiPlan.Phase.REPAYMENT,
                    emi,
                    principalComponent,
                    interest,
                    balance));
        }

        return rows;
    }
}
