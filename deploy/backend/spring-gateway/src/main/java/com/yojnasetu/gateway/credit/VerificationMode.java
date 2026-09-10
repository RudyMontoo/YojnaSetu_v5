package com.yojnasetu.gateway.credit;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

/**
 * How an application's documents get verified.
 *
 * DIGILOCKER and ACCOUNT_AGGREGATOR are declared but not selectable — the
 * integrations don't exist yet. They are named here so the field that records
 * "how was this checked" is shaped correctly from the start, rather than
 * needing a migration once those land. {@link #isAvailable()} is what gates
 * them, so an accidental request gets a clear refusal instead of silently
 * recording a verification that never happened.
 */
public enum VerificationMode {

    /** Documents uploaded by the citizen, checked by a branch rep. */
    MANUAL("manual", true),

    /** Documents presented in person at the branch or a CSC. */
    OFFLINE("offline", true),

    /** Planned — pull issued documents from DigiLocker. */
    DIGILOCKER("digilocker", false),

    /** Planned — income verification via an Account Aggregator. */
    ACCOUNT_AGGREGATOR("account_aggregator", false);

    private final String wireName;
    private final boolean available;

    VerificationMode(String wireName, boolean available) {
        this.wireName = wireName;
        this.available = available;
    }

    @JsonValue
    public String wireName() {
        return wireName;
    }

    /** False for modes whose integration is not built. */
    public boolean isAvailable() {
        return available;
    }

    @JsonCreator
    public static VerificationMode fromWire(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        String normalised = value.trim().toLowerCase().replace('-', '_');
        for (VerificationMode mode : values()) {
            if (mode.wireName.equals(normalised)) {
                return mode;
            }
        }
        throw new IllegalArgumentException("Unknown verificationMode '" + value + "'");
    }
}
