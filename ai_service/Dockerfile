# ai_service (FastAPI) — Cloud Run container.
# Cloud Run sets $PORT (default 8080) and the container MUST listen on it.
FROM python:3.12-slim

# libmagic1: required by python-magic (OCR MIME sniffing, CLAUDE.md security rule #2).
# build-essential + curl: some wheels (easyocr/sentence-transformers deps) need a compiler.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libmagic1 build-essential curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first (layer-cached unless requirements change).
COPY ai_service/requirements.txt ./ai_service/requirements.txt
RUN pip install --no-cache-dir -r ai_service/requirements.txt

# App code. .dockerignore (repo root) keeps venv/.env/tests/__pycache__ out.
COPY ai_service ./ai_service

# JWT PUBLIC key only — ai_service verifies citizen cookies (RS256) against it
# via JWT_PUBLIC_KEY_PATH. A public key is not a secret, so baking it is fine.
COPY deploy/backend/spring-gateway/keys/jwt_public.pem /app/keys/jwt_public.pem

# OpenCV (cv2, via easyocr) + mediapipe need X/GL runtime shared libs that the
# slim base doesn't ship (libxcb.so.1, libGL.so.1, libgthread). Installed AFTER
# pip so a rebuild reuses the large cached torch layer instead of re-pushing it.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libgles2 libglib2.0-0 libxcb1 libsm6 libxext6 libxrender1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 PORT=8080
EXPOSE 8080

# Bind to Cloud Run's $PORT. Single worker: the app is async (ASGI) and holds
# WebSockets — scale with Cloud Run instances, not in-process workers.
CMD ["sh", "-c", "uvicorn ai_service.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
