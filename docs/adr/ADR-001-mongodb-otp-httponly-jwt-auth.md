# ADR-001: Migrate auth/identity to MongoDB + OTP + httpOnly JWT, drop Supabase and Postgres/JPA

- **Status**: accepted
- **Date**: 2026-07-01
- **Deciders**: Rudra
- **Tags**: architecture, auth, database, v5.0-rebuild

## Context

Yojna Setu v5.0 (`update/01_Master_v5.docx`) requires a 12-agent LangGraph platform backed by MongoDB Atlas (9 collections: users, citizen_profiles, schemes, applications, conversation_sessions, reasoning_traces, admin_reports, agent_alerts, nudge_log), OTP-first authentication, and JWT delivered via httpOnly cookies — never in the response body or browser storage.

A codebase survey found the actual implementation split across three incompatible states:
- `frontend/` authenticates directly against **Supabase** (`lib/supabase.js`, `SignInPage.jsx`), a client-side-session pattern.
- `deploy/backend/spring-gateway/` is still **PostgreSQL + Spring Data JPA + Flyway**, with **username/password auth returning JWT in the JSON response body** — the exact anti-pattern the docs (v3 through v5) have consistently said to replace.
- `ai_service/` has no database-backed identity at all (in-memory sessions only).

Additionally, Pranjal — originally slated to own the Spring Boot/Mongo/security layer — is no longer on the project. Rudra now owns the full stack solo.

## Decision

Fully migrate `users` and `citizen_profiles` to MongoDB Atlas (Mumbai region), replacing Supabase and the Postgres/JPA gateway entirely. Auth becomes OTP-first (Twilio SMS, RS256 JWT, httpOnly cookies, per `docs/PRANJAL_HANDOFF.md`'s original spec). This is executed as Phase 1 of the rebuild plan, decoupled from the AI-agent work in Phase 2+.

Rejected alternative: keep Supabase for identity while MongoDB holds everything else. Rejected because it produces two sources of truth for citizen identity, two audit trails, and still doesn't deliver OTP-first/httpOnly-JWT auth (Supabase's client SDK is fundamentally token-in-browser-storage). The Postgres/JPA gateway has to be torn out regardless once `schemes`/`applications` move to Mongo for the agent layer — folding `users`/`citizen_profiles` into that same rewrite is finishing one migration, not doing two.

## Consequences

### Positive
- Single source of truth for citizen identity and audit trail across the whole platform.
- Matches the DPDP 2023 compliance model assumed by every version of the docs (field-level AES-256 encryption, immutable audit logs, consent capture, 72hr erasure).
- httpOnly JWT closes the XSS token-theft gap the current Spring Boot `AuthController` has.

### Negative
- Full rewrite of `deploy/backend/spring-gateway/src/main/java/**` (models, repositories, controllers) — no incremental refactor path, per prior survey.
- Frontend auth flow (`lib/supabase.js`, `SignInPage.jsx`, any page reading a Supabase session) must be repointed to the new gateway.
- Twilio WhatsApp/SMS Business approval has a multi-week lead time — must start early, not when Agent 6 (Nudge) is otherwise ready.

### Neutral
- `ai_service/` was already going to need MongoDB for `conversation_sessions`/`reasoning_traces`/`schemes` regardless of this decision — this ADR only decides where `users`/`citizen_profiles` live.

## Links
- Plan: `/home/rudra/.claude/plans/synchronous-tickling-riddle.md`
- `docs/PRANJAL_HANDOFF.md` (original OTP/MongoDB spec, now executed solo)
- `update/01_Master_v5.docx` (v5.0 target architecture)
