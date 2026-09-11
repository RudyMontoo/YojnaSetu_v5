package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.model.AuditLog;
import com.yojnasetu.gateway.repository.AuditLogRepository;
import com.yojnasetu.gateway.service.CitizenProfileService;
import com.yojnasetu.gateway.util.ClientIp;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * DigiLocker verification of a citizen's own PROFILE, as opposed to
 * {@link DigiLockerController}, which verifies documents for one specific
 * credit application.
 *
 * The distinction matters to the citizen: they register once, verify once, and
 * every later application inherits that, instead of being asked to connect
 * DigiLocker again for each loan they apply for. Mechanically it is the same
 * OAuth flow — this reuses {@link DigiLockerService} wholesale, passing
 * {@link DigiLockerService#profileScope(String)} where an applicationId would
 * normally go.
 *
 * NOTHING HERE VERIFIES ANYTHING TODAY WITHOUT EITHER REAL PARTNER
 * CREDENTIALS OR {@code app.demo.simulate-integrations=true}. When simulation
 * is on, every response carries {@code simulated: true}, and the document
 * names written to the profile are prefixed {@code simulated:} — so no record
 * in the database can later be read as a verification that did not happen.
 */
@RestController
@RequestMapping("/api/v2/sih/verification")
public class ProfileVerificationController {

    private final DigiLockerService digilocker;
    private final ConsentService consents;
    private final CitizenProfileService profiles;
    private final AuditLogRepository auditLog;

    public ProfileVerificationController(DigiLockerService digilocker,
                                         ConsentService consents,
                                         CitizenProfileService profiles,
                                         AuditLogRepository auditLog) {
        this.digilocker = digilocker;
        this.consents = consents;
        this.profiles = profiles;
        this.auditLog = auditLog;
    }

    public record StartRequest(boolean consent) {
    }

    /**
     * Begins the link. The citizen must tick the consent box first: DPDP-2023
     * wants purpose-specific, informed agreement before we fetch anything from
     * DigiLocker on their behalf, and {@code DIGILOCKER_FETCH}'s statement is
     * the exact wording the UI shows them.
     */
    @PostMapping("/digilocker/start")
    public ResponseEntity<?> start(Authentication auth,
                                   @RequestBody(required = false) StartRequest req,
                                   HttpServletRequest http) {
        String userId = auth.getName();
        if (req == null || !req.consent()) {
            return ResponseEntity.badRequest().body(Map.of(
                    "error", "Your consent is needed before we can fetch documents from DigiLocker",
                    "consentStatement", ConsentPurpose.DIGILOCKER_FETCH.statement()));
        }
        String scope = DigiLockerService.profileScope(userId);
        consents.grant(userId, ConsentPurpose.DIGILOCKER_FETCH, scope, ClientIp.of(http));
        try {
            DigiLockerService.AuthorizeUrl url = digilocker.startLink(userId, scope);
            auditLog.save(AuditLog.of(userId, "digilocker_profile_link_started",
                    "/api/v2/sih/verification/digilocker/start", ClientIp.of(http)));
            return ResponseEntity.ok(Map.of(
                    "url", url.url(),
                    "state", url.state(),
                    "simulated", digilocker.isSimulated()));
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
    }

    /**
     * Where the profile's verification stands. Also the point at which a
     * completed link is written back onto the profile — the OAuth callback is
     * keyed only on the state nonce and has no idea whose profile it belongs
     * to, whereas this request is authenticated, so the copy happens here and
     * is idempotent.
     */
    @GetMapping("/digilocker/status")
    public ResponseEntity<?> status(Authentication auth) {
        String userId = auth.getName();
        String scope = DigiLockerService.profileScope(userId);

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("available", digilocker.isConfigured());
        body.put("simulated", digilocker.isSimulated());

        Optional<DigiLockerLink> link = digilocker.linkedFor(scope);
        if (link.isEmpty()) {
            body.put("linked", false);
            body.put("documents", List.of());
            return ResponseEntity.ok(body);
        }

        List<DigiLockerService.IssuedDocument> documents = digilocker.fetchIssuedDocuments(scope);
        body.put("linked", true);
        body.put("linkedAt", link.get().getLinkedAt());
        body.put("simulated", link.get().isSimulated());
        body.put("documents", documents);
        recordOnProfile(userId, documents, link.get().isSimulated());
        return ResponseEntity.ok(body);
    }

    /**
     * Copies the fetched document types onto the profile's {@code verifiedDocs}.
     *
     * Simulated fetches are stored with a {@code simulated:} prefix rather than
     * being skipped: the demo needs to show a verified state, and a reader of
     * the database needs to be able to tell that state apart from a real one
     * without knowing which flag the server was booted with.
     *
     * A profile that doesn't exist yet is left alone — it is created by
     * POST /consent, and silently conjuring one here would store data for a
     * citizen who never agreed to profile storage.
     */
    private void recordOnProfile(String userId, List<DigiLockerService.IssuedDocument> documents, boolean simulated) {
        profiles.findDecrypted(userId).ifPresent(profile -> {
            List<String> verified = documents.stream()
                    .map(d -> (simulated ? "simulated:digilocker:" : "digilocker:") + d.docType())
                    .toList();
            if (verified.equals(profile.getVerifiedDocs())) {
                return; // nothing changed — don't rewrite (and re-encrypt) the document
            }
            profile.setVerifiedDocs(verified);
            profiles.saveEncrypted(profile);
        });
    }
}
