# CLAUDE.md — Yojna Setu
> Read this file at the start of every session. It is the single source of truth for codebase architecture, ownership, and conventions.

---

## What This Project Is
Yojna Setu is a multilingual AI assistant that helps Indian citizens discover and apply for government welfare schemes. It supports 22 Indian languages via text, voice (real-time), and WhatsApp. 419+ schemes indexed. DPDP Act 2023 compliant.

---

## Repo Structure
```
/
├── CLAUDE.md                  ← you are here
├── ai_service/                ← Rudra owns (Python 3.10, FastAPI)
│   ├── main.py
│   ├── routers/
│   │   ├── chat.py            ← text WebSocket + REST chat
│   │   ├── voice.py           ← voice WebSocket (WSS direct, NOT through Spring Boot)
│   │   ├── ocr.py             ← Aadhaar + income cert OCR
│   │   └── webhook.py         ← Twilio WhatsApp inbound
│   ├── orchestrator/
│   │   ├── graph.py           ← LangGraph StateGraph definition
│   │   ├── intent_classifier.py
│   │   ├── state.py           ← GraphState dataclass
│   │   └── router.py          ← conditional edge logic
│   ├── agents/
│   │   ├── agent1_eligibility/
│   │   │   ├── agent.py       ← ReAct loop
│   │   │   └── tools.py       ← 6 tool definitions
│   │   ├── agent2_discovery/
│   │   │   ├── agent.py       ← persistent event loop
│   │   │   ├── scrapers/      ← myscheme.py, pib_rss.py, datagov.py, states/
│   │   │   └── normalizer.py  ← Gemini eligibility extractor
│   │   ├── agent3_guidance/
│   │   │   ├── agent.py
│   │   │   ├── browser_navigator.py   ← browser-use wrapper
│   │   │   └── domain_whitelist.py    ← NEVER modify without security review
│   │   ├── agent4_document/
│   │   │   ├── agent.py
│   │   │   └── verifier.py
│   │   ├── agent5_grievance/
│   │   │   ├── agent.py
│   │   │   └── pgportal_navigator.py  ← browser-use, pgportal.gov.in only
│   │   ├── agent6_nudge/
│   │   │   ├── agent.py
│   │   │   └── whatsapp_sender.py
│   │   ├── agent7_financial/
│   │   │   └── agent.py
│   │   ├── agent8_comparison/
│   │   │   └── agent.py
│   │   ├── agent9_csc/
│   │   │   ├── agent.py
│   │   │   └── form_generator.py
│   │   └── agent10_analytics/
│   │       ├── agent.py
│   │       └── report_generator.py
│   ├── utils/
│   │   ├── encryption.py      ← AES-256 Fernet PII encrypt/decrypt
│   │   ├── pii_masker.py      ← strips Aadhaar/phone/PAN from text before LLM
│   │   └── injection_guard.py ← prompt injection detection
│   └── requirements.txt
├── pipeline/                  ← Rudra owns (Python 3.10, runs as Cloud Run Job)
│   ├── config.py              ← RATE_LIMIT_SECONDS=2, USER_AGENT, STATE_LIST, RESPECT_ROBOTS_TXT
│   ├── normalizer.py          ← Gemini Flash eligibility_rules extractor
│   ├── upsert.py              ← content-hash diff + MongoDB upsert + embedding flag
│   └── scrapers/
│       ├── myscheme.py        ← MyScheme sitemap scraper
│       ├── datagov.py         ← data.gov.in API puller
│       ├── pib_rss.py         ← PIB RSS watcher + Gemini extractor (every 30min)
│       └── states/            ← one file per state
│           ├── up.py          ← up.gov.in scheme section
│           ├── mh.py          ← maharashtra.gov.in
│           ├── rj.py          ← rajasthan.gov.in
│           ├── tn.py          ← tn.gov.in
│           └── wb.py          ← wb.gov.in
├── deploy/backend/spring-gateway/ ← Pranjal owns (Java 17, Spring Boot 3.2)
│   ├── src/main/java/com/yojnasetu/gateway/
│   │   ├── auth/              ← OTP + JWT (RS256)
│   │   ├── profile/           ← CitizenProfile CRUD
│   │   ├── model/             ← UserProfile, AuditLog, Scheme, StatusCheckLog
│   │   ├── applications/      ← Application tracking
│   │   └── audit/             ← AuditLog append-only writes
│   └── pom.xml
├── frontend/                  ← React 18 + Vite + Tailwind PWA
│   ├── src/
│   │   ├── components/
│   │   │   ├── VoiceRecorder.jsx   ← MediaRecorder → WSS to FastAPI DIRECT
│   │   │   ├── ChatWindow.jsx
│   │   │   ├── TrendingBar.jsx     ← top 5 trending schemes, refreshes every 6h
│   │   │   └── CSCDashboard.jsx
│   │   └── api/
│   │       ├── springClient.js     ← REST calls to Spring Boot (/api/v2/*)
│   │       └── aiClient.js         ← WebSocket to FastAPI (wss://ai.*)
│   └── package.json
├── voice/                     ← Pipecat pipeline modules (Rudra owns)
│   ├── sarvam_stt.py          ← Saaras V3, mode="transcribe", chunk ≤ 25s
│   ├── sarvam_tts.py          ← Bulbul V3, temperature + speaker config
│   └── vad_config.py          ← Saaras V3 exclusive VAD tuning params
└── docs/                      ← All 6 project documents
```

