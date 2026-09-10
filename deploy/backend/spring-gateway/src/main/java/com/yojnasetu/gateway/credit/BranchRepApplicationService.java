package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.credit.CreditApplicationService.Failure;
import com.yojnasetu.gateway.credit.CreditApplicationService.TransitionException;
import com.yojnasetu.gateway.model.User;
import com.yojnasetu.gateway.repository.UserRepository;
import com.yojnasetu.gateway.security.FieldEncryptionService;
import com.yojnasetu.gateway.service.EmailService;
import com.yojnasetu.gateway.util.AadhaarValidator;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.security.SecureRandom;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.regex.Pattern;

/**
 * "Become an assist helper" self-onboarding — the CSC-operator/NGO-worker/
 * field-agent side of {@link BranchRep} that had no application path at all
 * before this. Mirrors {@code HelperApplicationController}'s KYC and
 * credential-minting pattern deliberately: it is the same real problem
 * (a self-applied role needs privacy-safe identity proof and an admin gate)
 * that model already solves for the general-scheme helper role.
 */
@Service
public class BranchRepApplicationService {

    private static final Pattern PAN_RE = Pattern.compile("^[A-Z]{5}[0-9]{4}[A-Z]$");
    private static final String PW_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789";  // no ambiguous chars

    private final BranchRepApplicationRepository applications;
    private final BranchRepRepository branchReps;
    private final UserRepository users;
    private final FieldEncryptionService encryption;
    private final EmailService emailService;
    private final PasswordEncoder passwordEncoder = new BCryptPasswordEncoder();
    private final SecureRandom random = new SecureRandom();

    @Value("${encryption.aadhaar-salt}")
    private String aadhaarSalt;

    public BranchRepApplicationService(BranchRepApplicationRepository applications,
                                       BranchRepRepository branchReps,
                                       UserRepository users,
                                       FieldEncryptionService encryption,
                                       EmailService emailService) {
        this.applications = applications;
        this.branchReps = branchReps;
        this.users = users;
        this.encryption = encryption;
        this.emailService = emailService;
    }

    public record ApplyRequest(String fullName, String phone, String aadhaar, String pan,
                               RepType repType, String organisation, String workProofDetail) {
    }

    /**
     * Citizen submits an application. {@code repType} must be an assist-only
     * type — {@link RepType#BANK_BRANCH} is refused outright, not just
     * discouraged: a branch representative is appointed by the lending
     * Channel Partner, and a self-service path to that role would let anyone
     * claim to represent a bank.
     */
    public BranchRepApplication apply(String userId, ApplyRequest req) {
        if (req == null || isBlank(req.fullName()) || isBlank(req.phone())) {
            throw new TransitionException(Failure.BAD_REQUEST, "fullName and phone are required");
        }
        if (req.repType() == null) {
            throw new TransitionException(Failure.BAD_REQUEST, "repType is required");
        }
        if (req.repType() == RepType.BANK_BRANCH) {
            throw new TransitionException(Failure.BAD_REQUEST,
                    "Branch representatives are appointed by their lending institution, not self-applied. "
                            + "Choose csc, ngo_shg, or field_agent.");
        }
        if (isBlank(req.organisation())) {
            throw new TransitionException(Failure.BAD_REQUEST,
                    "organisation is required — the CSC code, NGO/SHG name, or district you work from");
        }

        String pan = req.pan() == null ? "" : req.pan().trim().toUpperCase();
        if (!PAN_RE.matcher(pan).matches()) {
            throw new TransitionException(Failure.BAD_REQUEST, "PAN must look like ABCDE1234F");
        }
        String aadhaarDigits = req.aadhaar() == null ? "" : req.aadhaar().replaceAll("\\s", "");
        if (!aadhaarDigits.matches("\\d{12}")) {
            throw new TransitionException(Failure.BAD_REQUEST, "Aadhaar must be 12 digits");
        }

        // One open application per citizen — same rule as HelperApplication,
        // for the same reason: a rejected applicant may re-apply, a pending
        // or already-approved one should not be able to file a duplicate.
        Optional<BranchRepApplication> existing = applications.findFirstByUserIdOrderByCreatedAtDesc(userId);
        if (existing.isPresent() && !"rejected".equals(existing.get().getStatus())) {
            throw new TransitionException(Failure.CONFLICT,
                    "You already have a " + existing.get().getStatus() + " application");
        }

        BranchRepApplication application = new BranchRepApplication();
        application.setUserId(userId);
        application.setFullName(encryption.encrypt(req.fullName().trim()));
        application.setPhone(encryption.encrypt(req.phone().trim()));
        application.setAadhaarHash(encryption.sha256Hash(aadhaarDigits, aadhaarSalt));
        application.setAadhaarMasked("XXXX-XXXX-" + aadhaarDigits.substring(8));
        application.setAadhaarVerified(AadhaarValidator.isValid(aadhaarDigits));
        application.setPan(encryption.encrypt(pan));
        application.setRepType(req.repType());
        application.setOrganisation(req.organisation().trim());
        application.setWorkProofDetail(req.workProofDetail() == null ? null : req.workProofDetail().trim());
        application.setStatus("pending");
        application.setCreatedAt(LocalDateTime.now());
        application.setUpdatedAt(LocalDateTime.now());
        return applications.save(application);
    }

