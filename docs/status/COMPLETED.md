# Completed Work — Detail

> Every entry here was verified against a running system (real HTTP calls, real Mongo state checks), not just written and assumed correct. File paths are repo-relative.

## Phase 1 — Spring Boot Foundation (`deploy/backend/spring-gateway/`)

Full rewrite per [ADR-001](../adr/ADR-001-mongodb-otp-httponly-jwt-auth.md) — dropped PostgreSQL/JPA/Flyway/password-auth entirely, not incrementally.

- **Mongo models**: `model/{User,CitizenProfile,OtpSession,AuditLog,Scheme,Application}.java` — `CitizenProfile` includes v5.0 pension fields from day one.
- **OTP-first auth** (`controller/AuthController.java`): `/api/v2/auth/{otp/send, otp/verify, refresh, logout}`. RS256 JWT (`security/JwtUtils.java`) delivered as httpOnly + `SameSite=Strict` cookies, never in the response body.
- **Field encryption** (`security/FieldEncryptionService.java`): AES-256-GCM for name/dob/phone, verified ciphertext at rest and correct decrypt round-trip.
- **Rate limiting** (`security/RateLimitFilter.java`): Bucket4j, 60 req/min/IP.
- **Internal service endpoints** (`controller/InternalProfileController.java`): `GET/PATCH /internal/profile/{userId}`, `GET /internal/scheme/{code}/rules` — `X-Internal-Key` gated.
- **Application CRUD** (`controller/ApplicationController.java`, added 2026-07-03): `GET/POST /api/v2/applications`, `GET/PATCH /api/v2/applications/{id}`. Ownership-checked on every read/write.
- **DPDP erasure cascade** (`controller/AccountController.java`, added 2026-07-03): `DELETE /api/v2/user/me` — see "Cross-service DPDP erasure" below.

### Real bug found: Spring Data MongoDB `auto-index-creation` was off by default
Every `@Indexed`/`@CompoundIndex` annotation in the codebase was decorative only — never applied to Mongo. Found while testing Application's duplicate-prevention index (posting the same scheme twice returned 201 twice instead of 409). This turned out to be bigger than that one symptom: `OtpSession`'s TTL index had *also* never been created, meaning OTP-code documents were accumulating in Mongo forever with no expiry.

Fixed by setting `spring.data.mongodb.auto-index-creation=true` in `application.properties`. That surfaced a second-order issue: `schemes`/`citizen_profiles` are collections ai_service *also* indexes (via its own `motor`-based `ensure_indexes()`), using Mongo's default index names — Spring's un-named `@Indexed` annotations generated different names for the identical key spec, causing a boot-time `IndexOptionsConflict`. Fixed with explicit `name=` values in `model/Scheme.java` and `model/CitizenProfile.java` matching ai_service's already-existing names.

**Verified**: `db.applications.getIndexes()` / `db.otp_sessions.getIndexes()` confirmed the real indexes now exist; a real duplicate-application POST now correctly 409s; app boots clean with no index conflicts.

## Phase 1b / cross-service — Real JWT verification in ai_service

Previously `/orchestrator/chat` and `/agents/financial-plan` took `citizen_id` directly in the request body and trusted it at face value — any caller could act as any citizen.

- `ai_service/utils/jwt_auth.py` — `get_current_citizen_id` FastAPI dependency, verifies the `access_token` httpOnly cookie against Spring Boot's RS256 **public** key (ai_service never touches the private key — the actual point of RS256 over HS256 in ADR-001).
- `ai_service/utils/spring_client.py` — `fetch_citizen_profile(citizen_id)`, calls Spring Boot's `GET /internal/profile/{userId}` with the shared `X-API-Key`/`X-Internal-Key` secret. Degrades to `{}` on any failure, never raises.
- `ai_service/routers/orchestrator_router.py` / `agents_router.py` updated to derive `citizen_id` from the verified token instead of the request body. `/agents/financial-plan` converted from POST to GET, matching what CLAUDE.md's endpoint table always specified.

