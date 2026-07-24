package com.yojnasetu.gateway.controller;

import com.yojnasetu.gateway.model.Helper;
import com.yojnasetu.gateway.model.HelperApplication;
import com.yojnasetu.gateway.model.User;
import com.yojnasetu.gateway.repository.HelperApplicationRepository;
import com.yojnasetu.gateway.repository.HelperRepository;
import com.yojnasetu.gateway.repository.UserRepository;
import com.yojnasetu.gateway.security.FieldEncryptionService;
import com.yojnasetu.gateway.service.EmailService;
import com.yojnasetu.gateway.util.AadhaarValidator;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.web.bind.annotation.*;

import java.security.SecureRandom;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;
import java.util.regex.Pattern;

/**
 * "Become a helper" onboarding + admin review. A citizen submits KYC (name,
 * phone, Aadhaar, PAN, proof of work); an admin approves, which promotes the
 * applicant's user role to CSC_OPERATOR (unlocking the helper area).
 *
 * KYC is stored privacy-safe: only the Aadhaar hash + masked form, never the
 * raw UID or an image. Admin-only routes check ROLE_ADMIN in the controller.
 */
@RestController
@RequestMapping("/api/v2/helper")
public class HelperApplicationController {

    private static final Pattern PAN_RE = Pattern.compile("^[A-Z]{5}[0-9]{4}[A-Z]$");

    private final HelperApplicationRepository repo;
    private final HelperRepository helperRepo;
    private final UserRepository userRepository;
    private final FieldEncryptionService encryption;
    private final EmailService emailService;
    private final BCryptPasswordEncoder passwordEncoder = new BCryptPasswordEncoder();
    private final SecureRandom random = new SecureRandom();
    private static final String PW_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789";  // no ambiguous chars

    @Value("${encryption.aadhaar-salt}")
    private String aadhaarSalt;

    public HelperApplicationController(HelperApplicationRepository repo, HelperRepository helperRepo,
                                       UserRepository userRepository, FieldEncryptionService encryption,
                                       EmailService emailService) {
        this.repo = repo;
        this.helperRepo = helperRepo;
        this.userRepository = userRepository;
        this.encryption = encryption;
        this.emailService = emailService;
    }

    private String randomToken(int len) {
        StringBuilder sb = new StringBuilder(len);
        for (int i = 0; i < len; i++) sb.append(PW_ALPHABET.charAt(random.nextInt(PW_ALPHABET.length())));
        return sb.toString();
    }

    private static boolean isAdmin(Authentication auth) {
        return auth.getAuthorities().stream().anyMatch(a -> a.getAuthority().equals("ROLE_ADMIN"));
    }

    public record ApplyRequest(String fullName, String phone, String aadhaar, String pan,
                               String workProofType, String workProofDetail) {}

    /** Decrypt the at-rest KYC PII for the (admin) reader. */
    private Map<String, Object> summary(HelperApplication a) {
        Map<String, Object> m = new HashMap<>();
        m.put("id", a.getId());
        m.put("userId", a.getUserId());
        m.put("fullName", encryption.decrypt(a.getFullName()));
        m.put("phone", encryption.decrypt(a.getPhone()));
        m.put("aadhaarMasked", a.getAadhaarMasked());
        m.put("aadhaarVerified", a.isAadhaarVerified());
        m.put("pan", encryption.decrypt(a.getPan()));
        m.put("workProofType", a.getWorkProofType());
        m.put("workProofDetail", a.getWorkProofDetail());
        m.put("status", a.getStatus());
        m.put("createdAt", a.getCreatedAt());
        return m;
    }

