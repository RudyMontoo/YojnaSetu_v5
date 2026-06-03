# Yojna Setu — Pranjal's Backend Handoff Doc
> **From**: Rudra | **For**: Pranjal | **Version**: v3.0 (Updated Architecture)
> 
> Read this fully before touching the codebase. The project has evolved significantly from the basic version you last saw.

---

## What Changed Since You Last Worked On It

The project has been fully re-architected. Here's the delta:

| Before | Now |
|--------|-----|
| PostgreSQL for everything | **MongoDB Atlas** for citizen data + AI sessions. PostgreSQL removed. |
| Username + password login | **Phone OTP only** (no passwords — reduces attack surface) |
| JWT in JSON response body | **JWT in httpOnly cookies** (XSS-proof) |
| Stateless sessions | **Persistent conversation history** in MongoDB |
| No encryption | **AES-256 field encryption** on all PII before any DB write |
| Basic UserProfile model | **5-collection MongoDB schema** (citizen_profiles, schemes, applications, conversation_sessions, audit_logs) |

> [!IMPORTANT]
> The current `AuthController.java` uses username + password. This is being replaced with OTP. Do NOT build on top of the existing auth — replace it.

---

## Your Role (What Pranjal Owns)

You own the entire **Spring Boot data service layer**:

- MongoDB Atlas setup + schema + indexes
- All REST endpoints under `/api/v2/*`
- JWT auth (OTP flow, RS256 tokens, httpOnly cookies)
- Field-level PII encryption
- Rate limiting
- Internal service endpoints (called by Rudra's FastAPI — critical)
- DPDP erasure pipeline
- Audit logging

**Rudra owns**: `ai_service/` (FastAPI, Python). Do NOT touch that directory.

---

## Week 1 Deliverables (Must Be Done First — Rudra Is Blocked On These)

```
[ ] 1. MongoDB Atlas cluster live (Mumbai region)
[ ] 2. Spring Data MongoDB connected (replace spring-data-jpa)
[ ] 3. CitizenProfile MongoDB document model + repository
[ ] 4. OTP-based auth working (send + verify endpoints)
[ ] 5. JWT in httpOnly cookie (NOT in response body)
[ ] 6. Internal profile endpoint for FastAPI: GET /internal/profile/{userId}
```

Items 1, 3, and 6 are on the **critical path** — Rudra cannot start the AI persistence work without them.

---

## Step 1: pom.xml Changes

Remove PostgreSQL + JPA. Add MongoDB + rate limiting:

```xml
<!-- REMOVE these -->
<!-- spring-boot-starter-data-jpa -->
<!-- postgresql -->
<!-- flyway-core -->

<!-- ADD these -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-data-mongodb</artifactId>
</dependency>

<!-- Rate limiting -->
<dependency>
    <groupId>com.github.bucket4j</groupId>
    <artifactId>bucket4j-core</artifactId>
    <version>8.7.0</version>
</dependency>

<!-- Field encryption (Fernet / AES-256) -->
<dependency>
    <groupId>com.google.crypto.tink</groupId>
    <artifactId>tink</artifactId>
    <version>1.13.0</version>
</dependency>

<!-- Twilio (for OTP SMS) -->
<dependency>
    <groupId>com.twilio.sdk</groupId>
    <artifactId>twilio</artifactId>
    <version>10.1.0</version>
</dependency>
```

Keep: `spring-boot-starter-security`, `jjwt-*`, `spring-boot-starter-validation`, `lombok`, `spring-boot-starter-webflux`.

---

## Step 2: application-local.yml

```yaml
spring:
  data:
    mongodb:
      uri: ${MONGODB_URI}
      database: yojnasetu

jwt:
  private-key-path: ${JWT_PRIVATE_KEY_PATH}   # RSA private key for signing
  public-key-path: ${JWT_PUBLIC_KEY_PATH}      # RSA public key for verification
  access-token-expiry-minutes: 60
  refresh-token-expiry-days: 7

encryption:
  key: ${FIELD_ENCRYPTION_KEY}   # 32-byte base64 key — load from GCP Secret Manager in prod

twilio:
  account-sid: ${TWILIO_ACCOUNT_SID}
  auth-token: ${TWILIO_AUTH_TOKEN}
  from-number: ${TWILIO_FROM_NUMBER}
```

---

## Step 3: MongoDB Collections + Java Models

### Collection 1: `citizen_profiles`

```java
@Document(collection = "citizen_profiles")
@CompoundIndexes({
    @CompoundIndex(def = "{'state':1,'category':1,'isBpl':1}"),  // pre-filter for vector search
    @CompoundIndex(def = "{'userId':1}", unique = true)
})
@Data
@NoArgsConstructor
public class CitizenProfile {

    @Id
    private String id;

    @Indexed(unique = true)
    private String userId;           // matches users._id

    // AES-256 encrypted before write — decrypt after read
    private String name;
    private String dob;
    private String phone;

    private String gender;           // male | female | other
    private Long annualIncome;
    private String category;         // general | obc | sc | st
    private String occupation;       // farmer | student | daily_wage | self_employed | unemployed
    private Boolean isBpl;
    private Boolean isDisabled;
    private Integer disabilityPct;

    @Indexed
    private String state;            // 2-char: UP, MH, RJ, etc.
    private String district;
    private Boolean isRural;
    private Integer familySize;
    private Boolean hasLand;
    private Double landAreaAcres;

    private String aadhaarHash;      // SHA-256(aadhaar + salt) — NEVER the raw UID
    private List<String> verifiedDocs;   // ["aadhaar","pan","income_cert"]
    private Integer profileCompleteness; // 0-100, auto-calculated

    private LocalDateTime consentGivenAt;   // DPDP — must be set before first profile write
    private LocalDateTime updatedAt;
}
```

### Collection 2: `applications`

```java
@Document(collection = "applications")
@CompoundIndexes({
    @CompoundIndex(def = "{'userId':1,'status':1}"),
    @CompoundIndex(def = "{'userId':1,'schemeId':1}", unique = true)
})
@Data
@NoArgsConstructor
public class Application {

    @Id
    private String id;

    private String userId;
    private String schemeId;

    // Denormalized — avoids extra lookup on list view
    private String schemeCode;
    private String schemeName;

    // saved | in_progress | submitted | approved | rejected | disbursed
    private String status;

    @Builder.Default
    private List<StatusEntry> statusHistory = new ArrayList<>();

    private String externalAppId;   // govt portal reference number (nullable)
    private Integer eligibilityScore;

    private LocalDateTime appliedAt;
    private LocalDateTime lastStatusCheck;

    @Data
    @AllArgsConstructor
    public static class StatusEntry {
        private String status;
        private LocalDateTime at;
    }
}
```

### Collection 3: `audit_logs` (append-only — never update, never delete)

```java
@Document(collection = "audit_logs")
@Data
@NoArgsConstructor
public class AuditLog {

    @Id
    private String id;

    private String userId;

    // profile_read | profile_write | scheme_search | otp_send |
    // otp_verify_fail | delete_request | consent_given
    private String action;

    private String endpoint;
    private String ip;

    // No PII here — no name, phone, Aadhaar in this collection
    private LocalDateTime at;
}
```

### Collection 4: `users` (auth layer only)

```java
@Document(collection = "users")
@Data
@NoArgsConstructor
public class User {

    @Id
    private String id;

    @Indexed(unique = true)
    private String phone;            // E.164 format: +919876543210

    private String role;             // CITIZEN | CSC_OPERATOR | ADMIN

    private String state;            // preferred state
    private String language;         // preferred language: hi | ta | bn ...

    private Integer otpFailCount;    // for lockout logic
    private LocalDateTime otpLockedUntil;

    private LocalDateTime createdAt;
    private LocalDateTime lastLoginAt;
}
```

### Collection 5: `otp_sessions` (TTL 10 minutes)

```java
@Document(collection = "otp_sessions")
@Data
@NoArgsConstructor
public class OtpSession {

    @Id
    private String id;

    @Indexed(unique = true)
    private String phone;

    private String otpHash;          // bcrypt hash of 6-digit OTP — never store raw OTP
    private Integer attemptCount;

    @Indexed(expireAfterSeconds = 0)
    private LocalDateTime expiresAt; // set to createdAt + 10 minutes — MongoDB TTL deletes automatically
}
```

---

## Step 4: Auth Flow (OTP — Replace Existing AuthController Completely)

```
POST /api/v2/auth/otp/send
  Body: { "phone": "+919876543210" }
  - Validate E.164 format
  - Check rate limit: max 5 OTP/hour per phone (Bucket4j)
  - Check if phone is locked (otpFailCount >= 5 → 15-min lockout)
  - Generate 6-digit OTP
  - Hash OTP with bcrypt and save to otp_sessions (TTL 10 min)
  - Send SMS via Twilio
  - Log to audit_logs: action="otp_send"
  - Response: { "success": true, "expires_in": 600 }
  - Rate limit header: X-RateLimit-Remaining

POST /api/v2/auth/otp/verify
  Body: { "phone": "+919876543210", "otp": "482910" }
  - Find otp_sessions by phone
  - If not found → 401 (expired or never sent)
  - bcrypt.verify(otp, otp_sessions.otpHash)
  - If wrong → increment attemptCount, if >= 5 → lock user 15 min, log otp_verify_fail
  - If correct → create/fetch User document, delete otp_sessions doc
  - Generate RS256 JWT (access + refresh)
  - Set BOTH as httpOnly cookies:
      Set-Cookie: access_token=...; HttpOnly; Secure; SameSite=Strict; Max-Age=3600
      Set-Cookie: refresh_token=...; HttpOnly; Secure; SameSite=Strict; Max-Age=604800
  - Log: action="otp_verify_success"
  - Response body: { "success": true, "user": { "id", "phone", "role", "language" } }
  - DO NOT put the token in the response body

POST /api/v2/auth/refresh
  - Read refresh_token from httpOnly cookie (NO request body needed)
  - Validate JWT signature + expiry
  - Issue new access_token cookie
  - Response: { "success": true }

POST /api/v2/auth/logout
  - Clear both cookies (Set-Cookie with Max-Age=0)
  - Response: { "success": true }
```

> [!CAUTION]
> JWT must be in httpOnly cookies only. If you put it in the JSON response body, XSS can steal it. The current `AuthController.java` returns the token in the body — this must be changed.

---

## Step 5: Field Encryption (PII Protection)

All PII fields (`name`, `dob`, `phone`) must be encrypted with AES-256 **before** any MongoDB write and decrypted **after** any MongoDB read.

```java
@Service
public class FieldEncryptionService {

    private final SecretKey aesKey;

    public FieldEncryptionService(@Value("${encryption.key}") String base64Key) {
        byte[] keyBytes = Base64.getDecoder().decode(base64Key);
        this.aesKey = new SecretKeySpec(keyBytes, "AES");
    }

    public String encrypt(String plaintext) {
        if (plaintext == null) return null;
        try {
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            byte[] iv = new byte[12];
            new SecureRandom().nextBytes(iv);
            cipher.init(Cipher.ENCRYPT_MODE, aesKey, new GCMParameterSpec(128, iv));
            byte[] encrypted = cipher.doFinal(plaintext.getBytes(StandardCharsets.UTF_8));
            // prepend IV to ciphertext for storage
            byte[] combined = new byte[iv.length + encrypted.length];
            System.arraycopy(iv, 0, combined, 0, iv.length);
            System.arraycopy(encrypted, 0, combined, iv.length, encrypted.length);
            return Base64.getEncoder().encodeToString(combined);
        } catch (Exception e) {
            throw new RuntimeException("Encryption failed", e);
        }
    }

    public String decrypt(String ciphertext) {
        if (ciphertext == null) return null;
        try {
            byte[] combined = Base64.getDecoder().decode(ciphertext);
            byte[] iv = Arrays.copyOfRange(combined, 0, 12);
            byte[] encrypted = Arrays.copyOfRange(combined, 12, combined.length);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, aesKey, new GCMParameterSpec(128, iv));
            return new String(cipher.doFinal(encrypted), StandardCharsets.UTF_8);
        } catch (Exception e) {
            throw new RuntimeException("Decryption failed", e);
        }
    }

    // Aadhaar: one-way hash only — never decrypt
    public String hashAadhaar(String rawUid, String salt) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return Base64.getEncoder().encodeToString(
                digest.digest((rawUid + salt).getBytes(StandardCharsets.UTF_8))
            );
        } catch (Exception e) {
            throw new RuntimeException("Hashing failed", e);
        }
    }
}
```

Use this service in `CitizenProfileService` — **never** in the controller directly.

---

## Step 6: Internal Endpoints for Rudra's FastAPI

These endpoints are called **service-to-service only** — not by the frontend. They must require a separate `Internal-Service-Key` header (a shared secret, NOT a citizen JWT).

```
GET  /internal/profile/{userId}
  - Called by FastAPI before every eligibility check
  - Returns DECRYPTED citizen profile (Rudra needs the real values for AI reasoning)
  - Validates Internal-Service-Key header
  - Logs: action="profile_read" in audit_logs

PATCH /internal/profile/{userId}
  - Called by FastAPI at end of each conversation session
  - Body: { "annualIncome": 150000, "state": "UP", "occupation": "farmer" }
  - Encrypts PII fields, saves to MongoDB
  - Recalculates profileCompleteness
  - Logs: action="profile_write" in audit_logs

GET /internal/scheme/{schemeId}/rules
  - Called by FastAPI eligibility agent
  - Returns eligibilityRules from schemes collection
  - No auth logging needed (scheme data is not sensitive)
```

> [!IMPORTANT]
> Tell Rudra the exact value of `INTERNAL_SERVICE_KEY` so he can add it to `ai_service/.env`. Agree on this in person before Week 1 ends.

---

## Step 7: Rate Limiting (Bucket4j)

Add this as a Spring Boot filter, not in individual controllers:

```java
@Component
public class RateLimitFilter extends OncePerRequestFilter {

    // 60 requests/min per IP for general endpoints
    // 5 OTP/hour per phone for auth endpoints
    // 1 concurrent voice session per userId (enforced in FastAPI, not here)

    private final Map<String, Bucket> buckets = new ConcurrentHashMap<>();

    private Bucket getBucket(String key) {
        return buckets.computeIfAbsent(key, k ->
            Bucket.builder()
                .addLimit(Bandwidth.classic(60, Refill.intervally(60, Duration.ofMinutes(1))))
                .build()
        );
    }

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res,
                                    FilterChain chain) throws ServletException, IOException {
        String ip = req.getRemoteAddr();
        Bucket bucket = getBucket(ip);
        if (bucket.tryConsume(1)) {
            chain.doFilter(req, res);
        } else {
            res.setStatus(429);
            res.setHeader("Retry-After", "60");
            res.getWriter().write("{\"error\":\"RATE_LIMITED\"}");
        }
    }
}
```

---

## Step 8: DPDP Right to Erasure

```
DELETE /api/v2/user/me
  - Requires citizen JWT cookie
  - Must cascade ALL 5 collections in order:
    1. Delete citizen_profiles where userId = me
    2. Anonymize applications: set userId = null, schemeName = "DELETED_USER"
    3. Delete conversation_sessions where userId = me
    4. Delete otp_sessions where phone = me.phone
    5. Delete users where id = me
    6. Log: action="delete_request" in audit_logs (keep this — legal requirement)
  - Send SMS confirmation via Twilio: "Aapka data 72 ghante mein delete ho jayega"
  - Response: { "success": true, "message": "Erasure scheduled" }
  - SLA: complete within 72 hours (DPDP requirement)
```

> [!WARNING]
> Do NOT delete the audit_log entries for this user. DPDP allows retaining records of the deletion request itself for legal compliance.

---

## REST Endpoints Summary (Your Full Scope)

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| POST | /api/v2/auth/otp/send | None | Rate: 5/hr per phone |
| POST | /api/v2/auth/otp/verify | None | Sets httpOnly cookies |
| POST | /api/v2/auth/refresh | Cookie | Reads refresh cookie |
| POST | /api/v2/auth/logout | Cookie | Clears cookies |
| POST | /api/v2/consent | JWT Cookie | MUST be called before profile write |
| GET | /api/v2/profile/me | JWT Cookie | Returns decrypted PII |
| PATCH | /api/v2/profile/me | JWT Cookie | Partial update, recalc completeness |
| DELETE | /api/v2/user/me | JWT Cookie | DPDP erasure cascade |
| GET | /api/v2/applications | JWT Cookie | Filter by ?status= |
| POST | /api/v2/applications | JWT Cookie | status='saved' on create |
| PATCH | /api/v2/applications/:id | JWT Cookie | Citizen updates status post-submit |
| GET | /api/v2/admin/impact | Admin JWT | Public aggregated stats — no PII |
| GET | /internal/profile/{userId} | Service Key | FastAPI reads profile |
| PATCH | /internal/profile/{userId} | Service Key | FastAPI writes session updates |
| GET | /internal/scheme/{id}/rules | Service Key | FastAPI reads eligibility rules |

---

## Security Checklist (Your Items)

```
[ ] MongoDB Atlas: Network Access whitelist — Cloud Run IPs only, no 0.0.0.0/0
[ ] Field encryption key in application.yml env var — NEVER hardcoded
[ ] JWT in httpOnly cookie — verify with browser DevTools that no token in response body
[ ] OTP stored as bcrypt hash in otp_sessions — never raw OTP
[ ] Aadhaar hash uses SHA-256 + server salt — raw UID discarded immediately
[ ] Rate limiting active on all endpoints — test with 61 rapid requests
[ ] CORS: whitelist production frontend domain only — no wildcard origins
[ ] DELETE /user/me cascade tested across all 5 collections
[ ] Audit log on every profile read/write with IP
[ ] No PII (name/phone/Aadhaar pattern) in Spring Boot log output
```

---

## What Rudra Will Provide to You

- `SARVAM_API_KEY` — not your concern, but coordinate the `INTERNAL_SERVICE_KEY`
- The exact JSON shape of `profileUpdates` that FastAPI will PATCH to `/internal/profile/{userId}`
  - Shape: `{ "annualIncome": 150000, "state": "UP", "category": "obc", "occupation": "farmer" }`
  - All fields optional — partial update only

---

## Communication Protocol

- **Daily sync**: 10-min standup (WhatsApp or call) to unblock each other
- **Blocking Rudra**: If `/internal/profile/{userId}` isn't live by end of Week 1, Rudra's MongoDB work stops
- **API changes**: Any change to the internal endpoints must be communicated to Rudra **before** merging
- **Schema changes**: Update `CLAUDE.md` in repo root + `docs/01_Master_Project_Document.docx` — both

---

*Last updated: 26 Jun 2026 | Reflects v3.0 architecture — MongoDB, OTP auth, Pipecat voice, DPDP compliance*
