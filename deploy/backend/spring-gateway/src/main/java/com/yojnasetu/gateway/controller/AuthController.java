package com.yojnasetu.gateway.controller;

import com.yojnasetu.gateway.util.ClientIp;
import com.yojnasetu.gateway.model.AuditLog;
import com.yojnasetu.gateway.model.User;
import com.yojnasetu.gateway.repository.AuditLogRepository;
import com.yojnasetu.gateway.repository.UserRepository;
import com.yojnasetu.gateway.security.JwtAuthFilter;
import com.yojnasetu.gateway.security.JwtUtils;
import com.yojnasetu.gateway.service.FirebaseTokenService;
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
    private final FirebaseTokenService firebaseTokenService;

    @Value("${app.cookie.secure:true}")
    private boolean cookieSecure;

    public AuthController(OtpService otpService, UserRepository userRepository,
                           AuditLogRepository auditLogRepository, JwtUtils jwtUtils,
                           FirebaseTokenService firebaseTokenService) {
        this.otpService = otpService;
        this.userRepository = userRepository;
        this.auditLogRepository = auditLogRepository;
        this.jwtUtils = jwtUtils;
        this.firebaseTokenService = firebaseTokenService;
    }

    // Exactly one of phone / email is required (validated in resolveTarget).
    public record OtpSendRequest(String phone, String email) {}
    public record OtpVerifyRequest(String phone, String email, String otp) {}

    private static final java.util.regex.Pattern PHONE_RE =
            java.util.regex.Pattern.compile("^\\+[1-9]\\d{9,14}$");
    private static final java.util.regex.Pattern EMAIL_RE =
            java.util.regex.Pattern.compile("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$");

    private record Target(String identifier, OtpService.Channel channel) {}

    /** Resolve the request to a single (identifier, channel), or null if neither,
     *  both, or an invalid value was supplied. */
    private Target resolveTarget(String phone, String email) {
        boolean hasPhone = phone != null && !phone.isBlank();
        boolean hasEmail = email != null && !email.isBlank();
        if (hasPhone == hasEmail) return null;                 // need exactly one
        if (hasPhone) {
            String p = phone.trim();
            return PHONE_RE.matcher(p).matches() ? new Target(p, OtpService.Channel.SMS) : null;
        }
        String e = email.trim().toLowerCase();
        return EMAIL_RE.matcher(e).matches() ? new Target(e, OtpService.Channel.EMAIL) : null;
    }

    @PostMapping("/otp/send")
    public ResponseEntity<?> sendOtp(@RequestBody OtpSendRequest req, HttpServletRequest httpReq) {
        Target t = resolveTarget(req.phone(), req.email());
        if (t == null) return ResponseEntity.badRequest()
                .body(Map.of("error", "Provide a valid phone (E.164, e.g. +919876543210) or email"));
        try {
            otpService.generateAndSend(t.identifier(), t.channel());
        } catch (OtpService.OtpRateLimitException e) {
            auditLogRepository.save(AuditLog.of(null, "otp_send_throttled", "/api/v2/auth/otp/send", clientIp(httpReq)));
            return ResponseEntity.status(429).body(Map.of("error", e.getMessage()));
        }
        auditLogRepository.save(AuditLog.of(null, "otp_send", "/api/v2/auth/otp/send", clientIp(httpReq)));
        return ResponseEntity.ok(Map.of("success", true, "expires_in", 600));
    }

    @PostMapping("/otp/verify")
    public ResponseEntity<?> verifyOtp(@RequestBody OtpVerifyRequest req, HttpServletRequest httpReq, HttpServletResponse res) {
        Target t = resolveTarget(req.phone(), req.email());
        if (t == null || req.otp() == null || req.otp().isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "Provide phone/email and the OTP"));
        }
        OtpService.VerifyResult result = otpService.verify(t.identifier(), req.otp());

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
                boolean isEmail = t.channel() == OtpService.Channel.EMAIL;
                User user = (isEmail ? userRepository.findByEmail(t.identifier())
                                     : userRepository.findByPhone(t.identifier()))
                        .orElseGet(() -> {
                            User u = new User();
                            if (isEmail) u.setEmail(t.identifier()); else u.setPhone(t.identifier());
                            u.setCreatedAt(LocalDateTime.now());
                            return u;
                        });
                user.setLastLoginAt(LocalDateTime.now());
                user = userRepository.save(user);

                issueCookies(res, user);
                auditLogRepository.save(AuditLog.of(user.getId(), "otp_verify_success", "/api/v2/auth/otp/verify", clientIp(httpReq)));

                // HashMap (not Map.of) — phone/email may be null and Map.of rejects nulls.
                Map<String, Object> userInfo = new java.util.HashMap<>();
                userInfo.put("id", user.getId());
                userInfo.put("phone", user.getPhone());
                userInfo.put("email", user.getEmail());
                userInfo.put("role", user.getRole());
                userInfo.put("language", user.getLanguage() != null ? user.getLanguage() : "hi");
                yield ResponseEntity.ok(Map.of("success", true, "user", userInfo));
            }
        };
    }

    public record PhoneVerifyRequest(String idToken) {}

    /**
     * Phone login via Firebase. The browser did the SMS-OTP with Firebase (Google
     * sends the code), then hands us the resulting ID token. We verify it, read the
     * proven phone number, and issue the SAME session cookies as email OTP — so the
     * rest of the app doesn't care which channel logged the citizen in.
     */
    @PostMapping("/phone/verify")
    public ResponseEntity<?> verifyPhone(@RequestBody PhoneVerifyRequest req,
                                         HttpServletRequest httpReq, HttpServletResponse res) {
        if (!firebaseTokenService.isEnabled()) {
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                    .body(Map.of("error", "Phone login isn't available right now — please use email."));
        }
        String phone = firebaseTokenService.verifiedPhone(req == null ? null : req.idToken());
        if (phone == null) {
            auditLogRepository.save(AuditLog.of(null, "phone_verify_fail", "/api/v2/auth/phone/verify", clientIp(httpReq)));
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(Map.of("error", "Phone verification failed"));
        }

        User user = userRepository.findByPhone(phone).orElseGet(() -> {
            User u = new User();
            u.setPhone(phone);
            u.setCreatedAt(LocalDateTime.now());
            return u;
        });
        user.setLastLoginAt(LocalDateTime.now());
        user = userRepository.save(user);

        issueCookies(res, user);
        auditLogRepository.save(AuditLog.of(user.getId(), "phone_verify_success", "/api/v2/auth/phone/verify", clientIp(httpReq)));

        Map<String, Object> userInfo = new java.util.HashMap<>();
        userInfo.put("id", user.getId());
        userInfo.put("phone", user.getPhone());
        userInfo.put("email", user.getEmail());
        userInfo.put("role", user.getRole());
        userInfo.put("language", user.getLanguage() != null ? user.getLanguage() : "hi");
        return ResponseEntity.ok(Map.of("success", true, "user", userInfo));
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
        return ClientIp.of(req);
    }
}
