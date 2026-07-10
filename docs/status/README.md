# Yojna Setu v5.0 — Project Status Dashboard

> Last verified: 2026-07-05, against the actual repo/Mongo state (not assumed from memory).
> Full detail: [COMPLETED.md](COMPLETED.md) · [REMAINING.md](REMAINING.md) · [AGENTS.md](AGENTS.md)

## Headline

**Overall: ~44-45% complete** (effort-weighted, not a simple phase count — see reasoning below). 7 of 11 rebuild phases substantially done end-to-end; the three phases that haven't moved at all (Agent 11, Agent 12, Cloud Run deployment) represent some of the single largest remaining chunks of real effort in the whole plan, which is why this isn't higher despite real progress elsewhere.
1,470 / ~4,729 real MyScheme.gov.in schemes synced (31%, up from 984 on 2026-07-03). 12-agent architecture: 10 of 13 fleet members working end-to-end, one (Agent 9 CSC) now with a real frontend dashboard, not just a backend endpoint.

Since 2026-07-03: WS chat now streams real tokens (not just REST-equivalent), a `small_talk` intent stops greetings from triggering fake scheme retrieval, chat now teaches the citizen profile (facts stated in conversation persist), session summaries write on disconnect, CSC Operator Dashboard shipped, and — found via a deliberate `require_api_key` sweep — **3 real production bugs fixed**: the document scanner, the CSC endpoint, and the voice-mode text fallback were all silently 403ing for real browser users. Also deprecated an undocumented, unauthenticated legacy "Jan Sahayak" helper marketplace (zero live users, removed rather than hardened), removed other dead legacy endpoints, added a minimal CI workflow (uncovered a real `requirements.txt` bug — the live OCR engine was missing from it entirely), and fixed a diagnostic bug in the rules-backfill script that was misreporting "nothing to extract" as "quota exhausted."

This is a **solo rebuild** (Pranjal is off the project — see the earlier ownership memory). The original v5.0 doc assumed a 4-person team over ~8 weeks; treat any remaining-work estimate here as solo-dev time, not team time.

## Phase-by-Phase

