package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.model.AuditLog;
import com.yojnasetu.gateway.repository.AuditLogRepository;
import com.yojnasetu.gateway.util.ClientIp;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

/**
 * Offline Aadhaar eKYC upload and retrieval.
 *
 * Same two-audience split as {@code LoanDocumentController}, for the same
 * reasons — a citizen may upload their own, a branch rep may read one on a
 * file assigned to their branch, and an assist-only helper may upload OR read
 * one on a file the citizen has authorized them for. A CSC operator is
 * explicitly the realistic path here: downloading the eKYC ZIP requires
 * UIDAI's own OTP-to-registered-mobile flow once, which is exactly the kind
 * of one-time, assisted step a CSC exists to help with — after which the
 * file itself needs no further network access to verify.
 */
@RestController
public class AadhaarEkycController {

    private final AadhaarOfflineEkycService service;
    private final CreditApplicationService applications;
    private final BranchRepRepository branchReps;
    private final AssistService assists;
    private final AuditLogRepository auditLogRepository;

    public AadhaarEkycController(AadhaarOfflineEkycService service,
                                 CreditApplicationService applications,
                                 BranchRepRepository branchReps,
                                 AssistService assists,
                                 AuditLogRepository auditLogRepository) {
        this.service = service;
        this.applications = applications;
        this.branchReps = branchReps;
        this.assists = assists;
        this.auditLogRepository = auditLogRepository;
    }

    // ------------------------------------------------------------- citizen

    @PostMapping(value = "/api/v2/sih/applications/{id}/aadhaar-ekyc", consumes = "multipart/form-data")
    public ResponseEntity<?> upload(Authentication auth, @PathVariable String id,
                                    @RequestParam("file") MultipartFile file,
                                    @RequestParam("shareCode") String shareCode,
                                    HttpServletRequest request) {
        try {
            CreditApplication application = applications.getForCitizen(auth.getName(), id);
            return storeAndRespond(application, file, shareCode, auth.getName(), "CITIZEN", request);
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
    }

    @GetMapping("/api/v2/sih/applications/{id}/aadhaar-ekyc")
    public ResponseEntity<?> list(Authentication auth, @PathVariable String id) {
        try {
            applications.getForCitizen(auth.getName(), id);
            return ResponseEntity.ok(service.listFor(id));
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
    }

    @GetMapping("/api/v2/sih/applications/{id}/aadhaar-ekyc/{recordId}/photo")
    public ResponseEntity<?> photo(Authentication auth, @PathVariable String id, @PathVariable String recordId) {
        try {
            applications.getForCitizen(auth.getName(), id);
            return servePhoto(id, recordId);
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
    }

    // ------------------------------------------------------- helper / rep

    /**
     * A CSC operator, NGO worker or field agent uploading on the citizen's
     * behalf — the realistic path per the research this feature answers: the
     * resident (or the helper, with them) downloads the file once at the
     * CSC, and it can be read here whenever.
     */
    @PostMapping(value = "/api/v2/branch/applications/{id}/aadhaar-ekyc", consumes = "multipart/form-data")
    public ResponseEntity<?> uploadByHelper(Authentication auth, @PathVariable String id,
                                            @RequestParam("file") MultipartFile file,
                                            @RequestParam("shareCode") String shareCode,
                                            HttpServletRequest request) {
        BranchRep helper = branchReps.findById(auth.getName()).filter(BranchRep::isActive).orElse(null);
        if (helper == null) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Not a helper session"));
        }

        CreditApplication application = resolveForStaff(helper, id);
        if (application == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "Application not found"));
        }
        try {
            return storeAndRespond(application, file, shareCode, auth.getName(),
                    helper.getRepType().name(), request);
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
    }

    @GetMapping("/api/v2/branch/applications/{id}/aadhaar-ekyc")
    public ResponseEntity<?> listForStaff(Authentication auth, @PathVariable String id) {
        BranchRep staff = branchReps.findById(auth.getName()).filter(BranchRep::isActive).orElse(null);
        if (staff == null) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Not a helper session"));
        }
        if (resolveForStaff(staff, id) == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "Application not found"));
        }
        return ResponseEntity.ok(service.listFor(id));
    }

    @GetMapping("/api/v2/branch/applications/{id}/aadhaar-ekyc/{recordId}/photo")
    public ResponseEntity<?> photoForStaff(Authentication auth, @PathVariable String id,
                                           @PathVariable String recordId, HttpServletRequest request) {
        BranchRep staff = branchReps.findById(auth.getName()).filter(BranchRep::isActive).orElse(null);
        if (staff == null) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "Not a helper session"));
        }
        if (resolveForStaff(staff, id) == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "Application not found"));
        }
        audit(auth.getName(), "aadhaar_ekyc_photo_read", request, id);
        return servePhoto(id, recordId);
    }

    /**
     * A branch rep's claim comes from their branch; an assist-only helper's
     * comes from the citizen's own authorization. Same split as
     * {@code LoanDocumentController.withRepAccess}.
     */
    private CreditApplication resolveForStaff(BranchRep staff, String applicationId) {
        CreditApplication application = applications.findById(applicationId).orElse(null);
        if (application == null) {
            return null;
        }
        boolean allowed = staff.isAssistOnly()
                ? assists.isAuthorized(applicationId, staff.getId())
                : java.util.Objects.equals(staff.getPartnerId(), application.getAssignedPartnerId());
        return allowed ? application : null;
    }

    // ---------------------------------------------------------------- shared

    private ResponseEntity<?> storeAndRespond(CreditApplication application, MultipartFile file, String shareCode,
                                              String uploadedByUserId, String uploadedByRole,
                                              HttpServletRequest request) {
        byte[] bytes;
        try {
            bytes = file == null ? null : file.getBytes();
        } catch (java.io.IOException e) {
            return ResponseEntity.badRequest().body(Map.of("error", "Could not read the uploaded file"));
        }

        AadhaarEkycRecord stored = service.extractAndStore(application, bytes, shareCode,
                uploadedByUserId, uploadedByRole);

        audit(uploadedByUserId, "aadhaar_ekyc_upload", request, application.getId());
        stored.setEncryptedPhoto(null);   // never echo ciphertext back
        return ResponseEntity.status(HttpStatus.CREATED).body(stored);
    }

    private ResponseEntity<?> servePhoto(String applicationId, String recordId) {
        AadhaarEkycRecord record = service.requireRecord(recordId);
        if (!applicationId.equals(record.getApplicationId())) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "Record not found"));
        }
        byte[] bytes = service.photoOf(record);
        return ResponseEntity.ok().contentType(MediaType.IMAGE_JPEG).body(bytes);
    }

    private void audit(String userId, String action, HttpServletRequest request, String applicationId) {
        auditLogRepository.save(AuditLog.forApplication(
                userId, action, request.getRequestURI(), ClientIp.of(request), applicationId));
    }
}
