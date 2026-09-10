package com.yojnasetu.gateway.workflow;

import com.yojnasetu.gateway.credit.CreditApplication;
import com.yojnasetu.gateway.credit.CreditApplicationService;
import com.yojnasetu.gateway.credit.CreditApplicationStatus;
import com.yojnasetu.gateway.credit.ReasonCode;
import com.yojnasetu.gateway.notify.NotificationEvent;
import com.yojnasetu.gateway.notify.NotificationService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * The workflow's hands. Every method delegates to services that already exist
 * and are already tested — nothing about the loan rules is decided here.
 *
 * Idempotency is the property that matters, because Temporal retries. Applying
 * a status the application already holds is treated as success, not as a
 * duplicate transition: the REST handler that triggered the signal has usually
 * applied it a moment earlier, so "already there" is the normal case.
 */
@Component
public class LoanApplicationActivitiesImpl implements LoanApplicationActivities {

    private static final Logger LOG = LoggerFactory.getLogger(LoanApplicationActivitiesImpl.class);

    private final CreditApplicationService applications;
    private final NotificationService notifications;

    public LoanApplicationActivitiesImpl(CreditApplicationService applications,
                                         NotificationService notifications) {
        this.applications = applications;
        this.notifications = notifications;
    }

    @Override
    public CreditApplicationStatus applyStatus(String applicationId,
                                               CreditApplicationStatus status,
                                               String actorUserId,
                                               String actorRole,
                                               String reasonCode,
                                               String note,
                                               List<String> requestedDocuments) {

        CreditApplication application = applications.findById(applicationId).orElse(null);
        if (application == null) {
            LOG.warn("Workflow referenced unknown application {}", applicationId);
            return null;
        }
        if (application.getStatus() == status) {
            return status; // already applied by the REST handler — the usual path
        }

        try {
            CreditApplication updated = applications.transition(application, status,
                    actorUserId, actorRole == null ? "SYSTEM" : actorRole,
                    reasonCode == null ? null : ReasonCode.fromWire(reasonCode),
                    note, requestedDocuments);
            return updated.getStatus();
        } catch (CreditApplicationService.TransitionException e) {
            // The domain rules refused it. Report what is actually true rather
            // than retrying forever against a decision that will never change —
            // the workflow reconciles to this and carries on.
            LOG.warn("Workflow transition {} -> {} refused for {}: {}",
                    application.getStatus(), status, applicationId, e.getMessage());
            return application.getStatus();
        }
    }

    @Override
    public CreditApplicationStatus readStatus(String applicationId) {
        return applications.findById(applicationId)
                .map(CreditApplication::getStatus)
                .orElse(null);
    }

    @Override
    public void sendVerificationReminder(String applicationId, int daysWaiting) {
        applications.findById(applicationId).ifPresent(application -> {
            // Addressed to the rep, not the citizen — this is a delay on our
            // side of the counter and nagging the applicant about it would be
            // both useless and unfair.
            String repId = application.getAssignedPartnerId();
            Map<String, String> params = baseParams(application);
            params.put("days", String.valueOf(daysWaiting));
            notifications.notify(repId, NotificationEvent.VERIFICATION_OVERDUE_REMINDER,
                    applicationId, params);
        });
    }

    @Override
    public void sendDocumentsReminder(String applicationId, int daysWaiting) {
        applications.findById(applicationId).ifPresent(application -> {
            Map<String, String> params = baseParams(application);
            params.put("days", String.valueOf(daysWaiting));
            notifications.notify(application.getUserId(),
                    NotificationEvent.DOCS_UPLOAD_OVERDUE_REMINDER, applicationId, params);
        });
    }

    @Override
    public void notifyRepOfUploadedDocs(String applicationId) {
        applications.findById(applicationId).ifPresent(application ->
                notifications.notify(application.getAssignedPartnerId(),
                        NotificationEvent.APPLICATION_UNDER_VERIFICATION,
                        applicationId, baseParams(application)));
    }

    private static Map<String, String> baseParams(CreditApplication application) {
        Map<String, String> params = new HashMap<>();
        params.put("scheme", application.getProductName());
        params.put("partner", application.getAssignedPartnerName());
        params.put("ref", shortRef(application.getId()));
        params.put("documents", application.getMissingDocuments() == null
                ? null : String.join(", ", application.getMissingDocuments()));
        return params;
    }

    private static String shortRef(String id) {
        return id == null || id.length() <= 6 ? id : id.substring(id.length() - 6).toUpperCase();
    }
}
