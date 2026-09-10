package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.model.AuditLog;
import com.yojnasetu.gateway.repository.AuditLogRepository;
import com.yojnasetu.gateway.util.ClientIp;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.Map;

/**
 * Upload and retrieval of the documents attached to a loan application.
 *
 * Two audiences with different rules, which is why the read paths are
 * separate rather than one endpoint with a branch inside:
 *
 *   - a citizen may see and remove their own documents;
 *   - a branch rep may READ documents on files assigned to their branch, and
 *     may not upload or delete. Evidence a rep can edit is not evidence.
 *
 * Every download is written to the audit log. These files name someone's caste
 * and income, so "who opened this, and when" has to be answerable.
 */
@RestController
public class LoanDocumentController {

    private final LoanDocumentService documents;
    private final CreditApplicationService applications;
    private final BranchRepRepository branchReps;
    private final AuditLogRepository auditLogRepository;

    public LoanDocumentController(LoanDocumentService documents,
                                  CreditApplicationService applications,
                                  BranchRepRepository branchReps,
                                  AuditLogRepository auditLogRepository) {
        this.documents = documents;
        this.applications = applications;
        this.branchReps = branchReps;
        this.auditLogRepository = auditLogRepository;
    }

    // ------------------------------------------------------------- citizen

    @PostMapping(value = "/api/v2/sih/applications/{id}/documents", consumes = "multipart/form-data")
    public ResponseEntity<?> upload(Authentication auth,
                                    @PathVariable String id,
                                    @RequestParam("file") MultipartFile file,
                                    @RequestParam(value = "documentType", required = false) String documentType,
                                    HttpServletRequest request) {
        try {
            CreditApplication application = applications.getForCitizen(auth.getName(), id);
            byte[] bytes = file == null ? null : file.getBytes();

            LoanDocument stored = documents.store(application, bytes,
                    file == null ? null : file.getOriginalFilename(),
                    documentType, auth.getName(), "CITIZEN");

            audit(auth.getName(), "loan_document_upload", request);
            // Never echo the content back — the caller already has the file.
            stored.setContent(null);
            return ResponseEntity.status(HttpStatus.CREATED).body(stored);

        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        } catch (java.io.IOException e) {
            return ResponseEntity.badRequest().body(Map.of("error", "Could not read the uploaded file"));
        }
    }

