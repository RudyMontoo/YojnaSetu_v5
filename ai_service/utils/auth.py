"""
auth.py — API Key authentication dependency for Yojna Setu AI Service.

All expensive/sensitive endpoints use:
    from ai_service.utils.auth import require_api_key
    @router.post("/...", dependencies=[Depends(require_api_key)])

The key is read from the `X-API-Key` request header and compared against
the `INTERNAL_API_KEY` environment variable using constant-time comparison
to prevent timing attacks.

Setup:
    1. Add INTERNAL_API_KEY=<a-long-random-string> to ai_service/.env
    2. Configure Spring Boot Gateway to forward:
           X-API-Key: <same-value>
       in every request proxied to FastAPI.
"""
import os
import secrets
import logging
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

# Header name the caller must supply
_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(api_key: str | None = Security(_API_KEY_HEADER)) -> None:
    """
    FastAPI dependency: validates the X-API-Key header.

    - Returns None (passes) if the key matches INTERNAL_API_KEY env var.
    - Raises 403 Forbidden if missing or wrong.
    - If INTERNAL_API_KEY is not set in the environment (e.g. local dev),
      auth is SKIPPED with a warning so development still works out-of-box.
    """
    expected_key = os.getenv("INTERNAL_API_KEY", "").strip()

    # Dev mode: if no key is configured, skip auth with a loud warning
    if not expected_key:
        logger.warning(
            "⚠️  INTERNAL_API_KEY is not set — API auth is DISABLED. "
            "Set this before deploying to production!"
        )
        return

    # Constant-time comparison to prevent timing attacks
    if not api_key or not secrets.compare_digest(api_key.strip(), expected_key):
        raise HTTPException(
            status_code=403,
            detail="Forbidden: invalid or missing API key.",
        )
