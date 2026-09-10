package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.security.JwtAuthFilter;
import com.yojnasetu.gateway.security.JwtUtils;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

/**
 * Login for Channel Partner branch representatives.
 *
 * Mirrors the helper portal: an admin-issued repId and password rather than
 * OTP, since reps are staff at a partner institution and do not necessarily
 * have a phone we control. Issues the same httpOnly JWT cookies as every other
 * principal, with role BRANCH_REP, which is what
 * {@code /api/v2/branch/**} already gates on in SecurityConfig.
 *
 * The JWT subject is the rep's document id, matching the Helper convention —
 * and matching what NotificationRecipient.Resolver looks up, so a rep can be
 * both authenticated and messaged by the same identifier.
 */
@RestController
@RequestMapping("/api/v2/branch-portal")
public class BranchRepAuthController {

    private static final String REFRESH_TOKEN_COOKIE = "refresh_token";

    private final BranchRepRepository branchReps;
    private final JwtUtils jwtUtils;
    private final PasswordEncoder passwordEncoder = new BCryptPasswordEncoder();

    @Value("${app.cookie.secure:false}")
    private boolean cookieSecure;

    public BranchRepAuthController(BranchRepRepository branchReps, JwtUtils jwtUtils) {
        this.branchReps = branchReps;
        this.jwtUtils = jwtUtils;
    }

    public record LoginRequest(String repId, String password) {}

    @PostMapping("/login")
    public ResponseEntity<?> login(@RequestBody LoginRequest req, HttpServletResponse res) {
        if (req == null || req.repId() == null || req.password() == null) {
            return ResponseEntity.badRequest().body(Map.of("error", "repId and password are required"));
        }

        BranchRep rep = branchReps.findByRepId(req.repId().trim()).orElse(null);
        // One message for every failure mode — an unknown id, a wrong password
        // and a deactivated account must be indistinguishable, or this becomes
        // a way to enumerate which rep ids exist.
        if (rep == null || !rep.isActive()
                || !passwordEncoder.matches(req.password(), rep.getPasswordHash())) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(Map.of("error", "Invalid rep ID or password"));
        }

        rep.setLastLoginAt(LocalDateTime.now());
        branchReps.save(rep);

        setCookie(res, JwtAuthFilter.ACCESS_TOKEN_COOKIE,
                jwtUtils.generateAccessToken(rep.getId(), "BRANCH_REP"),
                (int) jwtUtils.getAccessTokenExpirySeconds());
        setCookie(res, REFRESH_TOKEN_COOKIE, jwtUtils.generateRefreshToken(rep.getId()),
                (int) jwtUtils.getRefreshTokenExpirySeconds());

        Map<String, Object> body = new HashMap<>();
        body.put("success", true);
        body.put("mustResetPassword", rep.isMustResetPassword());
        // partnerId is what the queue endpoint needs, so the dashboard doesn't
        // have to ask the rep which branch they work at.
        body.put("rep", Map.of("id", rep.getId(), "repId", rep.getRepId(),
                "name", rep.getName() == null ? "" : rep.getName(),
                "partnerId", rep.getPartnerId() == null ? "" : rep.getPartnerId(),
                "partnerName", rep.getPartnerName() == null ? "" : rep.getPartnerName()));
        return ResponseEntity.ok(body);
    }

    public record ChangePasswordRequest(String currentPassword, String newPassword) {}

    /** Forced on first login, and available at any time after. */
    @PostMapping("/change-password")
    public ResponseEntity<?> changePassword(Authentication auth, @RequestBody ChangePasswordRequest req) {
        BranchRep rep = branchReps.findById(auth.getName()).orElse(null);
        if (rep == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(Map.of("error", "Not a branch-rep session"));
        }
        if (req == null || req.currentPassword() == null
                || !passwordEncoder.matches(req.currentPassword(), rep.getPasswordHash())) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(Map.of("error", "Current password is incorrect"));
        }
        if (req.newPassword() == null || req.newPassword().length() < 8) {
            return ResponseEntity.badRequest()
                    .body(Map.of("error", "New password must be at least 8 characters"));
        }

        rep.setPasswordHash(passwordEncoder.encode(req.newPassword()));
        rep.setMustResetPassword(false);
        branchReps.save(rep);
        return ResponseEntity.ok(Map.of("success", true));
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
}
