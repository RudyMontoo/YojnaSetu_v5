package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.credit.CreditApplicationService.Failure;
import com.yojnasetu.gateway.credit.CreditApplicationService.TransitionException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.Optional;

/**
 * Account Aggregator consent lifecycle — verifying a citizen's declared
 * income against their real bank-statement data, with their explicit,
 * revocable consent, instead of taking a self-declared figure at face value.
 *
 * NO AA/FIU CREDENTIALS ARE CONFIGURED IN THIS DEPLOYMENT. Two separate
 * honesty gaps, not one, and they matter differently:
 *
 *   1. Credentials. {@link #isConfigured()} is false until an AA API key
 *      exists — a business registration this codebase cannot obtain on its
 *      own, same as DigiLocker's Partner Portal signup. Every entry point
 *      below refuses outright rather than silently no-op'ing.
 *
 *   2. Scope. This class talks to a TSP's (Technology Service Provider —
 *      e.g. Setu, Finvu, Anumati) own simplified REST API for the CONSENT
 *      request/status lifecycle, NOT the raw ReBIT Account Aggregator
 *      network spec directly. Talking to the AA network itself requires FIU
 *      registration with Sahamati plus per-request JWS-signed payloads under
 *      a registered key pair — real PKI infrastructure most platforms this
 *      size delegate to a TSP rather than implement themselves, and that
 *      delegation is the realistic integration shape for this deployment.
 *      Even granting that, actually FETCHING the financial data once consent
 *      is approved (`FI/request` + `FI/fetch`) needs an ECDH key exchange
 *      and AES-GCM decryption per the AA spec — {@link #fetchFinancialData}
 *      deliberately throws rather than guess at that crypto with no real
 *      counterparty to validate it against; landing that wrong would either
 *      silently corrupt income data or look like a working feature that
 *      isn't. The consent request/status lifecycle below has none of that
 *      risk — it's a plain REST call — so it's built to spec.
 */
@Service
public class AccountAggregatorService {

    private static final Logger LOG = LoggerFactory.getLogger(AccountAggregatorService.class);

    private final AaConsentRequestRepository consentRequests;
    private final ConsentService consents;
    private final WebClient client;

    private final String apiKey;

    /**
     * Demo simulation — see {@code DigiLockerService.simulate} for the full
     * reasoning. Field-injected so the existing unit tests (which construct
     * this class directly) keep exercising the real path, default false, and
     * never set by deploy.sh.
     *
     * Note this simulates the CONSENT lifecycle only. {@link #fetchFinancialData}
     * still refuses even with simulation on: pretending to have decrypted real
     * bank statements would fabricate the citizen's income, which is exactly
     * the figure the whole eligibility decision turns on.
     */
    @Value("${app.demo.simulate-integrations:false}")
    private boolean simulate;

    // See DigiLockerService's identical constructor for why @Autowired is
    // required here: a second (test-only) constructor exists below, and
    // that alone stops Spring from auto-selecting the public constructor.
    @Autowired
    public AccountAggregatorService(AaConsentRequestRepository consentRequests,
                                    ConsentService consents,
                                    @Value("${app.account-aggregator.api-key:}") String apiKey,
                                    @Value("${app.account-aggregator.base-url:}") String baseUrl) {
        this(consentRequests, consents, apiKey, baseUrl, WebClient.builder().baseUrl(
                (baseUrl == null || baseUrl.isBlank()) ? "http://unconfigured.invalid" : baseUrl).build());
    }

    /** Package-private: lets tests inject a WebClient wired to a fake ExchangeFunction. */
    AccountAggregatorService(AaConsentRequestRepository consentRequests, ConsentService consents,
                             String apiKey, String baseUrl, WebClient client) {
        this.consentRequests = consentRequests;
        this.consents = consents;
        this.apiKey = apiKey;
        this.client = client;
    }

    /** See DigiLockerService.logStatus — reported post-injection so the line reflects the real flag. */
    @jakarta.annotation.PostConstruct
    void logStatus() {
        if (simulate) {
            LOG.warn("Account Aggregator is running in DEMO SIMULATION mode — the consent lifecycle is "
                    + "canned and marked simulated:true, and fetching real financial data still refuses. "
                    + "Never enable app.demo.simulate-integrations in production.");
        } else if (!isConfigured()) {
            LOG.info("Account Aggregator API key/base URL not configured — income verification via AA is disabled.");
        }
    }

    /** True when a real TSP key is configured, OR demo simulation is on. */
    public boolean isConfigured() {
        return simulate || notBlank(apiKey);
    }

    /** Whether responses from this service are simulated demo data. */
    public boolean isSimulated() {
        return simulate;
    }

    /** Package-private: lets tests exercise the simulated path. */
    void enableSimulationForTest() {
        this.simulate = true;
    }

