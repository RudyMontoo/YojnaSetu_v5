package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.credit.CreditApplicationService.Failure;
import com.yojnasetu.gateway.credit.CreditApplicationService.TransitionException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class ConsentServiceTest {

    private static final String CITIZEN = "citizen-1";

    private final List<Consent> stored = new ArrayList<>();
    private ConsentService service;

    @BeforeEach
    void setUp() {
        stored.clear();
        ConsentRepository repository = mock(ConsentRepository.class);

        when(repository.save(any(Consent.class))).thenAnswer(inv -> {
            Consent c = inv.getArgument(0);
            if (c.getId() == null) {
                c.setId("consent-" + (stored.size() + 1));
                stored.add(c);
            }
            return c;
        });
        when(repository.findByUserIdAndPurpose(anyString(), any(ConsentPurpose.class)))
                .thenAnswer(inv -> stored.stream()
                        .filter(c -> c.getUserId().equals(inv.getArgument(0)))
                        .filter(c -> c.getPurpose() == inv.getArgument(1))
                        .toList());
        when(repository.findByUserIdOrderByGrantedAtDesc(anyString()))
                .thenAnswer(inv -> stored.stream()
                        .filter(c -> c.getUserId().equals(inv.getArgument(0)))
                        .toList());

        service = new ConsentService(repository);
    }

    @Test
    void recordsWhatWasActuallyAgreedTo() {
        Consent consent = service.grant(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1", "1.2.3.4");

        assertEquals(ConsentPurpose.PARTNER_SHARING, consent.getPurpose());
        assertEquals("app-1", consent.getApplicationId());
        assertNotNull(consent.getGrantedAt());
        assertTrue(consent.isActive());
        // A copy of the wording, so changing the text later cannot rewrite what
        // this person agreed to.
        assertEquals(ConsentPurpose.PARTNER_SHARING.statement(), consent.getStatement());
    }

    @Test
    void treatsRepeatedAgreementAsTheSameConsent() {
        Consent first = service.grant(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1", null);
        Consent again = service.grant(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1", null);

        // Duplicates would make the history harder to read for no gain.
        assertSame(first, again);
        assertEquals(1, stored.size());
    }

    @Test
    void withdrawingIsRecordedRatherThanErasing() {
        service.grant(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1", null);

        assertEquals(1, service.revoke(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1"));

        // "Agreed on the 3rd, withdrew on the 9th" is a different fact from
        // "never agreed", and only one survives a deletion.
        assertEquals(1, stored.size());
        assertNotNull(stored.get(0).getRevokedAt());
        assertFalse(stored.get(0).isActive());
    }

    @Test
    void withdrawnConsentNoLongerPermitsAnything() {
        service.grant(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1", null);
        assertTrue(service.hasConsent(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1"));

        service.revoke(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1");
        assertFalse(service.hasConsent(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1"));
    }

    @Test
    void agreeingAgainAfterWithdrawalIsANewRecord() {
        service.grant(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1", null);
        service.revoke(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1");
        service.grant(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1", null);

        // Three facts, not one flag flipped twice.
        assertEquals(2, stored.size());
        assertTrue(service.hasConsent(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1"));
    }

    @Test
    void consentForOneLoanIsNotConsentForTheNext() {
        service.grant(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1", null);

        // The whole point of purpose- AND application-scoping: agreeing to
        // share one file with a bank is not agreeing to share every future one.
        assertTrue(service.hasConsent(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1"));
        assertFalse(service.hasConsent(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-2"));
    }

    @Test
    void anAccountWideGrantCoversAnyApplication() {
        service.grant(CITIZEN, ConsentPurpose.PROFILE_STORAGE, null, null);

        assertTrue(service.hasConsent(CITIZEN, ConsentPurpose.PROFILE_STORAGE, "app-1"));
        assertTrue(service.hasConsent(CITIZEN, ConsentPurpose.PROFILE_STORAGE, "app-99"));
    }

    @Test
    void agreeingToOneThingIsNotAgreeingToAnother() {
        service.grant(CITIZEN, ConsentPurpose.CREDIT_ELIGIBILITY, null, null);

        // The failure the old single consentGivenAt flag could not prevent.
        assertFalse(service.hasConsent(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1"));
    }

    @Test
    void oneCitizensConsentSaysNothingAboutAnother() {
        service.grant(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1", null);
        assertFalse(service.hasConsent("citizen-2", ConsentPurpose.PARTNER_SHARING, "app-1"));
    }

    @Test
    void refusesTheActionAndNamesWhatIsNeeded() {
        TransitionException thrown = assertThrows(TransitionException.class,
                () -> service.requireConsent(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1"));

        assertEquals(Failure.FORBIDDEN, thrown.failure());
        // The message carries the statement so the UI can show the right
        // prompt rather than a generic "forbidden".
        assertTrue(thrown.getMessage().contains("Channel Partner branch"));
    }

    @Test
    void allowsTheActionOnceAgreed() {
        service.grant(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1", null);
        service.requireConsent(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1");
    }

    @Test
    void withdrawingSomethingNeverAgreedIsNotAnError() {
        // A citizen asking us to stop must never be met with a failure.
        assertEquals(0, service.revoke(CITIZEN, ConsentPurpose.DIGILOCKER_FETCH, null));
    }

    @Test
    void refusesAGrantWithNoPurpose() {
        assertEquals(Failure.BAD_REQUEST, assertThrows(TransitionException.class,
                () -> service.grant(CITIZEN, null, null, null)).failure());
    }

    @Test
    void recordsTheRequestOriginWithoutOtherPii() {
        Consent consent = service.grant(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1", "203.0.113.9");
        assertEquals("203.0.113.9", consent.getIp());
        assertNull(consent.getStatement().contains("203.0.113.9") ? "leaked" : null);
    }

    @ParameterizedTest
    @EnumSource(ConsentPurpose.class)
    void everyPurposeStatesPlainlyWhatIsBeingAgreedTo(ConsentPurpose purpose) {
        String statement = purpose.statement();
        assertNotNull(statement);
        // Written to be read aloud to someone at a CSC counter, not skimmed.
        assertTrue(statement.startsWith("I agree"), () -> purpose + ": " + statement);
        assertTrue(statement.length() > 40, () -> purpose + " is too terse: " + statement);
        assertEquals(purpose, ConsentPurpose.fromWire(purpose.wireName()));
    }

    @Test
    void listsEverythingIncludingWithdrawnConsents() {
        service.grant(CITIZEN, ConsentPurpose.PROFILE_STORAGE, null, null);
        service.grant(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1", null);
        service.revoke(CITIZEN, ConsentPurpose.PROFILE_STORAGE, null);

        List<Consent> all = service.listFor(CITIZEN);
        assertEquals(2, all.size());
        assertEquals(1, all.stream().filter(Consent::isActive).count());
    }

    @Test
    void revokingOneApplicationLeavesOthersStanding() {
        service.grant(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1", null);
        service.grant(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-2", null);

        service.revoke(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1");

        assertFalse(service.hasConsent(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1"));
        assertTrue(service.hasConsent(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-2"));
    }

    @Test
    void revokingWithoutAnApplicationWithdrawsThemAll() {
        service.grant(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1", null);
        service.grant(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-2", null);

        // "Stop sharing my data" means all of it, not one file.
        assertEquals(2, service.revoke(CITIZEN, ConsentPurpose.PARTNER_SHARING, null));
        assertFalse(service.hasConsent(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-2"));
    }

    @Test
    void unknownPurposeIsRefusedRatherThanIgnored() {
        assertThrows(IllegalArgumentException.class, () -> ConsentPurpose.fromWire("everything"));
        assertNull(ConsentPurpose.fromWire(null));
    }

    @Test
    void grantedAtIsWhenItHappened() {
        LocalDateTime before = LocalDateTime.now().minusSeconds(1);
        Consent consent = service.grant(CITIZEN, ConsentPurpose.PARTNER_SHARING, "app-1", null);
        assertTrue(consent.getGrantedAt().isAfter(before));
    }
}