| Phase | What | Status | Evidence |
|---|---|---|---|
| 1 | Spring Boot foundation (Mongo models, OTP auth, RS256 JWT, encryption, rate limiting) | ✅ Done | Real OTP login → cookie → authenticated calls, verified today |
| 1b | Application CRUD + DPDP erasure cascade | ✅ Done | Real create/duplicate-reject/patch; real erasure across 4 collections in 0.35s |
| 1c | Trending schemes (`trend_events` + `GET /schemes/trending`) | ✅ Done | Real search/save events → real top-5 aggregation, 6h cache, `?state=` filter, admin-gated recompute — all verified 2026-07-03 |
| 1d | Observability (`GET /agents/health` + `GET /agents/trace/{id}`) | ✅ Done | Real fleet statuses from live data (honest `not_built` entries); trace endpoint enforces session ownership (404 for other citizens' sessions) — verified 2026-07-03 |
| 2 | LangGraph Orchestrator skeleton + Mongo persistence | ✅ Done (REST + WSS + streaming) | Real chat via both `POST /orchestrator/chat` and `WSS /ws/session/{id}` (cookie-auth, verified with real WebSocket client incl. tampered-token rejection). Token streaming shipped 2026-07-04; `small_talk` intent + chat-based profile learning + session summaries added |
| 3 | Agent 1 (Eligibility) + Agent 2 (Discovery) | 🟡 Mostly done | MyScheme scraper live, 1,470 schemes (31% of ~4,729 target); PIB/data.gov.in stubbed (no source config) |
| 4 | Agent 4 (Document + PPO verification) | ✅ Done | REST endpoint does full verification; chat gives accurate guidance (needs uploaded images, can't run from text) |
| 5 | Agent 7 (Financial Planning) + Agent 8 (Comparison) | ✅ Done | Both wired into chat graph, verified with real chat messages returning real scheme data |
| 6 | Agent 3 (Application Guidance) + Agent 5 (Grievance/NPCI) | 🟡 Fallback halves done | Agent 3 guidance + Agent 5 grievance-recording both live via chat + REST (verified 2026-07-03). Browser automation (both) + NPCI monitoring not started |
| 7 | Agent 6 (Nudge) + Agent 9 (CSC) + Agent 10 (Analytics) | 🟡 2 of 3 done | Agents 9 + 10 built & verified 2026-07-03; Agent 9 got a real frontend dashboard (`/csc-dashboard`) 2026-07-04. Agent 6 blocked on Twilio WhatsApp Business approval — not yet applied for |
| 8 | Agent 11 (Biometric Assist) | ❌ Not started | Model provenance (IllumiNet/MobileNetV3) still an open question |
| 9 | Agent 12 (Offline Survival Proof) | ❌ Not started | No PWA/offline-service-worker infrastructure exists yet |
| 10 | Frontend integration + DPDP UI + hardening | 🟡 Rebuilt + hardened | Full redesign: OTP login, chat+trending, applications+grievance, PPO check, profile+plan+DPDP delete, WS streaming chat, CSC dashboard — verified against live backends. 3 real production auth bugs found+fixed; legacy Jan Sahayak marketplace deprecated; voice reconnected to the real orchestrator. Remaining: real-time voice (Pipecat), offline service worker, real-device testing |
| 11 | Cloud Run deployment + pilot readiness | ❌ Not started (small down payment) | Everything still runs local-only. Minimal CI workflow added (`.github/workflows/ci.yml`, not yet pushed) — a first, tiny step toward pilot readiness, not deployment itself |

## Quick counts

- **Agents**: 10 working end-to-end (1, 2, 3-guidance, 4, 5-recording, 7, 8, 9, 10 + Discovery's MyScheme source), Agent 9 with a real frontend too · 2 fully not started (6, plus 11 & 12 — see [AGENTS.md](AGENTS.md))
- **Real, tested bugs found and fixed** (not just features added): `asyncio.gather()` exception isolation, Spring Data MongoDB `auto-index-creation` silently off, index-naming conflicts between the two services, a benefit-amount LLM misclassification bug, an OCR date-parsing artifact (2026-07-03) — **plus 3 more 2026-07-04/05**: the document scanner, CSC endpoint, and voice-mode text fallback were all silently 403ing for real browser users (an `X-API-Key` gate on endpoints only a browser ever calls), and `run_rules_backfill.py` was misreporting genuinely-unextractable schemes as quota exhaustion. See [COMPLETED.md](COMPLETED.md) for detail on each.
- **Schemes in Mongo**: 1,470 (started at 419; MyScheme's full catalog is ~4,729 — batches are resumable via `run_myscheme_batch.py --offset N`, currently at `--offset 1051`). Known data-quality caveat: schemes ingested during LLM-quota exhaustion have empty `eligibilityRules` (867 currently); a quota-aware backfill (`run_rules_backfill.py`) heals them from text already in Mongo, though free-tier LLM quota (Gemini 20 req/day, Groq ~100k tokens/day) makes this slow-going
- **Voice pipeline**: STT/TTS (Sarvam Saaras v3/Bulbul v3) were already spec-correct; 2026-07-08 reconnected voice to the real 12-agent orchestrator (was talking to the old pre-rebuild fixed-questionnaire instead) — verified end-to-end with real synthesized speech. Still NOT real-time (no Pipecat/WebSocket streaming) — turn-based record/upload/wait, not low-latency
- **WebSocket endpoints**: `/ws/session/{id}` (text chat) built and verified 2026-07-03, **real token streaming added 2026-07-04** — cookie-auth (JWT), shared turn logic with REST, per-turn error isolation. `/ws/voice/{id}` still not built
- **CI**: `.github/workflows/ci.yml` added 2026-07-04 (frontend build, Python import smoke-check, Spring compile) — validated against a genuinely clean install, not yet pushed to GitHub

## What "done" means here

Every item marked ✅ in this dashboard was verified by actually running it against real data (a real OTP login, a real Mongo write, a real signature check that rejects a tampered token) — not just "the code compiles" or "the file exists." Where that verification surfaced a real bug, the bug and its fix are documented in [COMPLETED.md](COMPLETED.md), not hidden. Where something is genuinely incomplete or stubbed, [REMAINING.md](REMAINING.md) says so plainly rather than rounding up.
