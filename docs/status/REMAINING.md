# Remaining Work — Detail

> Organized by the original phase sequencing (see the rebuild plan referenced in memory). Each item says plainly what exists vs. what doesn't — nothing here is rounded up to sound more done than it is.

## Immediate gaps in already-"done" phases

These aren't new phases — they're loose ends inside Phases 3–5:

- ~~Agent 4 and Agent 7 aren't reachable from chat~~ — **closed 2026-07-03.** Both now have real graph nodes (`run_financial_plan_agent`, `run_document_verify_guidance`), verified with real chat messages. Agent 4's chat node is guidance-only by design (real verification needs uploaded document images, which a text message can't carry) — that's not a remaining gap, it's the correct behavior for that channel.
- **PIB RSS + data.gov.in sources produce zero data.** Not a bug — genuinely blocked, and PIB's dead-end status was independently re-verified 2026-07-03 (not just assumed from an older note): `www.pib.gov.in` WAF-blocks non-browser traffic (even `robots.txt` 403s), and both the classic `ViewRss.aspx` URL and `archive.pib.gov.in`'s RSS path return plain HTML pages with zero `<rss>`/`<feed>`/`<?xml>` content, not feeds. If revisited, the productive next move is the same technique that found MyScheme's real API — read PIB's frontend JS bundles for `fetch()` calls — not searching for an RSS URL that no longer functions. data.gov.in needs `DATAGOVIN_API_KEY` + resource IDs found by browsing their catalog with a key.
- **MyScheme sync is at 984 / ~4,729 schemes** (565 from MyScheme + 419 original). Not blocked — resume with `run_myscheme_batch.py --limit 300 --offset 600` (the `--offset` flag was added 2026-07-03 after discovering that offset-less re-runs refetch the same first N schemes as a no-op). Two data-quality repairs in flight, both re-runnable until their counts hit zero: `run_rules_backfill.py` (~615 schemes with empty `eligibilityRules` from quota-exhausted ingestion, healing as quota allows) and `run_state_rehydration.py` (~130 MyScheme docs still missing state attribution after the mapper fix — most already healed).
- **The 5 state scrapers CLAUDE.md names** (`pipeline/scrapers/states/{up,mh,rj,tn,wb}.py`) — zero files exist. Worth reassessing priority now that MyScheme already covers state schemes too.
- **WS token streaming**: `/ws/session/{id}` sends one complete reply frame per turn; CLAUDE.md says "streams LLM tokens." Needs the orchestrator's compose step to expose an async token iterator — protocol already forward-compatible.

## Phase 6 — Agent 3 (Application Guidance) + Agent 5 (Grievance/NPCI Monitor)
**Status: Agent 3's guidance path DONE (2026-07-03); browser automation + Agent 5 not started.**

- Agent 3 guidance path shipped: curated playbook + grounded LLM fallback via the `application_request` chat intent, `domain_whitelist.py` live on every recommended URL. The browser-use automation half remains — unstable markup, CAPTCHA, session forms — and now composes on top of a working fallback instead of being the only path.
- Agent 5 recording path shipped 2026-07-03: `POST /agents/grievance` + `grievance` chat intent persist to the `grievances` collection (status `recorded` — the handoff point for portal automation later) and give CPGRAMS self-filing guidance. Still open: pgportal browser automation, NPCI/SPARSH monitoring (institutional access — mock/swappable design when attempted).
- `domain_whitelist.py` now exists (`ai_service/utils/`) and is enforced on recommended URLs; browser navigation enforcement hooks in when automation lands.
- `status_tracker.py` already exists as a scraper-based fallback path and can stay relevant here.

## Phase 7 — Agent 6 (Nudge) + Agent 9 (CSC) + Agent 10 (Analytics)
**Status: Agents 9 and 10 DONE (2026-07-03, see COMPLETED.md). Only Agent 6 remains.**

- Agent 6 (WhatsApp nudges) is blocked on Twilio WhatsApp Business approval, which has a **1–4+ week lead time** — this should be *applied for now*, independent of when the agent gets built, so the lead time isn't sitting on the critical path later.
- Agent 10's weekly Sunday-11PM-IST cron is a Phase 11 deployment concern; the report itself generates on demand today.

## Phase 8 — Agent 11 (Biometric Assist)
**Status: not started. Novel — biggest single unknown in the whole plan.**

It's genuinely unclear whether pretrained IllumiNet/MobileNetV3 weights exist from a prior "Jeevan-Setu" project, or whether this means training a liveness classifier from scratch. This needs to be resolved before any implementation estimate is meaningful.

## Phase 9 — Agent 12 (Offline Survival Proof)
**Status: not started. Novel.**

Needs RSA-2048 signing + QR + Bluetooth/WiFi Direct verification + sync-on-reconnect. No PWA manifest or offline service worker exists on the frontend yet — this would be the first such work on the frontend, not an extension of something partial.

**Note**: CLAUDE.md's current Agent Directory table (last updated 2026-06-26, labeled v4.0) only lists **10 agents** — Agent 11 and Agent 12 exist in the v5.0 master planning doc (`update/01_Master_v5.docx`) but haven't been added to CLAUDE.md's own agent table, timeout table, or GraphState yet. That's a doc-sync gap worth closing alongside actually building them.

## Phase 10 — Frontend Integration + Hardening
**Status: not started.**

- Frontend (`frontend/`) still authenticates via **Supabase directly** (`frontend/src/lib/supabase.js`, `lib/auth.js`), completely bypassing the new Spring Boot OTP/JWT gateway built in Phase 1. This is the single biggest remaining disconnect between backend and frontend.
- No DPDP consent/erasure UI exists — the backend endpoints (`POST /consent`, `DELETE /api/v2/user/me`) work, but nothing in the UI calls them yet.
- No PWA manifest exists — relevant both for general hardening and as a prerequisite for Phase 9.
- Per explicit instruction from the project owner (2026-07-02): **do not assume the current frontend survives as-is** — a real frontend rebuild is planned, not just swapping auth endpoints.

## Phase 11 — Cloud Run Deployment + Pilot Readiness
**Status: not started.**

Everything currently runs local-only: MongoDB via local Docker (`docker start yojna-mongo`, does not survive reboot automatically), ai_service on `localhost:8000`, Spring Boot on `localhost:8080`, no Atlas cluster, no Cloud Run services, no secret rotation, no CI security gates, no `asia-south1` deployment of anything.

## Other known gaps (not tied to a specific phase number)

- ~~WebSocket endpoints don't exist~~ — **`/ws/session/{id}` (text chat) built and verified 2026-07-03** (`ai_service/routers/ws_router.py`, shared turn logic in `graph/chat_turn.py`, cookie-JWT auth with 1008 closes on bad tokens). Still open within this: token streaming (currently one complete reply per turn — the spec says "streams LLM tokens", which needs the compose step to expose an async token iterator) and `/ws/voice/{id}` (blocked on the voice pipeline migration below).
- **Voice pipeline not migrated.** CLAUDE.md specifies Pipecat + Sarvam Saaras v3 (STT) + Bulbul v3 (TTS). What currently exists (`ai_service/utils/sarvam.py`, an offline Whisper model reference) predates this spec and hasn't been rebuilt against it.
- **Twilio not wired to a funded account.** OTP codes currently log to the server console in dev (`OtpService.java`'s fallback) rather than actually sending SMS. Fine for continued dev/testing; not fine for any real pilot user.
- **ai_service does not verify identity on every endpoint yet** — JWT verification (`jwt_auth.py`) is wired into `/orchestrator/chat` and `/agents/financial-plan` only. `/agents/document/verify-ppo` doesn't use citizen identity at all currently (arguably fine — it's stateless OCR+compare with no per-citizen data read/written), but this should be revisited as more citizen-scoped endpoints get added.
- **No CI pipeline** — nothing runs tests or security checks automatically on push; everything so far has been manual verification per session.
