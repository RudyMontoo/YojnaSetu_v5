package com.yojnasetu.gateway.credit;

import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;

/**
 * One citizen's attempt to link their DigiLocker account to a credit
 * application, via DigiLocker's OAuth 2.0 Partner API.
 *
 * Doubles as the OAuth CSRF nonce store: {@link #state} is generated when the
 * authorize URL is built and consumed exactly once at the callback, rather
 * than trusting a bare `code` query parameter an attacker could replay
 * against a different logged-in session. {@link #status} moving from
 * "pending" to "linked" IS the single-use guard — {@code DigiLockerService}
 * refuses to process a callback against a record that isn't still "pending".
 *
 * No DigiLocker Partner API credentials are configured in this deployment as
 * of this writing (see {@code DigiLockerService#isConfigured}), so nothing
 * ever reaches "linked" here yet — same honest-gap posture as
 * {@code AadhaarOfflineEkycService}'s UIDAI certificate. This class and its
 * service exist so the integration is ready to switch on the day real
 * partner credentials land, not to claim the integration works today.
 */
@Document(collection = "digilocker_links")
@Data
@NoArgsConstructor
public class DigiLockerLink {

    @Id
    private String id;

    @Indexed
    private String userId;

    private String applicationId;

    /** Single-use OAuth CSRF nonce — see class javadoc. */
    @Indexed(unique = true)
    private String state;

    /** pending | linked | expired */
    private String status = "pending";

    /** Encrypted at rest, same as every other credential this platform stores. */
    private String accessToken;

    /** DigiLocker's own opaque subject identifier for this citizen — never the raw Aadhaar. */
    private String digilockerUid;

    private LocalDateTime createdAt;
    private LocalDateTime linkedAt;
    private LocalDateTime tokenExpiresAt;
}
