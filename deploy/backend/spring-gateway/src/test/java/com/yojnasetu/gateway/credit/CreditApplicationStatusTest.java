package com.yojnasetu.gateway.credit;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

import static com.yojnasetu.gateway.credit.CreditApplicationStatus.DISBURSED;
import static com.yojnasetu.gateway.credit.CreditApplicationStatus.DRAFT;
import static com.yojnasetu.gateway.credit.CreditApplicationStatus.FORWARDED;
import static com.yojnasetu.gateway.credit.CreditApplicationStatus.MISSING_DOCS;
import static com.yojnasetu.gateway.credit.CreditApplicationStatus.REJECTED;
import static com.yojnasetu.gateway.credit.CreditApplicationStatus.SANCTIONED;
import static com.yojnasetu.gateway.credit.CreditApplicationStatus.SUBMITTED;
import static com.yojnasetu.gateway.credit.CreditApplicationStatus.UNDER_VERIFICATION;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class CreditApplicationStatusTest {

    @Test
    void walksTheHappyPathEndToEnd() {
        assertTrue(DRAFT.canMoveTo(SUBMITTED));
        assertTrue(SUBMITTED.canMoveTo(UNDER_VERIFICATION));
        assertTrue(UNDER_VERIFICATION.canMoveTo(FORWARDED));
        assertTrue(FORWARDED.canMoveTo(SANCTIONED));
        assertTrue(SANCTIONED.canMoveTo(DISBURSED));
    }

    @Test
    void letsAnApplicantAnswerADocumentRequestAndContinue() {
        // The point of missing_docs: supplying what was asked resumes
        // verification rather than restarting the application.
        assertTrue(UNDER_VERIFICATION.canMoveTo(MISSING_DOCS));
        assertTrue(MISSING_DOCS.canMoveTo(UNDER_VERIFICATION));
    }

    @Test
    void refusesToRewindADisbursedLoan() {
        // The welfare Application model accepts exactly this, because it
        // validates membership in a set rather than the move itself.
        assertFalse(DISBURSED.canMoveTo(DRAFT));
        assertFalse(DISBURSED.canMoveTo(SUBMITTED));
        assertTrue(DISBURSED.isTerminal());
    }

    @Test
    void refusesToReopenARejectedFile() {
        assertTrue(REJECTED.isTerminal());
        for (CreditApplicationStatus next : CreditApplicationStatus.values()) {
            assertFalse(REJECTED.canMoveTo(next), () -> "rejected should not reach " + next);
        }
    }

    @Test
    void refusesToSkipVerification() {
        assertFalse(SUBMITTED.canMoveTo(SANCTIONED));
        assertFalse(SUBMITTED.canMoveTo(DISBURSED));
        assertFalse(DRAFT.canMoveTo(UNDER_VERIFICATION));
    }

    @Test
    void allowsRejectionFromEveryLiveState() {
        // A file can go wrong at any point before it closes.
        assertTrue(SUBMITTED.canMoveTo(REJECTED));
        assertTrue(UNDER_VERIFICATION.canMoveTo(REJECTED));
        assertTrue(MISSING_DOCS.canMoveTo(REJECTED));
        assertTrue(FORWARDED.canMoveTo(REJECTED));
        // Even a sanction can fall through before the money moves.
        assertTrue(SANCTIONED.canMoveTo(REJECTED));
    }

    @ParameterizedTest
    @EnumSource(CreditApplicationStatus.class)
    void everyStatusDeclaresItsTransitionsAndNeverItself(CreditApplicationStatus status) {
        assertNotNull(status.allowedNext(), () -> status + " has no transition entry");
        assertFalse(status.canMoveTo(status), () -> status + " should not transition to itself");
    }

    @ParameterizedTest
    @EnumSource(CreditApplicationStatus.class)
    void terminalAndActiveAreExactOpposites(CreditApplicationStatus status) {
        assertEquals(status.isTerminal(), !status.isActive());
    }

    @Test
    void onlyTheTwoClosedStatesAreTerminal() {
        long terminal = java.util.Arrays.stream(CreditApplicationStatus.values())
                .filter(CreditApplicationStatus::isTerminal)
                .count();
        assertEquals(2, terminal);
    }

    @Test
    void usesSnakeCaseOnTheWire() throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        assertEquals("\"under_verification\"", mapper.writeValueAsString(UNDER_VERIFICATION));
        assertEquals(MISSING_DOCS, mapper.readValue("\"missing_docs\"", CreditApplicationStatus.class));
        // Hyphens are tolerated on input; anything unknown is refused.
        assertEquals(MISSING_DOCS, CreditApplicationStatus.fromWire("missing-docs"));
        assertThrows(IllegalArgumentException.class, () -> CreditApplicationStatus.fromWire("approved"));
    }
}
