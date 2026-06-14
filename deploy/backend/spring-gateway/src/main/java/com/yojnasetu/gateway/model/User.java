package com.yojnasetu.gateway.model;

import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;

/**
 * Auth identity only — per CLAUDE.md's `users` collection. OTP-first, no
 * password field: PRANJAL_HANDOFF.md's OTP flow issues a JWT after phone
 * verification, there's nothing to hash-and-compare here.
 */
@Document(collection = "users")
@Data
@NoArgsConstructor
public class User {

    @Id
    private String id;

    /** E.164 format: +919876543210 */
    @Indexed(unique = true)
    private String phone;

    /** CITIZEN | CSC_OPERATOR | ADMIN */
    private String role = "CITIZEN";

    /** Preferred state, 2-char code e.g. UP, MH */
    private String state;

    /** Preferred language, e.g. hi, ta, bn */
    private String language;

    private Integer otpFailCount = 0;
    private LocalDateTime otpLockedUntil;

    private LocalDateTime createdAt;
    private LocalDateTime lastLoginAt;
}
