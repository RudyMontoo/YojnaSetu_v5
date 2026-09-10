package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.model.AuditLog;
import com.yojnasetu.gateway.repository.AuditLogRepository;
import com.yojnasetu.gateway.util.ClientIp;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Arrays;
import java.util.List;
import java.util.Map;

/**
 * A citizen's own consents: what they have agreed to, and withdrawing it.
 *
 * The purposes endpoint exists so the frontend renders the exact wording from
 * {@link ConsentPurpose} rather than its own paraphrase. If the UI says one
 * thing and we store another, the record is worthless.
 */
@RestController
@RequestMapping("/api/v2/sih/consents")
public class ConsentController {

    private final ConsentService consents;
    private final AuditLogRepository auditLogRepository;

    public ConsentController(ConsentService consents, AuditLogRepository auditLogRepository) {
        this.consents = consents;
        this.auditLogRepository = auditLogRepository;
    }

    /** The vocabulary and the exact statements — build the UI from this. */
    @GetMapping("/purposes")
    public List<Map<String, String>> purposes() {
        return Arrays.stream(ConsentPurpose.values())
                .map(p -> Map.of("purpose", p.wireName(), "statement", p.statement()))
                .toList();
    }

    @GetMapping
    public List<Consent> mine(Authentication auth) {
        return consents.listFor(auth.getName());
    }

    public record GrantRequest(ConsentPurpose purpose, String applicationId) {}

    @PostMapping
    public ResponseEntity<?> grant(Authentication auth, @RequestBody GrantRequest request,
                                   HttpServletRequest httpRequest) {
        if (request == null || request.purpose() == null) {
            return ResponseEntity.badRequest().body(Map.of("error", "purpose is required"));
        }
        try {
            Consent consent = consents.grant(auth.getName(), request.purpose(),
                    request.applicationId(), ClientIp.of(httpRequest));
            audit(auth.getName(), "consent_granted", httpRequest);
            return ResponseEntity.ok(consent);
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
    }

    /**
     * Withdraws consent. Deliberately always succeeds, even when there was
     * nothing to withdraw — a citizen asking us to stop should never be met
     * with an error, and {@code revoked: 0} says plainly what happened.
     */
    @DeleteMapping("/{purpose}")
    public ResponseEntity<?> revoke(Authentication auth, @PathVariable ConsentPurpose purpose,
                                    @RequestParam(required = false) String applicationId,
                                    HttpServletRequest httpRequest) {
        int revoked = consents.revoke(auth.getName(), purpose, applicationId);
        audit(auth.getName(), "consent_revoked", httpRequest);
        return ResponseEntity.ok(Map.of("revoked", revoked, "purpose", purpose.wireName()));
    }

    private void audit(String userId, String action, HttpServletRequest request) {
        auditLogRepository.save(AuditLog.of(userId, action, request.getRequestURI(), ClientIp.of(request)));
    }
}
