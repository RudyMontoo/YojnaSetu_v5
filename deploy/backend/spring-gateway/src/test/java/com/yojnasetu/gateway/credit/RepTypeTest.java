package com.yojnasetu.gateway.credit;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class RepTypeTest {

    @Test
    void onlyTheLendersOwnStaffMayRecordACreditDecision() {
        assertTrue(RepType.BANK_BRANCH.canRecordDecisions());
        assertFalse(RepType.CSC.canRecordDecisions());
        assertFalse(RepType.NGO_SHG.canRecordDecisions());
        assertFalse(RepType.FIELD_AGENT.canRecordDecisions());
    }

    @ParameterizedTest
    @EnumSource(RepType.class)
    void assistOnlyIsExactlyTheInverseOfDecisionAuthority(RepType type) {
        // These two are read in opposite directions across the codebase; if
        // they ever disagree, some call site is granting what another denies.
        assertEquals(!type.canRecordDecisions(), type.isAssistOnly());
    }

    @ParameterizedTest
    @EnumSource(RepType.class)
    void everyTypeRoundTripsThroughItsWireName(RepType type) {
        assertEquals(type, RepType.fromWire(type.wireName()));
    }

    @Test
    void acceptsHyphensAndCasingTheWayTheOtherWireEnumsDo() {
        assertEquals(RepType.NGO_SHG, RepType.fromWire("ngo-shg"));
        assertEquals(RepType.FIELD_AGENT, RepType.fromWire("FIELD_AGENT"));
        assertEquals(RepType.CSC, RepType.fromWire(" csc "));
    }

    @Test
    void refusesAnUnknownTypeRatherThanDefaultingToOne() {
        // Defaulting an unrecognised type would have to default to something,
        // and every choice is wrong: to BANK_BRANCH grants decision authority
        // on a typo, to CSC silently downgrades a real rep.
        assertThrows(IllegalArgumentException.class, () -> RepType.fromWire("branch_manager"));
    }

    @Test
    void blankReadsAsAbsentNotAsAType() {
        assertNull(RepType.fromWire(null));
        assertNull(RepType.fromWire("  "));
    }

    @ParameterizedTest
    @EnumSource(RepType.class)
    void everyTypeHasALabelACitizenCouldRead(RepType type) {
        // This string is shown to an applicant reviewing who touched their
        // file, so an enum constant name leaking through is a real defect.
        assertTrue(type.label() != null && !type.label().isBlank());
        assertFalse(type.label().equals(type.name()));
    }

    @Test
    void anAccountWithNoRecordedTypeReadsAsABranchRep() {
        // Every account written before RepType existed is a branch rep, and a
        // null here would lock working reps out of their own queue on deploy.
        BranchRep legacy = new BranchRep();
        legacy.setRepType(null);

        assertEquals(RepType.BANK_BRANCH, legacy.getRepType());
        assertFalse(legacy.isAssistOnly());
    }
}
