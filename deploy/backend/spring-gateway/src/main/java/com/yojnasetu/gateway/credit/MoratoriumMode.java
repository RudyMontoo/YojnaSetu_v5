package com.yojnasetu.gateway.credit;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

/**
 * How a scheme treats interest accruing during its moratorium. Every NSFDC
 * product in this module carries a moratorium of 3–12 months, and the loan is
 * still accruing interest throughout it — the two treatments below produce
 * materially different repayment figures, so a quote must state which applies
 * rather than leaving it implied.
 */
public enum MoratoriumMode {

    /**
     * Citizen pays nothing during the moratorium; accrued interest is added to
     * the principal and EMIs are computed on that larger balance. Lower
     * immediate burden, higher total cost.
     */
    CAPITALISE("capitalise"),

    /**
     * Citizen pays interest-only each moratorium month; principal is untouched,
     * so EMIs are computed on the original amount. Costs money immediately,
     * less overall.
     */
    SERVICE_INTEREST("service-interest");

    /**
     * The value on the wire. These match the string constants the browser
     * already exports (frontend/src/lib/emiCalculator.js), so the same literal
     * travels unchanged from a React select, through this API, and back into a
     * quote — rather than each side spelling the mode its own way.
     */
    private final String wireName;

    MoratoriumMode(String wireName) {
        this.wireName = wireName;
    }

    @JsonValue
    public String wireName() {
        return wireName;
    }

    /**
     * Lenient on input: accepts the wire name or the enum constant, in any case.
     * An unrecognised value is rejected rather than silently defaulting, since
     * quietly quoting the wrong moratorium treatment is exactly the class of
     * bug this module exists to stop.
     */
    @JsonCreator
    public static MoratoriumMode fromWire(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        String normalised = value.trim().toLowerCase().replace('_', '-');
        for (MoratoriumMode mode : values()) {
            if (mode.wireName.equals(normalised)) {
                return mode;
            }
        }
        throw new IllegalArgumentException("Unknown moratoriumMode '" + value
                + "' — expected one of: capitalise, service-interest");
    }
}
