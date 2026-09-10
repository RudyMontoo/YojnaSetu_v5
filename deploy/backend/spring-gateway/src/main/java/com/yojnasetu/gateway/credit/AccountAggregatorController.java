package com.yojnasetu.gateway.credit;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/** See {@link AccountAggregatorService}'s class javadoc. */
@RestController
@RequestMapping("/api/v2/sih/account-aggregator")
public class AccountAggregatorController {

    private final AccountAggregatorService service;
    private final CreditApplicationService applications;

    public AccountAggregatorController(AccountAggregatorService service, CreditApplicationService applications) {
        this.service = service;
        this.applications = applications;
    }

    public record ConsentRequestBody(String applicationId, String vua) {
    }

    @PostMapping("/consent-request")
    public ResponseEntity<?> requestConsent(Authentication auth, @RequestBody ConsentRequestBody req) {
        try {
            applications.getForCitizen(auth.getName(), req.applicationId());
            AaConsentRequest request = service.createConsentRequest(auth.getName(), req.applicationId(), req.vua());
            return ResponseEntity.status(HttpStatus.CREATED).body(Map.of(
                    "consentHandle", request.getConsentHandle(), "status", request.getStatus()));
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
    }

    @GetMapping("/consent-status")
    public ResponseEntity<?> consentStatus(Authentication auth, @RequestParam String applicationId) {
        try {
            applications.getForCitizen(auth.getName(), applicationId);
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
        return service.latestFor(applicationId)
                .<ResponseEntity<?>>map(request -> {
                    try {
                        AaConsentRequest refreshed = service.refreshStatus(request.getConsentHandle());
                        return ResponseEntity.ok(Map.of("status", refreshed.getStatus()));
                    } catch (CreditApplicationService.TransitionException e) {
                        return CreditApplicationController.toResponse(e);
                    }
                })
                .orElseGet(() -> ResponseEntity.ok(Map.of("status", "none")));
    }
}