---

## Services and URLs

| Service | Dev | Staging | Prod |
|---|---|---|---|
| FastAPI (AI) | localhost:8000 | https://ai-staging.yojnasetu.in | https://ai.yojnasetu.in |
| Spring Boot (Data) | localhost:8080 | https://api-staging.yojnasetu.in/api/v2 | https://api.yojnasetu.in/api/v2 |
| React PWA | localhost:5173 | https://staging.yojnasetu.in | https://yojnasetu.in |
| MongoDB Atlas | Atlas M0 (free, dev cluster) | Atlas M10 Mumbai | Atlas M10+ Mumbai |

---

## Critical Architecture Rules

### Voice WebSocket — DIRECT to FastAPI, Never Through Spring Boot
```
CORRECT:   Browser → wss://ai.yojnasetu.in/ws/voice/{session_id}   (FastAPI, async)
WRONG:     Browser → Spring Boot gateway → FastAPI                  (thread exhaustion)
```
Spring Boot is thread-per-connection (blocking I/O). 100 concurrent voice sessions = thread pool exhaustion = total service failure. FastAPI is ASGI async — it handles thousands of concurrent WebSockets natively. This is a hard rule. Do not create any Spring Boot WebSocket endpoints.

### REST vs WebSocket Split
- **Spring Boot handles**: all REST endpoints (`/api/v2/*`), auth, profile CRUD, scheme metadata, applications, audit logs, PDF export
- **FastAPI handles**: all WebSocket connections (text chat + voice), OCR, Twilio webhook, internal AI operations, Pipecat pipeline

### Never Touch the Other Service's Domain
If editing `data_service/`, do not modify `ai_service/` routes and vice versa — unless explicitly updating both sides of an API contract change, in which case update the contract in `docs/06_API_Contract.docx` first.

