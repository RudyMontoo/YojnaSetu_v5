package com.yojnasetu.gateway.notify;

import com.yojnasetu.gateway.credit.CreditApplication;
import com.yojnasetu.gateway.credit.CreditApplicationStatus;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;

/**
 * Turns a status change into the right message for the right person.
 *
 * Kept separate from CreditApplicationService so the state machine stays a
 * pure decision about what is legal, and separate from NotificationService so
 * that class stays a dumb pipe. This is the only place that knows a
 * MISSING_DOCS transition should list the documents, or that a rejection must
 * carry its reason.
 *
 * When Temporal lands this is what sendNotificationActivity() will call — the
 * mapping doesn't change, only who invokes it.
 */
@Component
public class CreditApplicationNotifier {

    private static final Logger LOG = LoggerFactory.getLogger(CreditApplicationNotifier.class);

    private final NotificationService notificationService;

    public CreditApplicationNotifier(NotificationService notificationService) {
        this.notificationService = notificationService;
    }

    /**
     * Fires the notification for a transition that has already happened.
     *
     * Never throws. It is called after the application has been saved, so a
     * messaging failure here must not surface as a failed status update — the
     * transition is already a fact.
     */
    public void onStatusChanged(CreditApplication application, CreditApplicationStatus newStatus) {
        try {
            NotificationEvent event = eventFor(newStatus);
            if (event == null) {
                return; // DRAFT — nothing has happened worth interrupting anyone for
            }
            notificationService.notify(
                    application.getUserId(), event, application.getId(), paramsFor(application));
        } catch (Exception e) {
            LOG.warn("Notification for application {} -> {} failed: {}",
                    application.getId(), newStatus, e.toString());
        }
    }

    private static NotificationEvent eventFor(CreditApplicationStatus status) {
        return switch (status) {
            case DRAFT -> null;
            case SUBMITTED -> NotificationEvent.APPLICATION_SUBMITTED;
            case UNDER_VERIFICATION -> NotificationEvent.APPLICATION_UNDER_VERIFICATION;
            case MISSING_DOCS -> NotificationEvent.APPLICATION_MISSING_DOCS;
            case FORWARDED -> NotificationEvent.APPLICATION_FORWARDED;
            case SANCTIONED -> NotificationEvent.APPLICATION_SANCTIONED;
            case REJECTED -> NotificationEvent.APPLICATION_REJECTED;
            case DISBURSED -> NotificationEvent.APPLICATION_DISBURSED;
        };
    }

    private static Map<String, String> paramsFor(CreditApplication application) {
        Map<String, String> params = new HashMap<>();
        params.put("scheme", application.getProductName());
        params.put("partner", application.getAssignedPartnerName());
        // A citizen reads a short reference, not a 24-character Mongo id.
        params.put("ref", shortRef(application.getId()));
        params.put("documents", application.getMissingDocuments() == null
                ? null
                : String.join(", ", application.getMissingDocuments()));
        params.put("reason", latestReason(application));
        return params;
    }

    /** Last 6 characters, uppercased — short enough to read down a phone line. */
    private static String shortRef(String id) {
        if (id == null || id.length() <= 6) {
            return id;
        }
        return id.substring(id.length() - 6).toUpperCase();
    }

    /**
     * The reason code's description, or the rep's free-text note if they left
     * one. Never blank: a rejection message that cannot say why is precisely
     * the dead end the reason-code requirement exists to prevent.
     */
    private static String latestReason(CreditApplication application) {
        if (application.getStatusHistory() == null || application.getStatusHistory().isEmpty()) {
            return null;
        }
        var last = application.getStatusHistory().get(application.getStatusHistory().size() - 1);
        if (last.getReasonCode() != null) {
            return last.getReasonCode().description();
        }
        return last.getNote();
    }
}
