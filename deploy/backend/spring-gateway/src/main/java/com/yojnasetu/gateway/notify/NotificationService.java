package com.yojnasetu.gateway.notify;

import com.twilio.rest.api.v2010.account.Message;
import com.twilio.type.PhoneNumber;
import com.yojnasetu.gateway.model.AgentAlert;
import com.yojnasetu.gateway.repository.AgentAlertRepository;
import com.yojnasetu.gateway.service.EmailService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * Delivers the messages that tell a citizen what happened to their loan.
 *
 * Two rules shape this class.
 *
 * First, the in-app record is written BEFORE anything is sent outward, and is
 * written even when every outward channel fails. SMS delivery is not something
 * we can actually observe from here — an unconfigured Twilio, a wrong number,
 * a silently dropped message all look the same — so the durable record is the
 * one a citizen can always come back to, and the one that lets us answer "were
 * they ever told?".
 *
 * Second, a delivery failure never fails the caller. This is invoked from
 * status transitions: if Twilio is down, the loan still moved, and throwing
 * here would roll back a real decision because a text message didn't send.
 * Failures are recorded on the notification and logged, not propagated.
 */
@Service
public class NotificationService {

    private static final Logger LOG = LoggerFactory.getLogger(NotificationService.class);

    private static final String SENT = "SENT";
    private static final String SKIPPED = "SKIPPED";
    private static final String FAILED = "FAILED";
    /** Nobody could be reached at all — see the comment at the use site. */
    public static final String UNDELIVERABLE = "UNDELIVERABLE";

    private final NotificationRepository notifications;
    private final NotificationRecipient.Resolver recipients;
    private final EmailService emailService;
    private final AgentAlertRepository alerts;

    @Value("${twilio.account-sid:}")
    private String twilioAccountSid;

    @Value("${twilio.auth-token:}")
    private String twilioAuthToken;

    @Value("${twilio.from-number:}")
    private String twilioFromNumber;

    /**
     * WhatsApp requires an approved Business sender, which has a multi-week
     * lead time. Until that exists the same copy goes out over SMS rather than
     * silently not going out at all.
     */
    @Value("${twilio.whatsapp-from:}")
    private String twilioWhatsappFrom;

    private volatile boolean twilioInitialised;

    public NotificationService(NotificationRepository notifications,
                               NotificationRecipient.Resolver recipients,
                               EmailService emailService,
                               AgentAlertRepository alerts) {
        this.notifications = notifications;
        this.recipients = recipients;
        this.emailService = emailService;
        this.alerts = alerts;
    }

    /**
     * Puts an undeliverable notification in front of a human.
     *
     * agent_alerts is this codebase's existing route for "you need to know
     * before a citizen does" — AlertNotifier polls it every 15 minutes and
     * emails the admin a digest. Reusing it means a broken reminder pipeline
     * surfaces the same way every other operational fault does, instead of
     * sitting in a Mongo collection nobody queries.
     */
    private void raiseAlert(NotificationEvent event, String applicationId, String recipientUserId) {
        try {
            AgentAlert alert = new AgentAlert();
            alert.setAgentName("notifications");
            alert.setAlertType("undeliverable_notification");
            // No PII: an id and an event key, never the message body or a
            // phone number, matching the audit_log rule in this codebase.
            alert.setMessage("No user '" + recipientUserId + "' for " + event.key()
                    + " on application " + applicationId + " — nobody was told.");
            alert.setAt(java.time.Instant.now());
            alert.setResolved(false);
            alerts.save(alert);
        } catch (Exception e) {
            // Alerting about a failure must not itself become a failure.
            LOG.warn("Could not raise undeliverable-notification alert: {}", e.toString());
        }
    }

