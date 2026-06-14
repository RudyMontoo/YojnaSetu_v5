package com.yojnasetu.gateway.model;

import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;

/**
 * Per CLAUDE.md's `otp_sessions` collection — TTL 10 minutes. `expiresAt`
 * carries the annotation itself: `expireAfterSeconds = 0` tells MongoDB's
 * TTL monitor to delete the document once the current time passes the
 * field's own value (i.e. the field IS the absolute expiry instant, not an
 * offset from document creation).
 */
@Document(collection = "otp_sessions")
@Data
@NoArgsConstructor
public class OtpSession {

    @Id
    private String id;

    @Indexed(unique = true)
    private String phone;

    /** BCrypt hash of the 6-digit OTP — never store the raw OTP. */
    private String otpHash;

    private Integer attemptCount = 0;

    @Indexed(name = "expiresAt_ttl", expireAfterSeconds = 0)
    private LocalDateTime expiresAt;
}
