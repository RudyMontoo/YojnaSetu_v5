"""
Main FastAPI entrypoint — Yojna Setu AI Service
Runs on: http://localhost:8000
Docs:    http://localhost:8000/docs
"""
import os
import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv

# Load .env from ai_service directory explicitly
_env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)
logging.basicConfig(level=logging.INFO)

# Security rule #3/#8: strip Aadhaar/phone/PAN/email from every log line before
# emission. Installed right after basicConfig so it covers all handlers.
from ai_service.utils.log_redaction import install_pii_log_redaction  # noqa: E402
install_pii_log_redaction()

app = FastAPI(
    title="Yojna Setu AI Service",
    description="AI/ML backend for Yojna Setu — Indian Government Scheme Assistant",
    version="1.0.0",
)

# ── Security Headers Middleware ────────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects standard security headers on every response."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "object-src 'none';"
        )
        return response

app.add_middleware(SecurityHeadersMiddleware)

# ── CORS (allow React frontend on port 3000 and Spring Boot on 8080) ──────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",  # Vite dev server
        "http://localhost:8080",
        os.getenv("FRONTEND_URL", "http://localhost:5173"),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global unhandled exception handler (prevents stack trace leaks) ───────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.getLogger(__name__).error(
        f"Unhandled exception on {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again later."},
    )

# ── Mount routers ─────────────────────────────────────────────────────────────
from ai_service.routers.status_tracker import router as status_router
from ai_service.routers.agent_router import router as agent_router
from ai_service.routers.voice_conversation import router as voice_conv_router
from ai_service.routers.help_discovery import router as help_router
from ai_service.routers.apply_guide import router as apply_router
from ai_service.routers.ocr_router import router as ocr_router
from ai_service.routers.orchestrator_router import router as orchestrator_router
from ai_service.routers.agents_router import router as agents_router
from ai_service.routers.internal_router import router as internal_router
from ai_service.routers.ws_router import router as ws_router
from ai_service.routers.voice_ws_router import router as voice_ws_router
from ai_service.routers.translate_router import router as translate_router
from ai_service.routers.dlc_router import router as dlc_router

app.include_router(orchestrator_router)
app.include_router(agents_router)
app.include_router(internal_router)
app.include_router(ws_router)
app.include_router(voice_ws_router)
app.include_router(translate_router)
app.include_router(dlc_router)
app.include_router(status_router, prefix="/status")
app.include_router(agent_router)
app.include_router(voice_conv_router)
app.include_router(help_router)
app.include_router(apply_router)
app.include_router(ocr_router, prefix="/ocr")


# ── Root ───────────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "service": "Yojna Setu AI",
        "version": "1.0.0",
        "endpoints": {
            "chat":           "/orchestrator/chat (REST) + /ws/session/{id} (WebSocket, token streaming) — 12-agent LangGraph orchestrator",
            "agent":          "/agent/start + /agent/answer — legacy adaptive interview (pre-v5.0, still live for voice-mode text fallback)",
            "voice":          "/voice/conversation/start + /voice/conversation/answer — voice interview",
            "status_tracker": "/status/check — Live scheme application status",
            "help_csc":       "/help/csc/nearby — CSC Centre locator (OpenStreetMap)",
            "help_doc":       "/help/doc/guide — Document help guide (YouTube + portal)",
            "apply_guide":    "/apply/guide — Step-by-step Hinglish application wizard",
            "apply_schemes":  "/apply/schemes — List all guided schemes",
            "docs":           "/docs",
        }
    }


@app.get("/health")
async def health():
    """Health check — returns service status and ChromaDB index state."""
    from ai_service.rag_chain import get_chromadb_count, _memory_store

    chroma_count = get_chromadb_count()
    return {
        "status": "ok",
        "version": "1.0.0",
        "chromadb": {
            "indexed_schemes": chroma_count,
            "healthy": chroma_count > 0,
        },
        "chat_sessions_active": len(_memory_store),
    }


# ── Dev server ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("ai_service.main:app", host="0.0.0.0", port=8000, reload=True)
