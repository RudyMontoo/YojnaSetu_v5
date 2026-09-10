package com.yojnasetu.gateway.credit;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The contract between this API and the browser's moratorium selector. These
 * strings are duplicated across two languages, so they get a test rather than a
 * comment asking people to keep them in sync.
 */
class MoratoriumModeJsonTest {

    private final ObjectMapper mapper = new ObjectMapper();

    @Test
    void serialisesToTheStringsTheFrontendAlreadyUses() throws Exception {
        assertEquals("\"capitalise\"", mapper.writeValueAsString(MoratoriumMode.CAPITALISE));
        assertEquals("\"service-interest\"", mapper.writeValueAsString(MoratoriumMode.SERVICE_INTEREST));
    }

    @ParameterizedTest
    @ValueSource(strings = {"service-interest", "SERVICE-INTEREST", "service_interest", "SERVICE_INTEREST", " service-interest "})
    void acceptsEitherSpellingInAnyCase(String wire) throws Exception {
        assertEquals(MoratoriumMode.SERVICE_INTEREST,
                mapper.readValue("\"" + wire.trim() + "\"", MoratoriumMode.class));
    }

    @Test
    void deserialisesInsideARequestBody() throws Exception {
        String json = """
                {"need":"business","estimatedCost":100000,"annualIncome":300000,
                 "category":"sc","moratoriumMode":"service-interest"}""";

        EligibilityRequest request = mapper.readValue(json, EligibilityRequest.class);
        assertEquals(MoratoriumMode.SERVICE_INTEREST, request.moratoriumMode());
    }

    @Test
    void treatsAnAbsentModeAsUnsetSoTheDefaultApplies() throws Exception {
        String json = """
                {"need":"business","estimatedCost":100000,"annualIncome":300000,"category":"sc"}""";

        EligibilityRequest request = mapper.readValue(json, EligibilityRequest.class);
        assertNull(request.moratoriumMode());
        assertEquals(MoratoriumMode.CAPITALISE, request.modeOrDefault());
    }

    @Test
    void schedulePhasesMatchTheStringsTheBrowserSwitchesOn() throws Exception {
        assertEquals("\"moratorium\"", mapper.writeValueAsString(EmiPlan.Phase.MORATORIUM));
        assertEquals("\"repayment\"", mapper.writeValueAsString(EmiPlan.Phase.REPAYMENT));
    }

    @Test
    void rejectsAnUnknownModeRatherThanQuotingTheWrongOne() {
        Exception thrown = assertThrows(Exception.class,
                () -> mapper.readValue("\"interest-free\"", MoratoriumMode.class));
        assertTrue(thrown.getMessage().contains("Unknown moratoriumMode"));
    }
}