**Verified**: real OTP login against a live Spring Boot instance → real `access_token` cookie → called both endpoints on ai_service → citizen_id correctly derived from the JWT `sub` claim (confirmed against the persisted `conversation_sessions.userId` in Mongo) → **a single flipped character in the cookie correctly 401s** (actual signature verification, not just presence-checking).

## Cross-service DPDP erasure cascade (`DELETE /api/v2/user/me`)

First feature where Spring Boot calls *into* ai_service (the reverse of `spring_client.py`'s direction), reusing the same shared secret.

- `ai_service/routers/internal_router.py` — `DELETE /internal/citizen/{citizen_id}/data`. Resolves `reasoning_traces` (keyed by `session_id`, no direct `userId`) via that citizen's `conversation_sessions` first, then deletes both, plus `nudge_log`. Idempotent.
- `deploy/backend/.../controller/AccountController.java` — audit log written **first** (append-only, survives regardless) → deletes `citizen_profiles`/`applications` → calls ai_service's cascade (10s timeout, failure surfaced not fatal) → deletes `users` **last** → clears both cookies.

**Verified**: real OTP login → consent → profile write → application → live chat message (populating `conversation_sessions`+`reasoning_traces`) → confirmed all 4 collections had live rows → called the delete endpoint → **0.35 seconds total** → confirmed all 4 now read zero, `audit_logs` still has the `delete_request` record, response body reports real non-zero deletion counts, and `Set-Cookie` headers actually clear both cookies.

## Phase 2 — Orchestrator Skeleton (`ai_service/graph/`)

- `graph/state.py` — `GraphState` TypedDict shared by every agent.
- `graph/llm.py` — Gemini 2.5 Flash primary, automatic Groq fallback at call time (not just construction); `prefer="groq"` for bulk/high-volume callers since Gemini's free tier is ~5rpm/20-per-day.
- `graph/intent_classifier.py` — runs `injection_guard` + `pii_masker` before every LLM call.
- `graph/orchestrator.py` — LangGraph `StateGraph`, routes by intent.
- `db/mongo.py`, `db/embeddings.py`, `db/vector_search.py` — async Mongo layer, local `all-MiniLM-L6-v2` embeddings, Atlas `$vectorSearch` with brute-force cosine fallback (no Atlas Search available on local Docker Mongo).
- `routers/orchestrator_router.py` — `POST /orchestrator/chat`.

**Verified**: real chat message traversed the graph, correct intent routing, persisted to `conversation_sessions`/`reasoning_traces`, survived a full server restart.

## Phase 3 — Agent 1 (Eligibility) + Agent 2 (Discovery)

- `graph/agents/eligibility.py` — ports `agent/yojna_sathi.py`'s `UserProfile`/`score_eligibility` logic.
- `discovery/normalizer.py` — Gemini-based structured `eligibilityRules` extraction.
- `discovery/upsert.py` — content-hash diff-upsert (skip unchanged, only pay for LLM+embedding on new/changed).
- `discovery/sources/{pib_rss,datagov}.py` — built, but **not producing data**: PIB's RSS feed URL is genuinely unknown (site redesigned), data.gov.in needs an API key + resource IDs nobody has obtained yet. Both degrade to `[]` + an `agent_alerts` entry rather than crashing.
- `discovery/sources/myscheme.py` — MyScheme.gov.in's real public JSON API (found by reading their frontend's JS bundles, not scraping HTML), honest `User-Agent`, 2s rate limit, `robots.txt`-compliant.
- `scripts/migrate_schemes.py` — migrated the original 419 schemes (276 central + 143 state).
- `scripts/run_myscheme_batch.py` — standalone batch runner (separate from the HTTP endpoint since MyScheme's calls are synchronous/rate-limited and would block FastAPI's event loop).

### Real bug found: `asyncio.gather()` had no per-task exception isolation
A first 300-scheme batch run only landed 5 schemes — one scheme's exception cancelled every other in-flight task in `discovery/upsert.py`'s `diff_upsert_schemes()`. Fixed by wrapping each scheme's upsert in try/except, added a `"failed"` counter.

