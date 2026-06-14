package com.yojnasetu.gateway.model;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
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

    public static AuditLog of(String userId, String action, String endpoint, String ip) {
        return new AuditLog(null, userId, action, endpoint, ip, LocalDateTime.now());
    }
}
