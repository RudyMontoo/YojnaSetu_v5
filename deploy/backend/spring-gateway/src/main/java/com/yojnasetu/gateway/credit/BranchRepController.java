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
 * assigned to their partner, so {@link #queue} keys on the partnerId they pass
 * and the detail view refuses files belonging to a different partner.
 */
@RestController
@RequestMapping("/api/v2/branch/applications")
public class BranchRepController {

    private final CreditApplicationService service;
    private final AuditLogRepository auditLogRepository;

    public BranchRepController(CreditApplicationService service, AuditLogRepository auditLogRepository) {
        this.service = service;
        this.auditLogRepository = auditLogRepository;
    }

    /** The queue, newest submission first, optionally filtered by status. */
    @GetMapping
    public ResponseEntity<?> queue(@RequestParam String partnerId,
                                   @RequestParam(required = false) CreditApplicationStatus status) {
        if (partnerId == null || partnerId.isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "partnerId is required"));
        }
        return ResponseEntity.ok(service.queueForPartner(partnerId, status));
    }

    @GetMapping("/{id}")
    public ResponseEntity<?> detail(@PathVariable String id, @RequestParam String partnerId) {
        return service.findById(id)
                .filter(a -> partnerId.equals(a.getAssignedPartnerId()))
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
        if (request == null || request.partnerId() == null || request.partnerId().isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "partnerId is required"));
        }

        var found = service.findById(id)
                .filter(a -> request.partnerId().equals(a.getAssignedPartnerId()));
        if (found.isEmpty()) {
            return ResponseEntity.status(404).body(Map.of("error", "Application not found"));
        }

        try {
            CreditApplication updated = service.transition(found.get(), request.status(),
                    auth.getName(), "BRANCH_REP", request.reasonCode(), request.note(),
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
