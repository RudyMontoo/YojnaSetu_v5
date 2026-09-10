package com.yojnasetu.gateway.workflow;

import com.yojnasetu.gateway.credit.BranchRep;
import com.yojnasetu.gateway.credit.BranchRepRepository;
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
    private final BranchRepRepository branchReps;

    public LoanApplicationActivitiesImpl(CreditApplicationService applications,
                                         NotificationService notifications,
                                         BranchRepRepository branchReps) {
        this.applications = applications;
        this.notifications = notifications;
        this.branchReps = branchReps;
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
            // Addressed to the reps, not the citizen — this is a delay on our
            // side of the counter and nagging the applicant about it would be
            // both useless and unfair.
            //
            // The application records a BRANCH; people work at that branch.
            // Resolving one to the other is the join that was missing, and
            // without it every one of these reminders reached nobody.
            Map<String, String> params = baseParams(application);
            params.put("days", String.valueOf(daysWaiting));
            for (BranchRep rep : repsAt(application)) {
                requireDelivered(notifications.notify(rep.getId(),
                        NotificationEvent.VERIFICATION_OVERDUE_REMINDER, applicationId, params));
            }
        });
    }

    @Override
    public void sendDocumentsReminder(String applicationId, int daysWaiting) {
        applications.findById(applicationId).ifPresent(application -> {
            Map<String, String> params = baseParams(application);
            params.put("days", String.valueOf(daysWaiting));
            requireDelivered(notifications.notify(application.getUserId(),
                    NotificationEvent.DOCS_UPLOAD_OVERDUE_REMINDER, applicationId, params));
        });
    }

    @Override
    public void notifyRepOfUploadedDocs(String applicationId) {
        applications.findById(applicationId).ifPresent(application -> {
            for (BranchRep rep : repsAt(application)) {
                notifications.notify(rep.getId(), NotificationEvent.APPLICATION_UNDER_VERIFICATION,
                        applicationId, baseParams(application));
            }
        });
    }

    /**
     * The people who can act on this file.
     *
     * Throws when a branch has no active rep, rather than returning an empty
     * list and letting the caller quietly do nothing. An application assigned
     * to a branch nobody staffs is a real operational problem — the file will
     * sit there untouched — and it should surface as a failed activity and an
     * alert, not as a silently skipped loop.
     */
    private List<BranchRep> repsAt(CreditApplication application) {
        String partnerId = application.getAssignedPartnerId();
        List<BranchRep> reps = partnerId == null
                ? List.of()
                : branchReps.findByPartnerIdAndActiveTrue(partnerId);
        if (reps.isEmpty()) {
            throw new IllegalStateException("Application " + application.getId()
                    + " is assigned to branch '" + partnerId
                    + "', which has no active representative — nobody can action it.");
        }
        return reps;
    }

    /**
     * Refuses to report a reminder as sent when it reached nobody.
     *
     * This matters specifically in a workflow. The SLA timer's whole purpose is
     * to guarantee someone is chased, and Temporal records a completed activity
     * as proof that happened. Returning quietly here would let the workflow log
     * three reminders against a file nobody was ever told about, which is worse
     * than not chasing at all — it manufactures evidence of a follow-up that
     * never occurred.
     *
     * Throwing surfaces it as a failed activity in Temporal after its retries,
     * alongside the agent_alerts entry NotificationService raises. The retries
     * are not wasted: an unresolvable recipient today may be a real branch-rep
     * account tomorrow, since that account model is not built yet.
     */
    private static void requireDelivered(com.yojnasetu.gateway.notify.Notification notification) {
        boolean undeliverable = notification.getSms() != null
                && NotificationService.UNDELIVERABLE.equals(notification.getSms().getOutcome());
        if (undeliverable) {
            throw new IllegalStateException(
                    "Reminder for application " + notification.getApplicationId()
                            + " reached nobody: recipient '" + notification.getRecipientUserId()
                            + "' is not a user. Branch-rep accounts are not implemented yet.");
        }
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
