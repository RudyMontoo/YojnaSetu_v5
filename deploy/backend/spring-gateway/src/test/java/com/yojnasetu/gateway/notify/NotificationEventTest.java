package com.yojnasetu.gateway.notify;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class NotificationEventTest {

    private static final Map<String, String> FULL = Map.of(
            "scheme", "Micro Finance Scheme (MFS)",
            "partner", "Bank of Baroda, Connaught Place",
            "ref", "D79CC0",
            "documents", "Caste certificate, Income proof",
            "reason", "One or more required documents were not provided.",
            "days", "5");

    @ParameterizedTest
    @EnumSource(NotificationEvent.class)
    void neverLeaksTemplateSyntaxToACitizen(NotificationEvent event) {
        // Even with nothing supplied. A raw "{documents}" in an SMS is worse
        // than a gap, because the reader can't tell what was meant.
        String empty = event.render(Map.of());
        assertFalse(empty.contains("{"), () -> event.key() + " leaked a placeholder: " + empty);
        assertFalse(empty.contains("}"), () -> event.key() + " leaked a placeholder: " + empty);

        String full = event.render(FULL);
        assertFalse(full.contains("{"), () -> event.key() + " leaked a placeholder: " + full);
    }

    @ParameterizedTest
    @EnumSource(NotificationEvent.class)
    void everyEventTellsSomeoneWhichApplicationAndWhatHappens(NotificationEvent event) {
        String rendered = event.render(FULL);

        assertTrue(rendered.contains("D79CC0"),
                () -> event.key() + " does not identify the application: " + rendered);
        assertNotNull(event.subject());
        assertFalse(event.subject().isBlank());
        // Long enough to actually say something; an SMS that just names a
        // status has told the reader nothing they can act on.
        assertTrue(rendered.length() > 60, () -> event.key() + " is too terse: " + rendered);
    }

    @Test
    void tellsTheCitizenExactlyWhichDocumentsAreMissing() {
        String rendered = NotificationEvent.APPLICATION_MISSING_DOCS.render(FULL);
        assertTrue(rendered.contains("Caste certificate"));
        assertTrue(rendered.contains("Income proof"));
    }

    @Test
    void alwaysStatesWhyAnApplicationWasRejected() {
        String rendered = NotificationEvent.APPLICATION_REJECTED.render(FULL);
        assertTrue(rendered.contains("required documents were not provided"));
        // And that it isn't the end of the road.
        assertTrue(rendered.toLowerCase().contains("apply again"));
    }

    @Test
    void warnsAgainstFeeFraudOnTheSanctionMessage() {
        // A "your loan is approved" SMS is exactly what an advance-fee scam
        // impersonates, so the real one says not to pay anyone.
        assertTrue(NotificationEvent.APPLICATION_SANCTIONED.render(FULL)
                .toLowerCase().contains("do not pay anyone"));
    }

    @Test
    void addressesSlaRemindersToTheRightAudience() {
        assertEquals(NotificationEvent.Audience.BRANCH_REP,
                NotificationEvent.VERIFICATION_OVERDUE_REMINDER.audience());
        assertEquals(NotificationEvent.Audience.CITIZEN,
                NotificationEvent.DOCS_UPLOAD_OVERDUE_REMINDER.audience());
    }

    @ParameterizedTest
    @EnumSource(NotificationEvent.class)
    void hasAStableWireKey(NotificationEvent event) {
        assertTrue(event.key().matches("[a-z_]+\\.[a-z_]+"),
                () -> "unexpected key format: " + event.key());
    }
}
