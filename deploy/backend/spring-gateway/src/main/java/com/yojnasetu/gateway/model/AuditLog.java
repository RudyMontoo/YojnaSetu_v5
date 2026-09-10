package com.yojnasetu.gateway.model;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;

/**
 * Per CLAUDE.md: append-only, never update or delete. No PII here — no
 * name, phone, or Aadhaar pattern in this collection, ever.
 */
@Document(collection = "audit_logs")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class AuditLog {

    @Id
    private String id;

    private String userId;

    /** profile_read | profile_write | scheme_search | otp_send | otp_verify_fail | delete_request | consent_given */
    private String action;

    private String endpoint;
    private String ip;
    private LocalDateTime at;

    /**
     * The application this action touched, when it touched one. Null for
     * everything else, which is most of this collection.
     *
     * Added so a citizen can be shown who opened their file. The endpoint
     * string already contains the id, but answering "who read my documents"
     * by regex-scanning an append-only log that only grows is the kind of
     * query that works in a demo and times out in a year — and this question
     * is one an applicant is entitled to a fast, exact answer to.
     */
    @Indexed
    private String applicationId;

    public static AuditLog of(String userId, String action, String endpoint, String ip) {
        return new AuditLog(null, userId, action, endpoint, ip, LocalDateTime.now(), null);
    }

    /** Same, for an action against a specific loan application. */
    public static AuditLog forApplication(String userId, String action, String endpoint,
                                          String ip, String applicationId) {
        return new AuditLog(null, userId, action, endpoint, ip, LocalDateTime.now(), applicationId);
    }
}
