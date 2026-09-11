# Yojna Sarthi (YojnaSetu) — System Architecture

Last reviewed: 2026-09-11, against the current state of the repo, not the plan — every claim below was checked against source before being written down.

## 1. High-level shape

Three deployed services, one shared database, on Azure Container Apps.

```
Citizen / CSC operator / branch rep browser
                  │
                  │  HTTPS, httpOnly JWT cookies (SameSite, stateless sessions)
                  ▼
┌───────────────────────┐
│  frontend               │
│  React + Vite            │
│  (Charan & Ayush's scope)│
└───────────┬───────────┘
            │ REST                              │ WS/REST (chat, voice)
            ▼                                    ▼
┌────────────────────────────┐      ┌──────────────────────────────┐
│  spring-gateway              │      │  ai_service                    │
│  Java 17 / Spring Boot 3.2   │◄────►│  FastAPI / Python                │
│  system of record            │  X-API-Key /   │  LangGraph orchestrator +  │
│                               │  X-Internal-Key │  agents, chatbot, OCR      │
└───────────┬───────────┬─────┘      └───────────┬──────────────┘
            │           │                             │
            │           │ signals (fire-and-forget,    │
            │           │ optional — see §3)            │
            │           ▼                             │
            │   ┌──────────────────┐                   │
            │   │  Temporal          │                   │
            │   │  (SLA reminders     │                   │
            │   │  for credit apps,   │                   │
            │   │  OFF by default)    │                   │
            │   └──────────────────┘                   │
            │                                             │
            └───────────────────┬─────────────────────────┘
                                 ▼
                        ┌──────────────────┐
                        │  MongoDB            │
                        │  db "yojnasetu"      │
                        │  shared, both services│
                        │  connect directly     │
                        └──────────────────┘
```

**The integration pattern is a shared database, not an API boundary.** Both backend services hold their own `MONGODB_URI`/`MONGODB_DB` connection and read/write Mongo directly. Spring Data defines a schema (via `@Document`-annotated Java classes); the Python side accesses the same collections through raw Motor/PyMongo dicts with **no schema enforcement on that side**. This is fast to build against and is the right call for a hackathon-scale team, but it means:

- A field rename in a Spring `@Document` class silently breaks whatever Python code reads that field, with no compiler or type system to catch it — only a runtime `KeyError`/`None` or a live bug report.
- There is no single place that owns "what does a `citizen_profiles` document actually look like" — the Java class and every Python call site that touches it all have to independently agree.

