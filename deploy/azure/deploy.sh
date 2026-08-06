#!/usr/bin/env bash
# deploy/azure/deploy.sh — deploy all 3 Yojna Setu services to Azure Container Apps.
#
# Cloud Run equivalent: serverless containers, scale-to-zero, WebSocket support
# (needed for voice + chat). Images are built LOCALLY with Docker and pushed to
# ACR, because `az acr build` (ACR Tasks) is blocked on Azure for Students subs.
#
# Secrets are read from deploy/azure/.env.deploy (gitignored — copy the .example
# and fill it in). Nothing secret is passed on the command line.
#
#   cp deploy/azure/.env.deploy.example deploy/azure/.env.deploy   # then edit
#   bash deploy/azure/deploy.sh
#
# Re-running redeploys with the latest source. Idempotent (create-or-update).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
[ -f "$HERE/.env.deploy" ] && set -a && . "$HERE/.env.deploy" && set +a

RG="${RG:-yojna-setu}"
LOCATION="${LOCATION:-centralindia}"
ENVNAME="${ENVNAME:-yojna-env}"
ACR="${ACR:-}"                      # set/reused via .env.deploy so redeploys hit the same registry

: "${MONGODB_URI:?set MONGODB_URI in deploy/azure/.env.deploy (Atlas connection string)}"
: "${FIELD_ENCRYPTION_KEY:?set FIELD_ENCRYPTION_KEY}"
: "${AADHAAR_SALT:?set AADHAAR_SALT}"
: "${INTERNAL_API_KEY:?set INTERNAL_API_KEY (shared FastAPI<->Spring secret)}"
: "${GEMINI_API_KEY:=}" ; : "${GROQ_API_KEY:=}" ; : "${SARVAM_API_KEY:=}"
MONGODB_DB="${MONGODB_DB:-yojnasetu}"

echo "==> Resource group: $RG ($LOCATION)"
az group create -n "$RG" -l "$LOCATION" -o none

if [ -z "$ACR" ]; then
  ACR="yojnasetu$RANDOM"
  echo "!!  No ACR set — created a new one: $ACR"
  echo "!!  Add  ACR=$ACR  to deploy/azure/.env.deploy so redeploys reuse it."
fi
echo "==> Container Registry: $ACR"
az acr create -g "$RG" -n "$ACR" --sku Basic --admin-enabled true -o none 2>/dev/null || true
ACR_SERVER="$(az acr show -g "$RG" -n "$ACR" --query loginServer -o tsv)"
ACR_USER="$(az acr credential show -n "$ACR" --query username -o tsv)"
ACR_PASS="$(az acr credential show -n "$ACR" --query 'passwords[0].value' -o tsv)"

echo "==> Container Apps environment: $ENVNAME"
az containerapp env create -g "$RG" -n "$ENVNAME" -l "$LOCATION" -o none 2>/dev/null || true

# ── 1) Build the 3 images LOCALLY and push them ──
# NOTE: `az acr build` (ACR Tasks) is BLOCKED on Azure for Students subscriptions
# (TasksOperationsNotAllowed), so we build here with Docker and push. Bonus:
# Docker's build honors .dockerignore correctly (MatchesOrParentMatches), so the
# 7GB venv and .env secrets stay OUT of the image — unlike az's source-packer.
echo "==> Logging Docker in to ACR"
az acr login -n "$ACR"

echo "==> Building + pushing ai-service (large — torch/mediapipe/easyocr; first build slow)"
DOCKER_BUILDKIT=0 docker build -t "$ACR_SERVER/ai-service:latest"     -f "$REPO_ROOT/ai_service/Dockerfile" "$REPO_ROOT"
docker push "$ACR_SERVER/ai-service:latest"

# --no-cache on these two: the legacy builder (BuildKit off) unreliably caches the
# mvn/npm build step that runs AFTER the source COPY, shipping stale jars/bundles.
# They're fast (~1-2 min) so always building clean is worth the correctness.
echo "==> Building + pushing spring-gateway"
DOCKER_BUILDKIT=0 docker build --no-cache -t "$ACR_SERVER/spring-gateway:latest" -f "$REPO_ROOT/deploy/backend/spring-gateway/Dockerfile" "$REPO_ROOT/deploy/backend/spring-gateway"
docker push "$ACR_SERVER/spring-gateway:latest"

