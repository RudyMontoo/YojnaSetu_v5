package com.yojnasetu.gateway.workflow;

import com.yojnasetu.gateway.credit.BranchRep;
import com.yojnasetu.gateway.credit.BranchRepRepository;
import com.yojnasetu.gateway.credit.CreditApplication;
import com.yojnasetu.gateway.credit.CreditApplicationService;
import com.yojnasetu.gateway.notify.Notification;
import com.yojnasetu.gateway.notify.NotificationEvent;
import com.yojnasetu.gateway.notify.NotificationService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Covers the join that was missing: an application records a BRANCH, and
 * reminders have to reach the PEOPLE at that branch.
 *
 * Before branch-rep accounts existed, the activity passed the branch id
 * straight to NotificationService as if it were a user id. It resolved to
 * nobody, every SLA reminder was silently recorded as skipped, and the
 * workflow logged them as sent.
 */
class LoanApplicationActivitiesImplTest {

    private static final String PARTNER = "partner-7";

    private CreditApplicationService applications;
    private NotificationService notifications;
    private BranchRepRepository branchReps;
    private LoanApplicationActivitiesImpl activities;

    @BeforeEach
    void setUp() {
        applications = mock(CreditApplicationService.class);
        notifications = mock(NotificationService.class);
        branchReps = mock(BranchRepRepository.class);
        activities = new LoanApplicationActivitiesImpl(applications, notifications, branchReps);

        when(applications.findById("app-1")).thenReturn(Optional.of(application()));
        // Delivered unless a test says otherwise.
        when(notifications.notify(anyString(), any(), anyString(), any()))
                .thenAnswer(inv -> delivered(inv.getArgument(0)));
    }

    private static CreditApplication application() {
        CreditApplication a = new CreditApplication();
        a.setId("app-1");
        a.setUserId("citizen-1");
        a.setProductName("Micro Finance Scheme (MFS)");
        a.setAssignedPartnerId(PARTNER);
        a.setAssignedPartnerName("Bank of Baroda, Connaught Place");
        return a;
    }

    private static Notification delivered(String recipientId) {
        Notification n = new Notification();
        n.setRecipientUserId(recipientId);
        n.setApplicationId("app-1");
        n.setSms(Notification.Delivery.of("SENT", null));
        return n;
    }

    private static Notification undeliverable(String recipientId) {
        Notification n = new Notification();
        n.setRecipientUserId(recipientId);
        n.setApplicationId("app-1");
        n.setSms(Notification.Delivery.of(NotificationService.UNDELIVERABLE, "no such user"));
        return n;
    }

    private static BranchRep rep(String id) {
        BranchRep r = new BranchRep();
        r.setId(id);
        r.setPartnerId(PARTNER);
        r.setActive(true);
        return r;
    }

    @Test
    void sendsTheReminderToAPersonRatherThanToABranchId() {
        when(branchReps.findByPartnerIdAndActiveTrue(PARTNER)).thenReturn(List.of(rep("rep-9")));

        activities.sendVerificationReminder("app-1", 3);

        ArgumentCaptor<String> recipient = ArgumentCaptor.forClass(String.class);
        verify(notifications).notify(recipient.capture(),
                eq(NotificationEvent.VERIFICATION_OVERDUE_REMINDER), eq("app-1"), any());

        assertEquals("rep-9", recipient.getValue());
        // The old bug in one assertion: the branch id must never be used as a
        // recipient, because nobody is reachable at it.
        assertTrue(!PARTNER.equals(recipient.getValue()));
    }

    @Test
    void tellsEveryRepAtTheBranch() {
        when(branchReps.findByPartnerIdAndActiveTrue(PARTNER))
                .thenReturn(List.of(rep("rep-1"), rep("rep-2")));

        activities.sendVerificationReminder("app-1", 3);

        verify(notifications).notify(eq("rep-1"), any(), anyString(), any());
        verify(notifications).notify(eq("rep-2"), any(), anyString(), any());
    }

    @Test
    void refusesToReportSuccessWhenNobodyStaffsTheBranch() {
        // An application parked at an unstaffed branch will sit untouched. That
        // is an operational fault, not an empty loop to skip quietly.
        when(branchReps.findByPartnerIdAndActiveTrue(PARTNER)).thenReturn(List.of());

        IllegalStateException thrown = assertThrows(IllegalStateException.class,
                () -> activities.sendVerificationReminder("app-1", 3));

        assertTrue(thrown.getMessage().contains("no active representative"));
        verify(notifications, never()).notify(anyString(), any(), anyString(), any());
    }

    @Test
    void refusesToReportSuccessWhenTheMessageReachedNobody() {
        when(branchReps.findByPartnerIdAndActiveTrue(PARTNER)).thenReturn(List.of(rep("rep-9")));
        when(notifications.notify(anyString(), any(), anyString(), any()))
                .thenReturn(undeliverable("rep-9"));

        // Temporal records a completed activity as proof the chase happened.
        // Returning quietly here would manufacture evidence of a follow-up
        // that never occurred.
        assertThrows(IllegalStateException.class,
                () -> activities.sendVerificationReminder("app-1", 3));
    }

    @Test
    void chasesTheCitizenDirectlyForDocuments() {
        // The citizen path always worked — userId is a real user — and must
        // not have been broken by routing reps through the branch lookup.
        activities.sendDocumentsReminder("app-1", 5);

        verify(notifications).notify(eq("citizen-1"),
                eq(NotificationEvent.DOCS_UPLOAD_OVERDUE_REMINDER), eq("app-1"), any());
        verify(branchReps, never()).findByPartnerIdAndActiveTrue(anyString());
    }

    @Test
    void tellsTheBranchWhenDocumentsArrive() {
        when(branchReps.findByPartnerIdAndActiveTrue(PARTNER)).thenReturn(List.of(rep("rep-9")));

        activities.notifyRepOfUploadedDocs("app-1");

        verify(notifications).notify(eq("rep-9"),
                eq(NotificationEvent.APPLICATION_UNDER_VERIFICATION), eq("app-1"), any());
    }

    @Test
    void carriesTheWaitingDaysIntoTheMessage() {
        when(branchReps.findByPartnerIdAndActiveTrue(PARTNER)).thenReturn(List.of(rep("rep-9")));

        activities.sendVerificationReminder("app-1", 9);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, String>> params = ArgumentCaptor.forClass(Map.class);
        verify(notifications).notify(anyString(), any(), anyString(), params.capture());
        assertEquals("9", params.getValue().get("days"));
    }

    @Test
    void doesNothingForAnApplicationThatNoLongerExists() {
        when(applications.findById("gone")).thenReturn(Optional.empty());

        activities.sendVerificationReminder("gone", 3);

        verify(notifications, never()).notify(anyString(), any(), anyString(), any());
    }
}
