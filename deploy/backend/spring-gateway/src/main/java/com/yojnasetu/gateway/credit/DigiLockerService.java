package com.yojnasetu.gateway.credit;

import com.yojnasetu.gateway.credit.CreditApplicationService.Failure;
import com.yojnasetu.gateway.credit.CreditApplicationService.TransitionException;
import com.yojnasetu.gateway.security.FieldEncryptionService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.reactive.function.client.WebClient;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.time.LocalDateTime;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * DigiLocker Partner API (OAuth 2.0 authorization-code flow) — pulls a
 * citizen's own issued documents (income/caste certificate, education
 * marksheet, etc.) directly from DigiLocker instead of asking them to
 * photograph and upload one.
 *
 * NO DIGILOCKER PARTNER CREDENTIALS ARE CONFIGURED IN THIS DEPLOYMENT. This
 * class is built and wired end-to-end against DigiLocker's published Partner
 * API so it is ready to switch on the moment {@code DIGILOCKER_CLIENT_ID}/
 * {@code DIGILOCKER_CLIENT_SECRET} exist (a business registration on the
 * DigiLocker Partner Portal, not something this codebase can obtain on its
 * own) — but it has never been exercised against DigiLocker's real servers,
 * because doing so requires exactly those credentials. Treat the request/
 * response shapes here as "implemented to spec", not "verified live", until
 * someone runs it against a real partner sandbox. {@link #isConfigured()} is
 * what keeps this honest: every entry point refuses outright rather than
 * silently no-op'ing when credentials are absent, same convention as
 * {@code AadhaarOfflineEkycService}'s UIDAI certificate gate.
 *
 * {@link VerificationMode#DIGILOCKER} stays {@code isAvailable() == false}
 * even after this class exists — flipping that is a deliberate manual step
 * for once this has actually been run against a live DigiLocker sandbox and
 * confirmed working, not something that should happen automatically because
 * the code compiles.
 */
@Service
public class DigiLockerService {

    private static final Logger LOG = LoggerFactory.getLogger(DigiLockerService.class);
    private static final SecureRandom RANDOM = new SecureRandom();

    private final DigiLockerLinkRepository links;
    private final ConsentService consents;
    private final FieldEncryptionService encryption;
    private final WebClient client;

    private final String clientId;
    private final String clientSecret;
    private final String redirectUri;
    private final String baseUrl;

    /**
     * Demo simulation — walks the whole DigiLocker journey with canned data so
     * it can be shown end to end without partner credentials.
     *
     * A field-injected @Value rather than a constructor parameter on purpose:
     * it stays false in the unit tests (which build this class directly with
     * `new`), so every existing test still exercises the real, un-simulated
     * behaviour without being rewritten.
     *
     * Defaults to false and is deliberately NOT set anywhere in
     * deploy/azure/deploy.sh — a real deployment cannot accidentally serve
     * simulated verifications. Everything it produces is marked
     * {@code simulated: true} in both the response and the stored record.
     */
    @Value("${app.demo.simulate-integrations:false}")
    private boolean simulate;

    // Explicit @Autowired: this class also has a package-private constructor
    // (below, for test injection of a fake WebClient) — once a class has more
    // than one constructor, Spring stops auto-detecting the sole public one
    // for injection and instead tries a no-arg constructor, which doesn't
    // exist here. Confirmed live: without this, the app fails to boot
    // entirely with "No default constructor found" the moment this bean is
    // reached, even though every unit test passes (tests construct this
    // class directly with `new`, bypassing Spring, so they never hit it).
    @Autowired
    public DigiLockerService(DigiLockerLinkRepository links,
                             ConsentService consents,
                             FieldEncryptionService encryption,
                             @Value("${app.digilocker.client-id:}") String clientId,
                             @Value("${app.digilocker.client-secret:}") String clientSecret,
                             @Value("${app.digilocker.redirect-uri:}") String redirectUri,
                             @Value("${app.digilocker.base-url:https://digilocker.meripehchaan.gov.in}") String baseUrl) {
        this(links, consents, encryption, clientId, clientSecret, redirectUri, baseUrl,
                WebClient.builder().baseUrl(baseUrl).build());
    }

    /** Package-private: lets tests inject a WebClient wired to a fake ExchangeFunction. */
    DigiLockerService(DigiLockerLinkRepository links, ConsentService consents, FieldEncryptionService encryption,
                      String clientId, String clientSecret, String redirectUri, String baseUrl, WebClient client) {
        this.links = links;
        this.consents = consents;
        this.encryption = encryption;
        this.clientId = clientId;
        this.clientSecret = clientSecret;
        this.redirectUri = redirectUri;
        this.baseUrl = baseUrl;
        this.client = client;
    }

    /**
     * Reported after construction, not inside it: {@link #simulate} is a
     * field-injected @Value, so during the constructor it is still false and a
     * status line logged there would claim "not configured" even when demo
     * simulation is switched on — which is exactly the wrong thing to tell
     * someone who is trying to verify that it IS on.
     */
    @jakarta.annotation.PostConstruct
    void logStatus() {
        if (simulate) {
            LOG.warn("DigiLocker is running in DEMO SIMULATION mode — responses are canned and marked "
                    + "simulated:true. Never enable app.demo.simulate-integrations in production.");
        } else if (!isConfigured()) {
            LOG.info("DigiLocker Partner API credentials not configured — DigiLocker linking is disabled.");
        }
    }

    /** True when the real integration has credentials, OR demo simulation is on. */
    public boolean isConfigured() {
        return simulate || (notBlank(clientId) && notBlank(clientSecret) && notBlank(redirectUri));
    }

    /** Whether responses from this service are simulated demo data. */
    public boolean isSimulated() {
        return simulate;
    }

    /** Package-private: lets tests exercise the simulated path. */
    void enableSimulationForTest() {
        this.simulate = true;
    }

    public record AuthorizeUrl(String url, String state) {
    }

    /**
     * Starts a link attempt: requires DIGILOCKER_FETCH consent already
     * granted for this application, then records a single-use state nonce
     * and returns the URL to redirect the citizen's browser to.
     */
    public AuthorizeUrl startLink(String userId, String applicationId) {
        if (!isConfigured()) {
            throw new TransitionException(Failure.BAD_REQUEST,
                    "DigiLocker linking is not available in this deployment yet");
        }
        consents.requireConsent(userId, ConsentPurpose.DIGILOCKER_FETCH, applicationId);

        String state = randomToken(24);
        DigiLockerLink link = new DigiLockerLink();
        link.setUserId(userId);
        link.setApplicationId(applicationId);
        link.setState(state);
        link.setStatus("pending");
        link.setCreatedAt(LocalDateTime.now());
        links.save(link);

        if (simulate) {
            // Point the browser back at our own callback instead of DigiLocker's
            // servers, so the round trip completes locally and the demo shows
            // the real sequence of screens rather than a dead end.
            return new AuthorizeUrl("/digilocker-demo?state=" + encode(state), state);
        }

        String url = baseUrl + "/public/oauth2/1/authorize"
                + "?response_type=code"
                + "&client_id=" + encode(clientId)
                + "&redirect_uri=" + encode(redirectUri)
                + "&state=" + encode(state);
        return new AuthorizeUrl(url, state);
    }

    /**
     * Completes the flow: DigiLocker redirects the browser here with
     * {@code code}+{@code state}. Refuses to process a state that isn't
     * still "pending" — the single-use guard against a replayed callback
     * (see {@link DigiLockerLink} javadoc).
     */
    public DigiLockerLink completeLink(String state, String code) {
        if (!isConfigured()) {
            throw new TransitionException(Failure.BAD_REQUEST,
                    "DigiLocker linking is not available in this deployment yet");
        }
        DigiLockerLink link = links.findByState(state)
                .orElseThrow(() -> new TransitionException(Failure.NOT_FOUND, "Unknown or expired link attempt"));
        if (!"pending".equals(link.getStatus())) {
            throw new TransitionException(Failure.CONFLICT, "This link attempt was already completed");
        }

        if (simulate) {
            // No token exchange — there is no real account on the other end.
            // The record is marked simulated so nothing downstream mistakes it
            // for a genuine DigiLocker link.
            link.setStatus("linked");
            link.setSimulated(true);
            link.setDigilockerUid("DEMO-SIMULATED");
            link.setLinkedAt(LocalDateTime.now());
            return links.save(link);
        }

        MultiValueMap<String, String> form = new LinkedMultiValueMap<>();
        form.add("code", code);
        form.add("grant_type", "authorization_code");
        form.add("client_id", clientId);
        form.add("client_secret", clientSecret);
        form.add("redirect_uri", redirectUri);

        Map<String, Object> response = client.post()
                .uri("/public/oauth2/1/token")
                .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                .body(org.springframework.web.reactive.function.BodyInserters.fromFormData(form))
                .retrieve()
                .bodyToMono(new org.springframework.core.ParameterizedTypeReference<Map<String, Object>>() {})
                .block();

        if (response == null || response.get("access_token") == null) {
            throw new TransitionException(Failure.BAD_REQUEST, "DigiLocker did not return an access token");
        }

        String accessToken = String.valueOf(response.get("access_token"));
        Object expiresIn = response.get("expires_in");

        link.setAccessToken(encryption.encrypt(accessToken));
        link.setDigilockerUid(response.get("digilockerid") == null ? null : String.valueOf(response.get("digilockerid")));
        link.setStatus("linked");
        link.setLinkedAt(LocalDateTime.now());
        if (expiresIn instanceof Number n) {
            link.setTokenExpiresAt(LocalDateTime.now().plusSeconds(n.longValue()));
        }
        return links.save(link);
    }

    public Optional<DigiLockerLink> linkedFor(String applicationId) {
        return links.findFirstByApplicationIdAndStatusOrderByCreatedAtDesc(applicationId, "linked");
    }

    public record IssuedDocument(String name, String type, String docType, String uri, String mime, String date) {
    }

    /**
     * The canned document set the demo shows. Chosen to match what an SC
     * credit applicant would really hold in DigiLocker, so the walkthrough is
     * representative — but every caller labels these as simulated.
     */
    static final List<IssuedDocument> SIMULATED_DOCUMENTS = List.of(
            new IssuedDocument("Aadhaar Card", "certificate", "ADHAR", "in.gov.uidai-ADHAR-demo", "application/pdf", "2026-01-12"),
            new IssuedDocument("Caste Certificate (SC)", "certificate", "CASTE", "in.gov.rev-CASTE-demo", "application/pdf", "2026-02-03"),
            new IssuedDocument("Income Certificate", "certificate", "INCME", "in.gov.rev-INCME-demo", "application/pdf", "2026-02-03"),
            new IssuedDocument("Class X Marksheet", "marksheet", "MARKS", "in.gov.cbse-MARKS-demo", "application/pdf", "2019-05-28"));

    /** GET .../files/issued — the citizen's list of DigiLocker-issued documents. */
    public List<IssuedDocument> fetchIssuedDocuments(String applicationId) {
        DigiLockerLink link = requireLinked(applicationId);
        if (simulate) {
            return SIMULATED_DOCUMENTS;
        }
        String accessToken = encryption.decrypt(link.getAccessToken());

        Map<String, Object> response = client.get()
                .uri("/public/oauth2/1/files/issued")
                .header(HttpHeaders.AUTHORIZATION, "Bearer " + accessToken)
                .retrieve()
                .bodyToMono(new org.springframework.core.ParameterizedTypeReference<Map<String, Object>>() {})
                .block();

        Object items = response == null ? null : response.get("items");
        if (!(items instanceof List<?> list)) {
            return List.of();
        }
        return list.stream()
                .filter(Map.class::isInstance)
                .map(o -> (Map<?, ?>) o)
                .map(m -> new IssuedDocument(
                        str(m, "name"), str(m, "type"), str(m, "doctype"), str(m, "uri"), str(m, "mime"), str(m, "date")))
                .toList();
    }

    /** GET .../file/{uri} — the raw bytes of one specific issued document. */
    public byte[] fetchDocument(String applicationId, String documentUri) {
        DigiLockerLink link = requireLinked(applicationId);
        String accessToken = encryption.decrypt(link.getAccessToken());

        return client.get()
                .uri("/public/oauth2/1/file/{uri}", documentUri)
                .header(HttpHeaders.AUTHORIZATION, "Bearer " + accessToken)
                .retrieve()
                .bodyToMono(byte[].class)
                .block();
    }

    private DigiLockerLink requireLinked(String applicationId) {
        return linkedFor(applicationId)
                .orElseThrow(() -> new TransitionException(Failure.CONFLICT,
                        "No DigiLocker account is linked to this application yet"));
    }

    private static String str(Map<?, ?> m, String key) {
        Object v = m.get(key);
        return v == null ? null : String.valueOf(v);
    }

    private static boolean notBlank(String s) {
        return s != null && !s.isBlank();
    }

    private static String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }

    private static String randomToken(int len) {
        byte[] bytes = new byte[len];
        RANDOM.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }
}
