package com.yojnasetu.gateway.workflow;

import com.yojnasetu.gateway.credit.CreditApplicationStatus;
import io.temporal.client.WorkflowClient;
import io.temporal.client.WorkflowOptions;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * The one place the rest of the application talks to Temporal.
 *
 * Every method is a no-op when Temporal is disabled or unreachable. That is
 * the whole point: the REST endpoints already perform and persist the
 * transition themselves, so signalling is an addition — durable timers, SLA
 * chasing, orchestration history — and never a prerequisite. A Temporal outage
 * costs us reminders, not the ability to process loans.
 *
 * Because of that, callers do not handle failures here. There is nothing
 * useful for a controller to do about a failed signal that would not be worse
 * than carrying on.
 */
@Component
public class LoanWorkflowGateway {

    private static final Logger LOG = LoggerFactory.getLogger(LoanWorkflowGateway.class);

    private final ObjectProvider<WorkflowClient> clientProvider;

    public LoanWorkflowGateway(ObjectProvider<WorkflowClient> clientProvider) {
        this.clientProvider = clientProvider;
    }

    public boolean isEnabled() {
        return clientProvider.getIfAvailable() != null;
    }

    /**
     * Starts the workflow for a new application. The workflow id IS the
     * application id, so Temporal's own deduplication makes a second start for
     * the same application a no-op rather than a second orchestration.
     */
    public void start(String applicationId, String citizenUserId) {
        WorkflowClient client = clientProvider.getIfAvailable();
        if (client == null) {
            return;
        }
        try {
            LoanApplicationWorkflow workflow = client.newWorkflowStub(
                    LoanApplicationWorkflow.class,
                    WorkflowOptions.newBuilder()
                            .setTaskQueue(LoanApplicationWorkflow.TASK_QUEUE)
                            .setWorkflowId(applicationId)
                            .build());
            WorkflowClient.start(workflow::run, applicationId, citizenUserId);
        } catch (Exception e) {
            LOG.warn("Could not start loan workflow for {}: {}", applicationId, e.toString());
        }
    }

    /**
     * Reports a transition that has already been applied and persisted.
     *
     * @param documents only meaningful for a missing-documents request
     */
    public void signal(String applicationId, CreditApplicationStatus status,
                       String reasonCode, List<String> documents) {
        WorkflowClient client = clientProvider.getIfAvailable();
        if (client == null) {
            return;
        }
        try {
            LoanApplicationWorkflow workflow =
                    client.newWorkflowStub(LoanApplicationWorkflow.class, applicationId);
            switch (status) {
                case SUBMITTED -> workflow.applicationSubmitted();
                case UNDER_VERIFICATION -> {
                    if (documents != null) {
                        workflow.documentsUploaded();
                    } else {
                        workflow.verificationStarted();
                    }
                }
                case MISSING_DOCS -> workflow.missingDocsRequested(documents);
                case FORWARDED -> workflow.forwarded();
                case SANCTIONED -> workflow.sanctioned();
                case REJECTED -> workflow.rejected(reasonCode);
                case DISBURSED -> workflow.disbursed();
                case DRAFT -> { /* nothing has happened yet */ }
            }
        } catch (Exception e) {
            // Includes "no such workflow", which happens for applications
            // created before Temporal was switched on. Not worth failing a
            // request that has already succeeded.
            LOG.warn("Could not signal loan workflow {} for {}: {}",
                    status, applicationId, e.toString());
        }
    }
}
