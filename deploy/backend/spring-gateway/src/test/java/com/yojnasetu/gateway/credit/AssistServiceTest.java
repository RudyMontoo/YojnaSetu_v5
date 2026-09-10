package com.yojnasetu.gateway.credit;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Who a citizen has let help them, and what that does and does not permit.
 *
 * The rules worth pinning are the ones that would be tempting to relax under
 * deadline: a helper reaches a file only because the citizen said so, a branch
 * rep never needs that permission, and a withdrawal leaves a record behind.
 */
class AssistServiceTest {

    private AssistAuthorizationRepository authorizations;
    private BranchRepRepository helpers;
    private AssistService service;

    @BeforeEach
    void setUp() {
        authorizations = mock(AssistAuthorizationRepository.class);
        helpers = mock(BranchRepRepository.class);
        when(authorizations.save(any(AssistAuthorization.class))).thenAnswer(i -> i.getArgument(0));
        service = new AssistService(authorizations, helpers);
    }

    private static BranchRep helper(String id, String repId, RepType type) {
        BranchRep h = new BranchRep();
        h.setId(id);
        h.setRepId(repId);
        h.setName("R. Devi");
        h.setRepType(type);
        h.setOrganisation("CSC Ranchi");
        h.setActive(true);
        return h;
    }

    private static CreditApplication application() {
        CreditApplication a = new CreditApplication();
        a.setId("app-1");
        a.setUserId("citizen-1");
        return a;
    }

    @Test
    void grantsAccessToAnAssistOnlyHelperNamedByTheirCardId() {
        when(helpers.findByRepId("CSC-JH-201")).thenReturn(Optional.of(helper("h-1", "CSC-JH-201", RepType.CSC)));
        when(authorizations.findByApplicationIdAndHelperIdAndRevokedAtIsNull("app-1", "h-1"))
                .thenReturn(Optional.empty());

        AssistAuthorization granted = service.grant(application(), "citizen-1", "CSC-JH-201", "helped at the CSC");

        assertEquals("app-1", granted.getApplicationId());
        assertEquals("h-1", granted.getHelperId());
        assertEquals(RepType.CSC, granted.getHelperType());
        assertNotNull(granted.getGrantedAt());
        assertTrue(granted.isActive());
    }

    @Test
    void copiesTheHelpersNameAndOrganisationOntoTheRecord() {
        // A citizen's "who helped me" list has to stay readable years later,
        // including after the helper account is renamed or deactivated.
        when(helpers.findByRepId("CSC-JH-201")).thenReturn(Optional.of(helper("h-1", "CSC-JH-201", RepType.CSC)));
        when(authorizations.findByApplicationIdAndHelperIdAndRevokedAtIsNull("app-1", "h-1"))
                .thenReturn(Optional.empty());

        AssistAuthorization granted = service.grant(application(), "citizen-1", "CSC-JH-201", null);

        assertEquals("R. Devi", granted.getHelperName());
        assertEquals("CSC Ranchi", granted.getHelperOrganisation());
    }

    @Test
    void refusesToGrantToABranchRepBecauseTheyAlreadyHaveTheirOwnClaim() {
        when(helpers.findByRepId("BOB-CP-014"))
                .thenReturn(Optional.of(helper("rep-9", "BOB-CP-014", RepType.BANK_BRANCH)));

        var e = assertThrows(CreditApplicationService.TransitionException.class,
                () -> service.grant(application(), "citizen-1", "BOB-CP-014", null));

        assertEquals(CreditApplicationService.Failure.BAD_REQUEST, e.failure());
        verify(authorizations, never()).save(any());
    }

    @Test
    void refusesAnUnknownOrDeactivatedHelperId() {
        when(helpers.findByRepId("NOBODY")).thenReturn(Optional.empty());

        var e = assertThrows(CreditApplicationService.TransitionException.class,
                () -> service.grant(application(), "citizen-1", "NOBODY", null));

        assertEquals(CreditApplicationService.Failure.NOT_FOUND, e.failure());
    }

    @Test
    void grantingTwiceReturnsTheExistingAuthorizationRatherThanADuplicate() {
        AssistAuthorization existing = new AssistAuthorization();
        existing.setId("auth-1");
        when(helpers.findByRepId("CSC-JH-201")).thenReturn(Optional.of(helper("h-1", "CSC-JH-201", RepType.CSC)));
        when(authorizations.findByApplicationIdAndHelperIdAndRevokedAtIsNull("app-1", "h-1"))
                .thenReturn(Optional.of(existing));

        assertSame(existing, service.grant(application(), "citizen-1", "CSC-JH-201", null));
        verify(authorizations, never()).save(any());
    }

    @Test
    void revokingStampsTheRecordInsteadOfDeletingIt() {
        AssistAuthorization live = new AssistAuthorization();
        live.setApplicationId("app-1");
        live.setCitizenId("citizen-1");
        live.setHelperId("h-1");
        live.setGrantedAt(LocalDateTime.now().minusDays(2));
        when(authorizations.findByApplicationIdOrderByGrantedAtDesc("app-1")).thenReturn(List.of(live));

        service.revoke("app-1", "citizen-1", "h-1");

        assertNotNull(live.getRevokedAt(), "the row must stay, stamped — it is the evidence");
        assertFalse(live.isActive());
        verify(authorizations).save(live);
        verify(authorizations, never()).delete(any());
    }

    @Test
    void revokingWithNoHelperIdClosesEveryLiveAuthorizationOnTheFile() {
        AssistAuthorization one = new AssistAuthorization();
        one.setApplicationId("app-1");
        one.setCitizenId("citizen-1");
        one.setHelperId("h-1");
        AssistAuthorization two = new AssistAuthorization();
        two.setApplicationId("app-1");
        two.setCitizenId("citizen-1");
        two.setHelperId("h-2");
        when(authorizations.findByApplicationIdOrderByGrantedAtDesc("app-1")).thenReturn(List.of(one, two));

        service.revoke("app-1", "citizen-1", null);

        assertNotNull(one.getRevokedAt());
        assertNotNull(two.getRevokedAt());
    }

    @Test
    void oneCitizenCannotRevokeAnotherCitizensAuthorization() {
        AssistAuthorization someoneElses = new AssistAuthorization();
        someoneElses.setApplicationId("app-1");
        someoneElses.setCitizenId("citizen-2");
        someoneElses.setHelperId("h-1");
        when(authorizations.findByApplicationIdOrderByGrantedAtDesc("app-1")).thenReturn(List.of(someoneElses));

        service.revoke("app-1", "citizen-1", "h-1");

        org.junit.jupiter.api.Assertions.assertNull(someoneElses.getRevokedAt());
        verify(authorizations, never()).save(any());
    }

    @Test
    void requireAuthorizedRefusesRatherThanReturningNothing() {
        when(authorizations.findByApplicationIdAndHelperIdAndRevokedAtIsNull("app-1", "h-1"))
                .thenReturn(Optional.empty());

        var e = assertThrows(CreditApplicationService.TransitionException.class,
                () -> service.requireAuthorized("app-1", "h-1"));

        assertEquals(CreditApplicationService.Failure.FORBIDDEN, e.failure());
    }

    @Test
    void aRevokedHelperNoLongerCountsAsAuthorized() {
        when(authorizations.findByApplicationIdAndHelperIdAndRevokedAtIsNull("app-1", "h-1"))
                .thenReturn(Optional.empty());

        assertFalse(service.isAuthorized("app-1", "h-1"));
    }
}
