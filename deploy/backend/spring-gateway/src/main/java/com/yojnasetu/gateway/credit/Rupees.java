package com.yojnasetu.gateway.credit;

/**
 * Indian-grouped rupee formatting — ₹1,40,000 rather than ₹140,000.
 *
 * Hand-rolled because the JDK genuinely cannot do this. The Indian system
 * groups the last three digits and then in twos (1,40,000 / 50,00,000 /
 * 8,00,00,000), and {@link java.text.DecimalFormat} supports only a single
 * repeating group size, so every {@code en-IN}/{@code hi-IN} NumberFormat in
 * the JDK returns western grouping. Verified on this project's JDK before
 * writing this: all four locale spellings produce "600,000".
 *
 * This matters beyond cosmetics. The frontend formats with
 * {@code toLocaleString('en-IN')}, which DOES group Indian-style — so leaving
 * the server on the JDK default would show a citizen ₹6,00,000 on one screen
 * and ₹600,000 on the next for the same figure.
 */
public final class Rupees {

    private Rupees() {
    }

    /** Formats whole rupees with the ₹ symbol, e.g. {@code ₹1,40,000}. */
    public static String format(long amount) {
        return "₹" + (amount < 0 ? "-" : "") + group(Math.abs(amount));
    }

    private static String group(long amount) {
        String digits = Long.toString(amount);
        if (digits.length() <= 3) {
            return digits;
        }

        String lastThree = digits.substring(digits.length() - 3);
        String rest = digits.substring(0, digits.length() - 3);

        // Everything above the last three digits is grouped in twos, right to left.
        StringBuilder grouped = new StringBuilder();
        int cursor = rest.length();
        while (cursor > 2) {
            grouped.insert(0, "," + rest.substring(cursor - 2, cursor));
            cursor -= 2;
        }
        grouped.insert(0, rest, 0, cursor);

        return grouped + "," + lastThree;
    }
}
