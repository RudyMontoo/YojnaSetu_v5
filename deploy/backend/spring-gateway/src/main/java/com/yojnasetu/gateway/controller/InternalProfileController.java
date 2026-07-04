package com.yojnasetu.gateway.controller;

import com.yojnasetu.gateway.model.AuditLog;
import com.yojnasetu.gateway.model.CitizenProfile;
import com.yojnasetu.gateway.model.Scheme;
import com.yojnasetu.gateway.repository.AuditLogRepository;
import com.yojnasetu.gateway.repository.CitizenProfileRepository;
import com.yojnasetu.gateway.repository.SchemeRepository;
import com.yojnasetu.gateway.service.CitizenProfileService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.util.Optional;

/**
 * Service-to-service endpoints for FastAPI (ai_service), per CLAUDE.md:
 * "FastAPI -> Spring Boot only, service JWT" — here that's a shared-secret
 * header (X-Internal-Key) rather than a citizen JWT, since these calls
 * aren't on behalf of a browser session. NOT reachable by the frontend —
 * SecurityConfig permits this path but every handler re-validates the key
 * itself so a SecurityConfig mistake can't silently open it up.
 */
@RestController
@RequestMapping("/internal")
public class InternalProfileController {

    private final CitizenProfileRepository citizenProfileRepository;
    private final CitizenProfileService citizenProfileService;
    private final SchemeRepository schemeRepository;
    private final AuditLogRepository auditLogRepository;

    @Value("${app.internal-service-key}")
    private String expectedInternalKey;

    public InternalProfileController(CitizenProfileRepository citizenProfileRepository,
                                      CitizenProfileService citizenProfileService,
                                      SchemeRepository schemeRepository,
                                      AuditLogRepository auditLogRepository) {
        this.citizenProfileRepository = citizenProfileRepository;
        this.citizenProfileService = citizenProfileService;
        this.schemeRepository = schemeRepository;
        this.auditLogRepository = auditLogRepository;
    }

    private boolean isAuthorized(String providedKey) {
        return providedKey != null && !expectedInternalKey.isBlank()
                && java.security.MessageDigest.isEqual(providedKey.getBytes(), expectedInternalKey.getBytes());
    }

    @GetMapping("/profile/{userId}")
    public ResponseEntity<?> getProfile(@PathVariable String userId,
                                         @RequestHeader(value = "X-Internal-Key", required = false) String key,
                                         HttpServletRequest req) {
        if (!isAuthorized(key)) return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Invalid internal key"));

        Optional<CitizenProfile> profile = citizenProfileService.findDecrypted(userId);
        auditLogRepository.save(AuditLog.of(userId, "profile_read", "/internal/profile/" + userId, clientIp(req)));
        return profile.<ResponseEntity<?>>map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "No profile for userId")));
    }

    @PatchMapping("/profile/{userId}")
    public ResponseEntity<?> patchProfile(@PathVariable String userId,
                                           @RequestBody Map<String, Object> updates,
                                           @RequestHeader(value = "X-Internal-Key", required = false) String key,
                                           HttpServletRequest req) {
        if (!isAuthorized(key)) return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Invalid internal key"));

        CitizenProfile profile = citizenProfileService.findDecrypted(userId).orElseGet(() -> {
            CitizenProfile p = new CitizenProfile();
            p.setUserId(userId);
            return p;
        });

        if (updates.containsKey("annualIncome")) profile.setAnnualIncome(((Number) updates.get("annualIncome")).longValue());
        if (updates.containsKey("state")) profile.setState((String) updates.get("state"));
        if (updates.containsKey("category")) profile.setCategory((String) updates.get("category"));
        if (updates.containsKey("occupation")) profile.setOccupation((String) updates.get("occupation"));
        if (updates.containsKey("gender")) profile.setGender((String) updates.get("gender"));
        if (updates.containsKey("district")) profile.setDistrict((String) updates.get("district"));
        if (updates.containsKey("isBpl")) profile.setIsBpl((Boolean) updates.get("isBpl"));
        if (updates.containsKey("isDisabled")) profile.setIsDisabled((Boolean) updates.get("isDisabled"));
        if (updates.containsKey("isRural")) profile.setIsRural((Boolean) updates.get("isRural"));
        if (updates.containsKey("familySize")) profile.setFamilySize(((Number) updates.get("familySize")).intValue());
        if (updates.containsKey("hasLand")) profile.setHasLand((Boolean) updates.get("hasLand"));
        if (updates.containsKey("landAreaAcres")) profile.setLandAreaAcres(((Number) updates.get("landAreaAcres")).doubleValue());

        CitizenProfile saved = citizenProfileService.saveEncrypted(profile);
        auditLogRepository.save(AuditLog.of(userId, "profile_write", "/internal/profile/" + userId, clientIp(req)));
        return ResponseEntity.ok(Map.of("success", true, "profileCompleteness", saved.getProfileCompleteness()));
    }

    @GetMapping("/scheme/{schemeCode}/rules")
    public ResponseEntity<?> getSchemeRules(@PathVariable String schemeCode,
                                             @RequestHeader(value = "X-Internal-Key", required = false) String key) {
        if (!isAuthorized(key)) return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Invalid internal key"));

        return schemeRepository.findBySchemeCode(schemeCode)
                .<ResponseEntity<?>>map(s -> ResponseEntity.ok(Map.of(
                        "schemeCode", s.getSchemeCode(),
                        "eligibilityRules", s.getEligibilityRules() != null ? s.getEligibilityRules() : Map.of())))
                .orElseGet(() -> ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "Scheme not found")));
    }

    private String clientIp(HttpServletRequest req) {
        String forwardedFor = req.getHeader("X-Forwarded-For");
        if (forwardedFor != null && !forwardedFor.isBlank()) return forwardedFor.split(",")[0].trim();
        return req.getRemoteAddr();
    }
}
