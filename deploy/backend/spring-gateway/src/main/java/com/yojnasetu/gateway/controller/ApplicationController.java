package com.yojnasetu.gateway.controller;

import com.yojnasetu.gateway.model.AuditLog;
import com.yojnasetu.gateway.model.Application;
import com.yojnasetu.gateway.model.CitizenProfile;
import com.yojnasetu.gateway.model.Scheme;
import com.yojnasetu.gateway.model.TrendEvent;
import com.yojnasetu.gateway.repository.ApplicationRepository;
import com.yojnasetu.gateway.repository.AuditLogRepository;
import com.yojnasetu.gateway.repository.CitizenProfileRepository;
import com.yojnasetu.gateway.repository.SchemeRepository;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Citizen-facing application tracking, per CLAUDE.md's
 * `GET/POST /applications` endpoint table entries. Same auth pattern as
 * ProfileController — the JWT principal name IS the userId, no separate
 * lookup. Every handler re-checks `application.userId.equals(auth.getName())`
 * before returning/mutating a document, since Mongo ids are guessable and
 * there's no per-document ACL at the repository layer.
 */
@RestController
@RequestMapping("/api/v2/applications")
public class ApplicationController {

    private static final Set<String> VALID_STATUSES =
            Set.of("saved", "in_progress", "submitted", "approved", "rejected", "disbursed");

    private final ApplicationRepository applicationRepository;
    private final SchemeRepository schemeRepository;
    private final AuditLogRepository auditLogRepository;
    private final CitizenProfileRepository citizenProfileRepository;
    private final MongoTemplate mongoTemplate;

    public ApplicationController(ApplicationRepository applicationRepository,
                                  SchemeRepository schemeRepository,
                                  AuditLogRepository auditLogRepository,
                                  CitizenProfileRepository citizenProfileRepository,
                                  MongoTemplate mongoTemplate) {
        this.applicationRepository = applicationRepository;
        this.schemeRepository = schemeRepository;
        this.auditLogRepository = auditLogRepository;
        this.citizenProfileRepository = citizenProfileRepository;
        this.mongoTemplate = mongoTemplate;
    }

    @GetMapping
    public ResponseEntity<?> list(Authentication auth, @RequestParam(required = false) String status) {
        String userId = auth.getName();
        List<Application> apps = (status == null || status.isBlank())
                ? applicationRepository.findByUserId(userId)
                : applicationRepository.findByUserIdAndStatus(userId, status);
        return ResponseEntity.ok(apps);
    }

    @GetMapping("/{id}")
    public ResponseEntity<?> get(Authentication auth, @PathVariable String id) {
        return applicationRepository.findById(id)
                .filter(a -> a.getUserId().equals(auth.getName()))
                .<ResponseEntity<?>>map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "Application not found")));
    }

    public record CreateApplicationRequest(String schemeCode) {}

    @PostMapping
    public ResponseEntity<?> create(Authentication auth, @RequestBody CreateApplicationRequest req, HttpServletRequest httpReq) {
        String userId = auth.getName();
        if (req.schemeCode() == null || req.schemeCode().isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "schemeCode is required"));
        }

        Scheme scheme = schemeRepository.findBySchemeCode(req.schemeCode()).orElse(null);
        if (scheme == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "Unknown schemeCode: " + req.schemeCode()));
        }

        Application app = new Application();
        app.setUserId(userId);
        app.setSchemeId(scheme.getId());
        app.setSchemeCode(scheme.getSchemeCode());
        app.setSchemeName(scheme.getName());
        app.setStatus("saved");
        app.setStatusHistory(List.of(new Application.StatusEntry("saved", LocalDateTime.now())));
        app.setAppliedAt(LocalDateTime.now());

        Application saved;
        try {
            saved = applicationRepository.save(app);
        } catch (DuplicateKeyException e) {
            // user_scheme_unique compound index — this citizen already has an application for this scheme
            return ResponseEntity.status(HttpStatus.CONFLICT).body(Map.of("error", "Application already exists for this scheme"));
        }

        auditLogRepository.save(AuditLog.of(userId, "application_created", "/api/v2/applications", clientIp(httpReq)));

        // trend_events "save" signal (CLAUDE.md) — best-effort, analytics must
        // never fail an application create. user_state comes from the citizen's
        // profile (state is stored unencrypted, no decrypt needed).
        try {
            String userState = citizenProfileRepository.findByUserId(userId)
                    .map(CitizenProfile::getState).orElse(null);
            mongoTemplate.insert(TrendEvent.of(scheme.getSchemeCode(), scheme.getName(), "save", userState));
        } catch (Exception e) {
            System.err.println("trend_events save-event insert failed (non-fatal): " + e.getMessage());
        }

        return ResponseEntity.status(HttpStatus.CREATED).body(saved);
    }

    public record UpdateStatusRequest(String status, String externalAppId) {}

    @PatchMapping("/{id}")
    public ResponseEntity<?> updateStatus(Authentication auth, @PathVariable String id,
                                           @RequestBody UpdateStatusRequest req, HttpServletRequest httpReq) {
        if (req.status() == null || !VALID_STATUSES.contains(req.status())) {
            return ResponseEntity.badRequest().body(Map.of("error", "status must be one of " + VALID_STATUSES));
        }

        Application app = applicationRepository.findById(id).orElse(null);
        if (app == null || !app.getUserId().equals(auth.getName())) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "Application not found"));
        }

        app.setStatus(req.status());
        app.getStatusHistory().add(new Application.StatusEntry(req.status(), LocalDateTime.now()));
        if (req.externalAppId() != null && !req.externalAppId().isBlank()) {
            app.setExternalAppId(req.externalAppId());
        }
        app.setLastStatusCheck(LocalDateTime.now());

        Application saved = applicationRepository.save(app);
        auditLogRepository.save(AuditLog.of(auth.getName(), "application_status_update", "/api/v2/applications/" + id, clientIp(httpReq)));
        return ResponseEntity.ok(saved);
    }

    private String clientIp(HttpServletRequest req) {
        String forwardedFor = req.getHeader("X-Forwarded-For");
        if (forwardedFor != null && !forwardedFor.isBlank()) return forwardedFor.split(",")[0].trim();
        return req.getRemoteAddr();
    }
}