    @GetMapping("/api/v2/sih/applications/{id}/documents")
    public ResponseEntity<?> list(Authentication auth, @PathVariable String id) {
        try {
            applications.getForCitizen(auth.getName(), id);
            return ResponseEntity.ok(documents.listFor(id));
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
    }

    @GetMapping("/api/v2/sih/applications/{id}/documents/{documentId}")
    public ResponseEntity<?> download(Authentication auth, @PathVariable String id,
                                      @PathVariable String documentId, HttpServletRequest request) {
        try {
            applications.getForCitizen(auth.getName(), id);
            LoanDocument document = documents.requireDocument(documentId);
            if (!id.equals(document.getApplicationId())) {
                // Prevents reading another application's document by pairing a
                // valid id of yours with a document id that isn't.
                return ResponseEntity.status(HttpStatus.NOT_FOUND)
                        .body(Map.of("error", "Document not found"));
            }
            audit(auth.getName(), "loan_document_read", request);
            return serve(document);
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
    }

    @DeleteMapping("/api/v2/sih/applications/{id}/documents/{documentId}")
    public ResponseEntity<?> delete(Authentication auth, @PathVariable String id,
                                    @PathVariable String documentId, HttpServletRequest request) {
        try {
            CreditApplication application = applications.getForCitizen(auth.getName(), id);
            LoanDocument document = documents.requireDocument(documentId);
            if (!id.equals(document.getApplicationId())) {
                return ResponseEntity.status(HttpStatus.NOT_FOUND)
                        .body(Map.of("error", "Document not found"));
            }
            if (application.getStatus() != CreditApplicationStatus.DRAFT
                    && application.getStatus() != CreditApplicationStatus.MISSING_DOCS) {
                // Once a rep is verifying, the evidence they are looking at
                // must not disappear from under them.
                return ResponseEntity.status(HttpStatus.CONFLICT).body(Map.of(
                        "error", "Documents can only be removed while the application is a draft "
                                + "or you have been asked for more"));
            }
            documents.delete(document);
            audit(auth.getName(), "loan_document_delete", request);
            return ResponseEntity.ok(Map.of("deleted", true));
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
    }

    // ---------------------------------------------------------- branch rep

    /**
     * A rep reads documents for files assigned to THEIR branch. The branch is
     * taken from their own account rather than a request parameter, so a rep
     * cannot ask for another branch's paperwork.
     *
     * Mapped under /api/v2/branch/** so SecurityConfig's hasAnyRole matcher
     * covers it. Putting these under /api/v2/sih/** would have left them on
     * plain authenticated() — reachable by any logged-in citizen and defended
     * only by the check below, which is exactly the by-hand pattern this
     * module moved away from.
     */
    @GetMapping("/api/v2/branch/applications/{id}/documents")
    public ResponseEntity<?> listForRep(Authentication auth, @PathVariable String id) {
        return withRepAccess(auth, id, application -> ResponseEntity.ok(documents.listFor(id)));
    }

    @GetMapping("/api/v2/branch/applications/{id}/documents/{documentId}")
    public ResponseEntity<?> downloadForRep(Authentication auth, @PathVariable String id,
                                            @PathVariable String documentId,
                                            HttpServletRequest request) {
        return withRepAccess(auth, id, application -> {
            LoanDocument document = documents.requireDocument(documentId);
            if (!id.equals(document.getApplicationId())) {
                return ResponseEntity.status(HttpStatus.NOT_FOUND)
                        .body(Map.of("error", "Document not found"));
            }
            audit(auth.getName(), "loan_document_read_by_rep", request);
            return serve(document);
        });
    }

    private ResponseEntity<?> withRepAccess(Authentication auth, String applicationId,
                                            java.util.function.Function<CreditApplication, ResponseEntity<?>> action) {
        BranchRep rep = branchReps.findById(auth.getName()).orElse(null);
        if (rep == null) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN)
                    .body(Map.of("error", "Not a branch-rep session"));
        }
        CreditApplication application = applications.findById(applicationId).orElse(null);
        if (application == null || !java.util.Objects.equals(
                rep.getPartnerId(), application.getAssignedPartnerId())) {
            // Same 404-not-403 rule as elsewhere: confirming it exists would
            // reveal that another branch holds it.
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("error", "Application not found"));
        }
        try {
            return action.apply(application);
        } catch (CreditApplicationService.TransitionException e) {
            return CreditApplicationController.toResponse(e);
        }
    }

    // ---------------------------------------------------------------- shared

    private ResponseEntity<?> serve(LoanDocument document) {
        byte[] bytes = documents.contentOf(document);
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType(document.getContentType()))
                // `attachment` so a PDF or image can never be rendered inline
                // in our own origin, and the filename is quoted because it is
                // user-supplied text.
                .header("Content-Disposition",
                        "attachment; filename=\"" + document.getFilename().replace("\"", "") + "\"")
                .body(bytes);
    }

    private void audit(String userId, String action, HttpServletRequest request) {
        auditLogRepository.save(AuditLog.of(userId, action, request.getRequestURI(), ClientIp.of(request)));
    }

    /** Exposed for the frontend so it can show limits before an upload fails. */
    @GetMapping("/api/v2/sih/documents/limits")
    public Map<String, Object> limits() {
        return Map.of(
                "maxBytes", LoanDocumentService.MAX_DOCUMENT_BYTES,
                "maxPerApplication", LoanDocumentService.MAX_DOCUMENTS_PER_APPLICATION,
                "acceptedTypes", List.of("application/pdf", "image/jpeg", "image/png"));
    }
}
