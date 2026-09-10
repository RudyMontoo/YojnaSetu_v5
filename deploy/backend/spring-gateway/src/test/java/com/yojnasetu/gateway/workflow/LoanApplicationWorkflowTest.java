package com.yojnasetu.gateway.workflow;

import com.yojnasetu.gateway.credit.CreditApplicationStatus;
import io.temporal.client.WorkflowClient;
import io.temporal.client.WorkflowOptions;
import io.temporal.testing.TestWorkflowEnvironment;
import io.temporal.worker.Worker;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Runs the real workflow against Temporal's in-process test server, whose clock
 * is virtual — a three-day SLA timer fires in milliseconds. That is exactly the
 * behaviour that is impossible to test with a scheduled sweep, and the reason
 * this orchestration is worth its weight.
 *
 * Activities are faked here so the test is about sequence and timing. Whether a
 * transition is legal is decided by CreditApplicationService and covered by its
 * own tests.
 */
class LoanApplicationWorkflowTest {

    private TestWorkflowEnvironment env;
    private WorkflowClient client;
    private FakeActivities activities;

    /**
     * Behaves like the real activity: applying the status the application
     * already holds is a no-op, and it always answers with what is now true.
     */
    static class FakeActivities implements LoanApplicationActivities {
        final Map<String, CreditApplicationStatus> statuses = new ConcurrentHashMap<>();
        final List<Integer> verificationReminders = new ArrayList<>();
        final List<Integer> documentReminders = new ArrayList<>();
        int repNotifiedOfDocs;

        @Override
        public CreditApplicationStatus applyStatus(String id, CreditApplicationStatus status,
                                                   String actorUserId, String actorRole,
                                                   String reasonCode, String note,
                                                   List<String> requestedDocuments) {
            statuses.put(id, status);
            return status;
        }

        @Override
        public CreditApplicationStatus readStatus(String id) {
            return statuses.get(id);
        }

        @Override
        public synchronized void sendVerificationReminder(String id, int daysWaiting) {
            verificationReminders.add(daysWaiting);
        }

        @Override
        public synchronized void sendDocumentsReminder(String id, int daysWaiting) {
            documentReminders.add(daysWaiting);
        }

        @Override
        public synchronized void notifyRepOfUploadedDocs(String id) {
            repNotifiedOfDocs++;
        }
    }

    @BeforeEach
    void setUp() {
        env = TestWorkflowEnvironment.newInstance();
        Worker worker = env.newWorker(LoanApplicationWorkflow.TASK_QUEUE);
        worker.registerWorkflowImplementationTypes(LoanApplicationWorkflowImpl.class);
        activities = new FakeActivities();
        worker.registerActivitiesImplementations(activities);
        env.start();
        client = env.getWorkflowClient();
    }

    @AfterEach
    void tearDown() {
        env.close();
    }

    private LoanApplicationWorkflow startWorkflow(String applicationId) {
        LoanApplicationWorkflow workflow = client.newWorkflowStub(
                LoanApplicationWorkflow.class,
                WorkflowOptions.newBuilder()
                        .setTaskQueue(LoanApplicationWorkflow.TASK_QUEUE)
                        .setWorkflowId(applicationId)
                        .build());
        WorkflowClient.start(workflow::run, applicationId, "citizen-1");
        return workflow;
    }

    @Test
    void walksTheHappyPathToDisbursed() {
        LoanApplicationWorkflow workflow = startWorkflow("app-happy");

        workflow.applicationSubmitted();
        workflow.verificationStarted();
        workflow.forwarded();
        workflow.sanctioned();
        workflow.disbursed();

        assertEquals(CreditApplicationStatus.DISBURSED,
                io.temporal.client.WorkflowStub.fromTyped(workflow).getResult(CreditApplicationStatus.class));
        assertEquals(0, activities.verificationReminders.size(),
                "a file that kept moving should never be chased");
    }

    @Test
    void chasesARepWhoSitsOnAFile() {
        // The whole point of durable timers: nobody acts, and three days later
        // the reminder fires anyway. Virtual clock, so this is instant.
        LoanApplicationWorkflow workflow = startWorkflow("app-stalled");
        workflow.applicationSubmitted();

        env.sleep(Duration.ofDays(4));

        assertEquals(1, activities.verificationReminders.size());
        assertEquals(3, activities.verificationReminders.get(0));
    }

