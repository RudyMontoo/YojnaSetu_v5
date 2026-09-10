package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.model.AuditLog;
import com.yojnasetu.gateway.repository.AuditLogRepository;
import com.yojnasetu.gateway.util.ClientIp;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * The citizen's control over who is helping them, and the helper's view of
 * what they've been asked to help with.
 *
 * Both sides live here because they are two halves of one relationship, and
 * splitting them across controllers makes it easy for the grant side and the
 * access side to drift apart — which is the failure mode that leaves someone
 * with access nobody remembers granting.
 */
@RestController
public class AssistController {

    private final AssistService assists;
    private final CreditApplicationService applications;
    private final BranchRepRepository helpers;
    private final FileAccessService fileAccess;
    private final MisuseReportService misuseReports;
    private final AuditLogRepository auditLogRepository;

    public AssistController(AssistService assists,
                            CreditApplicationService applications,
                            BranchRepRepository helpers,
                            FileAccessService fileAccess,
                            MisuseReportService misuseReports,
                            AuditLogRepository auditLogRepository) {
        this.assists = assists;
        this.applications = applications;
        this.helpers = helpers;
        this.fileAccess = fileAccess;
        this.misuseReports = misuseReports;
        this.auditLogRepository = auditLogRepository;
    }

    // ------------------------------------------------------------- citizen

    /** "This person is helping me with this application." */
    @PostMapping("/api/v2/sih/applications/{id}/assist")
    public ResponseEntity<?> grant(Authentication auth, @PathVariable String id,
                                   @RequestBody GrantRequest request,
                                   HttpServletRequest httpRequest) {
        try {
            CreditApplication application = applications.getForCitizen(auth.getName(), id);
            AssistAuthorization granted = assists.grant(application, auth.getName(),
                    request == null ? null : request.helperRepId(),
                    request == null ? null : request.note());
            audit(auth.getName(), "assist_authorization_grant", httpRequest);
            return ResponseEntity.status(HttpStatus.CREATED).body(granted);
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
    }

    /**
     * "Stop letting them see this." Omitting helperId withdraws every live
     * authorization on the file at once — the panic button, for someone who
     * wants access closed now and will work out the details later.
     */
    @DeleteMapping("/api/v2/sih/applications/{id}/assist")
    public ResponseEntity<?> revoke(Authentication auth, @PathVariable String id,
                                    @RequestParam(required = false) String helperId,
                                    HttpServletRequest httpRequest) {
        try {
            applications.getForCitizen(auth.getName(), id);   // ownership check
            assists.revoke(id, auth.getName(), helperId);
            audit(auth.getName(), "assist_authorization_revoke", httpRequest);
            return ResponseEntity.ok(Map.of("revoked", true));
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
    }

    /** "Who is helping me with this?" — including anyone whose access was withdrawn. */
    @GetMapping("/api/v2/sih/applications/{id}/assist")
    public ResponseEntity<?> helpers(Authentication auth, @PathVariable String id) {
        try {
            applications.getForCitizen(auth.getName(), id);
            return ResponseEntity.ok(fileAccess.helpersFor(id));
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
    }

    /**
     * "Who has touched my file?" — the full activity list, including who
     * opened documents. The applicant's own copy of the audit trail.
     */
    @GetMapping("/api/v2/sih/applications/{id}/activity")
    public ResponseEntity<?> activity(Authentication auth, @PathVariable String id) {
        try {
            CreditApplication application = applications.getForCitizen(auth.getName(), id);
            return ResponseEntity.ok(fileAccess.timelineFor(application));
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
    }

    /**
     * Report that a helper did something they should not have.
     *
     * Deliberately does not require the application to still be open, or the
     * reported helper to still be authorized: the reports that matter most
     * arrive after the fact, once someone has had time to realise what
     * happened and to feel safe enough to say so.
     */
    @PostMapping("/api/v2/sih/applications/{id}/report-misuse")
    public ResponseEntity<?> reportMisuse(Authentication auth, @PathVariable String id,
                                          @RequestBody MisuseRequest request,
                                          HttpServletRequest httpRequest) {
        try {
            applications.getForCitizen(auth.getName(), id);
            MisuseReport filed = misuseReports.file(auth.getName(), id,
                    request == null ? null : request.reportedHelperId(),
                    request == null ? null : request.category(),
                    request == null ? null : request.description());
            audit(auth.getName(), "misuse_report_filed", httpRequest);
            return ResponseEntity.status(HttpStatus.CREATED).body(filed);
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
    }

    /** Everything this citizen has reported, and what came of it. */
    @GetMapping("/api/v2/sih/misuse-reports")
    public List<MisuseReport> myReports(Authentication auth) {
        return misuseReports.listForCitizen(auth.getName());
    }

    /** The vocabulary, so the UI renders the real categories rather than its own. */
    @GetMapping("/api/v2/sih/misuse-reports/categories")
    public List<Map<String, String>> misuseCategories() {
        return java.util.Arrays.stream(MisuseReport.Category.values())
                .map(c -> Map.of("category", c.wireName()))
                .toList();
    }

    // -------------------------------------------------------------- helper

    /**
     * The helper's own worklist: the files citizens have currently authorized
     * them to help with. Under /api/v2/branch/** so SecurityConfig's role
     * matcher covers it, same reasoning as the rep document endpoints.
     */
    @GetMapping("/api/v2/branch/assist")
    public ResponseEntity<?> myAssignments(Authentication auth) {
        BranchRep helper = helpers.findById(auth.getName()).filter(BranchRep::isActive).orElse(null);
        if (helper == null) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Not a helper session"));
        }

        List<Map<String, Object>> rows = assists.activeFor(helper.getId()).stream()
                .map(a -> {
                    Map<String, Object> row = new java.util.HashMap<>();
                    row.put("applicationId", a.getApplicationId());
                    row.put("grantedAt", a.getGrantedAt());
                    // Best-effort enrichment: an authorization can outlive the
                    // application row in a partially-restored environment, and
                    // a helper's worklist should degrade to "this id" rather
                    // than fail outright.
                    applications.findById(a.getApplicationId()).ifPresent(app -> {
                        row.put("productName", app.getProductName());
                        row.put("status", app.getStatus());
                        row.put("requestedAmount", app.getRequestedAmount());
                        row.put("missingDocuments", app.getMissingDocuments());
                    });
                    return row;
                })
                .toList();

        return ResponseEntity.ok(Map.of(
                "helperType", helper.getRepType().wireName(),
                "canRecordDecisions", helper.getRepType().canRecordDecisions(),
                "assignments", rows));
    }

    private void audit(String userId, String action, HttpServletRequest request) {
        auditLogRepository.save(AuditLog.of(userId, action, request.getRequestURI(), ClientIp.of(request)));
    }

    public record GrantRequest(String helperRepId, String note) {
    }

    public record MisuseRequest(String reportedHelperId, MisuseReport.Category category,
                                String description) {
    }
}
