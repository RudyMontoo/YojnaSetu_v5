package com.yojnasetu.gateway.service;

import com.yojnasetu.gateway.model.AgentAlert;
import com.yojnasetu.gateway.repository.AgentAlertRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.stream.Collectors;

/**
 * Self-alerting: polls the `agent_alerts` collection and emails the admin a
 * digest of anything unresolved, so YOU find out an agent is unhealthy before a
 * citizen does. Without this, agent_alerts is a table nobody reads until
 * something is already broken.
 *
 * Poll (default 15 min) instead of push because the alerts are written by a
 * different process (the Python ai_service / discovery Job) into Mongo — polling
 * keeps the two services decoupled and naturally batches a burst into one email.
 *
 * If email isn't configured yet (Brevo still propagating), sendAlert logs instead
 * and returns false, and we DON'T mark the alert notified — so it's retried and
 * actually delivered once email goes live. No alert is lost in the gap.
 */
@Component
public class AlertNotifier {

    private static final Logger log = LoggerFactory.getLogger(AlertNotifier.class);

    private final AgentAlertRepository alertRepo;
    private final EmailService emailService;

    @Value("${app.alert.email:}")
    private String alertEmail;

    public AlertNotifier(AgentAlertRepository alertRepo, EmailService emailService) {
        this.alertRepo = alertRepo;
        this.emailService = emailService;
    }

    // fixedDelay: wait this long AFTER each run finishes; initialDelay lets the app settle on boot.
    @Scheduled(fixedDelayString = "${app.alert.poll-ms:900000}", initialDelayString = "${app.alert.initial-delay-ms:60000}")
    public void checkAndNotify() {
        if (alertEmail == null || alertEmail.isBlank()) {
            return; // no recipient configured — nothing to do (don't spam logs every 15 min)
        }
        List<AgentAlert> pending;
        try {
            pending = alertRepo.findUnresolvedUnnotified();
        } catch (Exception e) {
            log.warn("AlertNotifier: could not query agent_alerts ({})", e.toString());
            return;
        }
        if (pending.isEmpty()) return;

        String subject = "[Yojna Sarthi] " + pending.size() + " agent alert(s) need attention";
        String body = "Unresolved agent alerts:\n\n" + pending.stream()
                .map(a -> "• [" + a.getAgentName() + "/" + a.getAlertType() + "] " + a.getMessage()
                        + (a.getAt() != null ? "  (" + a.getAt() + ")" : ""))
                .collect(Collectors.joining("\n"))
                + "\n\nResolve them in the agent_alerts collection (set resolved=true) once handled.\n\n— Yojna Sarthi monitor";

        boolean sent = emailService.sendAlert(alertEmail, subject, body);
        if (!sent) {
            log.warn("AlertNotifier: {} unresolved alert(s) but email not configured — will retry", pending.size());
            return; // leave notified unset so it retries once email is live
        }
        pending.forEach(a -> a.setNotified(true));
        alertRepo.saveAll(pending);
        log.info("AlertNotifier: emailed admin about {} alert(s)", pending.size());
    }
}
