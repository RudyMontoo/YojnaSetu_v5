package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.model.AuditLog;
import com.yojnasetu.gateway.repository.AuditLogRepository;
import com.yojnasetu.gateway.util.ClientIp;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * The Channel Partner branch representative's working surface: their queue, one
 * file at a time, and the decisions they're allowed to record.
 *
 * Access is gated in SecurityConfig by {@code hasAnyRole("BRANCH_REP","ADMIN")}
 * for {@code /api/v2/branch/**} rather than by hand-rolled authority checks
 * inside each handler. The older controllers in this codebase do the latter,
 * which means a new endpoint is unprotected until someone remembers to add the
 * check — a path-level matcher is protected by default.
 *
 * Note the asymmetry with the citizen side: a rep is scoped to applications
 * assigned to their partner.
 *
 * That scope is derived from the rep's OWN account, never from the request.
 * It used to come from a {@code partnerId} the caller supplied in the query
 * string or body, with the authenticated identity used only for the audit
 * line — so any logged-in rep could read, and act on, another partner's files
 * by naming their id. {@link #actingPartnerId} now resolves it from the JWT
 * subject instead. An ADMIN is the one caller who may still name a partner
 * explicitly, because cross-partner oversight is the point of that role.
 */
@RestController
@RequestMapping("/api/v2/branch/applications")
public class BranchRepController {

    private final CreditApplicationService service;
    private final AuditLogRepository auditLogRepository;
    private final com.yojnasetu.gateway.workflow.LoanWorkflowGateway workflows;
    private final BranchRepRepository branchReps;

    public BranchRepController(CreditApplicationService service,
                               AuditLogRepository auditLogRepository,
                               com.yojnasetu.gateway.workflow.LoanWorkflowGateway workflows,
                               BranchRepRepository branchReps) {
        this.service = service;
        this.auditLogRepository = auditLogRepository;
        this.workflows = workflows;
        this.branchReps = branchReps;
    }

    private static boolean isAdmin(Authentication auth) {
        return auth != null && auth.getAuthorities().stream()
                .anyMatch(a -> "ROLE_ADMIN".equals(a.getAuthority()));
    }

    private java.util.Optional<BranchRep> actingRep(Authentication auth) {
        return auth == null ? java.util.Optional.empty()
                : branchReps.findById(auth.getName()).filter(BranchRep::isActive);
    }

    /**
     * The partner whose files this caller may work, or empty if none.
     *
     * {@code requested} is honoured only for an ADMIN. For a rep it is ignored
     * outright rather than compared — a mismatch is not a bad request to be
     * reported, it is an attempt to act outside one's own branch, and the
     * answer is simply the branch they actually belong to.
     */
    private java.util.Optional<String> actingPartnerId(Authentication auth, String requested) {
        if (isAdmin(auth)) {
            return java.util.Optional.ofNullable(requested).filter(p -> !p.isBlank());
        }
        return actingRep(auth)
                .map(BranchRep::getPartnerId)
                .filter(p -> p != null && !p.isBlank());
    }

    private static ResponseEntity<?> noScope() {
        // Deliberately not "you sent the wrong partnerId": the caller doesn't
        // get to learn which partner ids exist or which one they missed.
        return ResponseEntity.status(403).body(Map.of(
                "error", "This account is not attached to a lending branch queue."));
    }

    /** The queue, newest submission first, optionally filtered by status. */
    @GetMapping
    public ResponseEntity<?> queue(Authentication auth,
                                   @RequestParam(required = false) String partnerId,
                                   @RequestParam(required = false) CreditApplicationStatus status) {
        return actingPartnerId(auth, partnerId)
                .<ResponseEntity<?>>map(scope -> ResponseEntity.ok(service.queueForPartner(scope, status)))
                .orElseGet(BranchRepController::noScope);
    }

    @GetMapping("/{id}")
    public ResponseEntity<?> detail(Authentication auth,
                                    @PathVariable String id,
                                    @RequestParam(required = false) String partnerId) {
        java.util.Optional<String> scope = actingPartnerId(auth, partnerId);
        if (scope.isEmpty()) {
            return noScope();
        }
        return service.findById(id)
                .filter(a -> scope.get().equals(a.getAssignedPartnerId()))
                .<ResponseEntity<?>>map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.status(404).body(Map.of("error", "Application not found")));
    }

    /**
     * Record a decision. The legality of the move itself is the state machine's
     * call, not this handler's — it only checks that the rep is entitled to
     * touch this file at all.
     */
    @PostMapping("/{id}/status")
    public ResponseEntity<?> updateStatus(Authentication auth,
                                          @PathVariable String id,
                                          @RequestBody StatusUpdateRequest request,
                                          HttpServletRequest httpRequest) {
        if (request == null || request.status() == null) {
            return ResponseEntity.badRequest().body(Map.of("error", "status is required"));
        }

        // A credit decision belongs to the lender. A CSC operator, NGO worker
        // or field agent holds an account so they can help a citizen assemble
        // a file — not so they can sanction or reject one. Checked here rather
        // than left to the UI, because the UI is not the security boundary.
        var rep = actingRep(auth);
        if (rep.isPresent() && !rep.get().getRepType().canRecordDecisions()) {
            return ResponseEntity.status(403).body(Map.of(
                    "error", "A " + rep.get().getRepType().label()
                            + " can help with documents but cannot record a decision on an application."));
        }

        java.util.Optional<String> scope = actingPartnerId(auth, request.partnerId());
        if (scope.isEmpty()) {
            return noScope();
        }

        var found = service.findById(id)
                .filter(a -> scope.get().equals(a.getAssignedPartnerId()));
        if (found.isEmpty()) {
            return ResponseEntity.status(404).body(Map.of("error", "Application not found"));
        }

        try {
            CreditApplication updated = service.transition(found.get(), request.status(),
                    auth.getName(), "BRANCH_REP", request.reasonCode(), request.note(),
                    request.requestedDocuments());

            workflows.signal(id, request.status(),
                    request.reasonCode() == null ? null : request.reasonCode().wireName(),
                    request.requestedDocuments());

            auditLogRepository.save(AuditLog.of(auth.getName(), "credit_application_status_update",
                    httpRequest.getRequestURI(), ClientIp.of(httpRequest)));

            return ResponseEntity.ok(updated);
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
    }

    /**
     * The reason-code vocabulary, so the rep's UI renders a real list instead of
     * hardcoding one that drifts from the enum.
     */
    @GetMapping("/reason-codes")
    public List<Map<String, String>> reasonCodes() {
        return java.util.Arrays.stream(ReasonCode.values())
                .map(c -> Map.of("code", c.wireName(), "description", c.description()))
                .toList();
    }

    public record StatusUpdateRequest(
            String partnerId,
            CreditApplicationStatus status,
            ReasonCode reasonCode,
            String note,
            List<String> requestedDocuments) {
    }
}
