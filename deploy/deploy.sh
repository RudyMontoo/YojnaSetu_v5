#!/usr/bin/env bash
# deploy/deploy.sh — build + deploy all three Yojna Setu services to Cloud Run.
# Requires: gcloud authed, PROJECT_ID set, secrets created (see DEPLOY.md).
#
#   PROJECT_ID=my-proj REGION=asia-south1 deploy/deploy.sh
#
# Idempotent: re-running redeploys with the latest source.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-asia-south1}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Project: $PROJECT_ID  Region: $REGION"
gcloud config set project "$PROJECT_ID" >/dev/null

# 1) ai-service (FastAPI) — WebSockets need a long timeout + a warm instance.
echo "==> Deploying ai-service"
gcloud run deploy ai-service \
  --source "$REPO_ROOT/ai_service" \
  --region "$REGION" --platform managed --no-allow-unauthenticated \
  --timeout 3600 --min-instances 1 --memory 2Gi --cpu 2 \
  --set-secrets "MONGODB_URI=MONGODB_URI:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest,GROQ_API_KEY=GROQ_API_KEY:latest,SARVAM_API_KEY=SARVAM_API_KEY:latest,FIELD_ENCRYPTION_KEY=FIELD_ENCRYPTION_KEY:latest,INTERNAL_API_KEY=INTERNAL_API_KEY:latest,JWT_PUBLIC_KEY=JWT_PUBLIC_KEY:latest" \
  --set-env-vars "MONGODB_DB=yojnasetu,SPRING_BOOT_INTERNAL_URL=SPRING_URL_PLACEHOLDER"
AI_URL="$(gcloud run services describe ai-service --region "$REGION" --format 'value(status.url)')"
echo "    ai-service: $AI_URL"

# 2) spring-gateway (Java) — builds from source via its multi-stage Dockerfile.
echo "==> Deploying spring-gateway"
gcloud run deploy spring-gateway \
  --source "$REPO_ROOT/deploy/backend/spring-gateway" \
  --region "$REGION" --platform managed --no-allow-unauthenticated \
  --memory 512Mi --cpu 1 \
  --set-secrets "MONGODB_URI=MONGODB_URI:latest,FIELD_ENCRYPTION_KEY=FIELD_ENCRYPTION_KEY:latest,INTERNAL_API_KEY=INTERNAL_API_KEY:latest,JWT_PRIVATE_KEY=JWT_PRIVATE_KEY:latest,JWT_PUBLIC_KEY=JWT_PUBLIC_KEY:latest" \
  --set-env-vars "AI_SERVICE_INTERNAL_URL=$AI_URL"
SPRING_URL="$(gcloud run services describe spring-gateway --region "$REGION" --format 'value(status.url)')"
echo "    spring-gateway: $SPRING_URL"

# Point ai-service at the now-known spring URL (internal profile calls).
gcloud run services update ai-service --region "$REGION" \
  --set-env-vars "MONGODB_DB=yojnasetu,SPRING_BOOT_INTERNAL_URL=$SPRING_URL" >/dev/null

# 3) frontend (nginx + SPA) — reverse-proxies to the two backend URLs.
echo "==> Deploying frontend"
gcloud run deploy frontend \
  --source "$REPO_ROOT/frontend" \
  --region "$REGION" --platform managed --allow-unauthenticated \
  --memory 256Mi --cpu 1 \
  --set-env-vars "AI_SERVICE_URL=$AI_URL,SPRING_URL=$SPRING_URL"
FRONTEND_URL="$(gcloud run services describe frontend --region "$REGION" --format 'value(status.url)')"

echo ""
echo "==> Done. App: $FRONTEND_URL"
echo "    (ai-service + spring-gateway are --no-allow-unauthenticated; the"
echo "     frontend nginx reaches them via Cloud Run's internal networking.)"