**Verified**: 15-scheme test run → `{'skipped': 5, 'updated': 0, 'inserted': 10, 'failed': 0}`. Full 300-scheme run → `{'skipped': 24, 'updated': 11, 'inserted': 265, 'failed': 0}` — **zero failures**, despite hitting both Gemini's daily quota and Groq's rate limit repeatedly (those degrade gracefully to sparse `eligibilityRules`, not crashes). Scheme count: 419 → 699.

## Phase 4 — Agent 4 (Document + PPO Verification)

- `utils/ppo_matcher.py` — CLAUDE.md's exact `M_ppo` Levenshtein formula. Honest finding documented in the docstring: CLAUDE.md's own worked example computes *below* its own stated threshold — implemented as specified rather than silently tuned to match the anecdote.
- `utils/identity_extractor.py` — PII-masked-first Gemini/Groq name+DOB extraction from OCR text.
- `routers/agents_router.py`'s `POST /agents/document/verify-ppo` — reuses `_run_ocr` from `ocr_router.py`, zero-retention (images OCR'd and discarded).
- `graph/agents/document_verification.py` — the LangGraph-node version of the same logic.

### Real bug found: OCR artifact broke date comparison
A `/` in a date got OCR'd as `,` (`15/08/1952` → `15,08/1952`), causing a false DOB mismatch. Found via a real (synthetic) image upload, not synthetic text. Fixed `normalize_date()` to treat `,` as a `/` synonym.

**Not wired into chat**: the `document_verify` intent in `graph/orchestrator.py` still routes to the placeholder node — this agent is only reachable via its own REST endpoint, not through `/orchestrator/chat`.

## Phase 5 — Agent 7 (Financial Planning) + Agent 8 (Comparison)

- `utils/benefit_parser.py` — classifies `benefit_type` (`direct_transfer`/`conditional_payout`/`savings_investment`/`tax_relief`/`subsidy_or_loan`/`in_kind`) before trusting any extracted rupee amount.
- `graph/agents/financial_planning.py` — `GET /agents/financial-plan`, real JWT-derived identity (see above).
- `graph/agents/comparison.py` — Agent 8, top-2 vector search + Gemini comparison. **Wired into `/orchestrator/chat`'s intent graph.**

### Real bug found: LLM extracted cash amounts from non-cash sentences
First version misread a tax-exemption threshold ("no tax up to ₹5 lakh") and a savings-scheme deposit ceiling as if they were direct cash benefits — inflating one test citizen's reported annual benefit from a real ~₹43,200 to a false ₹13,36,000. Fixed by adding the `benefit_type` classification step; only `direct_transfer` counts toward the guaranteed total, `conditional_payout` is surfaced separately.

**Not wired into chat**: same gap as Agent 4 — the `financial_plan` intent routes to the placeholder node in `graph/orchestrator.py`. Only reachable via the dedicated REST endpoint.

## WebSocket chat — `WSS /ws/session/{session_id}` (2026-07-03)

CLAUDE.md's real target surface for text chat. `graph/chat_turn.py` extracts the one shared turn implementation (REST + WS run identical logic); `routers/ws_router.py` authenticates via the httpOnly cookie on the handshake (browsers can't set custom headers on WebSocket, so the JWT is the sole gate — invalid token closes 1008 before any message). Verified with a real WebSocket client: tampered cookie rejected by signature, multi-turn on one connection, sessions persisted with JWT-derived userId. Real bug found by the test: `send_json` crashed on datetime fields in scheme docs — fixed with `jsonable_encoder`. Token streaming is NOT implemented (one reply frame per turn; protocol is forward-compatible).

## Agent 9 — CSC Assist (2026-07-03)

