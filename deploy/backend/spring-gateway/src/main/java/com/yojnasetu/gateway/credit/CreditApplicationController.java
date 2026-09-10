package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.model.AuditLog;
import com.yojnasetu.gateway.repository.AuditLogRepository;
import com.yojnasetu.gateway.util.ClientIp;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * The citizen's own applications. Authenticated — unlike the catalogue and
 * eligibility check, these carry identity.
 *
 * Every handler resolves the owner from the JWT principal and never from the
 * request body, so an application can only ever be created for, or read by, the
 * caller themselves.
 */
@RestController
@RequestMapping("/api/v2/sih/applications")
public class CreditApplicationController {

    private final CreditApplicationService service;
    private final AuditLogRepository auditLogRepository;
    /**
     * Signalled from the REST edge rather than from CreditApplicationService,
     * because a signal means "a human did this". The workflow's own activity
     * calls the service directly, so wiring it deeper would have the workflow
     * signalling itself in a loop.
     */
    private final com.yojnasetu.gateway.workflow.LoanWorkflowGateway workflows;
    private final ConsentService consents;

    public CreditApplicationController(CreditApplicationService service,
                                       com.yojnasetu.gateway.workflow.LoanWorkflowGateway workflows,
                                       ConsentService consents,
                                       AuditLogRepository auditLogRepository) {
        this.service = service;
        this.workflows = workflows;
        this.consents = consents;
        this.auditLogRepository = auditLogRepository;
    }

    @GetMapping
    public List<CreditApplication> list(Authentication auth) {
        return service.listForCitizen(auth.getName());
    }

    @GetMapping("/{id}")
    public ResponseEntity<?> get(Authentication auth, @PathVariable String id) {
        try {
            return ResponseEntity.ok(service.getForCitizen(auth.getName(), id));
        } catch (CreditApplicationService.TransitionException e) {
            return toResponse(e);
        }
    }

    @PostMapping
    public ResponseEntity<?> create(Authentication auth,
                                    @RequestBody CreditApplicationService.CreateApplicationRequest request,
                                    HttpServletRequest httpRequest) {
        try {
            CreditApplication created = service.create(auth.getName(), request);
            if (request.partnerId() != null && !request.partnerId().isBlank()) {
                created = service.assignPartner(created, request.partnerId(),
                        request.partnerName(), request.partnerType());
            }
            workflows.start(created.getId(), auth.getName());
            audit(auth.getName(), "credit_application_create", httpRequest);
            return ResponseEntity.status(HttpStatus.CREATED).body(created);
        } catch (CreditApplicationService.TransitionException e) {
            return toResponse(e);
        }
    }

    /**
     * Choose, or change, the branch this draft will be sent to.
     *
     * Separate from submission because the choice is consequential and a
     * citizen should be able to compare branches before committing: the same
     * scheme costs 6.5% through a State Channelising Agency and 15% through an
     * NBFC-MFI. Only permitted while the file is still a draft.
     */
    @PostMapping("/{id}/partner")
    public ResponseEntity<?> choosePartner(Authentication auth, @PathVariable String id,
                                           @RequestBody CreditApplicationService.PartnerSelectionRequest request,
                                           HttpServletRequest httpRequest) {
        if (request == null) {
            return ResponseEntity.badRequest().body(Map.of("error", "Request body is required"));
        }
        try {
            CreditApplication application = service.getForCitizen(auth.getName(), id);
            CreditApplication updated = service.assignPartner(application, request.partnerId(),
                    request.partnerName(), request.partnerType());
            audit(auth.getName(), "credit_application_choose_partner", httpRequest);
            return ResponseEntity.ok(updated);
        } catch (CreditApplicationService.TransitionException e) {
            return toResponse(e);
        }
    }

    /**
     * Hand the application to the partner. Separate from creation so a citizen
     * can build a draft, see the terms, and commit deliberately.
     */
    @PostMapping("/{id}/submit")
    public ResponseEntity<?> submit(Authentication auth, @PathVariable String id,
                                    HttpServletRequest httpRequest) {
        try {
            CreditApplication application = service.getForCitizen(auth.getName(), id);

            // The one moment consent stops being paperwork. Submitting is when
            // this citizen's caste and income certificates leave the platform
            // for a bank, so it is refused without explicit agreement to that
            // specific thing — not a general "I accept" ticked at signup.
            consents.requireConsent(auth.getName(), ConsentPurpose.PARTNER_SHARING, id);

            CreditApplication submitted = service.transition(application,
                    CreditApplicationStatus.SUBMITTED, auth.getName(), "CITIZEN", null, null, null);
            workflows.signal(id, CreditApplicationStatus.SUBMITTED, null, null);
            audit(auth.getName(), "credit_application_submit", httpRequest);
            return ResponseEntity.ok(submitted);
        } catch (CreditApplicationService.TransitionException e) {
            return toResponse(e);
        }
    }

    /**
     * The citizen says they've supplied what was asked for, moving the file back
     * into the rep's queue. Only legal from missing_docs — the state machine
     * enforces that rather than this handler.
     */
    @PostMapping("/{id}/documents-supplied")
    public ResponseEntity<?> documentsSupplied(Authentication auth, @PathVariable String id,
                                               HttpServletRequest httpRequest) {
        try {
            CreditApplication application = service.getForCitizen(auth.getName(), id);
            CreditApplication updated = service.transition(application,
                    CreditApplicationStatus.UNDER_VERIFICATION, auth.getName(), "CITIZEN",
                    null, "Applicant reported the requested documents were provided", null);
            // Non-null documents list is how the gateway tells "citizen supplied
            // documents" apart from "rep started verifying" — both land on
            // UNDER_VERIFICATION but mean different things to the workflow.
            workflows.signal(id, CreditApplicationStatus.UNDER_VERIFICATION, null, java.util.List.of());
            audit(auth.getName(), "credit_application_documents_supplied", httpRequest);
            return ResponseEntity.ok(updated);
        } catch (CreditApplicationService.TransitionException e) {
            return toResponse(e);
        }
    }

    private void audit(String userId, String action, HttpServletRequest request) {
        auditLogRepository.save(AuditLog.of(userId, action, request.getRequestURI(), ClientIp.of(request)));
    }

    static ResponseEntity<?> toResponse(CreditApplicationService.TransitionException e) {
        HttpStatus status = switch (e.failure()) {
            case NOT_FOUND -> HttpStatus.NOT_FOUND;
            case CONFLICT -> HttpStatus.CONFLICT;
            case FORBIDDEN -> HttpStatus.FORBIDDEN;
            case BAD_REQUEST -> HttpStatus.BAD_REQUEST;
        };
        return ResponseEntity.status(status).body(Map.of("error", e.getMessage()));
    }
}
