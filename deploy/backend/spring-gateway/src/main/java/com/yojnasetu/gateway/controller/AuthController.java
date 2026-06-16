package com.yojnasetu.gateway.controller;

import com.yojnasetu.gateway.model.AuditLog;
import com.yojnasetu.gateway.model.User;
import com.yojnasetu.gateway.repository.AuditLogRepository;
import com.yojnasetu.gateway.repository.UserRepository;
import com.yojnasetu.gateway.security.JwtAuthFilter;
import com.yojnasetu.gateway.security.JwtUtils;
import com.yojnasetu.gateway.service.OtpService;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * OTP-first auth per ADR-001 / docs/PRANJAL_HANDOFF.md — replaces the old
 * username+password AuthController entirely, not incrementally. JWT is set
 * as httpOnly cookies only; the response body never contains a token.
 */
@RestController
@RequestMapping("/api/v2/auth")
public class AuthController {

    private static final String REFRESH_TOKEN_COOKIE = "refresh_token";

    private final OtpService otpService;
    private final UserRepository userRepository;
    private final AuditLogRepository auditLogRepository;
    private final JwtUtils jwtUtils;

    @Value("${app.cookie.secure:true}")
    private boolean cookieSecure;

    public AuthController(OtpService otpService, UserRepository userRepository,
                           AuditLogRepository auditLogRepository, JwtUtils jwtUtils) {
        this.otpService = otpService;
        this.userRepository = userRepository;
        this.auditLogRepository = auditLogRepository;
        this.jwtUtils = jwtUtils;
    }

    public record OtpSendRequest(
            @NotBlank @Pattern(regexp = "^\\+[1-9]\\d{9,14}$", message = "phone must be E.164 format e.g. +919876543210")
            String phone) {}

    public record OtpVerifyRequest(@NotBlank String phone, @NotBlank String otp) {}

    @PostMapping("/otp/send")
    public ResponseEntity<?> sendOtp(@Valid @RequestBody OtpSendRequest req, HttpServletRequest httpReq) {
        otpService.generateAndSend(req.phone());
        auditLogRepository.save(AuditLog.of(null, "otp_send", "/api/v2/auth/otp/send", clientIp(httpReq)));
        return ResponseEntity.ok(Map.of("success", true, "expires_in", 600));
    }

    @PostMapping("/otp/verify")
    public ResponseEntity<?> verifyOtp(@Valid @RequestBody OtpVerifyRequest req, HttpServletRequest httpReq, HttpServletResponse res) {
        OtpService.VerifyResult result = otpService.verify(req.phone(), req.otp());

        if (result == OtpService.VerifyResult.WRONG_OTP || result == OtpService.VerifyResult.LOCKED) {
            auditLogRepository.save(AuditLog.of(null, "otp_verify_fail", "/api/v2/auth/otp/verify", clientIp(httpReq)));
        }

        return switch (result) {
            case EXPIRED_OR_NOT_FOUND -> ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(Map.of("error", "OTP expired or not requested"));
            case WRONG_OTP -> ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(Map.of("error", "Incorrect OTP"));
            case LOCKED -> ResponseEntity.status(HttpStatus.TOO_MANY_REQUESTS)
                    .body(Map.of("error", "Too many failed attempts — request a new OTP"));
            case SUCCESS -> {
                User user = userRepository.findByPhone(req.phone()).orElseGet(() -> {
                    User u = new User();
                    u.setPhone(req.phone());
                    u.setCreatedAt(LocalDateTime.now());
                    return u;
                });
                user.setLastLoginAt(LocalDateTime.now());
                user = userRepository.save(user);

                issueCookies(res, user);
                auditLogRepository.save(AuditLog.of(user.getId(), "otp_verify_success", "/api/v2/auth/otp/verify", clientIp(httpReq)));

                yield ResponseEntity.ok(Map.of(
                        "success", true,
                        "user", Map.of("id", user.getId(), "phone", user.getPhone(),
                                "role", user.getRole(), "language", user.getLanguage() != null ? user.getLanguage() : "hi")
                ));
            }
        };
    }

    @PostMapping("/refresh")
    public ResponseEntity<?> refresh(HttpServletRequest req, HttpServletResponse res) {
        String refreshToken = extractCookie(req, REFRESH_TOKEN_COOKIE);
        if (refreshToken == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(Map.of("error", "No refresh token"));
        }
        String userId = jwtUtils.validateAndGetUserId(refreshToken, "refresh");
        if (userId == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(Map.of("error", "Invalid or expired refresh token"));
        }
        User user = userRepository.findById(userId).orElse(null);
        if (user == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(Map.of("error", "User not found"));
        }
        setCookie(res, JwtAuthFilter.ACCESS_TOKEN_COOKIE, jwtUtils.generateAccessToken(user.getId(), user.getRole()),
                (int) jwtUtils.getAccessTokenExpirySeconds());
        return ResponseEntity.ok(Map.of("success", true));
    }

    @PostMapping("/logout")
    public ResponseEntity<?> logout(HttpServletResponse res) {
        setCookie(res, JwtAuthFilter.ACCESS_TOKEN_COOKIE, "", 0);
        setCookie(res, REFRESH_TOKEN_COOKIE, "", 0);
        return ResponseEntity.ok(Map.of("success", true));
    }

    private void issueCookies(HttpServletResponse res, User user) {
        setCookie(res, JwtAuthFilter.ACCESS_TOKEN_COOKIE, jwtUtils.generateAccessToken(user.getId(), user.getRole()),
                (int) jwtUtils.getAccessTokenExpirySeconds());
        setCookie(res, REFRESH_TOKEN_COOKIE, jwtUtils.generateRefreshToken(user.getId()),
                (int) jwtUtils.getRefreshTokenExpirySeconds());
    }

    private void setCookie(HttpServletResponse res, String name, String value, int maxAgeSeconds) {
        Cookie cookie = new Cookie(name, value);
        cookie.setHttpOnly(true);
        cookie.setSecure(cookieSecure);
        cookie.setPath("/");
        cookie.setMaxAge(maxAgeSeconds);
        cookie.setAttribute("SameSite", "Strict");
        res.addCookie(cookie);
    }

    private String extractCookie(HttpServletRequest req, String name) {
        if (req.getCookies() == null) return null;
        for (Cookie c : req.getCookies()) {
            if (name.equals(c.getName())) return c.getValue();
        }
        return null;
    }

    private String clientIp(HttpServletRequest req) {
        String forwardedFor = req.getHeader("X-Forwarded-For");
        if (forwardedFor != null && !forwardedFor.isBlank()) return forwardedFor.split(",")[0].trim();
        return req.getRemoteAddr();
    }
}
