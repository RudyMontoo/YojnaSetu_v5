package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.credit.CreditApplicationService.Failure;
import com.yojnasetu.gateway.credit.CreditApplicationService.TransitionException;
import com.yojnasetu.gateway.model.AgentAlert;
import com.yojnasetu.gateway.repository.AgentAlertRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

/**
 * Filing, and — the part that actually matters — making sure someone reads it.
 *
 * A report that lands in a collection nobody watches is worse than no reporting
 * channel at all, because it tells the applicant they have been heard when they
 * have not. Every report therefore raises an {@code agent_alerts} row, which
 * {@code AlertNotifier} already polls and emails to an administrator. That
 * mechanism exists and is running; this hooks into it rather than inventing a
 * second notification path that would need its own babysitting.
 */
@Service
public class MisuseReportService {

    private static final Logger LOG = LoggerFactory.getLogger(MisuseReportService.class);

    private final MisuseReportRepository reports;
    private final BranchRepRepository helpers;
    private final AgentAlertRepository alerts;

    public MisuseReportService(MisuseReportRepository reports,
                               BranchRepRepository helpers,
                               AgentAlertRepository alerts) {
        this.reports = reports;
        this.helpers = helpers;
        this.alerts = alerts;
    }

    public MisuseReport file(String citizenId, String applicationId, String reportedHelperId,
                             MisuseReport.Category category, String description) {
        if (category == null) {
            throw new TransitionException(Failure.BAD_REQUEST, "category is required");
        }
        if (description == null || description.isBlank()) {
            throw new TransitionException(Failure.BAD_REQUEST,
                    "Please describe what happened, in your own words.");
        }

        MisuseReport report = new MisuseReport();
        report.setCitizenId(citizenId);
        report.setApplicationId(applicationId);
        report.setCategory(category);
        report.setDescription(description.trim());
        report.setStatus(MisuseReport.Status.OPEN);
        report.setCreatedAt(LocalDateTime.now());

        // An unknown helper id is not a reason to refuse the report. The
        // applicant may be reading a name off a badge, or guessing. Record what
        // they said and let a human sort out who it refers to.
        if (reportedHelperId != null && !reportedHelperId.isBlank()) {
            report.setReportedHelperId(reportedHelperId.trim());
            Optional<BranchRep> helper = helpers.findById(reportedHelperId.trim());
            if (helper.isEmpty()) {
                helper = helpers.findByRepId(reportedHelperId.trim());
                helper.ifPresent(h -> report.setReportedHelperId(h.getId()));
            }
            helper.ifPresent(h -> report.setReportedHelperName(h.getName()));
        }

        MisuseReport saved = reports.save(report);
        raiseAlert(saved);
        return saved;
    }

    /**
     * Puts the report in front of an administrator.
     *
     * Carries ids only, never the applicant's description. That text is their
     * account of something that happened to them and routinely names people and
     * places; {@code agent_alerts} is a TTL'd operational collection that gets
     * emailed in a digest, and AuditLog's own rule in this codebase is that
     * PII does not go into logs. The alert says where to look, and the report
     * itself stays the single place the words live.
     *
     * Best-effort: a failure to alert must not lose the report, which is
     * already saved by the time this runs.
     */
    private void raiseAlert(MisuseReport report) {
        try {
            AgentAlert alert = new AgentAlert();
            alert.setAgentName("credit.misuse_report");
            alert.setAlertType("misuse_report_filed");
            alert.setMessage("Misuse report " + report.getId() + " filed (" + report.getCategory().wireName()
                    + ") on application " + report.getApplicationId()
                    + (report.getReportedHelperId() == null ? ""
                            : ", helper " + report.getReportedHelperId())
                    + ". Read the report itself for details.");
            alert.setAt(Instant.now());
            alert.setResolved(false);
            alerts.save(alert);
        } catch (Exception e) {
            LOG.error("Misuse report {} saved but could not be alerted on: {}",
                    report.getId(), e.toString());
        }
    }

    public List<MisuseReport> listForCitizen(String citizenId) {
        return reports.findByCitizenIdOrderByCreatedAtDesc(citizenId);
    }

    public List<MisuseReport> open() {
        return reports.findByStatusOrderByCreatedAtDesc(MisuseReport.Status.OPEN);
    }

    /**
     * Staff response. The note is written back onto the report because the
     * applicant is shown it — being told what came of your complaint is most of
     * what makes complaining feel worth doing.
     */
    public MisuseReport resolve(String reportId, MisuseReport.Status status, String resolutionNote) {
        MisuseReport report = reports.findById(reportId).orElseThrow(
                () -> new TransitionException(Failure.NOT_FOUND, "Report not found"));
        if (status == null) {
            throw new TransitionException(Failure.BAD_REQUEST, "status is required");
        }
        report.setStatus(status);
        report.setResolutionNote(resolutionNote);
        if (status == MisuseReport.Status.RESOLVED) {
            report.setResolvedAt(LocalDateTime.now());
        }
        return reports.save(report);
    }
}