echo "==> Building + pushing frontend"
DOCKER_BUILDKIT=0 docker build --no-cache -t "$ACR_SERVER/frontend:latest"       -f "$REPO_ROOT/frontend/Dockerfile" "$REPO_ROOT"
docker push "$ACR_SERVER/frontend:latest"

reg=(--registry-server "$ACR_SERVER" --registry-username "$ACR_USER" --registry-password "$ACR_PASS")

# ── 2) ai_service (internal ingress — only the frontend nginx reaches it) ──
echo "==> Deploying ai-service"
az containerapp create -g "$RG" -n ai-service --environment "$ENVNAME" \
  --image "$ACR_SERVER/ai-service:latest" "${reg[@]}" \
  --target-port 8080 --ingress internal --transport auto \
  --min-replicas 1 --max-replicas 3 --cpu 2 --memory 4Gi \
  --secrets mongodb-uri="$MONGODB_URI" gemini-key="$GEMINI_API_KEY" groq-key="$GROQ_API_KEY" \
            sarvam-key="$SARVAM_API_KEY" internal-key="$INTERNAL_API_KEY" \
            smtp-user="${SMTP_USERNAME:-}" smtp-pass="${SMTP_PASSWORD:-}" \
  --env-vars ENVIRONMENT=production MONGODB_DB="$MONGODB_DB" OLLAMA_ENABLED=0 \
             LLM_PREFER="${LLM_PREFER:-groq}" \
             JWT_PUBLIC_KEY_PATH=/app/keys/jwt_public.pem \
             SMTP_HOST="${SMTP_HOST:-smtp.gmail.com}" SMTP_PORT="${SMTP_PORT:-587}" \
             MAIL_FROM="${MAIL_FROM:-}" MAIL_FROM_NAME="${MAIL_FROM_NAME:-Yojna Sarthi}" MAIL_ENABLED="${MAIL_ENABLED:-false}" \
             SMTP_USERNAME=secretref:smtp-user SMTP_PASSWORD=secretref:smtp-pass \
             MONGODB_URI=secretref:mongodb-uri GEMINI_API_KEY=secretref:gemini-key \
             GROQ_API_KEY=secretref:groq-key SARVAM_API_KEY=secretref:sarvam-key \
             INTERNAL_API_KEY=secretref:internal-key -o none
AI_FQDN="$(az containerapp show -g "$RG" -n ai-service --query properties.configuration.ingress.fqdn -o tsv)"

# ── 3) spring-gateway (internal ingress) ──
echo "==> Deploying spring-gateway"
az containerapp create -g "$RG" -n spring-gateway --environment "$ENVNAME" \
  --image "$ACR_SERVER/spring-gateway:latest" "${reg[@]}" \
  --target-port 8080 --ingress internal --transport auto \
  --min-replicas 1 --max-replicas 3 --cpu 1 --memory 2Gi \
  --secrets mongodb-uri="$MONGODB_URI" enc-key="$FIELD_ENCRYPTION_KEY" \
            aadhaar-salt="$AADHAAR_SALT" internal-key="$INTERNAL_API_KEY" \
            smtp-user="${SMTP_USERNAME:-}" smtp-pass="${SMTP_PASSWORD:-}" \
            firebase-creds="${FIREBASE_CREDENTIALS_JSON:-}" \
  --env-vars MONGODB_DB="$MONGODB_DB" COOKIE_SECURE=true \
             JWT_PRIVATE_KEY_PATH=/app/keys/jwt_private.pem JWT_PUBLIC_KEY_PATH=/app/keys/jwt_public.pem \
             FASTAPI_URL="http://$AI_FQDN" \
             SMTP_HOST="${SMTP_HOST:-smtp.gmail.com}" SMTP_PORT="${SMTP_PORT:-587}" \
             MAIL_FROM="${MAIL_FROM:-}" MAIL_FROM_NAME="${MAIL_FROM_NAME:-Yojna Sarthi}" MAIL_ENABLED="${MAIL_ENABLED:-false}" \
             ALERT_EMAIL="${ALERT_EMAIL:-}" \
             SMTP_USERNAME=secretref:smtp-user SMTP_PASSWORD=secretref:smtp-pass \
             FIREBASE_CREDENTIALS_JSON=secretref:firebase-creds \
             MONGODB_URI=secretref:mongodb-uri FIELD_ENCRYPTION_KEY=secretref:enc-key \
             AADHAAR_SALT=secretref:aadhaar-salt INTERNAL_SERVICE_KEY=secretref:internal-key -o none