Two proper synchronous integration points exist on top of the shared DB, both shared-secret-header-gated (not JWT — these aren't on behalf of a browser session):

| Direction | Endpoint | Header | Purpose |
|---|---|---|---|
| ai_service → spring-gateway | `GET/PATCH /internal/profile/{userId}` (`InternalProfileController`) | `X-Internal-Key` | Read/write a citizen's decrypted profile during a chat turn (e.g. the chatbot learns "annual income ₹2L" mid-conversation and persists it back to the system of record) |
| spring-gateway → ai_service | `DELETE /internal/citizen/{id}/data`, admin chat proxy (`AccountController`, `ProxyController`) | `X-API-Key` | Account-deletion fan-out; admin console proxying into the AI service |

Both sides read the **same secret value** (`INTERNAL_SERVICE_KEY` / `INTERNAL_API_KEY`) — kept in sync manually across two deployments, which is itself worth automating (see §6).

---

## 2. `frontend/` — React + Vite

Owned by Charan & Ayush; out of scope for this document beyond the integration surface:

- `src/lib/api.js` — REST client to spring-gateway (cookie-based auth, no token handling in JS).
- `src/lib/voiceClient.js` / chat components — WS/REST to ai_service for the conversational assistant.
- `src/lib/emiCalculator.js`, `nsfdcSchemes.js` — credit-module math and reference data **mirrored** client-side for instant display; the authoritative numbers are computed/validated server-side in `spring-gateway`'s `credit/EmiCalculator.java` and `CreditProduct` catalogue. Any drift between the two is a display bug, not a security issue, but worth a periodic diff.

---

## 3. `spring-gateway/` — Java system of record

Package layout under `com.yojnasetu.gateway`:

- **`controller/`** — general platform: auth (OTP-based, no passwords for citizens), citizen profile, scheme catalogue, helper applications, admin proxy into ai_service.
- **`credit/`** (61 files — the majority of active development) — the SIH PS 26092 SC concessional-credit module:
  - `CreditApplication` / `CreditApplicationService` / `CreditApplicationStatus` — the application lifecycle (`DRAFT → SUBMITTED → UNDER_VERIFICATION → MISSING_DOCS ⇄ → FORWARDED → SANCTIONED/REJECTED → DISBURSED`). **This lifecycle is fully implemented and persisted synchronously over REST — it does not depend on Temporal being up** (see below).
  - `CreditProduct` / `CreditProductSeeder` — the NSFDC scheme catalogue (interest rate, loan ceiling, moratorium, margin-money %), the single source of truth both the frontend display and the chatbot's `credit_faq` RAG read from.
  - `BranchRep` / `BranchRepApplication` — lender staff plus the CSC/NGO/field-agent assist-only self-onboarding flow (added this session).
  - `AssistAuthorization` — a citizen's explicit, revocable grant of a specific helper onto a specific application (not a blanket branch assignment).
  - `Consent` / `ConsentPurpose` — DPDP-2023-oriented purpose-specific, revocable consent records, checked at the point of action (`ConsentService.requireConsent`), not just logged.
  - `LoanDocument` / `LoanDocumentService` — uploaded document storage, content-sniffed (magic bytes, not filename/MIME trust), size- and count-capped, encrypted at rest.
  - `AadhaarOfflineEkycExtractor` — real UIDAI offline-eKYC parsing **and** real XML-DSig signature verification (XXE-hardened, fixed trust-anchor key selector) — gated only by whether a real UIDAI certificate file is configured, not by anything left to build.
  - `DigiLockerService` / `AccountAggregatorService` — OAuth2 and consent-flow scaffolding built to spec, **never run against a live server**; both refuse outright when unconfigured, and `VerificationMode.isAvailable()` for both stays `false` regardless of whether the code exists (see §6).
  - `MisuseReportService`, `EmiCalculator`, `PincodeGeocoder`, `FileAccessService` — supporting domain logic.
- **`workflow/`** — see §3a below; this is smaller and more optional than the earlier draft of this document implied.
- **`security/`** — `FieldEncryptionService` (AES-256-GCM, 32-byte key from `encryption.key`/`FIELD_ENCRYPTION_KEY`, used for every PII field at rest: names, phone numbers, PAN, uploaded document content, DigiLocker tokens); `JwtUtils`/`JwtAuthFilter` (reads the JWT from an **httpOnly** `access_token` cookie, never a header — no token ever touches JS); `RateLimitFilter` (60 req/min/IP via Bucket4j, identity from a trusted `X-Real-IP` set by the reverse proxy, deliberately not `X-Forwarded-For[0]` which a client can spoof).
- **`notify/`** — notification fan-out for application-lifecycle events.
- **`model/` + `repository/`** — the general platform's Mongo documents (`User`, `CitizenProfile`, `Scheme`, `Application`, `Helper`, `Kendra`/CSC locations, `TrendEvent`).
- **`config/SecurityConfig.java`** — see §4.

### 3a. How Temporal is actually used (correction from an earlier draft of this doc)

An earlier version of this document drew Temporal as sitting in the critical request path, as if it were *the* workflow engine driving the credit application lifecycle. **That's not accurate.** The real shape, verified against `TemporalConfig.java` and `LoanWorkflowGateway.java`:

- Temporal is **off by default** (`@ConditionalOnProperty(name = "app.temporal.enabled", havingValue = "true")`). The gateway boots and serves every endpoint — including the full credit application lifecycle — with no Temporal cluster present at all.
- Every REST endpoint that transitions an application's status (`CreditApplicationController` → `CreditApplicationService`) **performs and persists that transition itself**, synchronously, against Mongo. Temporal is never in the path of "did this citizen's status change actually take effect."
- `LoanWorkflowGateway.signal(...)` is called *after* a transition has already been applied and saved, purely to inform a running Temporal workflow (if one exists) that it happened. Every method is wrapped so a Temporal outage, or Temporal never having been enabled for that application, is swallowed and logged — never surfaced to the citizen.
- What the `LoanApplicationWorkflow` actually does, once enabled: durable SLA timers per lifecycle stage (3 days before a first "please verify" reminder, 5 days for missing-document nudges, capped reminder counts, a 365-day maximum lifetime) — i.e. it is a **reminder/escalation scheduler layered on top of a lifecycle that already works without it**, not the lifecycle's engine of record.

This is a deliberate and reasonable design (per its own doc comment: *"a missing Temporal server must never stop a citizen submitting an application"*), but the earlier "Temporal = workflow engine" framing overstated its role. Accurate framing: **Mongo + REST is the durability layer; Temporal is an optional durability layer for reminders on top of that.**

---

## 4. Authorization model — route-level vs. in-handler, and where that's inconsistent

`SecurityConfig.java` sets the actual boundary. Two different enforcement styles coexist in this codebase, and the file's own comment explains why one was chosen over the other in at least one place:

**Route-level (matcher-based), enforced before any handler runs:**
```java
.requestMatchers("/api/v2/branch/**").hasAnyRole("BRANCH_REP", "ADMIN")
```
The comment on this line is explicit about *why*: *"so a newly-added `/api/v2/branch/**` endpoint is protected by default instead of protected once someone remembers."* This is the stronger pattern — a new endpoint under this prefix is safe by construction, even if whoever writes it forgets an authorization check entirely.

**In-handler (checked inside the controller method), for everything else under `/api/v2/sih/**`:**
```java
// e.g. BranchRepApplicationController.pending()
if (!isAdmin(auth)) {
    return ResponseEntity.status(HttpStatus.FORBIDDEN).body(...);
}
```
`/api/v2/sih/**` (outside `/credit/**`, which is intentionally public) only requires `authenticated()` at the route level — **any** logged-in citizen, helper, or rep passes the security filter chain. The actual admin/rep-only restriction on endpoints like:
- `BranchRepApplicationController`: `GET /pending`, `GET /pending/count`, `POST /{id}/approve`, `POST /{id}/reject`
- `HelperApplicationController`'s equivalent admin routes
- `DigiLockerController`/`AccountAggregatorController`'s citizen-ownership checks (`applications.getForCitizen(...)`)

...lives entirely inside each handler. This is the exact pattern the `/api/v2/branch/**` comment above was written to move *away* from — it works today because every handler was written carefully, but it has no structural guarantee: a new admin route added under `/api/v2/sih/**` by someone who doesn't know (or forgets) the `isAdmin(auth)` convention is reachable by any authenticated citizen with nothing in the security config to stop it.

**Concrete recommendation:** extend the route-matcher approach that already exists for `/api/v2/branch/**` to cover the admin-only sub-paths under `/api/v2/sih/**`, e.g.:
```java
.requestMatchers(HttpMethod.GET, "/api/v2/sih/branch-rep-applications/pending/**").hasRole("ADMIN")
.requestMatchers(HttpMethod.POST, "/api/v2/sih/branch-rep-applications/*/approve",
                                    "/api/v2/sih/branch-rep-applications/*/reject").hasRole("ADMIN")
```
This doesn't replace the in-handler check (defense in depth is still worth keeping), but it converts a single point of failure ("did the developer remember?") into two independent layers, matching the standard this codebase has already set for itself in one place but not applied uniformly.

---

## 5. `ai_service/` — Python FastAPI, the chatbot/AI layer

- **`graph/`** — a LangGraph state machine (`orchestrator.py`): `intent_classifier` (LLM-based, one of ~10 intents) → routes to exactly one real agent node → `response_composer`. Real agents behind real intents as of this writing: `eligibility.py` (Agent 1 — general scheme matching against the citizen's real profile fields and a scheme's actual `eligibilityRules`, not a keyword heuristic), `comparison.py` (Agent 8), `financial_planning.py` (Agent 7), `application_guidance.py` (Agent 3 — curated playbooks + free-form guidance), `document_verification.py` (Agent 4 — PPO/Aadhaar cross-match), `grievance.py` (Agent 5 — CPGRAMS filing guidance), `csc_assist.py` (Agent 9), `status_check.py`, `credit_application_intro.py` (hands off into the stateful credit slot-filling flow), and `credit_faq.py` (NSFDC scheme-terms RAG, added this session). Every intent not yet backed by a real agent routes to an honest `placeholder.py` node rather than a stub that pretends to work.
- **`graph/llm.py`** — the shared Gemini → Groq → Ollama fallback chain every agent calls through; handles free-tier quota exhaustion by falling through providers rather than failing the turn.
- **`db/vector_search.py`** — `$vectorSearch` against `schemes` with a brute-force cosine fallback when no Atlas Search index exists (true on local/dev Mongo). Used for **general** welfare-scheme discovery only.
- **`graph/agents/credit_faq.py`** deliberately does **not** use vector search — `credit_products` has no `embedding` field and is a small (~6-8 document), exactly-named catalogue, so a keyword/code matcher is both simpler and more precise (a citizen asking about "Term Loan" needs that exact product's real interest rate, not the topically-nearest one).
- **`discovery/`** (Agent 2) — the scheme-ingestion pipeline: normalizes and upserts scraped/collected scheme data into `schemes`, run daily via the `discovery-cron` job.
- **`routers/`** — `orchestrator_router` (main single-turn chat contract), `ws_router`/`voice_ws_router` (streaming), `application_assistant_router` → `services/application_assistant.py` (the **separate**, stateful, multi-turn credit-application slot-filling flow — deliberately not part of the single-turn orchestrator graph, since `GraphState`'s single-turn contract has no field for a structured multi-step payload), `agents_router` (direct agent invocation, e.g. PPO/Aadhaar match from a REST call rather than a chat turn), `internal_router` (receives Spring's `X-API-Key`-gated calls), `ocr_router`, `translate_router`, `dlc_router`.
- **`utils/`** — `pii_masker.py` (strips PII before it ever reaches an LLM prompt), `injection_guard.py` (blocks prompt-injection patterns before intent classification runs), `rate_limiter.py`, `jwt_auth.py` (validates the same JWT spring-gateway issues, for endpoints a citizen calls directly), `sarvam.py`/`tts.py` (voice), `vision_ocr.py`.

### How the chatbot integrates with spring-gateway for real data

The orchestrator never queries `credit_applications`, `citizen_profiles`, or scheme data through an API — it reads the shared Mongo collections directly (same caveat as §1: no schema contract). The **one** exception is profile writes learned mid-conversation (`profile_learner.py` → `spring_client.patch_citizen_profile()`), which goes through spring-gateway's `InternalProfileController` rather than writing `citizen_profiles` directly from Python — this keeps citizen-profile writes flowing through one code path regardless of whether they originated from a form submission or a chat message.

---

## 6. Security highlights

- **Encryption at rest:** `FieldEncryptionService` (AES-256-GCM) on every PII field a citizen provides — name, phone, PAN, uploaded document bytes, DigiLocker access tokens. Aadhaar numbers are **never stored raw anywhere** in this codebase — only a salted SHA-256 hash (for the "does this match a later submission" check) plus a masked display form (`XXXX-XXXX-1234`).
- **Auth:** citizens authenticate via OTP (no passwords), issued a JWT delivered as an **httpOnly** cookie — never accessible to JS, never sent as a bearer header from the browser. Helpers and branch reps use an admin-issued ID + BCrypt-hashed password instead of OTP (they're staff, not citizens of the platform), with a forced reset on first login.
- **Consent:** `ConsentPurpose` enumerates specific, plain-language-stated purposes (profile storage, eligibility checks, partner sharing, document verification, DigiLocker/AA fetch); `ConsentService.requireConsent(...)` is a **runtime gate** checked at the point of the action it governs, not a flag set once and never consulted again. Withdrawal writes a new record rather than mutating history, so "agreed → withdrew → agreed again" stays a readable sequence of facts.
- **Document security:** uploads are content-sniffed by magic bytes (an executable renamed `.pdf` is rejected regardless of its claimed extension/MIME type), size- and per-application-count-capped, and every download is written to an append-only audit log — these files carry someone's caste and income.
- **UIDAI signature verification:** real XML-DSig validation (`javax.xml.crypto.dsig`) against a fixed, self-configured trust anchor (the document's own embedded `KeyInfo` is never trusted — only our configured certificate counts), with DTD/XXE processing disabled outright on all untrusted XML parsing.
- **Known, explicitly-gated incompleteness (not a hidden gap):**
  - No production UIDAI certificate is configured in this deployment — every offline-eKYC record is honestly stored with `signatureVerified=false` until one is.
  - DigiLocker and Account Aggregator integrations are built to their published API specs but have **never been exercised against a live server** — no partner/FIU credentials exist for this deployment. Both refuse every entry point rather than silently no-op, and `VerificationMode.isAvailable()` for both stays hardcoded `false` independent of whether the integration code compiles — flipping that is a deliberate manual step for after a real sandbox run, not an automatic consequence of shipping this code.
  - Account Aggregator's financial-data **decryption** step (the AA spec's ECDH key exchange + AES-GCM) is deliberately not implemented at all, even once credentials exist — shipping unverified crypto with no real counterparty to test it against was judged a worse risk than the honest gap.
- **CSRF:** disabled at the framework level, with `SameSite` cookie attributes as the baseline defense instead of a token scheme — documented as an explicit scope decision (ADR-001), not an oversight, but worth re-examining if new state-changing GET-adjacent endpoints are added.

---

## 7. Deployment

Azure Container Apps (`deploy/azure/deploy.sh`): three images (`ai-service`, `spring-gateway`, `frontend`) built and pushed to a shared ACR, deployed as container apps inside one Container Apps Environment (so they can reach each other over the internal network). Two scheduled Container Apps Jobs: `discovery-cron` (daily 02:00 IST scheme-discovery pipeline) and `backup-cron` (Mongo → Azure Blob Storage snapshot). Secrets (Mongo URI, Gemini/Groq API keys, JWT key pair, field-encryption key, internal service key) are injected as Container Apps secrets — never baked into an image layer.

---

## 8. Frontend UX & product design guidance (target state — for the frontend team)

This section is **product/UX guidance for `frontend/`**, contributed for the frontend team (Charan & Ayush) to act on — it is not a description of code that exists, and none of it was implemented as part of this backend work (frontend edits are explicitly out of this session's scope). It's included in this architecture doc because it defines a login/auth boundary that the backend already supports but the frontend doesn't yet exploit — worth stating plainly rather than leaving implicit.

### Current state, checked against the repo (2026-09-11)

`frontend/src/App.jsx`'s root route (`/`) renders `SplashScreen`, which unconditionally redirects to `/signin` after ~2.8s with no branch for "browsing without an account." There is no route-level auth guard component (`ProtectedRoute`/`RequireAuth`) wrapping any route in `App.jsx` — every page (`/schemes`, `/credit-schemes`, `/apply/:schemeId`, etc.) is reachable by URL without login today, but the app's own entry flow funnels every visitor through sign-in before they reach any of them. **The backend already supports the public-first model below** — `SecurityConfig.java` (§4) already marks `/api/v2/sih/credit/**` (NSFDC catalogue, eligibility check, EMI quotes) `permitAll()` specifically so a citizen can learn what they qualify for before creating an account — the gap is that the frontend doesn't currently route a guest there. The rest of this section is the target UX; treat it as a frontend product brief.

### 8.1 Landing & browsing (no login required)

**Goal:** let users explore everything before asking for any commitment.

- **Open homepage with a clear value proposition** — heading ("Concessional Credit Schemes for SC Beneficiaries"), subtext, primary CTA ("Check Your Eligibility" → guided flow), secondary CTA ("Browse All Schemes").
- **Scheme browsing without login** — public scheme list (filterable by type/project cost/state) and scheme detail pages (eligibility criteria, benefits, required documents, a static EMI example), none of it behind auth.
- **Eligibility checker, partial, no login** — a short guest form (category, annual family income, project type/cost or education status) returning *indicative* eligible schemes. Login is only requested when the citizen wants to save results, apply, or see a personalized EMI.
- **EMI calculator in guest mode** — usable by anyone; login only prompted to save a calculation or attach it to an application.
- **Partner locator, view-only for guests** — map + list of branches (name, address, distance, supported schemes) visible without login; login required only to select a branch for an actual application.

**Pattern:** *"View everything, act only when needed."* Reduces drop-off and builds trust.

### 8.2 When to trigger login / registration

Make login feel like a natural step, not a gate. Trigger it only when the citizen tries to:

1. **Apply for a scheme** — "Apply Now" with no session opens login/register, then returns the citizen to the same form with whatever they'd already entered, if possible.
2. **Save schemes or calculations** — "Save this scheme"/"Save this EMI calculation" prompts login on click.
3. **Track application status** — a guest can read *how* tracking works; seeing their *own* applications requires login.
4. **Download personalized documents** — eligibility summary PDF, application receipt — tied to an identity, so login-gated.

Use soft framing: *"Login to apply for this scheme"* / *"Create an account to save your eligibility results and apply later"* — not *"You must register to continue."*

### 8.3 Simple, low-friction auth flow

- **Phone OTP as the primary login** (already the backend's model — citizens have no passwords in this system; see §6) — enter mobile number, receive OTP, enter OTP, logged in. First-time numbers create an account automatically.
- **Minimal registration** — name, mobile, district/state, category (can default to SC given this platform's scope). Collect anything further during the application flow itself, not upfront.
- **Continue as guest, then link later** — fill the eligibility form as a guest; only ask for login at "Apply"; carry forward whatever was already entered once logged in.
- **Clear, non-leaking error messages** — "The OTP you entered is incorrect. Please try again." A "number not found" case (if ever surfaced) should stay generic rather than confirming whether a number is registered.

### 8.4 Application flow

- **Step-by-step guided form** with a progress bar: basic details (pre-filled from profile where available) → project/education details → documents → review & submit.
- **Save & resume later** — draft applications, surfaced on the citizen's dashboard ("You have 1 draft application").
- **Document upload help** — per-document example of a valid file, allowed formats (PDF/JPG/PNG), max size (e.g. 4MB), and specific failure reasons on rejection ("File too large. Max size is 4 MB.") rather than a generic error.
- **Plain-language summary before submit** — scheme name, loan amount/tenure/moratorium, attached documents, then "Confirm & Submit".
- **Immediate confirmation** — success screen with application ID, next steps, a downloadable receipt, plus an SMS/WhatsApp with the application ID and a status link.

### 8.5 Status tracking & notifications

- **Simple status timeline** — a vertical timeline (Submitted → Under Verification → Missing Documents → Forwarded → Sanctioned/Rejected → Disbursed) with the current step highlighted, each step dated and annotated with a short remark (e.g. "Rejected — income above limit").
- **Next-step guidance per status** — what the citizen should actually do: "Upload these documents to proceed," "Your loan is sanctioned — disbursal will happen soon," "Reason: … you can contact the branch or apply for another scheme."
- **Notifications center** — in-app list ("Your application for X is now under verification," "Branch has requested additional documents"), read/unread state, optional per-application filter. (Backend already has `notify/`'s `NotificationService`/`NotificationController` and `NotificationEvent` model — see §3 — so this is primarily a frontend consumption gap, not a missing backend capability.)
- **SMS/WhatsApp reminders** on status change, on documents pending too long, and on sanction/disbursal.

### 8.6 Help & support

- **FAQ section** in simple language: who's eligible, what documents are needed, how long verification takes, what happens after sanction.
- **Guided (non-chatbot) help button** — FAQs, helpline/email, optional call-back request. (Distinct from — and can sit alongside — the LangGraph chatbot in `ai_service/`, which already exists as a richer channel; this is a lighter-weight fallback for citizens who don't want a conversational interface.)
- **Branch contact info** on the partner/branch detail page — address, phone, working hours.
- **Grievance/feedback form** — name, mobile, optional application ID, issue description, a stated response-time promise (e.g. "within 3 working days"). (Backend note: `ai_service/graph/agents/grievance.py`, Agent 5, already generates CPGRAMS filing guidance in the citizen's language — a simple in-app form like this could feed that agent rather than duplicate it.)

### 8.7 Accessibility & inclusivity

- **Language toggle (Hindi/English)** visible in the header, applied across key pages.
- **Plain language over jargon** — "No EMI for first 6 months" rather than a bare "Moratorium: 6 months."
- **Mobile-first design** — large tap targets, readable font sizes, works on low-end Android devices.
- **Low-data friendly** — light on images/animation, fast on 3G/4G.

### 8.8 Trust & transparency cues

- **Privacy/data-use notice near forms** — plain statement of what the data is used for and that it isn't shared outside official channel partners. (This should describe the *real* `ConsentPurpose` model in §6 — DPDP-oriented, purpose-specific, revocable — rather than a generic placeholder, so the UI text and the backend's actual consent semantics stay honest with each other.)
- **A short security line in the footer** — data is encrypted and stored securely (again, this is actually true per §6 — `FieldEncryptionService`/AES-256-GCM — so it's a claim the frontend can make without overstating anything).
- **Clear ownership statement** — what this platform is, and any government/NGO/bank partners involved.

### 8.9 Example target user journey

1. Lands on the homepage → sees a clear heading + "Check Eligibility."
2. Clicks "Check Eligibility" → fills a short guest form → sees indicative eligible schemes, no login.
3. Clicks a scheme → reads details, uses the EMI calculator → still no login.
4. Clicks "Apply Now" → prompted to log in / register via phone OTP.
5. After login, the application form is pre-filled with whatever was already entered as a guest.
6. Submits → gets an application ID + SMS.
7. Later, logs in to "Track Application" → sees the timeline, next steps, and notifications.

At no point should the citizen feel blocked from exploring — login should feel like a natural step only when they're ready to act, not a gate in front of the whole site.

### 8.10 Reference prompt for the frontend team

The brief below can be handed directly to whoever picks this up (Claude Code or otherwise) to scope the frontend changes — reproduced here as a ready-to-use starting point, not something generated or verified by this backend session:

```
You are a senior React + MUI engineer. Design our SC concessional credit platform frontend to be
as user-friendly and low-friction as UMANG (https://web.umang.gov.in/).

Key requirements:

1) Public-first experience:
   - Homepage, scheme listing, scheme details, EMI calculator, and partner locator must be fully
     accessible without login.
   - No login wall for browsing or using tools.

2) Login/registration triggers:
   - Only require login when the user tries to:
     - Apply for a scheme.
     - Save schemes or calculations.
     - Track their own applications.
     - Download personalized documents (eligibility summary, application receipt).
   - Show friendly messages like "Login to apply for this scheme" instead of hard gates.

3) Auth flow:
   - Primary login method: phone OTP (Firebase).
   - Minimal registration: name, mobile, district/state.
   - Allow guest users to fill eligibility forms, then prompt login on "Apply Now", carrying
     forward their data.

4) Application flow:
   - Step-by-step guided form with progress bar.
   - Save & resume later (draft applications).
   - Clear document upload guidance (formats, size, examples).
   - Plain-language summary before submit.
   - Success screen with application ID and next steps.

5) Status tracking:
   - Simple vertical timeline of statuses (Submitted, Under Verification, Missing Docs, etc.).
   - Next-step guidance for each status.
   - In-app notifications list + SMS/WhatsApp reminders.

6) Help & trust:
   - FAQ page with simple language.
   - "Need help?" button linking to FAQs + contact info.
   - Short privacy notice near forms ("Your data is used only for eligibility and application").
   - Language toggle (Hindi/English) in header.

Tech:
- React 18 + Vite + MUI v5.
- Responsive, mobile-first design.
- Clean, government-style UI similar to UMANG.

Output:
- Describe the page structure and key components.
- Generate code for:
  - Public homepage with hero, categories, featured schemes.
  - Scheme listing and detail pages (public).
  - EMI calculator page (public).
  - Login/register modal/page triggered only on actions like "Apply Now".
  - Application form (step-by-step) and status tracking page (for logged-in users).
```

---

## Key Risks & Recommended Improvements

1. **Shared-database coupling has no schema contract on the Python side.** A field rename or type change in a Spring `@Document` class can silently break `ai_service` with nothing catching it at build time. *Recommendation:* at minimum, a shared, generated (or hand-synced) schema reference doc per shared collection; ideally, Python-side Pydantic models mirroring the Java shape, validated in tests against a real fixture document from each service.

2. **In-handler authorization on new `/api/v2/sih/**` admin routes is a weaker pattern than the route-matcher approach the codebase already uses for `/api/v2/branch/**`.** This is not currently exploitable (every handler checks correctly today), but it's a single-point-of-failure pattern for every *future* admin endpoint. *Recommendation:* extend `SecurityConfig`'s matcher list to cover admin-only sub-paths explicitly (see §4), keeping the in-handler check as defense in depth rather than the only layer.

3. **The two internal-service secrets (`INTERNAL_SERVICE_KEY` on Spring, `INTERNAL_API_KEY` on ai_service) must be kept equal by hand across two independent deployments.** A silent mismatch after a redeploy fails closed (calls get rejected) rather than open, which is the safer failure direction, but it's still an operational footgun with no automated check. *Recommendation:* a startup health check or smoke test that verifies the two services can actually authenticate to each other, run as part of `deploy.sh` rather than discovered after a broken deploy.

4. **DigiLocker and Account Aggregator are real, spec-shaped code with zero live verification.** Nothing here is wrong per se, but "the code exists" and "the integration works" are different claims, and it would be easy for that distinction to get lost in a demo or a status update under time pressure. *Recommendation:* keep `VerificationMode.isAvailable()` hardcoded false until an actual sandbox run happens — already done — and treat the first live credential as a mandatory integration-test gate before flipping it, not just a "looks right" code review.

5. **Temporal's actual scope (SLA reminders, not the lifecycle engine) is easy to overstate**, as this document's own earlier draft did. If Temporal is highlighted to evaluators as "the workflow engine," be precise that the credit application lifecycle works fully without it — Temporal adds durable reminders on top, and its own design intentionally treats an outage as a lost reminder, not a lost transaction.

6. **CSRF protection relies solely on `SameSite` cookies, with CSRF tokens explicitly out of scope (ADR-001).** This is a reasonable call for the current single-frontend-origin setup, but it's worth re-confirming before any new integration (e.g. a webview, a mobile wrapper, or a third-party embed) that might not honor `SameSite` the same way a standard browser tab does.

7. **Two structurally separate "helper" identity systems exist side by side** (`Helper`/`HelperApplication` for general schemes vs. `BranchRep` with an assist-only `RepType` for the credit module) — a CSC operator who wants to help with both has to onboard twice, with two different login IDs. Not a security issue, but worth flagging to evaluators as a known product-design seam rather than letting it look like an oversight if it comes up in a demo.

8. **The frontend currently gates every visitor through sign-in before they reach any page** (`SplashScreen` unconditionally redirects to `/signin`), even though the backend already supports public browsing — `/api/v2/sih/credit/**` (NSFDC catalogue, eligibility check, EMI quotes) is explicitly `permitAll()` for exactly this reason. This is a real conversion/trust cost for a citizen who wants to see whether a scheme applies to them before creating an account. *Recommendation:* see §8 — this is scoped as a frontend product brief, not a backend change, since the backend capability the target UX needs is already there.
