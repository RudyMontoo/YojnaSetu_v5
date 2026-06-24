"""
jwt_auth.py — verifies the RS256 citizen JWT Spring Boot issues
(ADR-001, deploy/backend/spring-gateway/.../security/JwtUtils.java), read
from the httpOnly `access_token` cookie ONLY — never a header or request
body — matching Spring Boot's own JwtAuthFilter contract (CLAUDE.md: "JWT
... stored in httpOnly cookies only — NEVER localStorage").

RS256 is asymmetric: ai_service only ever needs Spring Boot's PUBLIC key to
verify a token it didn't issue — that's the whole point of choosing RS256
over HS256 in ADR-001, and why this file never touches the private key.

Before this, endpoints (financial-plan, orchestrator/chat) took citizen_id
directly in the request body and trusted it at face value — any caller
could act as any citizen. This dependency replaces that: citizen_id now
only ever comes from a signature-verified token.
"""
import logging
import os
from pathlib import Path

import jwt
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

ACCESS_TOKEN_COOKIE = "access_token"
DEV_BYPASS_CITIZEN_ID = "dev-citizen-001"

# Falls back to the sibling Spring Boot module's key if JWT_PUBLIC_KEY_PATH
# isn't set — both services live in this monorepo, so this holds for local
# dev without extra config; prod should set JWT_PUBLIC_KEY_PATH explicitly.
_DEFAULT_PUBLIC_KEY_PATH = (
    Path(__file__).resolve().parents[2]
    / "deploy" / "backend" / "spring-gateway" / "keys" / "jwt_public.pem"
)

_public_key_cache: str | None = None
_warned_dev_bypass = False


def _load_public_key() -> str | None:
    global _public_key_cache
    if _public_key_cache is not None:
        return _public_key_cache

    configured = os.getenv("JWT_PUBLIC_KEY_PATH", "").strip()
    path = Path(configured) if configured else _DEFAULT_PUBLIC_KEY_PATH
    if not path.exists():
        return None

    _public_key_cache = path.read_text()
    return _public_key_cache


def _claims_from_token(token: str | None) -> dict:
    """Core verification shared by every auth variant here. Returns the
    verified claims dict. Raises HTTPException(401) on any failure; returns
    dev-bypass claims when no public key exists (see get_current_citizen_id's
    docstring for the reasoning)."""
    global _warned_dev_bypass
    public_key = _load_public_key()

    if public_key is None:
        if not _warned_dev_bypass:
            logger.warning(
                "⚠️  Spring Boot JWT public key not found — JWT verification is DISABLED, "
                "using %s for all requests. Set JWT_PUBLIC_KEY_PATH before deploying to production!",
                DEV_BYPASS_CITIZEN_ID,
            )
            _warned_dev_bypass = True
        return {"sub": DEV_BYPASS_CITIZEN_ID, "role": "CITIZEN", "type": "access"}

    if not token:
        raise HTTPException(status_code=401, detail="Missing access_token cookie.")

    try:
        claims = jwt.decode(token, public_key, algorithms=["RS256"])
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {e.__class__.__name__}")

    if claims.get("type") != "access":
        raise HTTPException(status_code=401, detail="Not an access token.")

    if not claims.get("sub"):
        raise HTTPException(status_code=401, detail="Token missing subject.")
    return claims


def _citizen_id_from_token(token: str | None) -> str:
    return _claims_from_token(token)["sub"]


def get_current_citizen_id(request: Request) -> str:
    """FastAPI dependency: verifies the `access_token` cookie against Spring
    Boot's RS256 public key, returns the citizen's userId (JWT subject).

    Dev bypass: if no public key is found (Spring Boot keypair not
    generated yet — see JwtUtils.java's own ephemeral-keypair fallback),
    returns a fixed dev citizen id with a loud one-time warning, same
    pattern as utils/auth.py's require_api_key — local dev keeps working
    without a full Spring Boot OTP flow running, but this must never be the
    case in production."""
    return _citizen_id_from_token(request.cookies.get(ACCESS_TOKEN_COOKIE))


def citizen_id_from_websocket_cookies(cookies: dict) -> str:
    """WebSocket variant of get_current_citizen_id. Browsers cannot set
    custom headers (like X-API-Key) on a WebSocket handshake, but they DO
    send cookies — so the httpOnly access_token cookie is the auth for WS
    endpoints, same trust chain as HTTP. Raises HTTPException(401) on
    failure; the WS handler translates that into a policy-violation close
    (code 1008) since HTTP status codes don't exist mid-WebSocket."""
    return _citizen_id_from_token(cookies.get(ACCESS_TOKEN_COOKIE))


_OPERATOR_ROLES = {"CSC_OPERATOR", "ADMIN"}


def get_current_operator_id(request: Request) -> str:
    """Role-gated variant for CSC-operator endpoints (CLAUDE.md: 'Operator
    JWT'). The role claim is inside the RS256-signed token Spring Boot
    issued, so it's as tamper-proof as the identity itself — no extra
    lookup needed. 403 (not 401) for a valid citizen token without the
    role: the caller IS authenticated, just not allowed."""
    claims = _claims_from_token(request.cookies.get(ACCESS_TOKEN_COOKIE))
    if claims.get("role") not in _OPERATOR_ROLES:
        raise HTTPException(status_code=403, detail="Operator role required for this endpoint.")
    return claims["sub"]


def get_current_admin_id(request: Request) -> str:
    """Admin-only variant (CLAUDE.md: 'Admin JWT') — stricter than
    get_current_operator_id: CSC operators are NOT admins."""
    claims = _claims_from_token(request.cookies.get(ACCESS_TOKEN_COOKIE))
    if claims.get("role") != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin role required for this endpoint.")
    return claims["sub"]