    /** Citizen submits an application to become a helper. */
    @PostMapping("/apply")
    public ResponseEntity<?> apply(Authentication auth, @RequestBody ApplyRequest req) {
        if (req.fullName() == null || req.fullName().isBlank() || req.phone() == null || req.phone().isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "Name and phone are required"));
        }
        String pan = req.pan() == null ? "" : req.pan().trim().toUpperCase();
        if (!PAN_RE.matcher(pan).matches()) {
            return ResponseEntity.badRequest().body(Map.of("error", "PAN must look like ABCDE1234F"));
        }
        String aadhaarDigits = req.aadhaar() == null ? "" : req.aadhaar().replaceAll("\\s", "");
        if (!aadhaarDigits.matches("\\d{12}")) {
            return ResponseEntity.badRequest().body(Map.of("error", "Aadhaar must be 12 digits"));
        }
        // one open application per user
        var existing = repo.findFirstByUserIdOrderByCreatedAtDesc(auth.getName());
        if (existing.isPresent() && !"rejected".equals(existing.get().getStatus())) {
            return ResponseEntity.status(HttpStatus.CONFLICT)
                    .body(Map.of("error", "You already have a " + existing.get().getStatus() + " application", "status", existing.get().getStatus()));
        }

        HelperApplication a = new HelperApplication();
        a.setUserId(auth.getName());
        // PII encrypted at rest (Fernet), same stance as citizen_profiles.
        a.setFullName(encryption.encrypt(req.fullName().trim()));
        a.setPhone(encryption.encrypt(req.phone().trim()));
        a.setAadhaarHash(encryption.sha256Hash(aadhaarDigits, aadhaarSalt));  // one-way; never the raw UID
        a.setAadhaarMasked("XXXX-XXXX-" + aadhaarDigits.substring(8));         // masked display is not sensitive
        a.setAadhaarVerified(AadhaarValidator.isValid(aadhaarDigits));
        a.setPan(encryption.encrypt(pan));
        a.setWorkProofType(req.workProofType());
        a.setWorkProofDetail(req.workProofDetail() != null ? req.workProofDetail().trim() : null);
        a.setStatus("pending");
        a.setCreatedAt(LocalDateTime.now());
        a.setUpdatedAt(LocalDateTime.now());
        a = repo.save(a);
        return ResponseEntity.status(HttpStatus.CREATED).body(Map.of("success", true, "status", a.getStatus(), "aadhaarVerified", a.isAadhaarVerified()));
    }

    /** Citizen sees their own application status. */
    @GetMapping("/my-application")
    public ResponseEntity<?> mine(Authentication auth) {
        return repo.findFirstByUserIdOrderByCreatedAtDesc(auth.getName())
                .<ResponseEntity<?>>map(a -> ResponseEntity.ok(summary(a)))
                .orElse(ResponseEntity.ok(Map.of("status", "none")));
    }

    /** Admin: pending applications to review. */
    @GetMapping("/applications")
    public ResponseEntity<?> pending(Authentication auth) {
        if (!isAdmin(auth)) return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Admin only"));
        return ResponseEntity.ok(Map.of("applications",
                repo.findByStatusOrderByCreatedAtAsc("pending").stream().map(this::summary).toList()));
    }

    /** Admin confirms -> mint a Helper login (helperId + temp password), email it
     *  to the applicant, and return it to the admin too (to relay if email fails). */
    @PostMapping("/applications/{id}/approve")
    public ResponseEntity<?> approve(Authentication auth, @PathVariable String id) {
        if (!isAdmin(auth)) return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Admin only"));
        return repo.findById(id).<ResponseEntity<?>>map(a -> {
            if ("approved".equals(a.getStatus())) {
                return ResponseEntity.status(HttpStatus.CONFLICT).body(Map.of("error", "Already approved"));
            }
            a.setStatus("approved");
            a.setReviewedBy(auth.getName());
            a.setUpdatedAt(LocalDateTime.now());
            repo.save(a);

            // mint a unique helper login
            String helperId;
            do { helperId = "HLP-" + randomToken(5).toUpperCase(); } while (helperRepo.findByHelperId(helperId).isPresent());
            String tempPassword = randomToken(10);

            String plainName = encryption.decrypt(a.getFullName());
            Helper h = new Helper();
            h.setHelperId(helperId);
            h.setPasswordHash(passwordEncoder.encode(tempPassword));
            h.setName(a.getFullName());   // already-encrypted ciphertext carried over (decrypted at read)
            h.setPhone(a.getPhone());     // encrypted
            h.setApplicationId(a.getId());
            h.setCitizenUserId(a.getUserId());
            h.setActive(true);
            h.setMustResetPassword(true);
            h.setCreatedAt(LocalDateTime.now());
            helperRepo.save(h);

            // email the credentials to the applicant (look up their account email)
            String email = userRepository.findById(a.getUserId()).map(User::getEmail).orElse(null);
            boolean emailed = false;
            if (email != null && !email.isBlank()) {
                emailService.sendCredentials(email, plainName, helperId, tempPassword);
                emailed = true;
            }

            Map<String, Object> resp = new HashMap<>();
            resp.put("success", true);
            resp.put("status", "approved");
            resp.put("helperId", helperId);
            resp.put("tempPassword", tempPassword);   // shown to admin to relay if not emailed
            resp.put("emailedTo", emailed ? email : null);
            return ResponseEntity.ok(resp);
        }).orElse(ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "Application not found")));
    }

    /** Admin rejects. */
    @PostMapping("/applications/{id}/reject")
    public ResponseEntity<?> reject(Authentication auth, @PathVariable String id) {
        if (!isAdmin(auth)) return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Admin only"));
        return repo.findById(id).map(a -> {
            a.setStatus("rejected");
            a.setReviewedBy(auth.getName());
            a.setUpdatedAt(LocalDateTime.now());
            repo.save(a);
            return ResponseEntity.ok(Map.of("success", true, "status", "rejected"));
        }).orElse(ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "Application not found")));
    }
}