SPRING_FQDN="$(az containerapp show -g "$RG" -n spring-gateway --query properties.configuration.ingress.fqdn -o tsv)"

# ACA's internal ingress (Envoy) must accept plaintext HTTP/1.1 from the nginx
# hop: the frontend proxies over http:// to these FQDNs. Without allow-insecure +
# transport http, Envoy answers 426 "Upgrade Required" (and TLS without SNI 502s).
# The nginx side is handled in frontend/nginx.conf.template (proxy_http_version
# 1.1 + proxy_ssl_server_name on). Learned the hard way — do not revert.
for b in ai-service spring-gateway; do
  az containerapp ingress enable -g "$RG" -n "$b" --type internal --target-port 8080 --transport http --allow-insecure -o none
done

# ── 4) frontend (EXTERNAL ingress — public app; nginx reverse-proxies backends) ──
echo "==> Deploying frontend (public)"
az containerapp create -g "$RG" -n frontend --environment "$ENVNAME" \
  --image "$ACR_SERVER/frontend:latest" "${reg[@]}" \
  --target-port 8080 --ingress external --transport auto \
  --min-replicas 1 --max-replicas 3 --cpu 0.5 --memory 1Gi \
  --env-vars AI_SERVICE_URL="http://$AI_FQDN" SPRING_URL="http://$SPRING_FQDN" -o none
APP_URL="$(az containerapp show -g "$RG" -n frontend --query properties.configuration.ingress.fqdn -o tsv)"

# ── 5) Backfill cross-references now that all 3 URLs exist ──
# The app answers on BOTH the custom domain and the Azure FQDN, so the gateway's
# CORS allowlist must name all of them. Chrome sends an Origin header even on
# same-origin POSTs, so an origin missing here is rejected with 403 "Invalid CORS
# request" BEFORE reaching the handler — that silently broke phone-OTP login on
# yojsarthi.in while it still worked on the Azure URL (2026-08-05).
# PUBLIC_ORIGINS is the allowlist; FRONTEND_URL stays the canonical link base
# used in outbound emails, so it points at the custom domain.
PUBLIC_ORIGINS="https://yojsarthi.in,https://www.yojsarthi.in,https://$APP_URL"
CANONICAL_URL="https://yojsarthi.in"
echo "==> Wiring cross-service URLs (CORS allowlist + canonical link base)"
az containerapp update -g "$RG" -n ai-service \
  --set-env-vars SPRING_BOOT_INTERNAL_URL="http://$SPRING_FQDN" FRONTEND_URL="$CANONICAL_URL" PUBLIC_ORIGINS="$PUBLIC_ORIGINS" -o none
az containerapp update -g "$RG" -n spring-gateway \
  --set-env-vars FRONTEND_URL="$CANONICAL_URL" APP_CORS_ALLOWED_ORIGINS="$PUBLIC_ORIGINS" -o none

# ── 6) Scheduled discovery Job (Agent 2) — keeps the scheme catalogue fresh ──
# Separate Container Apps Job (not an in-process scheduler): a rate-limited
# 2s/request MyScheme sweep has no business blocking the request-serving app.
# Daily 02:00 IST = 20:30 UTC (matches CLAUDE.md SCRAPE_HOUR_IST=2). Self-healing
# diff-upsert: freshness over completeness — schemes upsert even when LLM quota is
# tight; empty eligibility rules re-extract on a later run. Idempotent (create-or-update).
echo "==> Deploying discovery-cron Job (daily 02:00 IST)"
JOB_VERB=create; az containerapp job show -g "$RG" -n discovery-cron -o none 2>/dev/null && JOB_VERB=update
if [ "$JOB_VERB" = create ]; then
  az containerapp job create -g "$RG" -n discovery-cron --environment "$ENVNAME" \
    --trigger-type Schedule --cron-expression "30 20 * * *" \
    --image "$ACR_SERVER/ai-service:latest" "${reg[@]}" \
    --cpu 1 --memory 2Gi \
    --replica-timeout 3600 --replica-retry-limit 1 --parallelism 1 --replica-completion-count 1 \
    --secrets mongodb-uri="$MONGODB_URI" gemini-key="$GEMINI_API_KEY" groq-key="$GROQ_API_KEY" \
    --env-vars MONGODB_URI=secretref:mongodb-uri MONGODB_DB="$MONGODB_DB" \
               GEMINI_API_KEY=secretref:gemini-key GROQ_API_KEY=secretref:groq-key \
               OLLAMA_ENABLED=0 DISCOVERY_MYSCHEME_LIMIT=300 PYTHONPATH=/app \
    --command "python" --args "/app/ai_service/scripts/run_discovery_job.py" -o none
