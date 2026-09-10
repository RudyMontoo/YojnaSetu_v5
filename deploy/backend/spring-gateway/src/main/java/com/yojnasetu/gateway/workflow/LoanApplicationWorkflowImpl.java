package com.yojnasetu.gateway.workflow;

import com.yojnasetu.gateway.credit.CreditApplicationStatus;
import io.temporal.activity.ActivityOptions;
import io.temporal.common.RetryOptions;
import io.temporal.workflow.Workflow;

import java.time.Duration;
import java.util.List;

/**
 * The loan lifecycle as a durable state machine.
 *
 * What this adds over the REST endpoints, and the only reason it is worth
 * running: nothing here drives the loan forward on its own — every move is a
 * human decision arriving as a signal — but the SLA timers survive restarts,
 * deploys and week-long waits. A file that a branch rep has quietly sat on for
 * five days gets chased whether or not anyone is watching, and the chasing is
 * recorded.
 *
 * Deliberately NOT reimplemented here: which transitions are legal. That lives
 * in CreditApplicationStatus and is enforced by CreditApplicationService, which
 * the activities call. If this workflow disagrees with the REST API about
 * whether missing_docs may become disbursed, the REST API wins — there is only
 * one rule set and this is not it.
 */
public class LoanApplicationWorkflowImpl implements LoanApplicationWorkflow {

    /** How long a rep may hold a file before the first reminder. */
    static final Duration VERIFICATION_SLA = Duration.ofDays(3);

    /** How long a citizen has to supply documents before being chased. */
    static final Duration DOCUMENTS_SLA = Duration.ofDays(5);

    /** Reminders per stall before we stop nagging and leave it to ops. */
    static final int MAX_REMINDERS = 3;

    /**
     * Upper bound on a single application's life in the workflow. Without it a
     * forgotten file pins a workflow open forever; NSFDC processes settle well
     * inside a year.
     */
    static final Duration MAX_LIFETIME = Duration.ofDays(365);

    private final LoanApplicationActivities activities = Workflow.newActivityStub(
            LoanApplicationActivities.class,
            ActivityOptions.newBuilder()
                    .setStartToCloseTimeout(Duration.ofSeconds(30))
                    // Mongo blips and SMS outages are transient; give up only
                    // after a genuine run of failures rather than on the first.
                    .setRetryOptions(RetryOptions.newBuilder()
                            .setInitialInterval(Duration.ofSeconds(2))
                            .setMaximumAttempts(5)
                            .build())
                    .build());

    private String applicationId;
    private String citizenUserId;

    private CreditApplicationStatus status = CreditApplicationStatus.DRAFT;
    private int remindersSent;

    /** Reset whenever the file moves, so each stage gets its own SLA clock. */
    private int remindersForStage;

    /**
     * Signals land here and are applied by the main loop.
     *
     * Signal handlers deliberately do NOT call activities. A handler that
     * blocks on one queues behind every other signal, so a run of rapid
     * transitions is processed late and a query reads state several moves
     * stale — which is exactly what happened before this was split out.
     * Handlers now only enqueue; the workflow method does the work.
     */
    private final java.util.Deque<Move> inbox = new java.util.ArrayDeque<>();

    /** One requested transition, as reported by a human action. */
    record Move(CreditApplicationStatus status, String actorUserId, String actorRole,
                String reasonCode, String note, List<String> documents) {
    }

    @Override
    public CreditApplicationStatus run(String applicationId, String citizenUserId) {
        this.applicationId = applicationId;
        this.citizenUserId = citizenUserId;

        while (!status.isTerminal()) {
            Duration sla = slaFor(status);
            boolean acted;

            if (sla == null || remindersForStage >= MAX_REMINDERS) {
                // Nothing to chase here: either the delay belongs to an
                // external authority, or we have already nudged enough and
                // further messages become harassment. Wait, bounded.
                acted = Workflow.await(MAX_LIFETIME, () -> !inbox.isEmpty());
                if (!acted) {
                    return status; // abandoned
                }
            } else {
                acted = Workflow.await(sla, () -> !inbox.isEmpty());
                if (!acted) {
                    remindersForStage++;
                    remindersSent++;
                    int daysWaiting = (int) sla.toDays() * remindersForStage;
                    if (status == CreditApplicationStatus.MISSING_DOCS) {
                        activities.sendDocumentsReminder(applicationId, daysWaiting);
                    } else {
                        activities.sendVerificationReminder(applicationId, daysWaiting);
                    }
                    continue;
                }
            }

            applyPending();
        }
        return status;
    }

