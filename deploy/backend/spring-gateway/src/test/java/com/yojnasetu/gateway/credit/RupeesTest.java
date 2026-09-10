package com.yojnasetu.gateway.credit;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * Expected values here are exactly what the frontend's
 * {@code toLocaleString('en-IN')} produces for the same numbers — that
 * agreement is the whole reason this class exists.
 */
class RupeesTest {

    @ParameterizedTest
    @CsvSource({
            "0,           ₹0",
            "500,         ₹500",
            "5000,        ₹5|000",
            "99999,       ₹99|999",
            "140000,      ₹1|40|000",          // Micro Finance cap
            "500000,      ₹5|00|000",          // income ceiling
            "600000,      ₹6|00|000",          // the case the JDK got wrong
            "2000000,     ₹20|00|000",         // education loan cap
            "5000000,     ₹50|00|000",         // term loan cap
            "80000000,    ₹8|00|00|000",       // 8 crore
            "1000000000,  ₹1|00|00|00|000",    // 100 crore
    })
    void groupsInTheIndianLakhCroreSystem(long amount, String expected) {
        // '|' stands in for ',' so the CSV itself stays parseable.
        assertEquals(expected.replace('|', ','), Rupees.format(amount));
    }

    @Test
    void keepsTheSignOutsideTheSymbol() {
        assertEquals("₹-1,40,000", Rupees.format(-140_000));
    }

    @Test
    void neverUsesWesternGroupingAboveALakh() {
        // Guards the specific regression: NumberFormat.getNumberInstance for
        // every en-IN/hi-IN spelling returns "600,000" on this JDK.
        assertEquals("₹6,00,000", Rupees.format(600_000));
    }
}
