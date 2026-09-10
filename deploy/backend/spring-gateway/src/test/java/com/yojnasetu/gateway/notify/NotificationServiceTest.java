package com.yojnasetu.gateway.notify;

import com.yojnasetu.gateway.model.User;
import com.yojnasetu.gateway.repository.UserRepository;
import com.yojnasetu.gateway.service.EmailService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class NotificationServiceTest {

    private NotificationRepository notifications;
    private UserRepository users;
    private EmailService emailService;
    private NotificationService service;

    @BeforeEach
    void setUp() {
        notifications = mock(NotificationRepository.class);
        users = mock(UserRepository.class);
        emailService = mock(EmailService.class);
        service = new NotificationService(notifications, users, emailService);

        when(notifications.save(any(Notification.class)))
                .thenAnswer(inv -> inv.getArgument(0));
        // Twilio credentials are @Value-injected and blank in a plain unit test,
        // which is the unconfigured path — exactly what we want to exercise.
    }

    private static User user(String phone, String email) {
        User u = new User();
        u.setId("citizen-1");
        u.setPhone(phone);
        u.setEmail(email);
        return u;
    }

    private Notification notifyFor(User u) {
        when(users.findById("citizen-1")).thenReturn(Optional.ofNullable(u));
        return service.notify("citizen-1", NotificationEvent.APPLICATION_SUBMITTED, "app-1",
                Map.of("scheme", "MFS", "partner", "Bank of Baroda", "ref", "ABC123"));
    }

    @Test
    void recordsTheNotificationEvenWhenNoChannelCanDeliverIt() {
        // The in-app record is the channel of record. A citizen with no phone,
        // no email and no Twilio must still be able to open the app and find
        // out what happened.
        Notification n = notifyFor(user(null, null));

        assertNotNull(n.getMessage());
        assertTrue(n.getMessage().contains("ABC123"));
        assertEquals("SKIPPED", n.getSms().getOutcome());
        assertEquals("SKIPPED", n.getEmail().getOutcome());
        verify(notifications).save(any(Notification.class));
    }

    @Test
    void saysWhyEachChannelWasSkippedRatherThanJustFailing() {
        Notification n = notifyFor(user(null, null));

        assertEquals("no phone number on file", n.getSms().getDetail());
        assertEquals("no email address on file", n.getEmail().getDetail());
    }

    @Test
    void skipsSmsWhenTwilioIsNotConfigured() {
        // Has a number, but no credentials — a different skip reason, and one
        // that is our problem rather than the citizen's.
        Notification n = notifyFor(user("+919999999999", null));

        assertEquals("SKIPPED", n.getSms().getOutcome());
        assertEquals("Twilio not configured", n.getSms().getDetail());
    }

    @Test
    void recordsEmailAsSentOnlyWhenTheMailerSaysSo() {
        when(emailService.sendAlert(anyString(), anyString(), anyString())).thenReturn(true);
        assertEquals("SENT", notifyFor(user(null, "a@b.com")).getEmail().getOutcome());

        when(emailService.sendAlert(anyString(), anyString(), anyString())).thenReturn(false);
        assertEquals("SKIPPED", notifyFor(user(null, "a@b.com")).getEmail().getOutcome());
    }

    @Test
    void neverThrowsWhenAChannelBlowsUp() {
        // Called from inside a status transition. Throwing here would fail a
        // loan decision because a message didn't send.
        when(emailService.sendAlert(anyString(), anyString(), anyString()))
                .thenThrow(new RuntimeException("SMTP exploded"));

        Notification n = notifyFor(user(null, "a@b.com"));

        assertEquals("FAILED", n.getEmail().getOutcome());
        assertEquals("RuntimeException", n.getEmail().getDetail());
    }

    @Test
    void neverRecordsMessageContentsInTheFailureDetail() {
        when(emailService.sendAlert(anyString(), anyString(), anyString()))
                .thenThrow(new RuntimeException("failed sending to +919999999999: MFS approved"));

        Notification n = notifyFor(user(null, "a@b.com"));

        // Exception type only. Audit logs in this codebase carry no PII and
        // neither should this.
        assertEquals("RuntimeException", n.getEmail().getDetail());
        assertFalse(n.getEmail().getDetail().contains("9999999999"));
    }

    @Test
    void handlesAnUnknownRecipientWithoutBlowingUp() {
        Notification n = notifyFor(null);

        assertEquals("SKIPPED", n.getSms().getOutcome());
        assertEquals("no such user", n.getSms().getDetail());
        verify(emailService, never()).sendAlert(anyString(), anyString(), anyString());
    }

    @Test
    void deepLinksBackToTheApplication() {
        assertEquals("app-1", notifyFor(user(null, null)).getApplicationId());
    }

    @Test
    void marksReadOnlyForTheOwner() {
        Notification n = new Notification();
        n.setId("n-1");
        n.setRecipientUserId("citizen-1");
        when(notifications.findById("n-1")).thenReturn(Optional.of(n));

        assertTrue(service.markRead("citizen-1", "n-1"));
        assertNotNull(n.getReadAt());

        // Someone else's id is a miss, not a forbidden.
        assertFalse(service.markRead("citizen-2", "n-1"));
    }

    @Test
    void doesNotRewriteTheReadTimestampOnASecondOpen() {
        Notification n = new Notification();
        n.setId("n-1");
        n.setRecipientUserId("citizen-1");
        when(notifications.findById("n-1")).thenReturn(Optional.of(n));

        service.markRead("citizen-1", "n-1");
        var firstRead = n.getReadAt();
        service.markRead("citizen-1", "n-1");

        assertEquals(firstRead, n.getReadAt());
    }

    @Test
    void unknownNotificationIsNotFound() {
        when(notifications.findById("nope")).thenReturn(Optional.empty());
        assertFalse(service.markRead("citizen-1", "nope"));
    }

    @Test
    void leavesUnreadNotificationsUnread() {
        Notification n = notifyFor(user(null, null));
        assertNull(n.getReadAt());
    }
}
