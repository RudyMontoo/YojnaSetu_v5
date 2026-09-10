package com.yojnasetu.gateway.config;

import com.yojnasetu.gateway.credit.ChannelPartnerType;
import com.yojnasetu.gateway.credit.ConsentPurpose;
import com.yojnasetu.gateway.credit.CreditApplicationStatus;
import com.yojnasetu.gateway.credit.MoratoriumMode;
import com.yojnasetu.gateway.credit.ReasonCode;
import com.yojnasetu.gateway.credit.VerificationMode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.format.support.DefaultFormattingConversionService;
import org.springframework.format.support.FormattingConversionService;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Pins the fix for a bug that only showed up when the app was running.
 *
 * @JsonCreator covers request bodies. Path variables and query parameters use
 * the ConversionService, which defaults to Enum.valueOf — so
 * ?status=under_verification returned 400 while the same string inside a JSON
 * body parsed correctly. Every unit test passed, because none of them went
 * through Spring MVC's parameter binding.
 */
class WireEnumConvertersTest {

    private FormattingConversionService conversion;

    @BeforeEach
    void setUp() {
        conversion = new DefaultFormattingConversionService();
        new WireEnumConverters().addFormatters(conversion);
    }

    @Test
    void readsTheStatusTheApiContractTellsTheFrontendToSend() {
        // The exact value documented in SIH-CREDIT-API.md for the queue filter.
        assertEquals(CreditApplicationStatus.UNDER_VERIFICATION,
                conversion.convert("under_verification", CreditApplicationStatus.class));
        assertEquals(CreditApplicationStatus.MISSING_DOCS,
                conversion.convert("missing_docs", CreditApplicationStatus.class));
    }

    @Test
    void readsAConsentPurposeFromAPathVariable() {
        assertEquals(ConsentPurpose.PARTNER_SHARING,
                conversion.convert("partner_sharing", ConsentPurpose.class));
    }

    @Test
    void readsTheHyphenatedSpellingsToo() {
        assertEquals(MoratoriumMode.SERVICE_INTEREST,
                conversion.convert("service-interest", MoratoriumMode.class));
        assertEquals(ChannelPartnerType.NBFC_MFI,
                conversion.convert("NBFC-MFI", ChannelPartnerType.class));
    }

    @Test
    void readsReasonCodesAndVerificationModes() {
        assertEquals(ReasonCode.DOCUMENTS_INCOMPLETE,
                conversion.convert("documents_incomplete", ReasonCode.class));
        assertEquals(VerificationMode.MANUAL,
                conversion.convert("manual", VerificationMode.class));
    }

    @Test
    void stillRefusesAValueThatMeansNothing() {
        // Converting is not the same as accepting anything — an unknown status
        // must fail rather than silently become the first enum constant.
        assertThrows(Exception.class,
                () -> conversion.convert("approved", CreditApplicationStatus.class));
        assertThrows(Exception.class,
                () -> conversion.convert("everything", ConsentPurpose.class));
    }

    @Test
    void agreesWithWhatTheJsonBodyWouldHaveParsed() {
        // The point of reusing fromWire: one spelling rule across the API, so a
        // value cannot be valid in a body and invalid in a query string.
        for (CreditApplicationStatus status : CreditApplicationStatus.values()) {
            assertEquals(status, conversion.convert(status.wireName(), CreditApplicationStatus.class));
        }
        for (ConsentPurpose purpose : ConsentPurpose.values()) {
            assertEquals(purpose, conversion.convert(purpose.wireName(), ConsentPurpose.class));
        }
        for (ReasonCode code : ReasonCode.values()) {
            assertEquals(code, conversion.convert(code.wireName(), ReasonCode.class));
        }
        for (ChannelPartnerType type : ChannelPartnerType.values()) {
            assertEquals(type, conversion.convert(type.wireName(), ChannelPartnerType.class));
        }
    }

    @Test
    void everyWireNameIsLowercaseSoUrlsReadNaturally() {
        for (CreditApplicationStatus status : CreditApplicationStatus.values()) {
            assertTrue(status.wireName().equals(status.wireName().toLowerCase()),
                    () -> status + " has a non-lowercase wire name");
        }
    }
}
