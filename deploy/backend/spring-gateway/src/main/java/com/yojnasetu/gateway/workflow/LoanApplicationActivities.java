package com.yojnasetu.gateway.workflow;

import com.yojnasetu.gateway.credit.CreditApplicationStatus;
import io.temporal.activity.ActivityInterface;
import io.temporal.activity.ActivityMethod;

import java.util.List;

/**
 * The side effects a loan workflow performs: writing status to Mongo and
 * telling people what happened.
 *
 * These are thin. Each one delegates to the existing Spring services rather
 * than reimplementing anything, which is what keeps the transition rules in a
 * single tested place instead of forked between REST and workflow paths.
 *
 * Activities must be idempotent — Temporal retries them, and a retried
 * transition that has already been applied has to be a no-op rather than a
 * duplicate history entry or a second SMS.
 */
@ActivityInterface
public interface LoanApplicationActivities {

    /**
     * Applies a status change on behalf of the workflow.
     *
     * @return the status actually in force afterwards. If the application is
     *         already there, this is a no-op and returns it unchanged — the
     *         REST call that triggered the signal usually applied it already,
     *         so this is the common case, not the exceptional one.
     */
    @ActivityMethod
    CreditApplicationStatus applyStatus(String applicationId,
                                        CreditApplicationStatus status,
                                        String actorUserId,
                                        String actorRole,
                                        String reasonCode,
                                        String note,
                                        List<String> requestedDocuments);

    /** Reads current status, so the workflow can reconcile after a replay. */
    @ActivityMethod
    CreditApplicationStatus readStatus(String applicationId);

    /** Chases a branch rep who has not acted within the SLA. */
    @ActivityMethod
    void sendVerificationReminder(String applicationId, int daysWaiting);

    /** Chases a citizen who has not supplied requested documents. */
    @ActivityMethod
    void sendDocumentsReminder(String applicationId, int daysWaiting);

    /** Notifies the assigned rep that requested documents have arrived. */
    @ActivityMethod
    void notifyRepOfUploadedDocs(String applicationId);
}
