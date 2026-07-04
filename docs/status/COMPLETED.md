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

CLAUDE.md's real target surface for text chat. `graph/chat_turn.py` extracts the one shared turn implementation (REST + WS run identical logic); `routers/ws_router.py` authenticates via the httpOnly cookie on the handshake (browsers can't set custom headers on WebSocket, so the JWT is the sole gate — invalid token closes 1008 before any message). Verified with a real WebSocket client: tampered cookie rejected by signature, multi-turn on one connection, sessions persisted with JWT-derived userId. Real bug found by the test: `send_json` crashed on datetime fields in scheme docs — fixed with `jsonable_encoder`.

**Token streaming shipped 2026-07-04.** `stream_chat_turn` (graph/chat_turn.py) is the streaming twin of `run_chat_turn` — LangGraph `astream(stream_mode=["messages","values"])` taps the LLM calls *inside* agent nodes (langchain-core auto-upgrades `ainvoke` to streaming when a token callback is attached), so no agent needed rewriting; the intent classifier's tokens are filtered out by node name. Protocol per turn: 0..N `{"type":"token","text"}` frames, then one authoritative `{"type":"done", reply, intent, active_schemes}` — clients replace accumulated token text with done.reply, because a mid-stream provider fallback can leave partial tokens behind. Frontend: ChatPage talks WebSocket first (client-generated UUID session id, `/ws` added to the Vite proxy with `ws:true`, live-updating streaming bubble) and falls back to `POST /orchestrator/chat` if the socket can't open. Verified with a real JWT cookie through the Vite proxy: 163 token frames, first token ~6s, done frame with 5 schemes, and session/traces/trend_events all persisted in Mongo.

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

## small_talk intent — no more fake recommendations for "hello" (2026-07-04)

User-found bug: "hello" had no matching intent label, so the classifier forced it into `eligibility_query`, vector search returned the 5 nearest schemes to the literal word "hello" (random ones, wrong-state included), and the composer presented them as "aapke profile ke hisaab se" — confidently wrong. Fix: new `small_talk` label in the classifier (greeting/thanks/chit-chat, with an explicit "a bare greeting is never eligibility_query" instruction) routed to `graph/agents/small_talk.py` — warm multilingual reply inviting the citizen to share state/occupation/income, **zero scheme cards, no retrieval claimed**, static fallback if the LLM call fails. Verified over WS: "hello" and "thank you sathi" → small_talk with 0 schemes; the real kisan query still → eligibility_query with 5.

## Chat learns your profile (2026-07-04)

"Main UP ka kisan hoon, income 1.5 lakh" used to die with the turn — the next session started blank. Now `graph/profile_learner.py` runs fire-and-forget after every fact-bearing turn (eligibility_query / financial_plan / application_request only; scheduled via `asyncio.create_task` from `_persist_turn`, so reply latency never pays for it): PII-masked message → Groq extraction (saves Gemini quota) → strict whitelist/range validation (state must be a real 2-char code, category/occupation/gender enums, income/land clamped — a hallucination can never invent a field or write PII) → diff against current profile → `PATCH /internal/profile/{userId}` (Spring creates the profile if missing, recalculates completeness; PATCH widened to gender/district/isBpl/isRural/isDisabled/familySize/hasLand/landAreaAcres) → `conversation_sessions.profileUpdates` per the CLAUDE.md schema. Verified end-to-end: one Hinglish sentence set 7 fields (profileCompleteness 0→57), and a **new** session's vague "koi yojna batao" returned farmer-targeted schemes incl. a UP state scheme — personalization from memory, not from the message.

## Session summaries at chat end (2026-07-04)