    /**
     * Creates a consent request with the citizen's AA handle (VUA) — the
     * citizen approves it out-of-band in their own AA app, we only poll
     * status here.
     */
    public AaConsentRequest createConsentRequest(String userId, String applicationId, String vua) {
        if (!isConfigured()) {
            throw new TransitionException(Failure.BAD_REQUEST,
                    "Account Aggregator verification is not available in this deployment yet");
        }
        if (vua == null || vua.isBlank()) {
            throw new TransitionException(Failure.BAD_REQUEST, "Your Account Aggregator handle (VUA) is required");
        }
        consents.requireConsent(userId, ConsentPurpose.ACCOUNT_AGGREGATOR_FETCH, applicationId);

        if (simulate) {
            AaConsentRequest simulated = new AaConsentRequest();
            simulated.setUserId(userId);
            simulated.setApplicationId(applicationId);
            simulated.setVua(vua);
            simulated.setConsentHandle("DEMO-" + java.util.UUID.randomUUID());
            // Straight to approved: the citizen's approval happens in their own
            // AA app, which does not exist in a demo, so waiting on "pending"
            // forever would just look broken.
            simulated.setStatus("approved");
            simulated.setConsentId("DEMO-CONSENT");
            simulated.setSimulated(true);
            simulated.setCreatedAt(LocalDateTime.now());
            simulated.setUpdatedAt(LocalDateTime.now());
            return consentRequests.save(simulated);
        }

        Map<String, Object> body = Map.of(
                "vua", vua,
                "purpose", "Income verification for SC concessional credit application",
                "fiTypes", java.util.List.of("DEPOSIT"),
                "consentType", "PERIODIC",
                "customerId", applicationId);

        Map<String, Object> response = client.post()
                .uri("/consents")
                .header(HttpHeaders.AUTHORIZATION, "Bearer " + apiKey)
                .bodyValue(body)
                .retrieve()
                .bodyToMono(new org.springframework.core.ParameterizedTypeReference<Map<String, Object>>() {})
                .block();

        if (response == null || response.get("id") == null) {
            throw new TransitionException(Failure.BAD_REQUEST,
                    "Account Aggregator did not return a consent handle");
        }

        AaConsentRequest request = new AaConsentRequest();
        request.setUserId(userId);
        request.setApplicationId(applicationId);
        request.setVua(vua);
        request.setConsentHandle(String.valueOf(response.get("id")));
        request.setStatus("pending");
        request.setCreatedAt(LocalDateTime.now());
        request.setUpdatedAt(LocalDateTime.now());
        return consentRequests.save(request);
    }

    /** Polls the TSP for the citizen's approve/reject decision. */
    public AaConsentRequest refreshStatus(String consentHandle) {
        if (!isConfigured()) {
            throw new TransitionException(Failure.BAD_REQUEST,
                    "Account Aggregator verification is not available in this deployment yet");
        }
        AaConsentRequest request = consentRequests.findByConsentHandle(consentHandle)
                .orElseThrow(() -> new TransitionException(Failure.NOT_FOUND, "Unknown consent request"));

        if (simulate) {
            return request;  // already approved at creation; nothing to poll
        }

        Map<String, Object> response = client.get()
                .uri("/consents/{id}", consentHandle)
                .header(HttpHeaders.AUTHORIZATION, "Bearer " + apiKey)
                .retrieve()
                .bodyToMono(new org.springframework.core.ParameterizedTypeReference<Map<String, Object>>() {})
                .block();

        if (response != null && response.get("status") != null) {
            request.setStatus(String.valueOf(response.get("status")).toLowerCase());
            if (response.get("consentId") != null) {
                request.setConsentId(String.valueOf(response.get("consentId")));
            }
            request.setUpdatedAt(LocalDateTime.now());
            request = consentRequests.save(request);
        }
        return request;
    }

    public Optional<AaConsentRequest> latestFor(String applicationId) {
        return consentRequests.findFirstByApplicationIdOrderByCreatedAtDesc(applicationId);
    }

    /**
     * Deliberately not implemented — see class javadoc, point 2. Approved
     * consent alone is not enough to safely pull and decrypt FI data; that
     * needs the AA spec's ECDH/AES-GCM exchange, which has never been run
     * against a real counterparty from this codebase.
     */
    public byte[] fetchFinancialData(String consentHandle) {
        throw new TransitionException(Failure.BAD_REQUEST,
                "Fetching and decrypting Account Aggregator financial data is not implemented in this "
                        + "deployment — the consent lifecycle above works, but FI data retrieval needs the AA "
                        + "spec's key-exchange/decryption step, which has not been built or verified against a "
                        + "real Account Aggregator.");
    }

    private static boolean notBlank(String s) {
        return s != null && !s.isBlank();
    }
}
