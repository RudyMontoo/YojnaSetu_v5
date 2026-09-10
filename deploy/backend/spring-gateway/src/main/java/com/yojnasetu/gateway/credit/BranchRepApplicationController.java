package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.security.FieldEncryptionService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * "Become an assist helper" — citizen-facing application + admin review, for
 * the CSC-operator/NGO-worker/field-agent side of {@link BranchRep}.
 *
 * Under /api/v2/sih so it sits with the rest of the credit module's
 * citizen-facing surface; admin routes here check ROLE_ADMIN in the handler,
 * same convention as {@code HelperApplicationController} rather than a path
 * matcher, since this whole controller is citizen-reachable except those
 * three endpoints.
 */
@RestController
@RequestMapping("/api/v2/sih/branch-rep-applications")
public class BranchRepApplicationController {

    private final BranchRepApplicationService service;
    private final FieldEncryptionService encryption;

    public BranchRepApplicationController(BranchRepApplicationService service,
                                          FieldEncryptionService encryption) {
        this.service = service;
        this.encryption = encryption;
    }

    private static boolean isAdmin(Authentication auth) {
        return auth != null && auth.getAuthorities().stream()
                .anyMatch(a -> "ROLE_ADMIN".equals(a.getAuthority()));
    }

    private Map<String, Object> summary(BranchRepApplication a) {
        Map<String, Object> m = new HashMap<>();
        m.put("id", a.getId());
        m.put("userId", a.getUserId());
        m.put("fullName", encryption.decrypt(a.getFullName()));
        m.put("phone", encryption.decrypt(a.getPhone()));
        m.put("aadhaarMasked", a.getAadhaarMasked());
        m.put("aadhaarVerified", a.isAadhaarVerified());
        m.put("pan", encryption.decrypt(a.getPan()));
        m.put("repType", a.getRepType() == null ? null : a.getRepType().wireName());
        m.put("repTypeLabel", a.getRepType() == null ? null : a.getRepType().label());
        m.put("organisation", a.getOrganisation());
        m.put("workProofDetail", a.getWorkProofDetail());
        m.put("status", a.getStatus());
        m.put("createdAt", a.getCreatedAt());
        return m;
    }

    /** Citizen submits an application to become an assist-only helper. */
    @PostMapping
    public ResponseEntity<?> apply(Authentication auth, @RequestBody BranchRepApplicationService.ApplyRequest req) {
        try {
            BranchRepApplication application = service.apply(auth.getName(), req);
            return ResponseEntity.status(HttpStatus.CREATED).body(Map.of(
                    "success", true, "status", application.getStatus(),
                    "aadhaarVerified", application.isAadhaarVerified()));
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
    }

    /** Citizen sees their own application status. */
    @GetMapping("/mine")
    public ResponseEntity<?> mine(Authentication auth) {
        return service.myApplication(auth.getName())
                .<ResponseEntity<?>>map(a -> ResponseEntity.ok(summary(a)))
                .orElse(ResponseEntity.ok(Map.of("status", "none")));
    }

    /** Admin: pending applications to review. */
    @GetMapping("/pending")
    public ResponseEntity<?> pending(Authentication auth) {
        if (!isAdmin(auth)) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Admin only"));
        }
        List<Map<String, Object>> rows = service.pending().stream().map(this::summary).toList();
        return ResponseEntity.ok(Map.of("applications", rows));
    }

    /** Admin: at-a-glance count, for a dashboard badge. */
    @GetMapping("/pending/count")
    public ResponseEntity<?> pendingCount(Authentication auth) {
        if (!isAdmin(auth)) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Admin only"));
        }
        return ResponseEntity.ok(Map.of("pending", service.countPending()));
    }

    /**
     * Admin approves: mints a BranchRep login, emails it, and returns it so
     * an admin can relay the credentials by hand if email delivery fails —
     * a credential minted here must never simply be lost.
     */
    @PostMapping("/{id}/approve")
    public ResponseEntity<?> approve(Authentication auth, @PathVariable String id) {
        if (!isAdmin(auth)) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Admin only"));
        }
        try {
            BranchRepApplicationService.ApprovalResult result = service.approve(id, auth.getName());
            Map<String, Object> resp = new HashMap<>();
            resp.put("success", true);
            resp.put("status", "approved");
            resp.put("repId", result.repId());
            resp.put("tempPassword", result.tempPassword());
            resp.put("emailedTo", result.emailedTo());
            return ResponseEntity.ok(resp);
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
    }

    /** Admin rejects. */
    @PostMapping("/{id}/reject")
    public ResponseEntity<?> reject(Authentication auth, @PathVariable String id) {
        if (!isAdmin(auth)) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Admin only"));
        }
        try {
            service.reject(id, auth.getName());
            return ResponseEntity.ok(Map.of("success", true, "status", "rejected"));
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
    }
}
