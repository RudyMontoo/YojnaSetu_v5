package com.yojnasetu.gateway.controller;

import com.yojnasetu.gateway.model.HelpRequest;
import com.yojnasetu.gateway.repository.HelpRequestRepository;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * Offline-help callback queue. A citizen files a request ("I need a person to
 * help me"); CSC operators see the queue, claim one, phone the citizen back,
 * and mark it resolved.
 *
 * Auth: every route needs a logged-in user (SecurityConfig authenticates
 * /api/v2/help/**). The operator-only routes additionally require the
 * ROLE_CSC_OPERATOR (or ROLE_ADMIN) authority — checked here in the controller,
 * since SecurityConfig only distinguishes public vs authenticated.
 */
@RestController
@RequestMapping("/api/v2/help")
public class HelpRequestController {

    private final HelpRequestRepository repo;

    public HelpRequestController(HelpRequestRepository repo) {
        this.repo = repo;
    }

    private static boolean isOperator(Authentication auth) {
        return auth.getAuthorities().stream().anyMatch(a ->
                a.getAuthority().equals("ROLE_HELPER")
                        || a.getAuthority().equals("ROLE_CSC_OPERATOR")
                        || a.getAuthority().equals("ROLE_ADMIN"));
    }

    public record CreateHelpRequest(String message, String phone, String citizenName,
                                    String schemeCode, String schemeName) {}

    /** Citizen files a callback request. */
    @PostMapping("/request")
    public ResponseEntity<?> create(Authentication auth, @RequestBody CreateHelpRequest req) {
        if (req.phone() == null || req.phone().isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "A callback phone number is required"));
        }
        HelpRequest hr = new HelpRequest();
        hr.setCitizenId(auth.getName());
        hr.setCitizenName(req.citizenName());
        hr.setPhone(req.phone().trim());
        hr.setMessage(req.message() != null ? req.message().trim() : "");
        hr.setSchemeCode(req.schemeCode());
        hr.setSchemeName(req.schemeName());
        hr.setStatus("waiting");
        hr.setCreatedAt(LocalDateTime.now());
        hr.setUpdatedAt(LocalDateTime.now());
        hr = repo.save(hr);
        return ResponseEntity.status(HttpStatus.CREATED).body(Map.of("success", true, "id", hr.getId(), "status", hr.getStatus()));
    }

    /** Citizen sees the status of their own requests. */
    @GetMapping("/my-requests")
    public ResponseEntity<?> mine(Authentication auth) {
        return ResponseEntity.ok(Map.of("requests", repo.findByCitizenIdOrderByCreatedAtDesc(auth.getName())));
    }

    /** Helper sees the requests they've claimed/resolved. */
    @GetMapping("/my-handled")
    public ResponseEntity<?> myHandled(Authentication auth) {
        if (!isOperator(auth)) return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Operator access only"));
        return ResponseEntity.ok(Map.of("requests", repo.findByAssignedOperatorIdOrderByUpdatedAtDesc(auth.getName())));
    }

    /** Operator queue: everything still open (waiting + assigned), oldest first. */
    @GetMapping("/requests")
    public ResponseEntity<?> queue(Authentication auth) {
        if (!isOperator(auth)) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Operator access only"));
        }
        return ResponseEntity.ok(Map.of("requests", repo.findByStatusInOrderByCreatedAtAsc(List.of("waiting", "assigned"))));
    }

    /** Operator claims a waiting request (assigns it to themselves). */
    @PostMapping("/requests/{id}/claim")
    public ResponseEntity<?> claim(Authentication auth, @PathVariable String id) {
        if (!isOperator(auth)) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Operator access only"));
        }
        return repo.findById(id).map(hr -> {
            hr.setStatus("assigned");
            hr.setAssignedOperatorId(auth.getName());
            hr.setUpdatedAt(LocalDateTime.now());
            repo.save(hr);
            return ResponseEntity.ok(Map.of("success", true, "status", hr.getStatus()));
        }).orElse(ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "Request not found")));
    }

    /** Operator marks a request resolved once they've helped the citizen. */
    @PostMapping("/requests/{id}/resolve")
    public ResponseEntity<?> resolve(Authentication auth, @PathVariable String id) {
        if (!isOperator(auth)) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Operator access only"));
        }
        return repo.findById(id).map(hr -> {
            hr.setStatus("resolved");
            hr.setUpdatedAt(LocalDateTime.now());
            repo.save(hr);
            return ResponseEntity.ok(Map.of("success", true, "status", hr.getStatus()));
        }).orElse(ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "Request not found")));
    }
}