### State Fields: Two Representations Exist — Always Match Both
`citizen_profiles.state` holds 2-char codes ("UP"); `schemes.state` holds full names ("Uttar Pradesh" — what MyScheme's API returns). Any query joining the two MUST go through `ai_service/utils/states.py`'s `state_match_variants()` — a raw equality match silently excludes all state schemes from results (real bug, 2026-07-03: every citizen was getting only central schemes). Same class of rule as index naming: on shared collections, ai_service's `ensure_indexes()` owns index creation; Java models use explicit `name=` matching it, or declare none.

---

## Environment Variables

### FastAPI (`ai_service/.env`) — never commit this file
```
GEMINI_API_KEY=
SARVAM_API_KEY=
GOOGLE_CLOUD_PROJECT=
GCS_BUCKET_TEMP_OCR=
SPRING_BOOT_INTERNAL_URL=http://localhost:8080
FIELD_ENCRYPTION_KEY=           # Fernet key — load from GCP Secret Manager in prod
TWILIO_AUTH_TOKEN=              # for X-Twilio-Signature validation
TWILIO_ACCOUNT_SID=
DATAGOVIN_API_KEY=              # free key from data.gov.in account page
PIPELINE_MONGO_URI=             # same Atlas cluster, separate connection for pipeline job
```

### Spring Boot (`data_service/src/main/resources/application-local.yml`) — never commit
```
spring.data.mongodb.uri=
JWT_PRIVATE_KEY_PATH=
JWT_PUBLIC_KEY_PATH=
FIELD_ENCRYPTION_KEY=           # same key as FastAPI — load from GCP Secret Manager in prod
```

---

## MongoDB Collections

### citizen_profiles
```json
{
  "_id": "ObjectId",
  "userId": "ObjectId (ref: users, unique)",
  "name": "string (AES-256 encrypted)",
  "dob": "string (AES-256 encrypted)",
  "phone": "string (AES-256 encrypted)",
  "gender": "male|female|other",
  "annualIncome": "number",
  "category": "general|obc|sc|st",
  "occupation": "farmer|student|daily_wage|...",
  "isBpl": "boolean",
  "isDisabled": "boolean",
  "state": "UP|MH|... (2-char code)",
  "district": "string",
  "isRural": "boolean",
  "familySize": "number",
  "aadhaarHash": "string (SHA-256 + salt — NEVER raw UID)",
  "verifiedDocs": ["aadhaar","pan","income_cert"],
  "profileCompleteness": "0-100",
  "consentGivenAt": "ISODate",
  "updatedAt": "ISODate"
}
```

### schemes
```json
{
  "_id": "ObjectId",
  "schemeCode": "string (unique)",
  "name": "string",
  "ministry": "string",
  "state": "string|null (null = central scheme)",
  "category": ["farmer","student","sc","disabled",...],
  "eligibilityRules": { "maxIncome": 200000, "minAge": 18, ... },
  "benefitAmount": "string",
  "applyUrl": "string",
  "embedding": "[384-dim vector for Atlas Vector Search]",
  "lastUpdated": "ISODate"
}
```

### applications
```json
{
  "_id": "ObjectId",
  "userId": "ObjectId",
  "schemeId": "ObjectId",
  "schemeCode": "string (denormalized)",
  "schemeName": "string (denormalized)",
  "status": "saved|in_progress|submitted|approved|rejected|disbursed",
  "statusHistory": [{ "status": "string", "at": "ISODate" }],
  "eligibilityScore": "0-100",
  "externalAppId": "string (govt portal ref)",
  "appliedAt": "ISODate"
}
```

### conversation_sessions
```json
{
  "_id": "ObjectId",
  "userId": "ObjectId",
  "sessionId": "UUID v4 (unique)",
  "channel": "web|whatsapp|voice",
  "lang": "hi|ta|bn|te|mr|...",
  "summary": "string (written by Gemini at session end)",
  "profileUpdates": { "annualIncome": 150000 },
  "schemesShown": ["ObjectId"],
  "messages": [{ "role": "user|assistant", "content": "string", "at": "ISODate" }],
  "intentTags": ["scheme_discovery","eligibility_check"],
  "startedAt": "ISODate",
  "expiresAt": "ISODate (TTL: startedAt + 90 days)"
}
```

### audit_logs (append-only — never update or delete)
```json
{
  "_id": "ObjectId",
  "userId": "ObjectId",
  "action": "profile_read|profile_write|scheme_search|delete_request",
  "endpoint": "string",
  "ip": "string",
  "at": "ISODate"
}
```

### trend_events (TTL 30 days — auto-deleted)
```json
{
  "_id": "ObjectId",
  "scheme_code": "string (the key — scheme_id is NOT stored; vector-search results project _id out, and scheme_code is the public identifier everywhere else)",
  "scheme_name": "string (denormalized for display)",
  "event_type": "search | save | view",
  "user_state": "UP|MH|...",
  "at": "ISODate (TTL index: 30 days)"
}
```
Index: `{ scheme_code: 1, user_state: 1, at: -1 }` — created by ai_service's `ensure_indexes()` ONLY; the Java `TrendEvent` model deliberately declares no indexes (two services creating the same index under different names = IndexOptionsConflict boot failure)
Trending computation aggregation (runs every 6h, cached with TTL 6h):
```js
db.trend_events.aggregate([
  { $match: { at: { $gte: 7_days_ago } } },
  { $group: { _id: "$scheme_code", count: { $sum: 1 } } },
  { $sort: { count: -1 } },
  { $limit: 5 }
])
```

### reasoning_traces (TTL 30 days)
```json
{
  "session_id": "string",
  "agent_name": "string",
  "tool_called": "string",
  "input": "string",
  "output": "string",
  "reasoning": "string",
  "duration_ms": "number",
  "at": "ISODate"
}
```

### admin_reports (permanent)
```json
{
  "report_date": "ISODate",
  "top_dropoff_schemes": "string[]",
  "confusing_criteria": "string[]",
  "state_gaps": "string[]",
  "new_citizens": "number",
  "benefits_unlocked_estimate": "number",
  "narrative": "string"
}
```

### agent_alerts (TTL 7 days)
```json
{
  "agent_name": "string",
  "alert_type": "string",
  "message": "string",
  "at": "ISODate",
  "resolved": "bool"
}
```

### nudge_log (TTL 90 days)
```json
{
  "citizen_id": "string",
  "message_type": "string",
  "scheme_id": "string",
  "sent_at": "ISODate",
  "delivered": "bool",
  "replied": "bool"
}
```

---

## Key API Endpoints

### Spring Boot REST (`/api/v2/*`)
| Method | Path | Notes |
|---|---|---|
| POST | /auth/otp/send | 3 req/hour per phone |
| POST | /auth/otp/verify | Returns httpOnly JWT cookies |
| GET | /profile/me | PII decrypted server-side |
| PATCH | /profile/me | Auto-recalculates profileCompleteness |
| DELETE | /user/me | Cascades all 5 collections in 30s |
| POST | /consent | Must be called before any profile write |
| GET | /applications | Filter by ?status= |
| POST | /applications | Creates with status='saved' |
| GET | /internal/profile/{userId} | FastAPI → Spring Boot only, service JWT |
| PATCH | /internal/profile/{userId} | FastAPI writes session-end profile updates |
| GET | /internal/scheme/{id}/rules | Machine-readable eligibility rules |
| GET | /schemes/trending | Any JWT — top 5 national trending (cached 6h). Optional ?state=UP for state-specific |
| GET | /schemes/trending/states | Any JWT — all-state trending map, pre-populates state toggle on frontend |
| GET | /admin/pipeline/status | Admin JWT — {last_run, duration_minutes, schemes_added, schemes_updated, errors[]} |
| POST | /admin/pipeline/trigger | Admin JWT — manually triggers Cloud Run pipeline job (emergency refresh) |
| GET | /admin/schemes/unembedded | Admin JWT — scheme_ids flagged for re-embedding not yet processed |
| POST | /admin/trend/recompute | Admin JWT — forces trending recompute outside 6h cache |

**Implementation status (2026-07-03)** — LIVE: otp/send, otp/verify, plus `/auth/refresh` + `/auth/logout` (not in table above), profile/me GET/PATCH, consent, DELETE /user/me (verified 0.35s cascade incl. ai_service's collections via its internal endpoint), applications GET/POST + GET/PATCH `/applications/{id}`, internal profile GET/PATCH + scheme rules, schemes/trending (+`?state=`), admin/trend/recompute (ROLE_ADMIN). NOT built: trending/states, admin/pipeline/*, admin/schemes/unembedded.

### FastAPI (`ai.yojnasetu.in`)
| Method | Path | Notes |
|---|---|---|
| WSS | /ws/session/{session_id} | Text chat WebSocket, streams LLM tokens |
| WSS | /ws/voice/{session_id} | Voice WebSocket — DIRECT, async, Pipecat entry |
| POST | /voice/session/start | Creates session in MongoDB, returns session_id |
| POST | /voice/session/end | Triggers summary + profileUpdates write |
| POST | /ocr/aadhaar | Multipart image, max 5MB, MIME validated via python-magic |
| POST | /ocr/income-cert | Multipart PDF or image |
| POST | /webhook/whatsapp | MUST validate X-Twilio-Signature on every request |
| GET | /metrics/impact | Admin JWT only |
| GET | /agents/health | Admin JWT — status of all 10 agents: {agent_name, status: green/yellow/red, last_active} |
| GET | /agents/trace/{session_id} | Citizen JWT — full reasoning trace: [{agent, tool, input, output, reasoning, duration_ms}] |
| POST | /agents/compare | Citizen JWT — body: {scheme_id_a, scheme_id_b}. Triggers Agent 8. |
| GET | /agents/financial-plan | Citizen JWT — triggers Agent 7. Returns {total_annual_benefit, breakdown, calendar, ranked} |
| POST | /agents/grievance | Citizen JWT — body: {scheme_id, external_app_id, complaint_description}. Triggers Agent 5. |
| GET | /agents/nudge/status | Citizen JWT — nudge preferences + last 5 nudges sent |
| POST | /agents/nudge/optout | Citizen JWT — sets nudge_opted_out=true |
| POST | /agents/document/verify | Citizen JWT — multipart: document file + scheme_ids[]. Triggers Agent 4. |
| POST | /agents/csc/alternatives | Operator JWT — body: {scheme_id, missing_doc_type}. Triggers Agent 9. |
| GET | /admin/agents/analytics/latest | Admin JWT — latest Agent 10 weekly report |
| POST | /admin/agents/nudge/trigger | Admin JWT — manually triggers Agent 6 batch |

**Implementation status (2026-07-03)** — LIVE (with path deviations from the table above where noted): `WSS /ws/session/{id}` (cookie-JWT auth, streams real LLM tokens as `{"type":"token"}` frames + one authoritative `{"type":"done"}` frame per turn — 2026-07-04), `POST /orchestrator/chat` (REST twin of the WS endpoint, not in table), `GET /agents/health` (13-agent registry, honest `not_built` statuses), `GET /agents/trace/{id}` (ownership-enforced via session userId), `GET /agents/financial-plan`, `POST /agents/document/verify-ppo` (two-file PPO/Aadhaar mismatch — the generic single-doc `/agents/document/verify` is NOT built), `POST /agents/csc/alternatives` (body uses `scheme_code`, not scheme_id), analytics at `POST /agents/admin/analytics/run` + `GET /agents/admin/analytics/latest` (not `/admin/agents/...`), `DELETE /internal/citizen/{id}/data` (DPDP cascade, called by Spring Boot). NOT built: voice WS + voice sessions, /webhook/whatsapp, /agents/compare (comparison runs via chat intent instead), /agents/grievance, nudge endpoints, /metrics/impact.

---

## Voice Pipeline (Pipecat — CONFIRMED, not LiveKit)

**Stack**: Pipecat → Sarvam Saaras V3 (STT) → Gemini 2.5 Flash (LLM) → Sarvam Bulbul V3 (TTS)

**Key rules**:
- STT: always pass `mode="transcribe"` — specify explicitly even though it's the Saaras v3 default
- STT: audio chunks MUST be ≤ 25 seconds (Sarvam hard limit: 30s — keep buffer)
- STT: audio format: 16kHz mono PCM or WAV
- TTS: always specify `model="bulbul:v3"` explicitly — do NOT rely on defaults
- TTS: bulbul:v3 supports `pace` and `temperature` ONLY — do NOT use `pitch` or `loudness` (v2 params, silently fail on v3)
- TTS: set `speaker`, `pace`, and `temperature` per language in Pipecat config
- VAD: use Saaras V3 exclusive fine-grained VAD tuning params in `voice/vad_config.py`
- Session: one concurrent voice session per userId enforced
- Audio: NEVER persisted — only text transcript written to conversation_sessions
- Install: `uv add "pipecat-ai[sarvam]"` (not pip install pipecat — use uv)

```python
# voice/voice_pipeline.py — reference pattern
# IMPORTANT: split imports — not from pipecat.services.sarvam directly
from pipecat.services.sarvam.stt import SarvamSTTService
from pipecat.services.sarvam.tts import SarvamTTSService

stt = SarvamSTTService(
    api_key=os.environ["SARVAM_API_KEY"],
    model="saaras:v3",
    mode="transcribe",  # always specify explicitly even though it's the default
    language="hi-IN",   # detected per session, updated dynamically
)

tts = SarvamTTSService(
    api_key=os.environ["SARVAM_API_KEY"],
    model="bulbul:v3",
    speaker="meera",    # one of 35+ available speakers
    temperature=0.7,
    pace=1.0,           # bulbul:v3 supports: pace + temperature ONLY
    # DO NOT USE: pitch, loudness — those are bulbul:v2 only, will silently fail on v3
)
```

---

## Security Rules (Non-Negotiable)

1. **Twilio webhook**: validate `X-Twilio-Signature` on EVERY POST to `/webhook/whatsapp` using `twilio.request_validator.RequestValidator`. Return 403 on invalid. No exceptions — unvalidated webhooks allow credit-draining attacks.

2. **OCR MIME validation**: use `python-magic` to inspect actual file bytes. Do NOT trust file extension. Accept only confirmed `image/jpeg`, `image/png`, `application/pdf` byte signatures.

3. **Aadhaar**: SHA-256 hash + server-side salt only. Never log, never store raw UID. Add `assert "aadhaar" not in log_line` check in logging middleware.

4. **PII encryption**: encrypt `name`, `dob`, `phone`, `email`, `address` with Fernet (AES-256) before every MongoDB write. Key from GCP Secret Manager only.

5. **JWT**: RS256, stored in httpOnly cookies only — NEVER localStorage. 60-min access token, 7-day refresh.

6. **Voice audio**: processed in-memory in Pipecat. Never written to disk or GCS. Only transcript goes to MongoDB.

7. **Prompt injection**: run `injection_guard.py` on every voice transcript AND text input before LLM call.

8. **No PII in logs**: logging middleware must strip name, phone, Aadhaar-pattern from all log lines before emission.

---

## Multi-Agent System

**Framework**: LangGraph StateGraph
All agents share GraphState. Never call agents directly — always go through Orchestrator.

### Agent Directory

| Agent | Type | Trigger | Timeout | Built? (2026-07-04, detail in docs/status/) |
|---|---|---|---|---|
| Orchestrator | Always-on (FastAPI) | Every citizen message | 30s total | ✅ `ai_service/graph/orchestrator.py`, incl. `small_talk` intent (no fake scheme retrieval on greetings) |
| Agent 1 — Eligibility | On-demand (LangGraph node) | Orchestrator route | 10s | ✅ |
| Agent 2 — Discovery | Always-on (Cloud Run service) | PIB RSS 30min + daily cron | 2h for full run | ✅ MyScheme live (1,230 schemes, growing — see docs/status/REMAINING.md); PIB/data.gov.in blocked on config |
| Agent 3 — Application | On-demand (Cloud Run job) | Citizen apply action | 60s | ✅ guidance path (curated playbook + grounded LLM fallback, domain-whitelisted URLs) via `application_request` chat intent; ❌ browser-use automation not started |
| Agent 4 — Document | On-demand (FastAPI) | Document upload | 15s | ✅ incl. v5.0 PPO/Aadhaar mismatch check |
| Agent 5 — Grievance | On-demand (Cloud Run job) | Citizen grievance request | 120s | ✅ recording path (persists to `grievances`, CPGRAMS self-filing guidance) via `grievance` chat intent + `POST /agents/grievance`; ❌ pgportal automation + NPCI/SPARSH monitoring not started |
| Agent 6 — Nudge | Scheduled (Cloud Run job) | Daily 8AM + weekly Mon 9AM IST | 10min | ❌ blocked on Twilio WhatsApp approval |
| Agent 7 — Financial | On-demand (LangGraph node) | Orchestrator route | 10s | ✅ |
| Agent 8 — Comparison | On-demand (LangGraph node) | Orchestrator route | 10s | ✅ |
| Agent 9 — CSC | On-demand (LangGraph node) | CSC operator request | 15s | ✅ doc-alternatives, operator-JWT-gated (browser dashboard at `/csc-dashboard`, no service key required) |
| Agent 10 — Analytics | Scheduled (Cloud Run job) | Weekly Sunday 11PM IST | 30min | ✅ on-demand; weekly cron is Phase 11 |
| Agent 11 — Biometric Assist (v5.0) | On-demand (CV module) | DLC liveness attempt | 20s | ❌ not started; model provenance unresolved |
| Agent 12 — Offline Survival Proof (v5.0) | On-demand (PWA + signing) | Offline DLC generation | 30s | ❌ not started; needs PWA infra first |

### GraphState (never rename fields without updating all agents)
Actual implementation is `ai_service/graph/state.py` — a `TypedDict, total=False`, not a `@dataclass` (every agent imports from there rather than redefining its own shape):
```python
class GraphState(TypedDict, total=False):
    citizen_id: str
    session_id: str
    channel: str          # "web|voice|whatsapp"
    lang: str
    profile: dict         # CitizenProfile decrypted
    messages: list[dict]  # conversation history: [{"role": "user"|"assistant", "content": str}]
    intent: str           # set by intent_classifier
    active_schemes: list[dict]  # set by Agent 1 / Agent 8
    reasoning_trace: list[dict] # append-only, every agent writes here
    agent_outputs: dict    # keyed by agent name
    reply: str             # final composed response text
```

### Orchestrator Routing (LangGraph conditional edges)
Reflects the actual `_INTENT_TO_NODE` map in `ai_service/graph/orchestrator.py` — every branch below routes to a real node, not a placeholder (the only placeholder targets left are `status_check` and the injection guard's `blocked` pseudo-intent):
```
START
  → intent_classifier node
      → "eligibility_query"   → Agent1
      → "application_request" → Agent3 (guidance path)
      → "grievance"           → Agent5 (recording path)
      → "comparison"          → Agent8
      → "financial_plan"      → Agent7
      → "document_verify"     → Agent4 (guidance-only on this text channel)
      → "csc_assist"          → Agent9
      → "small_talk"          → small_talk node (greetings/thanks — NO scheme retrieval)
      → "status_check"        → placeholder ("use Spring Boot's applications API")
      → "blocked"             → placeholder (injection guard's own reply)
END
```

### Agent Ownership Rules
- When editing any agent file, check `state.py` first — GraphState is shared, any field change affects all agents
- Agent 3 and Agent 5 browser-use domain whitelists are in `domain_whitelist.py` — **NEVER hardcode URLs elsewhere**
- Agent 2 scrapers follow rate limit config in `agents/agent2_discovery/config.py` — `RATE_LIMIT_SECONDS = 2`, `RESPECT_ROBOTS_TXT = True` — never override
- Adding a new tool to Agent 1: add to `tools.py` AND update tool descriptions in `agent.py` system prompt AND update this CLAUDE.md

### Browser-Use Security Rules (Agent 3 and Agent 5)
- Domain whitelist is the **ONLY** access control — agents cannot navigate outside `*.gov.in`
- Allowed domains: `*.gov.in`, `pgportal.gov.in`, `scholarships.gov.in`, `pmayg.nic.in`, `pmkisan.gov.in`
- No login credentials stored — agents use publicly accessible portal pages only
- Screenshots stored in GCS temp bucket, TTL 24 hours — **never** in MongoDB
- If browser-use throws `DomainBlockedError`, log to `agent_alerts` and return graceful failure — never retry with different domain
- `domain_whitelist.py` changes require a formal security review — do not edit casually

### Agent Timeout Table
```
Orchestrator total:    30s   (hard limit — LangGraph graph-level timeout)
Agent 1 Eligibility:   10s
Agent 2 Discovery:     2h    (full pipeline run)
Agent 3 Guidance:      60s   (portal navigation — not built yet; guidance path is a single LLM call, well under 10s)
Agent 4 Document:      15s
Agent 5 Grievance:     120s  (portal navigation + submission — not built yet; recording path is a single Mongo write, well under 10s)
Agent 6 Nudge batch:   10min
Agent 7 Financial:     10s
Agent 8 Comparison:    10s
Agent 9 CSC:           15s
Agent 10 Analytics:    30min
small_talk:            n/a   (no scheme retrieval, single LLM call, well under any other node's budget)
```

### Common Claude Code Tasks — Multi-Agent

**Add a new tool to Agent 1:**
1. Add tool function to `agents/agent1_eligibility/tools.py`
2. Add tool description to `agent.py` system prompt tool list
3. Add tool to the `tools=[]` list in the ReAct agent constructor
4. Write unit test in `tests/test_agent1_tools.py`
5. Update this CLAUDE.md tool registry

**Add a new agent:**
1. Create `/agents/agentN_name/` directory with `agent.py`
2. Add agent node to `orchestrator/graph.py`
3. Add routing condition to `orchestrator/router.py`
4. Add new intent label to `orchestrator/intent_classifier.py`
5. Add agent output key to `GraphState` in `orchestrator/state.py`
6. Add health check entry to `/agents/health` endpoint
7. Update this CLAUDE.md agent directory table

**Debug an agent timeout:**
1. Check `/agents/health` — which agent is red/yellow
2. Check `agent_alerts` collection for recent alerts from that agent
3. For browser-use agents (3, 5): check if govt portal changed its UI — most common cause
4. For Agent 2: check `agent_alerts` for source blocks (MyScheme rate limiting)
5. Paste Cloud Run logs into Claude Code — it will identify root cause

---

## Data Pipeline Agent

**Location**: `pipeline/` (separate from `ai_service/` and Spring Boot — standalone Cloud Run Job)
**Owner**: Rudra
**Schedule**: Cloud Run Job, daily at **2AM IST** (`cron: "0 2 * * *"`)
**PIB RSS watcher**: separate lightweight Cloud Run Job, every **30 minutes**

**Legal rules hardcoded in `pipeline/config.py` — never change these:**
```python
RATE_LIMIT_SECONDS = 2          # sleep between every HTTP request — no exceptions
USER_AGENT = "YojnaSetu-Bot/1.0 (student project; contact: rudra@yojnasetu.in)"
RESPECT_ROBOTS_TXT = True       # never set to False
SCRAPE_HOUR_IST = 2             # always run off-peak (2-4AM IST)
```

**Sub-agents:**

| File | Role | Rate limit |
|---|---|---|
| `pipeline/scrapers/myscheme.py` | MyScheme sitemap → all scheme URLs → parse each page | 1 req/2s |
| `pipeline/scrapers/datagov.py` | data.gov.in REST API → PM-KISAN, PMAY, NSP, Ayushman datasets | API key, no rate limit |
| `pipeline/scrapers/pib_rss.py` | PIB RSS feed → detect keyword matches → Gemini extracts eligibility | polls every 30min |
| `pipeline/scrapers/states/up.py` | up.gov.in scheme section | 1 req/2s |
| `pipeline/scrapers/states/mh.py` | maharashtra.gov.in | 1 req/2s |
| `pipeline/scrapers/states/rj.py` | rajasthan.gov.in | 1 req/2s |
| `pipeline/scrapers/states/tn.py` | tn.gov.in | 1 req/2s |
| `pipeline/scrapers/states/wb.py` | wb.gov.in | 1 req/2s |
| `pipeline/normalizer.py` | Gemini Flash → extracts `eligibility_rules` JSON from raw text | ~₹2/day |
| `pipeline/upsert.py` | content-hash diff → MongoDB upsert → flags changed schemes for re-embedding | — |

**Gemini normalizer extraction prompt targets:**
```
{maxIncome, minAge, maxAge, category: [], occupation: [], state, isRural, isBpl, hasLand}
```

**Upsert logic (in `pipeline/upsert.py`):**
- `scheme_code` = unique key (slug of scheme name + ministry code)
- Content hash unchanged → **skip** (no DB write)
- Content changed → **update** + flag `needs_embedding=true`
- New scheme → **insert** + flag `needs_embedding=true`
- Only flagged schemes go through Atlas Vector Search re-embedding — no full re-index

**PIB RSS detection keywords** (in `pipeline/config.py`):
`["scheme", "yojana", "launch", "welfare", "benefit", "beneficiary", "crore", "lakh", "subsidy"]`

New Central scheme target: **detected within 60 minutes of PIB publication**, upserted within same day.

---

## Testing Conventions

- Unit tests: `pytest` for FastAPI, `JUnit 5` for Spring Boot
- Integration tests: generated by Claude Code after each new endpoint
- Voice pipeline tests: mock Sarvam API with 25s audio fixture; test VAD split behavior
- Security tests: see pre-launch checklist in `docs/05_Security_Design_Document.docx`

---

## Ownership Map

| Area | Owner | Do NOT edit without owner review |
|---|---|---|
| `ai_service/` | Rudra | Pranjal |
| `voice/` | Rudra | Pranjal |
| `deploy/backend/spring-gateway/` | Pranjal | Rudra |
| `frontend/` | Frontend teammate | Both |
| `pipeline/` | Rudra | Pranjal |
| MongoDB schema | Pranjal | Rudra |
| LangChain chains | Rudra | Pranjal |
| API contract (`docs/06`) | Both | Both |

---

## Common Claude Code Tasks

**Add a new API endpoint:**
1. Update `docs/06_API_Contract.docx` first
2. Add FastAPI route in `ai_service/routers/` OR Spring Boot controller in `data_service/`
3. Generate integration test
4. Update this CLAUDE.md if new env vars or collections are needed

**Debug a voice pipeline issue:**
1. Check Cloud Run logs for the `ai_service` container
2. Grep for `[VOICE]` tagged log lines
3. Check Sarvam API status at status.sarvam.ai
4. Common causes: chunk > 25s (VAD misconfiguration), wrong `mode` param, Bulbul model not specified

**Update MongoDB schema:**
1. Update schema in this CLAUDE.md (above)
2. Update Java model in `data_service/src/main/java/.../`
3. Update Pydantic schema in `ai_service/`
4. Update relevant section in `docs/01_Master_Project_Document.docx`

**Add a new state scraper:**
1. Copy `pipeline/scrapers/states/up.py` as template
2. Update target URLs for the new state portal
3. Check new state portal's `robots.txt` before writing any selectors
4. Test with 10-page crawl + `--dry-run` flag before full run
5. Add state code to `pipeline/config.py` → `STATE_LIST`
6. Update the `pipeline/` directory tree in this CLAUDE.md

**Debug a pipeline run failure:**
1. Check Cloud Run Job execution log in GCP Console
2. Look for `[PIPELINE]` tagged log lines — each sub-agent prefixes its logs
3. Check `GET /admin/pipeline/status` for last run metrics
4. Common causes: robots.txt blocked (don't fight it), Gemini quota hit (check daily usage), MongoDB Atlas connection timeout
5. Never lower `RATE_LIMIT_SECONDS` below 2 — adds legal risk and gets IP banned

---

*Last updated: 2026-06-26 — v4.0: 10-Agent LangGraph architecture. Added orchestrator/ + agents/ directory (10 agents), GraphState, agent directory table, browser-use security rules, timeout table, multi-agent Claude Code tasks. 4 new MongoDB collections: reasoning_traces, admin_reports, agent_alerts, nudge_log. 11 new agent API endpoints.*

*Updated 2026-07-03 — v5.0 build-state sync: agent table now covers all 12 agents (11/12 from the v5.0 master doc) with honest built/not-built status; endpoint tables carry implementation-status blocks with actual path deviations; trend_events schema corrected to what's actually written (scheme_code-keyed); new "State Fields" cross-service rule. Directory layout note: the implemented code lives in `ai_service/graph/` (orchestrator + agents as modules, not per-agent directories), `ai_service/discovery/` (Agent 2 + sources, absorbing the planned `pipeline/`), `ai_service/scripts/` (batch/repair jobs). Live build status: docs/status/{README,COMPLETED,REMAINING,AGENTS}.md.*

*Updated 2026-07-04 — doc-sync pass against actual code (Agent Directory table hadn't been touched since 2026-07-03 and had drifted): Agent 3 and Agent 5 corrected from "❌ not started" to their real guidance/recording-path status (both shipped 2026-07-03, this file just never caught up); scheme count 984→1,230; GraphState code block corrected from a `@dataclass` sketch to match the actual `TypedDict` in `state.py` (was missing the `reply` field entirely); Orchestrator Routing diagram corrected — `eligibility_query` never fanned out to "[Agent1, Agent2] parallel" in the real code (Agent 2 is a separate always-on discovery service, not a graph node), `application_request`/`grievance` already routed to real Agent3/Agent5 nodes despite the table above them claiming those agents didn't exist, and the new `small_talk` intent (added same day — greetings no longer trigger fake scheme retrieval) was missing entirely. `/ws/session/{id}` endpoint entry updated for token streaming (shipped same day). Also fixed 3 live bugs unrelated to this doc but found the same day: `/agents/csc/alternatives`, `/ocr/scan`, and `/agent/start`+`/agent/answer` all required `X-API-Key` despite being called directly from the browser — browsers can't hold a service secret, so every real citizen hitting these paths (document scan, CSC operator lookup, voice-mode text fallback) got a silent 403. All three fixed and verified via the literal user-reachable path; detail in docs/status/COMPLETED.md.*
