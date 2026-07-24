package com.yojnasetu.gateway.model;

import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;

/**
 * A verified helper's login identity for the SEPARATE helper portal. Distinct
 * from the citizen `users` collection: helpers don't use OTP — they get an
 * admin-issued helperId + password. Created only when an admin approves a
 * HelperApplication.
 */
@Document(collection = "helpers")
@Data
@NoArgsConstructor
public class Helper {

    @Id
    private String id;

    /** Admin-issued login username, e.g. "HLP-7F3A9". */
    @Indexed(unique = true)
    private String helperId;

    /** BCrypt hash of the issued password — never the raw password. */
    private String passwordHash;

    private String name;
    private String phone;

    /** The HelperApplication this was minted from, and the citizen userId behind it. */
    private String applicationId;
    private String citizenUserId;

    /** Admin can deactivate a helper without deleting them. */
    private boolean active = true;

    /** True until the helper changes the admin-issued temp password. The portal
     *  forces a reset on first login. */
    private boolean mustResetPassword = true;

    private LocalDateTime createdAt;
    private LocalDateTime lastLoginAt;
}