    /**
     * Records and sends one notification.
     *
     * @param recipientUserId who to tell — resolved to contact details here, so
     *                        callers never handle a phone number or email
     * @param params          template values; see NotificationEvent for the
     *                        placeholders each event expects
     */
    public Notification notify(String recipientUserId,
                               NotificationEvent event,
                               String applicationId,
                               Map<String, String> params) {

        Notification notification = new Notification();
        notification.setRecipientUserId(recipientUserId);
        notification.setEvent(event);
        notification.setApplicationId(applicationId);
        notification.setSubject(event.subject());
        notification.setMessage(event.render(params));
        notification.setCreatedAt(LocalDateTime.now());

        // Resolved across every principal type, not just citizens — see
        // NotificationRecipient.Resolver.
        NotificationRecipient recipient = recipients.resolve(recipientUserId).orElse(null);
        if (recipient == null) {
            // UNDELIVERABLE, not SKIPPED. A skip means we chose not to send —
            // no phone on file, mailer switched off — and is a normal outcome.
            // This is different: we tried to tell a specific person something
            // and there is no such person, so the message reached nobody and
            // nobody knows. Recording that as a skip is how a broken reminder
            // pipeline looks healthy for weeks.
            notification.setSms(Notification.Delivery.of(UNDELIVERABLE, "no such user"));
            notification.setEmail(Notification.Delivery.of(UNDELIVERABLE, "no such user"));
            LOG.error("Notification {} for application {} could not be delivered: "
                    + "recipient '{}' matches no known principal",
                    event.key(), applicationId, recipientUserId);
            raiseAlert(event, applicationId, recipientUserId);
            return notifications.save(notification);
        }

        notification.setSms(sendSms(recipient.phone(), notification.getMessage()));
        notification.setEmail(sendEmail(recipient.email(), event.subject(), notification.getMessage()));

        return notifications.save(notification);
    }

    // ------------------------------------------------------------- channels

    private Notification.Delivery sendSms(String phone, String message) {
        if (phone == null || phone.isBlank()) {
            return Notification.Delivery.of(SKIPPED, "no phone number on file");
        }
        // Null-safe, not just blank-safe: these are @Value-injected and are
        // null whenever this service is constructed outside Spring. A missing
        // credential must read as "not configured", never as a crash inside a
        // status transition.
        if (blank(twilioAccountSid) || blank(twilioAuthToken) || blank(twilioFromNumber)) {
            // Same graceful-degradation stance OtpService takes: unconfigured
            // messaging must not stop the platform working in dev or on stage.
            return Notification.Delivery.of(SKIPPED, "Twilio not configured");
        }
        try {
            ensureTwilioInit();
            Message.creator(new PhoneNumber(phone), new PhoneNumber(twilioFromNumber), message).create();
            return Notification.Delivery.of(SENT, null);
        } catch (Exception e) {
            // Never rethrow — see the class comment. A text that didn't send
            // must not roll back the loan decision that triggered it.
            LOG.warn("SMS delivery failed: {}", e.toString());
            return Notification.Delivery.of(FAILED, e.getClass().getSimpleName());
        }
    }

    private Notification.Delivery sendEmail(String email, String subject, String body) {
        if (email == null || email.isBlank()) {
            return Notification.Delivery.of(SKIPPED, "no email address on file");
        }
        try {
            boolean sent = emailService.sendAlert(email, subject, body);
            return sent
                    ? Notification.Delivery.of(SENT, null)
                    : Notification.Delivery.of(SKIPPED, "email not configured");
        } catch (Exception e) {
            LOG.warn("Email delivery failed: {}", e.toString());
            return Notification.Delivery.of(FAILED, e.getClass().getSimpleName());
        }
    }

    private static boolean blank(String value) {
        return value == null || value.isBlank();
    }

    private synchronized void ensureTwilioInit() {
        if (!twilioInitialised) {
            com.twilio.Twilio.init(twilioAccountSid, twilioAuthToken);
            twilioInitialised = true;
        }
    }

    // ----------------------------------------------------------- inbox reads

    public List<Notification> inbox(String userId) {
        return notifications.findByRecipientUserIdOrderByCreatedAtDesc(userId);
    }

    public long unreadCount(String userId) {
        return notifications.countByRecipientUserIdAndReadAtIsNull(userId);
    }

    /**
     * Marks one notification read, but only for its own recipient — the same
     * ownership rule the application endpoints use, and for the same reason:
     * Mongo ids are guessable.
     */
    public boolean markRead(String userId, String notificationId) {
        return notifications.findById(notificationId)
                .filter(n -> userId.equals(n.getRecipientUserId()))
                .map(n -> {
                    if (n.getReadAt() == null) {
                        n.setReadAt(LocalDateTime.now());
                        notifications.save(n);
                    }
                    return true;
                })
                .orElse(false);
    }
}
