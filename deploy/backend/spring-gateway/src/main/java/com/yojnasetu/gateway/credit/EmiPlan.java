package com.yojnasetu.gateway.credit;

import com.fasterxml.jackson.annotation.JsonValue;

import java.util.List;

/**
 * A complete repayment quote. {@code totalInterest} is the full cost of credit
 * measured against the amount actually disbursed — it includes everything
 * accrued or paid during the moratorium, so a citizen comparing two schemes is
 * comparing like with like.
 *
 * @param financedPrincipal what the EMI is computed against: the disbursed
 *                          amount under SERVICE_INTEREST, or the
 *                          moratorium-inflated balance under CAPITALISE
 * @param moratoriumPayment what the citizen actually hands over during the
 *                          moratorium (zero under CAPITALISE)
 */
public record EmiPlan(
        double emi,
        double totalPayment,
        double totalInterest,
        double moratoriumInterest,
        double moratoriumPayment,
        double financedPrincipal,
        int moratoriumMonths,
        MoratoriumMode moratoriumMode,
        List<ScheduleRow> schedule) {

    /**
     * One month of the loan's life. Months are numbered absolutely across the
     * whole term — moratorium months are 1..m and repayment runs m+1..m+n — so
     * a citizen never reads row 1 as their first instalment when it isn't.
     */
    public record ScheduleRow(
            int month,
            Phase phase,
            double emi,
            double principalComponent,
            double interestComponent,
            double balance) {
    }

    /**
     * Serialised lowercase to match the string the browser's schedule renderer
     * already switches on (frontend/src/lib/emiCalculator.js), so a row from
     * this API drops into the same table component unmodified.
     */
    public enum Phase {
        MORATORIUM("moratorium"),
        REPAYMENT("repayment");

        private final String wireName;

        Phase(String wireName) {
            this.wireName = wireName;
        }

        @JsonValue
        public String wireName() {
            return wireName;
        }
    }
}
