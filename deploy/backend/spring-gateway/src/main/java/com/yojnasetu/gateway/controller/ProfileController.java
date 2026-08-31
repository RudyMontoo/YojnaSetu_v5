package com.yojnasetu.gateway.controller;

import com.yojnasetu.gateway.util.ClientIp;
import com.yojnasetu.gateway.model.AuditLog;
import com.yojnasetu.gateway.model.CitizenProfile;
import com.yojnasetu.gateway.repository.AuditLogRepository;
import com.yojnasetu.gateway.repository.CitizenProfileRepository;
import com.yojnasetu.gateway.service.CitizenProfileService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.ByteArrayInputStream;
import java.time.LocalDateTime;
import java.util.Base64;
import java.util.Map;

/**
 * Citizen-facing profile endpoints. Authentication comes from JwtAuthFilter
 * — the principal name IS the userId (see JwtAuthFilter), there's no
 * separate username lookup anymore.
 */
@RestController
@RequestMapping("/api/v2")
public class ProfileController {

    private final CitizenProfileRepository citizenProfileRepository;
    private final CitizenProfileService citizenProfileService;
    private final AuditLogRepository auditLogRepository;

    public ProfileController(CitizenProfileRepository citizenProfileRepository,
                              CitizenProfileService citizenProfileService,
                              AuditLogRepository auditLogRepository) {
        this.citizenProfileRepository = citizenProfileRepository;
        this.citizenProfileService = citizenProfileService;
        this.auditLogRepository = auditLogRepository;
    }

    @PostMapping("/consent")
    public ResponseEntity<?> giveConsent(Authentication auth) {
        String userId = auth.getName();
        CitizenProfile profile = citizenProfileRepository.findByUserId(userId).orElseGet(() -> {
            CitizenProfile p = new CitizenProfile();
            p.setUserId(userId);
            return p;
        });
        profile.setConsentGivenAt(LocalDateTime.now());
        citizenProfileRepository.save(profile);
        auditLogRepository.save(AuditLog.of(userId, "consent_given", "/api/v2/consent", null));
        return ResponseEntity.ok(Map.of("success", true));
    }

