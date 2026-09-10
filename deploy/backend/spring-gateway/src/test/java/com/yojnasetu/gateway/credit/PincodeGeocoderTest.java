package com.yojnasetu.gateway.credit;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Covers the shape check only. The Nominatim lookup itself isn't unit-tested —
 * stubbing an HTTP client to assert we parse our own stub proves nothing, and
 * hitting the live service from CI would be both flaky and a breach of its
 * usage policy. What matters here is that malformed input never reaches the
 * network at all.
 */
class PincodeGeocoderTest {

    @ParameterizedTest
    @ValueSource(strings = {
            "110001", // New Delhi
            "400001", // Mumbai
            "700001", // Kolkata
            "600001", // Chennai
            "800001", // Patna
            "999999", // upper bound of the valid shape
    })
    void acceptsRealIndianPincodes(String pincode) {
        assertTrue(PincodeGeocoder.isWellFormed(pincode));
    }

    @Test
    void toleratesSurroundingWhitespace() {
        // Citizens type with spaces, and a keyboard on a cheap phone adds them.
        assertTrue(PincodeGeocoder.isWellFormed("  110001 "));
    }

    @ParameterizedTest
    @ValueSource(strings = {
            "011001",  // Indian PIN codes never start with zero
            "000000",
            "11001",   // five digits
            "1100011", // seven
            "11000A",
            "110 001", // internal space is not the same as surrounding
            "abcdef",
            "-110001",
    })
    void rejectsAnythingThatIsNotAnIndianPincode(String pincode) {
        assertFalse(PincodeGeocoder.isWellFormed(pincode),
                () -> "should have rejected '" + pincode + "'");
    }

    @ParameterizedTest
    @NullAndEmptySource
    @ValueSource(strings = {"   "})
    void rejectsAbsentInput(String pincode) {
        assertFalse(PincodeGeocoder.isWellFormed(pincode));
    }

    @Test
    void neverCallsTheNetworkForMalformedInput() {
        // locate() short-circuits on the shape check, so this returns without
        // a request — instantly, and without throwing.
        PincodeGeocoder geocoder = new PincodeGeocoder();

        assertEquals(PincodeGeocoder.GeocodeResult.Status.NOT_FOUND, geocoder.locate("abc").status());
        assertEquals(PincodeGeocoder.GeocodeResult.Status.NOT_FOUND, geocoder.locate(null).status());
    }

    @Test
    void keepsNotFoundAndUnavailableApart() {
        // These read identically in code if both are an empty Optional, but
        // they are opposite messages to a citizen: one says you typed something
        // wrong, the other says we are broken. A slow third-party service must
        // never be reported as "that PIN code doesn't exist".
        assertTrue(PincodeGeocoder.GeocodeResult.notFound().status()
                != PincodeGeocoder.GeocodeResult.unavailable().status());

        assertFalse(PincodeGeocoder.GeocodeResult.notFound().isUnavailable());
        assertTrue(PincodeGeocoder.GeocodeResult.unavailable().isUnavailable());
        assertFalse(PincodeGeocoder.GeocodeResult.unavailable().isFound());
        assertFalse(PincodeGeocoder.GeocodeResult.notFound().isFound());
    }

    @Test
    void carriesNoLocationUnlessTheLookupSucceeded() {
        assertNull(PincodeGeocoder.GeocodeResult.notFound().location());
        assertNull(PincodeGeocoder.GeocodeResult.unavailable().location());

        var found = PincodeGeocoder.GeocodeResult.found(
                new PincodeGeocoder.Location(28.63, 77.22, "New Delhi, Delhi", "110001"));
        assertTrue(found.isFound());
        assertEquals("110001", found.location().pincode());
    }
}
