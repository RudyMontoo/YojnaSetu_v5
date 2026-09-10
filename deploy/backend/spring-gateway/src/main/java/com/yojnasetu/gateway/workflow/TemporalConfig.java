package com.yojnasetu.gateway.workflow;

import io.temporal.client.WorkflowClient;
import io.temporal.serviceclient.WorkflowServiceStubs;
import io.temporal.serviceclient.WorkflowServiceStubsOptions;
import io.temporal.worker.Worker;
import io.temporal.worker.WorkerFactory;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Temporal wiring, deliberately behind {@code app.temporal.enabled} and OFF by
 * default.
 *
 * The gateway must boot and serve every endpoint with no Temporal cluster
 * present. Orchestration is durability and SLA chasing layered on top of a
 * lifecycle that already works over REST — if a missing Temporal server could
 * stop a citizen submitting an application, we would have made the platform
 * less reliable by adding a reliability tool. It also means local development
 * and demo machines need nothing extra running.
 *
 * With the flag on, this registers a worker for the loan task queue against
 * {@code app.temporal.target} (default {@code 127.0.0.1:7233}).
 */
@Configuration
@ConditionalOnProperty(name = "app.temporal.enabled", havingValue = "true")
public class TemporalConfig {

    private static final Logger LOG = LoggerFactory.getLogger(TemporalConfig.class);

    @Value("${app.temporal.target:127.0.0.1:7233}")
    private String target;

    @Value("${app.temporal.namespace:default}")
    private String namespace;

    private WorkflowServiceStubs stubs;
    private WorkerFactory factory;

    @Bean
    public WorkflowServiceStubs workflowServiceStubs() {
        this.stubs = WorkflowServiceStubs.newServiceStubs(
                WorkflowServiceStubsOptions.newBuilder().setTarget(target).build());
        return stubs;
    }

    @Bean
    public WorkflowClient workflowClient(WorkflowServiceStubs stubs) {
        return WorkflowClient.newInstance(stubs,
                io.temporal.client.WorkflowClientOptions.newBuilder()
                        .setNamespace(namespace)
                        .build());
    }

    /**
     * The worker polls the task queue and runs workflow and activity code.
     * Activities are registered as the Spring bean, so they keep their injected
     * services — this is the seam that lets workflow code reuse the domain
     * layer instead of duplicating it.
     */
    @Bean
    public WorkerFactory workerFactory(WorkflowClient client, LoanApplicationActivities activities) {
        this.factory = WorkerFactory.newInstance(client);
        Worker worker = factory.newWorker(LoanApplicationWorkflow.TASK_QUEUE);
        worker.registerWorkflowImplementationTypes(LoanApplicationWorkflowImpl.class);
        worker.registerActivitiesImplementations(activities);
        factory.start();
        LOG.info("Temporal worker started on task queue '{}' against {}",
                LoanApplicationWorkflow.TASK_QUEUE, target);
        return factory;
    }

    @PreDestroy
    public void shutdown() {
        if (factory != null) {
            factory.shutdown();
        }
        if (stubs != null) {
            stubs.shutdown();
        }
    }
}