CLAUDE.md's schema always said `conversation_sessions.summary` is "written by Gemini at session end" — but web chat never had a session-end event, so no summary was ever written. Now the WS disconnect *is* the end event: `graph/session_summary.py` is scheduled fire-and-forget from ws_router's `finally` block — loads the transcript, PII-masks every line, LLM (prefer=groq) writes a 2-3 sentence English summary covering the citizen's situation, schemes discussed, and pending next steps. `summarizedMessageCount` makes it idempotent across reconnects (connect-and-leave without chatting writes nothing; reconnecting and chatting more rewrites the summary for the fuller transcript). Verified: 2-turn PM Kisan conversation → disconnect → accurate summary in Mongo within seconds. REST-only sessions still get no summary (no end event exists there) — fine, the UI is WS-first.

## CSC Operator Dashboard — Agent 9 UI, plus a real auth bug it uncovered (2026-07-04)

Agent 9's backend (`POST /agents/csc/alternatives`) existed but had no frontend — CSC operators had no way to actually use it. Built `frontend/src/pages/CscDashboardPage.jsx` (route `/csc-dashboard`): scheme code + missing-document-type form, verdict badge (alternatives available / mandatory-no-substitute / none found), per-alternative "how to get it" cards, operator advice line. Wired `ai.cscAlternatives()` into `lib/api.js`.

**Building it surfaced a real bug**: the endpoint required BOTH an operator JWT cookie AND an `X-API-Key` header (`dependencies=[Depends(require_api_key)]`) — but a CSC operator uses this from a browser, and browsers can't hold a service secret without exposing it client-side. This is the exact class of bug the 2026-07-03 citizen-endpoint fix (JWT-cookie-only, X-API-Key reserved for admin/internal) was supposed to close everywhere; this one endpoint fell through. Fixed by dropping `require_api_key` from `/agents/csc/alternatives` — the operator-role JWT check (`get_current_operator_id`, 403 for non-operators) is the correct sole gate, same trust model as every other citizen-facing endpoint.