    public Optional<BranchRepApplication> myApplication(String userId) {
        return applications.findFirstByUserIdOrderByCreatedAtDesc(userId);
    }

    public List<BranchRepApplication> pending() {
        return applications.findByStatusOrderByCreatedAtAsc("pending");
    }

    public long countPending() {
        return applications.countByStatus("pending");
    }

    /**
     * Admin approves: mints a {@link BranchRep} login (repId + temp
     * password), emails it, and returns the credentials so an admin can
     * relay them if the email doesn't land — same "never silently lose a
     * credential" rule as the general helper flow.
     */
    public ApprovalResult approve(String applicationId, String adminUserId) {
        BranchRepApplication application = applications.findById(applicationId)
                .orElseThrow(() -> new TransitionException(Failure.NOT_FOUND, "Application not found"));
        if ("approved".equals(application.getStatus())) {
            throw new TransitionException(Failure.CONFLICT, "Already approved");
        }

        application.setStatus("approved");
        application.setReviewedBy(adminUserId);
        application.setUpdatedAt(LocalDateTime.now());
        applications.save(application);

        String repId;
        String prefix = switch (application.getRepType()) {
            case CSC -> "CSC-";
            case NGO_SHG -> "NGO-";
            case FIELD_AGENT -> "FA-";
            case BANK_BRANCH -> "REP-"; // unreachable — apply() refuses this type
        };
        do {
            repId = prefix + randomToken(6).toUpperCase();
        } while (branchReps.findByRepId(repId).isPresent());
        String tempPassword = randomToken(10);

        String plainName = encryption.decrypt(application.getFullName());

        BranchRep rep = new BranchRep();
        rep.setRepId(repId);
        rep.setPasswordHash(passwordEncoder.encode(tempPassword));
        rep.setName(plainName);
        rep.setPhone(application.getPhone());   // already-encrypted ciphertext, decrypted at read
        rep.setRepType(application.getRepType());
        rep.setOrganisation(application.getOrganisation());
        rep.setActive(true);
        rep.setMustResetPassword(true);
        rep.setCreatedAt(LocalDateTime.now());
        branchReps.save(rep);

        String email = users.findById(application.getUserId()).map(User::getEmail).orElse(null);
        boolean emailed = false;
        if (email != null && !email.isBlank()) {
            emailService.sendBranchRepCredentials(email, plainName, application.getRepType().label(),
                    repId, tempPassword);
            emailed = true;
        }

        return new ApprovalResult(repId, tempPassword, emailed ? email : null);
    }

    public void reject(String applicationId, String adminUserId) {
        BranchRepApplication application = applications.findById(applicationId)
                .orElseThrow(() -> new TransitionException(Failure.NOT_FOUND, "Application not found"));
        application.setStatus("rejected");
        application.setReviewedBy(adminUserId);
        application.setUpdatedAt(LocalDateTime.now());
        applications.save(application);
    }

    public record ApprovalResult(String repId, String tempPassword, String emailedTo) {
    }

    private String randomToken(int len) {
        StringBuilder sb = new StringBuilder(len);
        for (int i = 0; i < len; i++) {
            sb.append(PW_ALPHABET.charAt(random.nextInt(PW_ALPHABET.length())));
        }
        return sb.toString();
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}
