package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.model.AuditLog;
import com.yojnasetu.gateway.repository.AuditLogRepository;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * "Who has touched my application, and what did they do?" — answered for the
 * person the file is about.
 *
 * The system already recorded all of this: authorizations, status decisions,
 * document uploads, document reads. What it never did was show any of it to
 * the applicant. An audit trail only the operator can read protects the
 * operator; the person whose caste certificate and income are in that file
 * learns nothing about who opened it. In an assisted flow — where the whole
 * design depends on someone else handling your documents — that asymmetry is
 * the problem, not a detail of it.
 *
 * This is a read model over existing records, not a new log. Nothing here is
 * written; if an event is missing from this view it is missing from the
 * system, which is the correct place to fix it.
 */
@Service
public class FileAccessService {

    private final AssistAuthorizationRepository authorizations;
    private final LoanDocumentRepository documents;
    private final AuditLogRepository auditLogs;
    private final BranchRepRepository helpers;

    public FileAccessService(AssistAuthorizationRepository authorizations,
                             LoanDocumentRepository documents,
                             AuditLogRepository auditLogs,
                             BranchRepRepository helpers) {
        this.authorizations = authorizations;
        this.documents = documents;
        this.auditLogs = auditLogs;
        this.helpers = helpers;
    }

    /**
     * One entry in the citizen's activity list.
     *
     * @param at      when it happened
     * @param actorId the acting principal's id, for a misuse report to reference
     * @param actor   who they are, in words the applicant can recognise
     * @param action  a stable machine key the UI localizes
     * @param detail  optional human context, already free of anything sensitive
     */
    public record AccessEvent(LocalDateTime at, String actorId, String actor,
                              String action, String detail) {
    }

    /**
     * Everything that happened to this application, newest first.
     *
     * Assembled from four sources rather than one, because no single one of
     * them knows the whole story: authorizations know who was let in, the
     * status history knows who decided, the documents know who added, and the
     * audit log knows who looked. A list built from only the first three would
     * quietly omit reads, which is the event an applicant most wants to know
     * about.
     */
    public List<AccessEvent> timelineFor(CreditApplication application) {
        List<AccessEvent> events = new ArrayList<>();

        for (AssistAuthorization authorization : authorizations
                .findByApplicationIdOrderByGrantedAtDesc(application.getId())) {
            String who = describeHelper(authorization);
            events.add(new AccessEvent(authorization.getGrantedAt(), authorization.getHelperId(),
                    who, "assist_granted", "You allowed them to help with this application"));
            if (authorization.getRevokedAt() != null) {
                events.add(new AccessEvent(authorization.getRevokedAt(), authorization.getHelperId(),
                        who, "assist_revoked", "You withdrew their access"));
            }
        }

        if (application.getStatusHistory() != null) {
            for (CreditApplication.StatusEntry entry : application.getStatusHistory()) {
                events.add(new AccessEvent(entry.getAt(), entry.getByUserId(),
                        describeActor(entry.getByUserId(), entry.getByRole()),
                        "status_changed",
                        entry.getStatus() == null ? null : entry.getStatus().wireName()));
            }
        }

        for (LoanDocument document : documents
                .findByApplicationIdOrderByUploadedAtDesc(application.getId())) {
            events.add(new AccessEvent(document.getUploadedAt(), document.getUploadedByUserId(),
                    describeActor(document.getUploadedByUserId(), document.getUploadedByRole()),
                    "document_uploaded", document.getFilename()));
        }

        for (AuditLog log : auditLogs.findByApplicationIdOrderByAtDesc(application.getId())) {
            // Uploads and deletes are already covered above, from the document
            // records themselves, which carry more detail than the log line.
            // Reads exist nowhere else, and are the point of including this.
            if (!isReadAction(log.getAction())) {
                continue;
            }
            events.add(new AccessEvent(log.getAt(), log.getUserId(),
                    describeActor(log.getUserId(), null), "document_viewed", null));
        }

        // Nulls sort last rather than throwing: a record with no timestamp is a
        // data problem worth showing, not a reason to fail the whole view.
        events.sort(Comparator.comparing(AccessEvent::at,
                Comparator.nullsLast(Comparator.reverseOrder())));
        return events;
    }

    private static boolean isReadAction(String action) {
        return "loan_document_read".equals(action) || "loan_document_read_by_rep".equals(action);
    }

    private static String describeHelper(AssistAuthorization authorization) {
        String name = authorization.getHelperName() == null ? "A helper" : authorization.getHelperName();
        String type = authorization.getHelperType() == null ? null : authorization.getHelperType().label();
        String org = authorization.getHelperOrganisation();
        StringBuilder description = new StringBuilder(name);
        if (type != null) {
            description.append(" (").append(type);
            if (org != null && !org.isBlank()) {
                description.append(", ").append(org);
            }
            description.append(')');
        }
        return description.toString();
    }

    /**
     * Names the actor where we can, and says plainly what we cannot.
     *
     * The citizen themselves is "You". A staff account is looked up so the
     * list reads "R. Devi (CSC operator)" rather than a document id — a list
     * of opaque ids answers the question in form only. An id that resolves to
     * nothing becomes "A staff member", never a raw id: showing internal
     * identifiers to an applicant is noise to them and a small leak to anyone
     * else reading over their shoulder.
     */
    private String describeActor(String userId, String role) {
        if (userId == null) {
            return "System";
        }
        if ("CITIZEN".equals(role)) {
            return "You";
        }
        Optional<BranchRep> staff = helpers.findById(userId);
        if (staff.isPresent()) {
            BranchRep person = staff.get();
            String label = person.getRepType().label();
            String org = person.getOrganisation() != null && !person.getOrganisation().isBlank()
                    ? person.getOrganisation() : person.getPartnerName();
            return person.getName() + " (" + label
                    + (org == null || org.isBlank() ? "" : ", " + org) + ")";
        }
        return role == null ? "A staff member" : "A staff member (" + role + ")";
    }

    /** Just the helpers, for the simpler "who helped you" question. */
    public List<Map<String, Object>> helpersFor(String applicationId) {
        return authorizations.findByApplicationIdOrderByGrantedAtDesc(applicationId).stream()
                .map(a -> {
                    Map<String, Object> row = new java.util.LinkedHashMap<>();
                    row.put("helperId", a.getHelperId());
                    row.put("name", a.getHelperName());
                    row.put("type", a.getHelperType() == null ? null : a.getHelperType().wireName());
                    row.put("typeLabel", a.getHelperType() == null ? null : a.getHelperType().label());
                    row.put("organisation", a.getHelperOrganisation());
                    row.put("grantedAt", a.getGrantedAt());
                    row.put("revokedAt", a.getRevokedAt());
                    row.put("active", a.isActive());
                    return row;
                })
                .toList();
    }
}