Verified end-to-end through the Vite proxy with no API-key header: CITIZEN-role token → 403 ("Operator role required"); same account flipped to `CSC_OPERATOR` in Mongo + re-logged-in (role rides in the JWT claim, confirmed via Spring's `JwtUtils`) → 200 with the real scheme name resolved; unknown scheme_code → 404. The LLM-generated alternatives content itself hit the same quota wall as the backfill jobs below (safe static fallback, not a crash) — mechanics are fully proven, content will populate once quota resets.

## Minimal CI workflow + a real requirements.txt bug it caught before it shipped (2026-07-04)

Built `.github/workflows/ci.yml` — 3 jobs, scoped honestly to what this repo actually has (no pytest/JUnit suite exists, so these are smoke checks, not test coverage): `frontend-build` (`npm ci && npm run build`), `python-import-check` (installs `ai_service/requirements.txt` then runs `python -c "import ai_service.main"` — a real import that eagerly evaluates every router's module-level code, including decorator arguments, so it would have caught the `agent_router.py`/`ocr_router.py` `Depends(require_api_key)`-after-removing-the-import mistakes made and self-caught earlier this same session), and `spring-compile` (`mvn -B -q compile`).

Didn't stop at "the workflow file looks right" — actually ran the python-import-check's core assumption against a **fresh venv on real disk** (not the long-lived dev venv, which accumulates ad-hoc installs that mask real `requirements.txt` gaps). That surfaced a genuine bug: **`easyocr` — the actual OCR engine `ocr_router.py` imports and that was verified live-scanning a real document earlier today — was missing from `requirements.txt` entirely.** It only worked locally because someone had `pip install`ed it directly into the dev venv at some point, never adding it to the requirements file. A fresh production install would have silently shipped a broken document scanner. Meanwhile `requirements.txt` carried two now-dead, very heavy dependencies: `openai-whisper` (pulls a multi-**gigabyte** CUDA/GPU torch dependency chain — cudnn, nccl, triton, cusparselt — for a feature, `voice.py`, deleted earlier this same session) and `paddlepaddle`/`paddleocr` (~200MB, zero import references anywhere in the live codebase; `easyocr` is the OCR engine actually used). Fixed: added `easyocr>=1.7`, removed both dead entries.

Verified the fix properly, not just by reasoning about it: a second from-scratch venv install of the corrected `requirements.txt` completed with `Successfully installed...`, and `python -c "import ai_service.main"` against *that* fresh install printed `FRESH INSTALL IMPORT: OK`. (First attempt at this verification hit `No space left on device` — turned out to be the session's `/tmp` scratchpad living on a small 7.7GB RAM-backed tmpfs, not a real disk-space problem; moved the test venv to `/home/rudra/.cache/` and it completed cleanly. Test venvs deleted after use.)

Workflow file created but **not pushed or committed** — per this session's standing rule, creating a file is fine unprompted, git actions that touch the remote or history are not, without an explicit ask.

## Dead legacy endpoints removed (2026-07-04)

Follow-up to the `require_api_key` sweep's "confirmed dead, not touched" list. Re-checked and removed the two purely superseded router files: `ai_service/routers/chat.py` (`/chat/`, `/chat/stream` — the pre-rebuild ChromaDB RAG chatbot, fully replaced by `/orchestrator/chat` + `/ws/session/{id}`) and `ai_service/routers/voice.py` (`/voice/transcribe`, `/voice/query` — local-Whisper transcription, unrelated to and unused by the live `voice_conversation.py`). Checked first that nothing else in the codebase imports either file directly — confirmed only `main.py`'s router mounts referenced them. Their shared dependency `rag_chain.py` stays: `main.py`'s `/health` endpoint uses `get_chromadb_count`/`_memory_store` from it independently of `chat.py`. Also removed two now-orphaned rate limiter instances (`chat_limiter`, `voice_limiter` in `rate_limiter.py`) and corrected `main.py`'s root `/` endpoint description, which still advertised `/chat` and Whisper-based `/voice/*` as if live.

Left alone, deliberately: `status_tracker.py`'s `/status/check` — also currently uncalled by the frontend, but REMAINING.md's Phase 6 notes flag it as a scraper-based fallback path worth keeping for Agent 5's future grievance/status work, unlike `chat.py`/`voice.py` which have no forward value (their v5.0 replacements already exist and are better).

Verified: direct curl to the real backend port confirms all four removed paths now 404; `/agent/start`, `/health`, `/`, `/openapi.json` (endpoints sharing `main.py`'s startup/import code) still return 200; both backend and frontend build clean.

## "Jan Sahayak" helper marketplace deprecated and removed (2026-07-04)

The `require_api_key` sweep below turned up a whole separate, pre-rebuild feature nobody had documented: a human-helper marketplace (`jan_sahayak.py` + 4 frontend pages — HelperFinder, HelperRegistration, HelperLogin, HelperDashboard) with no auth on any endpoint (IDOR risk — helper dashboard and login worked by raw ID with no session), permanent unencrypted storage of uploaded government ID documents on local disk, a hardcoded fallback admin secret in source, a raw SQLite database instead of MongoDB, and zero mention in CLAUDE.md.

Checked for live impact first: `sahayak.db` had 0 registered helpers and 0 appointments; `secure_uploads/helper_docs/` was empty. Nothing was actually at risk. Presented the user three options (deprecate / harden / leave as-is) — decision was **deprecate**, since Agent 9 (CSC Assist) already serves the "get human help" need correctly: operator-mediated, MongoDB-backed, JWT-gated, no raw document storage.

Removed: `ai_service/routers/jan_sahayak.py`, `ai_service/sahayak.db`, `ai_service/secure_uploads/`, the router mount in `main.py`, all 4 frontend pages + their CSS, their imports/routes in `App.jsx`, the `/sahayak` Vite proxy entry. Fixed two now-dangling "Get Offline Help" CTAs (`SchemeDetailPage.jsx`, `ApplyMethodModal.jsx`) that linked to the deleted `/helpers` route — both now point at the still-live `/csc-finder` page, with copy corrected to promise a real CSC visit rather than the removed feature's "a Jan Sahayak will come help you" claim. Verified: backend `/openapi.json` shows zero `/sahayak` paths, direct `curl` to the backend port 404s, frontend and backend both build clean, unrelated features (`/ocr/scan`, `/csc-finder`) unaffected.

## Full require_api_key sweep — a third live bug found in the legacy voice-interview path (2026-07-04)

After finding the CSC and OCR bugs (below), grepped every `require_api_key` usage in `ai_service` and cross-referenced against every direct `fetch()` call in the frontend to find any other browser-facing endpoint gated by a header browsers can't send.

**Found #3**: `/agent/start` + `/agent/answer` (`agent_router.py`, the pre-rebuild Yojna Sathi ReAct interview) were both API-key-gated. `/agent/start` looked unreachable from the current frontend at first glance — but `voice_conversation.py`'s `/start` (no gate, called by ChatPage's mic button) writes directly into the **same shared in-memory `_sessions` dict** as `agent_router.py`. So the real path is: tap the mic (starts a voice session, no gate) → type a text answer instead of speaking (ChatPage's `sendMessage` voice-mode branch calls `/agent/answer`) → 403. Confirmed live before the fix, and confirmed fixed after: `/voice/conversation/start` → real session_id → `/agent/answer` with that id → 200, correct next question, through the vite proxy with zero API key.

**Audited and left alone** (legitimate as-is): `/internal/citizen/{id}/data` (Spring Boot → ai_service, genuine service-to-service), `/agents/health` + `/admin/analytics/*` + `/orchestrator/admin/discovery/run` (admin-only ops triggers, no browser admin dashboard exists to call them). **Confirmed dead, not a live bug** (zero frontend callers, so unreachable regardless of gate — flagged as legacy-cleanup candidates, not touched): `/chat/`, `/chat/stream` (old v4 REST/stream chat), `/voice/transcribe`, `/voice/query`, `/status/check`.

## Document scanner (Jan-Sahayak Lens) was silently broken for every real user — found + fixed (2026-07-04)

While auditing ai_service's endpoint auth coverage (prompted by finding the CSC auth bug earlier the same day), found `POST /ocr/scan` — the document scanner `ChatPage.jsx` calls directly from the browser with no session — required `X-API-Key`, the exact browser-incompatible gate just fixed on `/agents/csc/alternatives`. Confirmed live: a plain `curl` through the vite proxy with no API key returned 403. Every real citizen scanning a document in the app was hitting this. Fixed by dropping `require_api_key` — the endpoint is legitimately anonymous by design (zero-retention, in-memory only, `ocr_limiter` already does IP-based rate limiting; nothing citizen-scoped is read or written), so JWT wasn't the fix either — the browser call itself just needed no gate blocking it.

Same file had a second, independent bug: CLAUDE.md's non-negotiable OCR rule #2 ("use python-magic to inspect actual file bytes, do NOT trust the file extension") wasn't implemented — the code branched on the client-supplied `content_type` header and filename extension only, both spoofable. Added real byte-signature detection via `python-magic` (`ai_service/requirements.txt`; needs system `libmagic1`, confirmed already present). Verified both fixes together: a `.txt` file renamed to `fake.jpg` is now rejected with `415` showing the *true* detected mime (`text/plain`), not fooled by the extension; a synthetic PAN-card-style PNG with real text now scans end-to-end with no API key — 200, correct `doc_type: "PAN Card"`, masked ID `XXXXX1234X`, official-seal keyword detected.

## Cleanup (2026-07-03)

Removed 10 stale pre-v5 planning/team docs that described the old 4-person-team architecture (a "Flask OCR Worker" that hasn't existed since the rebuild, "Member 1/2/3/4" divisions) — fully superseded by `CLAUDE.md` + `docs/adr/ADR-001`. Untracked a 1.5MB tool-state DB file that had been committed by mistake. Removed a redundant 334-directory marketplace-skills copy after confirming the same set exists at the user-level `~/.claude/skills`. `docs/PRANJAL_HANDOFF.md` was deliberately **kept** — it's still actively cited from 6 Java files as design rationale for the encryption service, despite Pranjal being off the project.
