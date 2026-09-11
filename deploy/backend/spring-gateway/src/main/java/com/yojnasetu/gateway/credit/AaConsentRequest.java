package com.yojnasetu.gateway.credit;

import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;

/**
 * One Account Aggregator consent request — the ReBIT/Sahamati AA network
 * flow for pulling bank-statement data to verify a citizen's declared
 * income, as an FIU (Financial Information User).
 *
 * NO AA/FIU CREDENTIALS ARE CONFIGURED IN THIS DEPLOYMENT — see
 * {@code AccountAggregatorService}'s class javadoc for what that does and
 * does not mean. This record only carries the consent REQUEST/STATUS
 * lifecycle (`POST /Consent`, `GET /Consent/handle/{handle}` in the AA
 * spec); it deliberately does not carry fetched financial data. Actually
 * pulling FI data (`POST /FI/request` + `GET /FI/fetch/{sessionId}`)
 * requires an ECDH key-exchange + AES-GCM decryption step defined in the AA
 * spec that this module does not implement — shipping that crypto without a
 * real AA counterparty to validate it against is a correctness and security
 * risk worse than the honest gap, so {@code AccountAggregatorService}
 * refuses that call outright rather than guessing at it.
 */
@Document(collection = "aa_consent_requests")
@Data
@NoArgsConstructor
public class AaConsentRequest {

    @Id
    private String id;

    @Indexed
    private String userId;

    private String applicationId;

    /** The citizen's Account Aggregator handle, e.g. "9999999999@onemoney". */
    private String vua;

    /** AA gateway's handle for this request, returned by POST /Consent. */
    @Indexed(unique = true)
    private String consentHandle;

    /** Only present once the citizen has approved in their AA app. */
    private String consentId;

    /** pending | approved | rejected | revoked | expired */
    private String status = "pending";

    /**
     * True when this consent was produced by demo simulation rather than a
     * real Account Aggregator — see {@link DigiLockerLink#isSimulated()} for
     * why this is persisted rather than only displayed.
     */
    private boolean simulated;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
