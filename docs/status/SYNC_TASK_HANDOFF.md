# Data Sync Task — Handoff Brief

> **✅ STATUS 2026-07-11: THIS TASK IS COMPLETE. Both jobs are done — no need to run this anymore.**
> The full MyScheme catalog is ingested: **4,901 total schemes** (4,482 MyScheme + 419 original), with **99.4% eligibility-rule coverage** (4,872 extracted, 29 empty — 27 permanently non-extractable + 2 retryable). Sync confirmed 100% by probing the frontier (`--offset 4748` → 0 candidates, listing exhausted). The instructions below are retained as a record of how it was done + in case MyScheme adds new schemes later (re-run Job 1 from `--offset 4748` to pick up any additions; use `--provider ollama` with `ollama serve` running). Everything below the numbers is historical.

> Paste this whole file (or just say "read docs/status/SYNC_TASK_HANDOFF.md and do the task") into a **new, separate Claude Code conversation**. That conversation doesn't need any other context — everything it needs is below. Run this alongside your main conversation, not instead of it.

## What this task is

Yojna Setu's scheme catalogue is being synced in from MyScheme.gov.in, 300 schemes at a time (the site would block faster scraping). Separately, each scheme needs an AI call to extract structured eligibility rules (income limit, age, category, etc.) from its text — but the free AI quota (Gemini: 20 requests/day, Groq: ~100k tokens/day) runs out fast, so that part has to be retried periodically, not done once.

This is **two repeatable jobs**, not one. Run them in this order, every time you pick this up:

## Job 1 — Continue the MyScheme sync

1. **Use the "next offset" recorded in the Current numbers block below — NOT the synced-doc count.** (Historical note / why: the original instruction here said to pass the myscheme doc-count as `--offset`. That's wrong and wastes batches. `--offset` is a position in MyScheme's *listing*, but the doc-count only advances by the number of schemes actually **inserted** each batch — and every batch skips/updates some (content-hash-unchanged or already-present), so inserts < the 300-scheme fetch window. Result: doc-count lags the true listing frontier, and re-using it re-fetches ground the previous batch already covered. Real example 2026-07-09: offset 2343 = the doc-count → 80 fetched, only **5 new** (72 were already-synced re-treads). Re-run at the true frontier offset 2440 → **177 new**. Advance the offset by the fetch window (≈300) from the *previous batch's start*, with a small overlap, since overlap only costs cheap skips but a gap permanently misses schemes.)
2. Run the next batch:
   ```
   cd /home/rudra/dev/playground/Yojna_Setu
   ai_service/venv/bin/python -m ai_service.scripts.run_myscheme_batch --limit 300 --offset <next-offset-from-Current-numbers-block>
   ```
3. This takes a while (rate-limited ~2s/request + detail page fetches) — just wait for it to finish and print `Done. {...}`. **Note**: the runner may report exit code 144 in this sandbox even on success — that's spurious; verify real outcome via the Mongo count, not the exit code or the (sometimes-deleted) log file. Also watch for `Connection reset by peer` mid-run — MyScheme sometimes drops the connection early, cutting the batch short (e.g. only 80 of 300 fetched); if that happens, just re-run from the same offset.
4. After it finishes, compute the **next offset = this batch's start offset + 300** (minus a small overlap to be gap-safe), and record it in the Current numbers block.
5. **Stop condition**: once the myscheme total reaches ~4,729 (the site's real catalog size), this job is done.

## Job 2 — Heal empty eligibility rules

1. Check LLM quota isn't already dead (don't burn a retry if it obviously is):
   ```
   curl -s https://api.groq.com/openai/v1/chat/completions -X POST -H "Authorization: Bearer $(grep -oP '^GROQ_API_KEY=\K.*' ai_service/.env)" -H "Content-Type: application/json" -d '{"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'
   ```
   If this 429s, don't bother running the backfill — quota's dead, wait for another day.
2. If it works, run:
   ```
   ai_service/venv/bin/python -m ai_service.scripts.run_rules_backfill --limit 900 --pause 4
   ```
3. Read the final line: `Done. healed=X no_rules_found=Y api_failed=Z`.
   - `healed` = real progress, great.
   - `no_rules_found` = correctly empty (narrow eligibility like "ex-servicemen" — not a bug, don't worry about these, they'll never heal and that's fine).
   - `api_failed` ≥ 8 = quota's dead again, stop for today, don't keep retrying same-day (it won't work — confirmed repeatedly, a single successful test call does NOT mean there's batch headroom left).
4. **Stop condition**: `empty rules` count reaches 0 (or only `no_rules_found`-type schemes remain).

## After each run, update the record

Edit `docs/status/REMAINING.md`'s "MyScheme sync" bullet (near the top, under "Immediate gaps in already-done phases") with the new numbers — total schemes, myscheme total, empty rules count, next offset to resume from. Keep it honest: if a run healed 0, say so; don't round up.

## Current numbers as of 2026-07-11 — ✅ BOTH JOBS COMPLETE (100%)

- Total schemes: **4,901** — full MyScheme catalog ingested (4,482 MyScheme + 419 original). The "~4,729" estimate was low; frontier probe at `--offset 4748` returned 0 candidates = listing exhausted = 100%.
- **Eligibility-rule coverage: 4,872 / 4,901 (99.4%). Empty: 29** — 27 genuinely non-extractable (permanent) + 2 retryable small-model slips. **Job 2 is DONE.**
- If MyScheme adds schemes later, resume Job 1 from `--offset 4748 --provider ollama` (with `ollama serve` up).
- **What cleared it — READ THIS BEFORE ANY FUTURE BULK RUN:** the backfill only became viable once **local Ollama** was used. Start it first: `OLLAMA_HOST=127.0.0.1:11434 ollama serve &` (model `qwen2.5:3b` is already pulled), then `run_rules_backfill --provider ollama --limit 2000 --pause 0` (--provider ollama is the default and sets `OLLAMA_ENABLED=1` itself, so extraction goes straight to the local GPU — ~1s/scheme, free, no quota). On 2026-07-11 this healed ~960 schemes in one pass.
- **The trap it replaced:** with Ollama OFF, every extraction falls through dead Gemini (20 req/DAY) + dead Groq (100k tok/day) and stalls ~39s/scheme on their 429 back-offs. A fetch batch that should take ~12 min took 77 min on 2026-07-10 and had to be killed for exactly this. Cloud free-tiers CANNOT do bulk extraction — Ollama is the only workable engine at this scale.
- Small-model caveat: `qwen2.5:3b` occasionally emits malformed JSON (~1-2% parse-fail rate observed) — those few schemes stay empty; re-run or sweep with Gemini later if desired. Not data loss.
- Tip (2026-07-08): if ever running Job 1 + Job 2 on cloud quota the same day, run Job 2 first — but this is moot now that Ollama is the extraction engine.

## Don't touch

- Don't change `--pause` below 2 seconds (rate-limit courtesy to MyScheme's server).
- Don't run Job 1 and Job 2 at the exact same time — they can both hit the same LLM quota and waste it.
- If `docker`/`mongo`/services aren't running, that's a separate "relaunch the stack" step, not part of this task — check the main project memory for the relaunch commands (mongo, uvicorn `:8000`, spring-gateway `:8080`, vite `:5173`).