    /**
     * Drains every queued signal, applying each through the domain rules. The
     * activity answers with what is actually true afterwards, so a move the
     * rules refused leaves this workflow reconciled rather than believing
     * something that never happened.
     */
    private void applyPending() {
        while (!inbox.isEmpty()) {
            Move move = inbox.removeFirst();
            CreditApplicationStatus before = status;

            CreditApplicationStatus now = activities.applyStatus(applicationId, move.status(),
                    move.actorUserId(), move.actorRole(), move.reasonCode(), move.note(),
                    move.documents());
            if (now != null) {
                status = now;
            }

            if (status != before) {
                remindersForStage = 0; // a new stage gets its own clock
            }
            // Told the rep only once the documents genuinely landed.
            if (move.status() == CreditApplicationStatus.UNDER_VERIFICATION
                    && before == CreditApplicationStatus.MISSING_DOCS
                    && status == CreditApplicationStatus.UNDER_VERIFICATION) {
                activities.notifyRepOfUploadedDocs(applicationId);
            }
        }
    }

    /** How long this stage may sit before we chase, or null if we never chase it. */
    private static Duration slaFor(CreditApplicationStatus status) {
        return switch (status) {
            case SUBMITTED, UNDER_VERIFICATION -> VERIFICATION_SLA;
            case MISSING_DOCS -> DOCUMENTS_SLA;
            // A draft nobody submitted, or a file with the sanctioning
            // authority: the delay is not ours to chase.
            case DRAFT, FORWARDED, SANCTIONED, REJECTED, DISBURSED -> null;
        };
    }

    // ------------------------------------------------------------- signals
    //
    // Enqueue only. See the comment on `inbox`.

    @Override
    public void applicationSubmitted() {
        inbox.addLast(new Move(CreditApplicationStatus.SUBMITTED, citizenUserId, "CITIZEN",
                null, null, null));
    }

    @Override
    public void verificationStarted() {
        inbox.addLast(new Move(CreditApplicationStatus.UNDER_VERIFICATION, null, "BRANCH_REP",
                null, null, null));
    }

    @Override
    public void missingDocsRequested(List<String> documents) {
        inbox.addLast(new Move(CreditApplicationStatus.MISSING_DOCS, null, "BRANCH_REP",
                "documents_incomplete", null,
                documents == null ? List.of() : List.copyOf(documents)));
    }

    @Override
    public void documentsUploaded() {
        inbox.addLast(new Move(CreditApplicationStatus.UNDER_VERIFICATION, citizenUserId, "CITIZEN",
                null, "Applicant reported the requested documents were provided", null));
    }

    @Override
    public void forwarded() {
        inbox.addLast(new Move(CreditApplicationStatus.FORWARDED, null, "BRANCH_REP",
                null, null, null));
    }

    @Override
    public void sanctioned() {
        inbox.addLast(new Move(CreditApplicationStatus.SANCTIONED, null, "BRANCH_REP",
                null, null, null));
    }

    @Override
    public void rejected(String reasonCode) {
        inbox.addLast(new Move(CreditApplicationStatus.REJECTED, null, "BRANCH_REP",
                reasonCode, null, null));
    }

    @Override
    public void disbursed() {
        inbox.addLast(new Move(CreditApplicationStatus.DISBURSED, null, "BRANCH_REP",
                null, null, null));
    }

    // ------------------------------------------------------------- queries

    @Override
    public CreditApplicationStatus currentStatus() {
        return status;
    }

    @Override
    public int remindersSent() {
        return remindersSent;
    }
}