    @Test
    void keepsChasingButStopsBeforeItBecomesHarassment() {
        LoanApplicationWorkflow workflow = startWorkflow("app-ignored");
        workflow.applicationSubmitted();

        env.sleep(Duration.ofDays(60));

        assertEquals(LoanApplicationWorkflowImpl.MAX_REMINDERS,
                activities.verificationReminders.size());
        // Each reminder is a fresh SLA period of silence, not a burst.
        assertEquals(List.of(3, 6, 9), activities.verificationReminders);
    }

    @Test
    void stopsChasingTheMomentTheRepActs() {
        LoanApplicationWorkflow workflow = startWorkflow("app-acts-late");
        workflow.applicationSubmitted();

        env.sleep(Duration.ofDays(4));
        assertEquals(1, activities.verificationReminders.size());

        workflow.verificationStarted();
        env.sleep(Duration.ofDays(2));

        // Moving to a new stage restarts its own clock; the old one is dead.
        assertEquals(1, activities.verificationReminders.size());
    }

    @Test
    void chasesTheCitizenForDocumentsOnItsOwnSchedule() {
        LoanApplicationWorkflow workflow = startWorkflow("app-docs");
        workflow.applicationSubmitted();
        workflow.verificationStarted();
        workflow.missingDocsRequested(List.of("Caste certificate"));

        env.sleep(Duration.ofDays(6));

        assertEquals(1, activities.documentReminders.size());
        // Citizens get longer than reps do — they may need to travel for a document.
        assertEquals(5, activities.documentReminders.get(0));
        assertTrue(activities.verificationReminders.isEmpty(),
                "waiting on the citizen must not be logged as the rep being slow");
    }

    @Test
    void resumesVerificationWhenDocumentsArrive() {
        LoanApplicationWorkflow workflow = startWorkflow("app-docs-supplied");
        workflow.applicationSubmitted();
        workflow.verificationStarted();
        workflow.missingDocsRequested(List.of("Income proof"));
        workflow.documentsUploaded();

        // Signals are asynchronous — querying in the same breath as sending
        // four of them reads whatever the workflow has processed so far, which
        // is a race, not a guarantee. One virtual second is instant here and
        // nowhere near the 3-day SLA, so it settles the queue without arming a
        // reminder.
        env.sleep(Duration.ofSeconds(1));

        assertEquals(CreditApplicationStatus.UNDER_VERIFICATION, workflow.currentStatus());
        assertEquals(1, activities.repNotifiedOfDocs,
                "the rep has to be told the documents arrived, or the file stalls again");
    }

    @Test
    void completesOnRejection() {
        LoanApplicationWorkflow workflow = startWorkflow("app-rejected");
        workflow.applicationSubmitted();
        workflow.verificationStarted();
        workflow.rejected("documents_illegible");

        assertEquals(CreditApplicationStatus.REJECTED,
                io.temporal.client.WorkflowStub.fromTyped(workflow).getResult(CreditApplicationStatus.class));
    }

    @Test
    void doesNotChaseWhileAnExternalAuthorityHoldsTheFile() {
        // Once forwarded, the delay is not ours; nagging our own rep about it
        // would be noise.
        LoanApplicationWorkflow workflow = startWorkflow("app-forwarded");
        workflow.applicationSubmitted();
        workflow.verificationStarted();
        workflow.forwarded();

        env.sleep(Duration.ofDays(30));

        assertEquals(0, activities.verificationReminders.size());
        assertEquals(CreditApplicationStatus.FORWARDED, workflow.currentStatus());
    }

    @Test
    void reportsHowOftenItHasChased() {
        LoanApplicationWorkflow workflow = startWorkflow("app-query");
        workflow.applicationSubmitted();
        env.sleep(Duration.ofDays(7));

        // What an ops dashboard filters on to find genuinely stuck files.
        assertEquals(2, workflow.remindersSent());
        assertEquals(CreditApplicationStatus.SUBMITTED, workflow.currentStatus());
    }

    @Test
    void abandonsAnApplicationThatIsNeverSubmitted() {
        startWorkflow("app-abandoned");

        env.sleep(Duration.ofDays(366));

        // A draft nobody ever submitted must not pin a workflow open forever.
        assertTrue(activities.verificationReminders.isEmpty());
    }
}