`graph/agents/csc_assist.py` + `POST /agents/csc/alternatives` — suggests alternative documents when a citizen lacks one, grounded in the scheme's REAL document list from Mongo, explicitly instructed to answer "mandatory, no substitute" (Aadhaar, land records) rather than invent alternatives that would waste a citizen's CSC trip. First **role-gated** endpoint: `get_current_operator_id` in jwt_auth.py requires CSC_OPERATOR/ADMIN from the RS256-signed role claim. Verified: citizen → 403, operator → real alternatives (cancelled cheque/bank statement/bank letter for a missing passbook), unknown scheme → 404, quota-dead → graceful fallback, chat `csc_assist` intent → guidance reply.

## Agent 10 — Analytics (2026-07-03)

`graph/agents/analytics.py` + `POST /agents/admin/analytics/run` + `GET /agents/admin/analytics/latest` (admin-only via new `get_current_admin_id` — CSC operators also 403). All metrics are pure Mongo aggregations (quota-proof); LLM only writes the narrative, with a template fallback. `benefits_unlocked_estimate` is deliberately null with the reason stated — no disbursal tracking exists, and inventing a rupee figure would repeat the benefit_parser fake-precision bug. **Its first report immediately exposed two real citizen-facing data bugs (below) — the feature paid for itself within minutes.**

## Trending schemes (2026-07-03)

`trend_events` collection (TTL 30d): ai_service writes "search" events per scheme surfaced in chat, Spring Boot writes "save" events on application create. `GET /api/v2/schemes/trending` (top-5 over 7 days, 6h in-memory cache, `?state=` filter) + admin-gated cache clear. Verified with real events end-to-end.

## Observability — `/agents/health` + `/agents/trace/{session_id}` (2026-07-03)

Health: all 13 fleet members with honest statuses (`not_built` for missing agents, green/yellow/red from real `agent_alerts` + 48h staleness), liveness from reasoning_traces / schemes.lastUpdated / admin_reports. Trace: citizen-facing, **ownership enforced via the session's userId** — another citizen requesting the same UUID gets an indistinguishable 404.

## Two state-attribution bugs — found by Agent 10's first report, fixed same day (2026-07-03)

**Bug 1**: `citizen_profiles.state` holds codes ("UP"), `schemes.state` holds full names ("Uttar Pradesh") — the vector-search state filter exact-matched the code, so **every state scheme was invisible to every citizen** (only central schemes ever matched). Fixed with `utils/states.py` (`state_match_variants`) in both search paths + analytics.

**Bug 2**: ALL 565 MyScheme-ingested schemes had `state=None` — `basicDetails.state.label` (where MyScheme actually puts the state when `beneficiaryState` is null) was never read, so hundreds of state schemes were filed as central and shown nationally. Fixed the mapper (+ `nodalDepartmentName` as ministry fallback) and wrote `scripts/run_state_rehydration.py` (metadata-only refetch, no LLM, no re-embedding). The two bugs compounded: citizens saw other states' schemes as central AND missed their own state's.

## Data-quality repair infrastructure (2026-07-03)

- `scripts/run_myscheme_batch.py --offset N`: fixed the no-op-refetch bug (offset-less re-runs refetched the same first N schemes). Batch 4 with offset: 699 → 984 schemes, zero failures.
- `upsert.py`: empty `eligibilityRules` + non-empty text no longer content-hash-skipped (was permanently freezing quota-failure holes in). `scripts/run_rules_backfill.py` heals them from text already in Mongo — quota-aware, stops early after 8 consecutive failures, safe to re-run until zero.

## Cleanup (2026-07-03)

Removed 10 stale pre-v5 planning/team docs that described the old 4-person-team architecture (a "Flask OCR Worker" that hasn't existed since the rebuild, "Member 1/2/3/4" divisions) — fully superseded by `CLAUDE.md` + `docs/adr/ADR-001`. Untracked a 1.5MB tool-state DB file that had been committed by mistake. Removed a redundant 334-directory marketplace-skills copy after confirming the same set exists at the user-level `~/.claude/skills`. `docs/PRANJAL_HANDOFF.md` was deliberately **kept** — it's still actively cited from 6 Java files as design rationale for the encryption service, despite Pranjal being off the project.
