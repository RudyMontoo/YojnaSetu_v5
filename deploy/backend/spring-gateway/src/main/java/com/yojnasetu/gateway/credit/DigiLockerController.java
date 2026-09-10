package com.yojnasetu.gateway.credit;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * See {@link DigiLockerService}'s class javadoc — this is real, spec-shaped
 * OAuth wiring with no live credentials configured in this deployment yet.
 *
 * {@code /callback} is deliberately NOT under citizen authentication:
 * DigiLocker redirects the citizen's browser here directly, and the
 * single-use {@code state} nonce recorded at {@code /authorize-url} time is
 * what actually authorizes the exchange — see
 * {@link DigiLockerLink}'s javadoc.
 */
@RestController
@RequestMapping("/api/v2/sih/digilocker")
public class DigiLockerController {

    private final DigiLockerService service;
    private final CreditApplicationService applications;

    public DigiLockerController(DigiLockerService service, CreditApplicationService applications) {
        this.service = service;
        this.applications = applications;
    }

    public record AuthorizeUrlRequest(String applicationId) {
    }

    @PostMapping("/authorize-url")
    public ResponseEntity<?> authorizeUrl(Authentication auth, @RequestBody AuthorizeUrlRequest req) {
        try {
            // Same ownership check every other application-scoped endpoint in
            // this module makes — without it, any logged-in citizen could pass
            // someone else's applicationId and start a DigiLocker link attempt
            // recorded against another citizen's file.
            applications.getForCitizen(auth.getName(), req.applicationId());
            DigiLockerService.AuthorizeUrl result = service.startLink(auth.getName(), req.applicationId());
            return ResponseEntity.ok(Map.of("url", result.url(), "state", result.state()));
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
    }

    @GetMapping("/callback")
    public ResponseEntity<?> callback(@RequestParam String state, @RequestParam String code) {
        try {
            DigiLockerLink link = service.completeLink(state, code);
            return ResponseEntity.ok(Map.of("success", true, "applicationId", link.getApplicationId(),
                    "status", link.getStatus()));
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
    }

    @GetMapping("/status")
    public ResponseEntity<?> status(Authentication auth, @RequestParam String applicationId) {
        try {
            applications.getForCitizen(auth.getName(), applicationId);
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
        return service.linkedFor(applicationId)
                .<ResponseEntity<?>>map(link -> ResponseEntity.ok(Map.of(
                        "linked", true, "linkedAt", link.getLinkedAt())))
                .orElseGet(() -> ResponseEntity.ok(Map.of("linked", false)));
    }

    @GetMapping("/documents")
    public ResponseEntity<?> issuedDocuments(Authentication auth, @RequestParam String applicationId) {
        try {
            applications.getForCitizen(auth.getName(), applicationId);
            return ResponseEntity.ok(Map.of("documents", service.fetchIssuedDocuments(applicationId)));
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
    }
}
