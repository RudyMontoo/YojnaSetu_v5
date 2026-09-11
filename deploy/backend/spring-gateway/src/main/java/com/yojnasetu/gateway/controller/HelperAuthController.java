package com.yojnasetu.gateway.controller;

import com.yojnasetu.gateway.model.Helper;
import com.yojnasetu.gateway.repository.HelperRepository;
import com.yojnasetu.gateway.security.FieldEncryptionService;
import com.yojnasetu.gateway.security.JwtAuthFilter;
import com.yojnasetu.gateway.security.JwtUtils;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * Login for the SEPARATE helper portal. Helpers authenticate with an
 * admin-issued helperId + password (no OTP), and receive the same httpOnly JWT
 * cookies as citizens but with role HELPER — so the JwtAuthFilter gates helper
 * routes via ROLE_HELPER.
 */
@RestController
@RequestMapping("/api/v2/helper-portal")
public class HelperAuthController {

    private static final String REFRESH_TOKEN_COOKIE = "refresh_token";

    private final HelperRepository helperRepository;
    private final JwtUtils jwtUtils;
    private final FieldEncryptionService encryption;
    private final BCryptPasswordEncoder passwordEncoder = new BCryptPasswordEncoder();

    @Value("${app.cookie.secure:true}")
    private boolean cookieSecure;

    public HelperAuthController(HelperRepository helperRepository, JwtUtils jwtUtils, FieldEncryptionService encryption) {
        this.helperRepository = helperRepository;
        this.jwtUtils = jwtUtils;
        this.encryption = encryption;
    }

    public record LoginRequest(String helperId, String password) {}

    @PostMapping("/login")
    public ResponseEntity<?> login(@RequestBody LoginRequest req, HttpServletResponse res) {
        if (req.helperId() == null || req.password() == null) {
            return ResponseEntity.badRequest().body(Map.of("error", "helperId and password are required"));
        }
        Helper helper = helperRepository.findByHelperId(req.helperId().trim()).orElse(null);
        if (helper == null || !helper.isActive() || !passwordEncoder.matches(req.password(), helper.getPasswordHash())) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(Map.of("error", "Invalid helper ID or password"));
        }
        helper.setLastLoginAt(LocalDateTime.now());
        helperRepository.save(helper);

        setCookie(res, JwtAuthFilter.ACCESS_TOKEN_COOKIE, jwtUtils.generateAccessToken(helper.getId(), "HELPER"),
                (int) jwtUtils.getAccessTokenExpirySeconds());
        setCookie(res, REFRESH_TOKEN_COOKIE, jwtUtils.generateRefreshToken(helper.getId()),
                (int) jwtUtils.getRefreshTokenExpirySeconds());

        return ResponseEntity.ok(Map.of("success", true,
                "mustResetPassword", helper.isMustResetPassword(),
                "helper", Map.of("id", helper.getId(), "helperId", helper.getHelperId(),
                        "name", encryption.decrypt(helper.getName()), "available", helper.isAvailable())));
    }

    public record ChangePasswordRequest(String currentPassword, String newPassword) {}

    /** Helper changes their password (forced on first login, or any time after). */
    @PostMapping("/change-password")
    public ResponseEntity<?> changePassword(Authentication auth, @RequestBody ChangePasswordRequest req) {
        Helper helper = helperRepository.findById(auth.getName()).orElse(null);
        if (helper == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(Map.of("error", "Not a helper session"));
        }
        if (req.currentPassword() == null || !passwordEncoder.matches(req.currentPassword(), helper.getPasswordHash())) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(Map.of("error", "Current password is incorrect"));
        }
        if (req.newPassword() == null || req.newPassword().length() < 6) {
            return ResponseEntity.badRequest().body(Map.of("error", "New password must be at least 6 characters"));
        }
        helper.setPasswordHash(passwordEncoder.encode(req.newPassword()));
        helper.setMustResetPassword(false);
        helperRepository.save(helper);
        return ResponseEntity.ok(Map.of("success", true));
    }

    @GetMapping("/me")
    public ResponseEntity<?> me(Authentication auth) {
        return helperRepository.findById(auth.getName())
                .<ResponseEntity<?>>map(h -> ResponseEntity.ok(Map.of("id", h.getId(), "helperId", h.getHelperId(),
                        "name", encryption.decrypt(h.getName()), "available", h.isAvailable())))
                .orElse(ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(Map.of("error", "Not a helper session")));
    }

    public record AvailabilityRequest(boolean available) {}

    /** Helper toggles their own on-duty / away status. */
    @PostMapping("/availability")
    public ResponseEntity<?> availability(Authentication auth, @RequestBody AvailabilityRequest req) {
        return helperRepository.findById(auth.getName()).<ResponseEntity<?>>map(h -> {
            h.setAvailable(req.available());
            helperRepository.save(h);
            return ResponseEntity.ok(Map.of("success", true, "available", h.isAvailable()));
        }).orElse(ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(Map.of("error", "Not a helper session")));
    }

    @PostMapping("/logout")
    public ResponseEntity<?> logout(HttpServletResponse res) {
        setCookie(res, JwtAuthFilter.ACCESS_TOKEN_COOKIE, "", 0);
        setCookie(res, REFRESH_TOKEN_COOKIE, "", 0);
        return ResponseEntity.ok(Map.of("success", true));
    }

    private void setCookie(HttpServletResponse res, String name, String value, int maxAgeSeconds) {
        Cookie cookie = new Cookie(name, value);
        cookie.setHttpOnly(true);
        cookie.setSecure(cookieSecure);
        cookie.setPath("/");
        cookie.setMaxAge(maxAgeSeconds);
        // SameSite=None only when cookieSecure (https) — see AuthController.setCookie
        // for why Strict silently breaks cross-site auth. Lax over local http is
        // functionally identical to Strict for API fetch/XHR calls.
        cookie.setAttribute("SameSite", cookieSecure ? "None" : "Lax");
        res.addCookie(cookie);
    }
}
