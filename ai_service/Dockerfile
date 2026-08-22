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

# Pre-download the 384-dim embedding model into the image. Without this,
# sentence-transformers fetches all-MiniLM-L6-v2 from huggingface.co on the FIRST
# scheme query of every cold container — ~40 HTTP round-trips, ~15s of user-visible
# latency, plus an unauthenticated-HF rate limit and a hard runtime dependency on
# HF being reachable (measured in prod 2026-08-05). Baking it makes the first query
# as fast as the rest and keeps the app working if HF is down.
ENV HF_HOME=/opt/hf
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
# Baking the weights alone isn't enough: sentence-transformers still HEAD-revalidates
# every file against the Hub on load, which is where most of those round-trips go.
# HF_HUB_OFFLINE makes it read the baked cache directly. Safe because the model is
# pinned into the image above — there is nothing to fetch at runtime.
ENV HF_HUB_OFFLINE=1

# App code. .dockerignore (repo root) keeps venv/.env/tests/__pycache__ out.
COPY ai_service ./ai_service

# JWT PUBLIC key is supplied at runtime via JWT_PUBLIC_KEY or
# JWT_PUBLIC_KEY_PATH. The image stays independent from the signing keypair.

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
