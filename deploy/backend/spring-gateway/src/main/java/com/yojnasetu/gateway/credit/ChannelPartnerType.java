package com.yojnasetu.gateway.credit;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

/**
 * The kinds of institution NSFDC lends through.
 *
 * This is not a taxonomy for its own sake. NSFDC funds a scheme at one rate to
 * the channel partner, and the partner sets its own rate to the beneficiary —
 * so the SAME scheme costs the citizen very different amounts depending on who
 * processes it. Micro-finance is 6.5% through a State Channelising Agency and
 * 15% through an NBFC-MFI. Walking into the wrong branch more than doubles the
 * interest rate on an identical loan, which is why the locator needs to know
 * which types can deliver which scheme.
 */
public enum ChannelPartnerType {

    /**
     * State Channelising Agency — the state-level SC finance/development
     * corporation, one nominated per State/UT. Usually the cheapest route.
     *
     * NOT discoverable from OpenStreetMap: these are government corporations,
     * not tagged bank branches, so the locator cannot point at one. The
     * response says so rather than pretending the list is complete.
     */
    SCA("SCA", "State Channelising Agency", false),

    /** Public Sector Bank. Detectable from the branch name. */
    PSB("PSB", "Public Sector Bank", true),

    /** Regional Rural Bank — "Gramin/Grameen Bank" in the name. Detectable. */
    RRB("RRB", "Regional Rural Bank", true),

    /**
     * NBFC-MFI. Carries NSFDC's widest spread to the beneficiary (5% to the
     * MFI, 15% from it), so a citizen should know when this is the channel.
     * Not reliably detectable from OpenStreetMap bank tags.
     */
    NBFC_MFI("NBFC-MFI", "Micro-finance institution", false),

    /** Co-operative bank or society acting as a Channelising Agency. */
    COOPERATIVE("COOPERATIVE", "Co-operative bank or society", false),

    /**
     * A real, named branch whose type we could not determine from its name.
     * Deliberately NOT treated as "not a partner" — it means we don't know,
     * and saying otherwise about a real institution would misrepresent it.
     */
    UNCLASSIFIED("Unclassified", "Type not confirmed", true);

    private final String wireName;
    private final String label;
    private final boolean appearsInOpenStreetMap;

    ChannelPartnerType(String wireName, String label, boolean appearsInOpenStreetMap) {
        this.wireName = wireName;
        this.label = label;
        this.appearsInOpenStreetMap = appearsInOpenStreetMap;
    }

    @JsonValue
    public String wireName() {
        return wireName;
    }

    public String label() {
        return label;
    }

    /**
     * Whether the locator can actually find one of these. False means the
     * citizen has to be told to look elsewhere — an SCA will never show up in
     * a bank-branch search however hard we look.
     */
    public boolean appearsInOpenStreetMap() {
        return appearsInOpenStreetMap;
    }

    @JsonCreator
    public static ChannelPartnerType fromWire(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        String normalised = value.trim().toUpperCase().replace('-', '_');
        for (ChannelPartnerType type : values()) {
            if (type.name().equals(normalised) || type.wireName.equalsIgnoreCase(value.trim())) {
                return type;
            }
        }
        throw new IllegalArgumentException("Unknown channel partner type '" + value + "'");
    }
}
