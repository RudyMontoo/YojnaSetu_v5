# Yojna Setu v5.0 — Project Status Dashboard

> Last verified: 2026-07-03, against the actual repo/Mongo state (not assumed from memory).
> Full detail: [COMPLETED.md](COMPLETED.md) · [REMAINING.md](REMAINING.md) · [AGENTS.md](AGENTS.md)

## Headline

**7 of 11 rebuild phases substantially done and verified end-to-end (incl. Agent 3's guidance half of Phase 6). Remaining: Agent 5, Agent 6, Agents 11/12, frontend, deployment.**
984 / ~4,729 real MyScheme.gov.in schemes synced. 12-agent architecture: 9 of 13 fleet members working end-to-end.

This is a **solo rebuild** (Pranjal is off the project — see the earlier ownership memory). The original v5.0 doc assumed a 4-person team over ~8 weeks; treat any remaining-work estimate here as solo-dev time, not team time.

## Phase-by-Phase

| Phase | What | Status | Evidence |
|---|---|---|---|
| 1 | Spring Boot foundation (Mongo models, OTP auth, RS256 JWT, encryption, rate limiting) | ✅ Done | Real OTP login → cookie → authenticated calls, verified today |
| 1b | Application CRUD + DPDP erasure cascade | ✅ Done | Real create/duplicate-reject/patch; real erasure across 4 collections in 0.35s |
| 1c | Trending schemes (`trend_events` + `GET /schemes/trending`) | ✅ Done | Real search/save events → real top-5 aggregation, 6h cache, `?state=` filter, admin-gated recompute — all verified 2026-07-03 |
| 1d | Observability (`GET /agents/health` + `GET /agents/trace/{id}`) | ✅ Done | Real fleet statuses from live data (honest `not_built` entries); trace endpoint enforces session ownership (404 for other citizens' sessions) — verified 2026-07-03 |
| 2 | LangGraph Orchestrator skeleton + Mongo persistence | ✅ Done (REST + WSS) | Real chat via both `POST /orchestrator/chat` and `WSS /ws/session/{id}` (cookie-auth, verified with real WebSocket client incl. tampered-token rejection). Token streaming not yet implemented |
| 3 | Agent 1 (Eligibility) + Agent 2 (Discovery) | 🟡 Mostly done | MyScheme scraper live, 984 schemes; PIB/data.gov.in stubbed (no source config) |
| 4 | Agent 4 (Document + PPO verification) | ✅ Done | REST endpoint does full verification; chat gives accurate guidance (needs uploaded images, can't run from text) |
| 5 | Agent 7 (Financial Planning) + Agent 8 (Comparison) | ✅ Done | Both wired into chat graph, verified with real chat messages returning real scheme data |
| 6 | Agent 3 (Application Guidance) + Agent 5 (Grievance/NPCI) | 🟡 Fallback halves done | Agent 3 guidance + Agent 5 grievance-recording both live via chat + REST (verified 2026-07-03). Browser automation (both) + NPCI monitoring not started |
| 7 | Agent 6 (Nudge) + Agent 9 (CSC) + Agent 10 (Analytics) | 🟡 2 of 3 done | Agents 9 + 10 built & verified 2026-07-03. Agent 6 blocked on Twilio WhatsApp Business approval — not yet applied for |
| 8 | Agent 11 (Biometric Assist) | ❌ Not started | Model provenance (IllumiNet/MobileNetV3) still an open question |
| 9 | Agent 12 (Offline Survival Proof) | ❌ Not started | No PWA/offline-service-worker infrastructure exists yet |
| 10 | Frontend integration + DPDP UI + hardening | ❌ Not started | Frontend still uses Supabase auth (`frontend/src/lib/supabase.js`), not the new gateway |
| 11 | Cloud Run deployment + pilot readiness | ❌ Not started | Everything currently runs local-only (`localhost:8000` / `:8080`) |

## Quick counts

- **Agents**: 10 working end-to-end (1, 2, 3-guidance, 4, 5-recording, 7, 8, 9, 10 + Discovery's MyScheme source) · 2 fully not started (6, plus 11 & 12 which aren't in CLAUDE.md's table at all yet — see [AGENTS.md](AGENTS.md))
- **Real, tested bugs found and fixed this session** (not just features added): `asyncio.gather()` exception isolation, Spring Data MongoDB `auto-index-creation` silently off, index-naming conflicts between the two services, a benefit-amount LLM misclassification bug, an OCR date-parsing artifact — see [COMPLETED.md](COMPLETED.md) for detail on each
- **Schemes in Mongo**: 984 (started at 419; MyScheme's full catalog is ~4,729 — batches are resumable via `run_myscheme_batch.py --offset N`). Known data-quality caveat: schemes ingested during LLM-quota exhaustion have empty `eligibilityRules`; a quota-aware backfill (`run_rules_backfill.py`) heals them from text already in Mongo
- **Voice pipeline**: NOT migrated to the v5.0 spec (Pipecat + Sarvam Saaras v3/Bulbul v3) — only the old Whisper/Sarvam utility scripts exist
- **WebSocket endpoints**: `/ws/session/{id}` (text chat) built and verified 2026-07-03 — cookie-auth (JWT), shared turn logic with REST, per-turn error isolation. Token streaming and `/ws/voice/{id}` still not built

## What "done" means here

Every item marked ✅ in this dashboard was verified by actually running it against real data (a real OTP login, a real Mongo write, a real signature check that rejects a tampered token) — not just "the code compiles" or "the file exists." Where that verification surfaced a real bug, the bug and its fix are documented in [COMPLETED.md](COMPLETED.md), not hidden. Where something is genuinely incomplete or stubbed, [REMAINING.md](REMAINING.md) says so plainly rather than rounding up.