else
  # Refresh only the image on redeploys; schedule/secrets already set.
  az containerapp job update -g "$RG" -n discovery-cron --image "$ACR_SERVER/ai-service:latest" -o none
fi
echo "    discovery-cron: daily 02:00 IST (manual run: az containerapp job start -g $RG -n discovery-cron)"

# ── 6b) Nightly Mongo backup Job — Atlas M0 has no automated backups ──
# Dumps the whole DB (gzipped) to a private Blob container via a write-only SAS.
# Needs BACKUP_BLOB_BASE + BACKUP_SAS in .env.deploy (storage account + container
# + SAS provisioned once — see EMAIL_SETUP.md-style note / git history). Skipped
# if those aren't set. Daily 03:30 IST = 22:00 UTC (after the discovery run).
if [ -n "${BACKUP_SAS:-}" ] && [ -n "${BACKUP_BLOB_BASE:-}" ]; then
  echo "==> Build+push mongo-backup image"
  DOCKER_BUILDKIT=0 docker build -t "$ACR_SERVER/mongo-backup:latest" -f "$HERE/backup/Dockerfile" "$HERE/backup"
  docker push "$ACR_SERVER/mongo-backup:latest"
  echo "==> Deploying backup-cron Job (daily 03:30 IST)"
  BJOB=create; az containerapp job show -g "$RG" -n backup-cron -o none 2>/dev/null && BJOB=update
  if [ "$BJOB" = create ]; then
    az containerapp job create -g "$RG" -n backup-cron --environment "$ENVNAME" \
      --trigger-type Schedule --cron-expression "0 22 * * *" \
      --image "$ACR_SERVER/mongo-backup:latest" "${reg[@]}" \
      --cpu 0.5 --memory 1Gi \
      --replica-timeout 1800 --replica-retry-limit 1 --parallelism 1 --replica-completion-count 1 \
      --secrets mongodb-uri="$MONGODB_URI" backup-sas="$BACKUP_SAS" \
      --env-vars MONGODB_URI=secretref:mongodb-uri BACKUP_BLOB_BASE="$BACKUP_BLOB_BASE" BACKUP_SAS=secretref:backup-sas -o none
  else
    az containerapp job update -g "$RG" -n backup-cron --image "$ACR_SERVER/mongo-backup:latest" -o none
  fi
  echo "    backup-cron: daily 03:30 IST (manual run: az containerapp job start -g $RG -n backup-cron)"
else
  echo "==> Skipping backup-cron (BACKUP_SAS/BACKUP_BLOB_BASE not set in .env.deploy)"
fi

# ── 7) Post-deploy smoke test — real public user path through nginx ──
echo "==> Running post-deploy smoke test"
if bash "$HERE/smoke_test.sh" "https://$APP_URL"; then
  echo "    smoke test passed"
else
  echo "!!  SMOKE TEST FAILED — deploy completed but something isn't healthy (see above)"
fi

echo ""
echo "==> DONE.  App is live at:  https://$APP_URL"
echo "    ai-service (internal): $AI_FQDN"
echo "    spring     (internal): $SPRING_FQDN"
echo "    Gateway logs:"
echo "      az containerapp logs show -g $RG -n spring-gateway --follow"
echo ""
echo "    NOTE: login OTPs are NO LONGER printed to the logs (they are live"
echo "    credentials — see EmailService.devEcho). If OTP email isn't arriving,"
echo "    set MAIL_ENABLED=true + MAIL_* in .env.deploy; do not expect a log echo."
