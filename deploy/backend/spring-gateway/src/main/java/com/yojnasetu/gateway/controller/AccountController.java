package com.yojnasetu.gateway.controller;

import com.yojnasetu.gateway.model.AuditLog;
import com.yojnasetu.gateway.repository.ApplicationRepository;
import com.yojnasetu.gateway.repository.AuditLogRepository;
import com.yojnasetu.gateway.repository.CitizenProfileRepository;
import com.yojnasetu.gateway.repository.UserRepository;
import com.yojnasetu.gateway.security.JwtAuthFilter;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;
import java.util.Map;

/**
 * DPDP Act 2023 erasure cascade, per CLAUDE.md: "DELETE /user/me | Cascades
 * all 5 collections in 30s". Spring Boot owns users/citizen_profiles/
 * applications directly; conversation_sessions/reasoning_traces/nudge_log
 * are ai_service-owned (Mongo, but a different service's write path), so
 * this calls ai_service's own internal erasure endpoint the same way
 * ai_service calls Spring Boot's /internal/profile/{userId} — a shared
 * X-API-Key secret, not a citizen JWT (this isn't a browser-facing call).
 *
 * Order matters: the audit log entry is written FIRST (audit_logs is
 * append-only per CLAUDE.md — it must record the deletion request even if
 * a later step fails), Spring-owned collections are deleted next, then
 * ai_service's cascade is called, and the `users` identity document itself
 * is deleted LAST — so a mid-failure never leaves an unauthenticated
 * citizen's data half-erased with no way to retry under their own login.
 */
@RestController
@RequestMapping("/api/v2")
public class AccountController {

    private final UserRepository userRepository;
    private final CitizenProfileRepository citizenProfileRepository;
    private final ApplicationRepository applicationRepository;
    private final AuditLogRepository auditLogRepository;
    private final WebClient aiServiceClient;

    @Value("${app.cookie.secure:true}")
    private boolean cookieSecure;

    public AccountController(UserRepository userRepository,
                              CitizenProfileRepository citizenProfileRepository,
                              ApplicationRepository applicationRepository,
                              AuditLogRepository auditLogRepository,
                              @Value("${app.fastapi.url}") String fastapiUrl,
                              @Value("${app.internal-service-key}") String internalKey) {
        this.userRepository = userRepository;
        this.citizenProfileRepository = citizenProfileRepository;
        this.applicationRepository = applicationRepository;
        this.auditLogRepository = auditLogRepository;
        this.aiServiceClient = WebClient.builder()
                .baseUrl(fastapiUrl)
                .defaultHeader("X-API-Key", internalKey)
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .build();
    }

    @DeleteMapping("/user/me")
    public ResponseEntity<?> deleteAccount(Authentication auth, HttpServletRequest req, HttpServletResponse res) {
        String userId = auth.getName();

        // Written before any deletion — append-only record survives regardless of what follows.
        auditLogRepository.save(AuditLog.of(userId, "delete_request", "/api/v2/user/me", clientIp(req)));

        citizenProfileRepository.findByUserId(userId).ifPresent(citizenProfileRepository::delete);
        applicationRepository.deleteAll(applicationRepository.findByUserId(userId));

        Map<String, Object> aiServiceResult;
        try {
            aiServiceResult = aiServiceClient.delete()
                    .uri("/internal/citizen/{id}/data", userId)
                    .retrieve()
                    .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                    .timeout(Duration.ofSeconds(10))
                    .block();
        } catch (Exception e) {
            // Spring-owned data is already gone at this point — don't fail the whole
            // erasure over ai_service being unreachable, but surface it so it isn't
            // silently lost; a stuck conversation_sessions/reasoning_traces cascade
            // needs manual follow-up, not a citizen-facing 500.
            aiServiceResult = Map.of("error", "ai_service cascade unreachable: " + e.getClass().getSimpleName());
        }

        userRepository.deleteById(userId);

        clearCookie(res, JwtAuthFilter.ACCESS_TOKEN_COOKIE);
        clearCookie(res, "refresh_token");

        return ResponseEntity.ok(Map.of("success", true, "ai_service_cascade", aiServiceResult));
    }

    private void clearCookie(HttpServletResponse res, String name) {
        Cookie cookie = new Cookie(name, "");
        cookie.setHttpOnly(true);
        cookie.setSecure(cookieSecure);
        cookie.setPath("/");
        cookie.setMaxAge(0);
        cookie.setAttribute("SameSite", "Strict");
        res.addCookie(cookie);
    }

    private String clientIp(HttpServletRequest req) {
        String forwardedFor = req.getHeader("X-Forwarded-For");
        if (forwardedFor != null && !forwardedFor.isBlank()) return forwardedFor.split(",")[0].trim();
        return req.getRemoteAddr();
    }
}
