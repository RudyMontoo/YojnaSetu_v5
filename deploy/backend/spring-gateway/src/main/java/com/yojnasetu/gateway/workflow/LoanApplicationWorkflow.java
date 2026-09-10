package com.yojnasetu.gateway.workflow;

import com.yojnasetu.gateway.credit.CreditApplicationStatus;
import io.temporal.workflow.QueryMethod;
import io.temporal.workflow.SignalMethod;
import io.temporal.workflow.WorkflowInterface;
import io.temporal.workflow.WorkflowMethod;

/**
 * Durable orchestration of one loan application, start to close.
 *
 * The division of responsibility is deliberate and worth stating, because
 * getting it wrong is the usual way Temporal adoptions go bad:
 *
 *   - This workflow owns TIME and SEQUENCE — how long a rep may sit on a file
 *     before a reminder fires, how many reminders, when to escalate, and what
 *     to retry.
 *   - {@code CreditApplicationStatus} and {@code CreditApplicationService}
 *     remain the sole authority on which transitions are LEGAL. The activities
 *     call straight into them, so the rules stay in one place, keep their
 *     tests, and cannot drift from what the REST API enforces.
 *
 * Every transition here is human-initiated — a citizen submits, a rep decides.
 * The workflow does not drive the loan forward on its own; it waits, records,
 * notifies, and chases when nobody acts. That "chasing when nobody acts" is
 * the part that is genuinely hard without durable timers, and the reason this
 * exists.
 *
 * The workflow id is the application id, so signalling is possible from
 * anywhere that knows the application, and Temporal's own deduplication
 * prevents two workflows for one application.
 */
@WorkflowInterface
public interface LoanApplicationWorkflow {

    String TASK_QUEUE = "loan-application";

    /**
     * Runs for the life of the application and returns its final status.
     * Completes only when the file reaches a terminal state.
     */
    @WorkflowMethod
    CreditApplicationStatus run(String applicationId, String citizenUserId);

    // ---- signals: something a human did, reported to the workflow ----

    /** Citizen submitted the draft to their chosen branch. */
    @SignalMethod
    void applicationSubmitted();

    /** A branch rep picked the file up and started checking documents. */
    @SignalMethod
    void verificationStarted();

    /** Rep asked for named documents; starts the chase timer. */
    @SignalMethod
    void missingDocsRequested(java.util.List<String> documents);

    /** Citizen says the requested documents are provided. */
    @SignalMethod
    void documentsUploaded();

    /** Verified and sent to the sanctioning authority. */
    @SignalMethod
    void forwarded();

    @SignalMethod
    void sanctioned();

    /** Terminal. Reason code is already recorded on the application. */
    @SignalMethod
    void rejected(String reasonCode);

    /** Terminal. Money has reached the citizen. */
    @SignalMethod
    void disbursed();

    // ---- queries: read workflow state without disturbing it ----

    /** What the workflow believes the status is. */
    @QueryMethod
    CreditApplicationStatus currentStatus();

    /** How many SLA reminders have fired — what an ops dashboard wants. */
    @QueryMethod
    int remindersSent();
}
