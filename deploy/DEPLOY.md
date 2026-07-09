# Deploying Yojna Setu to Google Cloud Run (Phase 11)

> Everything here is buildable/verifiable EXCEPT the steps that need your GCP
> account + billing + a real Atlas cluster. Those are marked **[YOU]**. The
> Dockerfiles and `deploy.sh` are ready — once your GCP project exists, deploy
> is essentially running `deploy.sh`.

## Architecture in prod

Three Cloud Run services, region **asia-south1** (Mumbai — closest to users,
and the Atlas region CLAUDE.md specifies):

```
                    ┌─────────────────────────┐
  citizen browser → │ frontend (nginx + SPA)  │  yojnasetu.in
                    │  reverse-proxies:        │
                    │   /api/*   → spring       │
                    │   /ws,/orchestrator,…→ ai │
                    └─────────┬───────┬─────────┘
                              │       │
             ┌────────────────┘       └───────────────┐
             ▼                                         ▼
   ┌───────────────────┐                   ┌───────────────────────┐
   │ spring-gateway    │  REST/auth        │ ai-service (FastAPI)  │  WS/AI
   │ (Java 17)         │                   │ (Python 3.12)         │
   └─────────┬─────────┘                   └───────────┬───────────┘
             └──────────────┬──────────────────────────┘
                            ▼
                  MongoDB Atlas (M0→M10, asia-south1)
```

The frontend stays **single-origin** (nginx reverse-proxies the backends) so
the httpOnly `SameSite=Strict` auth cookies keep working — the prod mirror of
the dev vite proxy. No CORS setup needed.

## Prerequisites **[YOU]**

1. **GCP project + billing.** `gcloud projects create yojna-setu` (or use an
   existing one), enable billing, then:
   ```
   gcloud config set project <PROJECT_ID>
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com artifactregistry.googleapis.com
   ```
2. **MongoDB Atlas cluster** in asia-south1 (M0 free tier is fine to start).
   Whitelist `0.0.0.0/0` (Cloud Run has no static egress IP without a VPC
   connector — or add one later). Get the `mongodb+srv://…` URI.
3. **Secrets** — put every secret in Secret Manager, never in an image or env
   literal (CLAUDE.md security rules):
   ```
   printf '%s' "<value>" | gcloud secrets create MONGODB_URI            --data-file=-
   printf '%s' "<value>" | gcloud secrets create GEMINI_API_KEY         --data-file=-
   printf '%s' "<value>" | gcloud secrets create GROQ_API_KEY           --data-file=-
   printf '%s' "<value>" | gcloud secrets create SARVAM_API_KEY         --data-file=-
   printf '%s' "<value>" | gcloud secrets create FIELD_ENCRYPTION_KEY   --data-file=-
   printf '%s' "<value>" | gcloud secrets create INTERNAL_API_KEY       --data-file=-
   # JWT RS256 keypair (Spring signs, ai_service verifies):
   gcloud secrets create JWT_PRIVATE_KEY --data-file=deploy/backend/spring-gateway/keys/jwt_private.pem
   gcloud secrets create JWT_PUBLIC_KEY  --data-file=deploy/backend/spring-gateway/keys/jwt_public.pem
   # Twilio (only when WhatsApp is approved — Agent 6):
   # ...TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_WHATSAPP_FROM
   ```

## Deploy

Once the prerequisites exist, from the repo root:

```
PROJECT_ID=<your-project> REGION=asia-south1 deploy/deploy.sh
```

`deploy.sh` builds and deploys all three services with `gcloud run deploy
--source` (Cloud Build builds each Dockerfile), wires the secrets, and prints
the frontend URL. It deploys **ai-service** and **spring-gateway** first
(internal), then injects their URLs into the **frontend** service's env so
nginx can reverse-proxy to them.

## Notes / deferred

- **Ollama (bulk LLM):** the rules-backfill uses a local Ollama model. That's a
  dev-box tool, not part of the deployed services — run it locally against the
  Atlas cluster when you need to heal rules, or add a paid LLM tier for
  in-cloud bulk work.
- **Voice (Pipecat):** ai-service holds long-lived WebSockets — Cloud Run
  supports this, but set `--timeout=3600` and `--min-instances=1` on ai-service
  so a voice call isn't cut at the default request timeout / cold start.
- **Scheduled agents (Agent 6 nudges, Agent 10 analytics):** use Cloud Scheduler
  → `POST /agents/admin/nudge/trigger` and `/agents/admin/analytics/run` on a
  cron. That's the "weekly cron / daily 8AM" the agent tables mention.
- **`.env` is never deployed** (it's in `.dockerignore`) — all config comes from
  Secret Manager + Cloud Run env vars.