    @GetMapping("/profile/me")
    public ResponseEntity<?> getProfile(Authentication auth, HttpServletRequest req) {
        String userId = auth.getName();
        CitizenProfile profile = citizenProfileService.findDecrypted(userId).orElse(null);
        auditLogRepository.save(AuditLog.of(userId, "profile_read", "/api/v2/profile/me", clientIp(req)));
        if (profile == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "Profile not created yet — call POST /consent first"));
        }
        return ResponseEntity.ok(profile);
    }

    @PatchMapping("/profile/me")
    public ResponseEntity<?> updateProfile(Authentication auth, @RequestBody Map<String, Object> updates, HttpServletRequest req) {
        String userId = auth.getName();
        CitizenProfile profile = citizenProfileService.findDecrypted(userId).orElse(null);
        if (profile == null) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN)
                    .body(Map.of("error", "Consent required before first profile write — call POST /consent first"));
        }

        applyUpdates(profile, updates);
        CitizenProfile saved = citizenProfileService.saveEncrypted(profile);
        auditLogRepository.save(AuditLog.of(userId, "profile_write", "/api/v2/profile/me", clientIp(req)));
        return ResponseEntity.ok(saved);
    }

    // Frontend resizes to ~480px JPEG before upload (typically tens of KB) — 3MB
    // was a needlessly generous backstop for an avatar-sized image, wasting
    // bandwidth and ImageIO-decode CPU on anything exploiting the gap between
    // what the UI actually sends and what the API would accept.
    private static final long MAX_PHOTO_BYTES = 800 * 1024; // 800KB
    private static final int MAX_PHOTO_DIMENSION = 512;          // avatar use only, no reason to keep anything larger

    @PostMapping(value = "/profile/me/photo", consumes = "multipart/form-data")
    public ResponseEntity<?> uploadProfilePhoto(Authentication auth, @RequestParam("photo") MultipartFile photo,
                                                 HttpServletRequest req) {
        String userId = auth.getName();
        CitizenProfile profile = citizenProfileService.findDecrypted(userId).orElse(null);
        if (profile == null) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN)
                    .body(Map.of("error", "Consent required before first profile write — call POST /consent first"));
        }
        if (photo.isEmpty()) {
            return ResponseEntity.badRequest().body(Map.of("error", "No file received"));
        }
        if (photo.getSize() > MAX_PHOTO_BYTES) {
            return ResponseEntity.badRequest().body(Map.of("error", "Photo exceeds 800KB limit"));
        }

        byte[] bytes;
        BufferedImage image;
        try {
            bytes = photo.getBytes();
            // ImageIO.read() decodes actual pixel data — unlike trusting the
            // Content-Type header, a non-image file (or a renamed .exe) fails
            // here rather than getting stored as someone's avatar.
            image = ImageIO.read(new ByteArrayInputStream(bytes));
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(Map.of("error", "Could not read uploaded file"));
        }
        if (image == null) {
            return ResponseEntity.badRequest().body(Map.of("error", "File is not a valid image"));
        }
        if (image.getWidth() > MAX_PHOTO_DIMENSION || image.getHeight() > MAX_PHOTO_DIMENSION) {
            return ResponseEntity.badRequest().body(Map.of(
                    "error", "Image too large — please crop to " + MAX_PHOTO_DIMENSION + "x" + MAX_PHOTO_DIMENSION + " or smaller"));
        }

        String mime = photo.getContentType() != null && photo.getContentType().startsWith("image/")
                ? photo.getContentType() : "image/jpeg";
        String dataUri = "data:" + mime + ";base64," + Base64.getEncoder().encodeToString(bytes);
        profile.setProfilePhoto(dataUri);
        CitizenProfile saved = citizenProfileService.saveEncrypted(profile);
        auditLogRepository.save(AuditLog.of(userId, "profile_photo_write", "/api/v2/profile/me/photo", clientIp(req)));
        return ResponseEntity.ok(Map.of("profilePhoto", saved.getProfilePhoto()));
    }

    @DeleteMapping("/profile/me/photo")
    public ResponseEntity<?> deleteProfilePhoto(Authentication auth, HttpServletRequest req) {
        String userId = auth.getName();
        CitizenProfile profile = citizenProfileService.findDecrypted(userId).orElse(null);
        if (profile == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "Profile not found"));
        }
        profile.setProfilePhoto(null);
        citizenProfileService.saveEncrypted(profile);
        auditLogRepository.save(AuditLog.of(userId, "profile_photo_delete", "/api/v2/profile/me/photo", clientIp(req)));
        return ResponseEntity.ok(Map.of("success", true));
    }

    // Partial update from a generic map — mirrors the old ProfileController's approach,
    // deliberately not a strict DTO so the frontend can send whichever subset of fields it has.
    private void applyUpdates(CitizenProfile p, Map<String, Object> u) {
        if (u.containsKey("name")) p.setName((String) u.get("name"));
        if (u.containsKey("dob")) p.setDob((String) u.get("dob"));
        if (u.containsKey("phone")) p.setPhone((String) u.get("phone"));
        if (u.containsKey("gender")) p.setGender((String) u.get("gender"));
        if (u.containsKey("annualIncome")) p.setAnnualIncome(toLong(u.get("annualIncome")));
        if (u.containsKey("category")) p.setCategory((String) u.get("category"));
        if (u.containsKey("occupation")) p.setOccupation((String) u.get("occupation"));
        if (u.containsKey("isBpl")) p.setIsBpl((Boolean) u.get("isBpl"));
        if (u.containsKey("isDisabled")) p.setIsDisabled((Boolean) u.get("isDisabled"));
        if (u.containsKey("disabilityPct")) p.setDisabilityPct(toInt(u.get("disabilityPct")));
        if (u.containsKey("state")) p.setState((String) u.get("state"));
        if (u.containsKey("district")) p.setDistrict((String) u.get("district"));
        if (u.containsKey("isRural")) p.setIsRural((Boolean) u.get("isRural"));
        if (u.containsKey("familySize")) p.setFamilySize(toInt(u.get("familySize")));
        if (u.containsKey("hasLand")) p.setHasLand((Boolean) u.get("hasLand"));
        if (u.containsKey("landAreaAcres")) p.setLandAreaAcres(u.get("landAreaAcres") == null ? null : ((Number) u.get("landAreaAcres")).doubleValue());
        if (u.containsKey("bankIfsc")) p.setBankIfsc((String) u.get("bankIfsc"));
        if (u.containsKey("pensionEnrolled")) p.setPensionEnrolled((Boolean) u.get("pensionEnrolled"));
        if (u.containsKey("pensionType")) p.setPensionType((String) u.get("pensionType"));
    }

    private Long toLong(Object o) { return o == null ? null : ((Number) o).longValue(); }
    private Integer toInt(Object o) { return o == null ? null : ((Number) o).intValue(); }

    private String clientIp(HttpServletRequest req) {
        return ClientIp.of(req);
    }
}
