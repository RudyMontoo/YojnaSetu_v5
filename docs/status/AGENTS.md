# 12-Agent Status Table

> CLAUDE.md's own Agent Directory table (as it stands today) only documents 10 agents — Agent 11 and 12 come from the v5.0 master planning doc and haven't been synced into CLAUDE.md yet. This table includes all 12 so the gap is visible, not hidden.

| # | Agent | Built? | Reachable how | Notes |
|---|---|---|---|---|
| — | Orchestrator | ✅ | `POST /orchestrator/chat` | REST only — no WebSocket yet |
| 1 | Eligibility | ✅ | Chat (`eligibility_query` intent) | Ports `yojna_sathi.py`'s interview logic |
| 2 | Discovery | 🟡 | `POST /orchestrator/admin/discovery/run` | MyScheme source live (984 schemes synced); PIB/data.gov.in sources built but produce zero data (missing config, not a bug) |
| 3 | Application Guidance | 🟡 | Chat (`application_request` intent) | Guidance path built 2026-07-03: curated 11-scheme playbook + grounded LLM fallback, every applyUrl domain-whitelisted. Browser automation (the risky half) still not started |
| 4 | Document Verification | 🟡 | `POST /agents/document/verify-ppo` (full check) + chat (`document_verify` intent, guidance only) | Full check needs uploaded document images, which text chat can't carry — chat now gives an accurate reply pointing to the real upload endpoint instead of the old stale "still being built" placeholder |
| 5 | Grievance / NPCI Monitor | 🟡 | `POST /agents/grievance` (Citizen JWT) + chat (`grievance` intent) | Recording path built 2026-07-03: durable `grievances` collection + CPGRAMS self-filing guidance. pgportal browser automation + NPCI/SPARSH monitoring (needs institutional access) not started |
| 6 | Nudge (WhatsApp) | ❌ | — | Not started. Blocked on Twilio WhatsApp Business approval (not yet applied for) |
| 7 | Financial Planning | ✅ | `GET /agents/financial-plan` and chat (`financial_plan` intent) | Wired into the chat graph 2026-07-03 — verified with a real chat message returning a real per-scheme benefit breakdown |
| 8 | Comparison | ✅ | Chat (`comparison` intent) | Top-2 vector search + Gemini comparison |
| 9 | CSC Assist | ✅ | `POST /agents/csc/alternatives` (Operator JWT) + chat (`csc_assist` intent, guidance only) | Built 2026-07-03: grounded missing-document alternatives with honest "mandatory, no substitute" answers. First role-gated endpoint — citizen tokens get 403, verified with a real CSC_OPERATOR JWT |
| 10 | Analytics | ✅ | `POST /agents/admin/analytics/run` + `GET /agents/admin/analytics/latest` (Admin JWT) | Built 2026-07-03: real Mongo-aggregation metrics (LLM only for narrative, template fallback), writes permanent `admin_reports`. Its first report immediately exposed two real data bugs (state-code mismatch + MyScheme state misattribution) — both fixed same day. Weekly cron is Phase 11 work |
| 11 | Biometric Assist | ❌ | — | Not started. Not even in CLAUDE.md's agent table yet. Model provenance (IllumiNet/MobileNetV3) unresolved |
| 12 | Offline Survival Proof | ❌ | — | Not started. Not even in CLAUDE.md's agent table yet. No PWA/offline infra exists as a prerequisite |

**Legend**: ✅ built + verified + reachable as designed · 🟡 built + verified but with a real gap (see Notes) · ❌ not started

## What "wired into the chat graph" means

CLAUDE.md's Orchestrator Routing table says every intent should route to its agent through `/orchestrator/chat`'s conditional edges (`orchestrator/graph.py` → now `ai_service/graph/orchestrator.py`). As of 2026-07-03, `_INTENT_TO_NODE` has real edges for `eligibility_query` (Agent 1), `comparison` (Agent 8), `financial_plan` (Agent 7), and `document_verify` (Agent 4, guidance-only — see its row above for why full verification can't run from a text message). Only `status_check` still hits the placeholder (it belongs to Spring Boot per the routing table — a direct data lookup, not an agent).
