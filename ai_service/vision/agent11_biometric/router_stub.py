"""
router_stub.py — Agent 11's live FastAPI surface (face liveness).

Two endpoints, deliberately split so liveness can't be replayed:

  POST /agents/biometric/challenge  → server issues a RANDOM action
      ("blink" / "turn_left" / "turn_right") + a single-use nonce with a short
      TTL. The client can't pick the action, and a captured burst is only valid
      for that one nonce.

  POST /agents/biometric/liveness   → client sends the frame burst + the nonce.
      Server validates the nonce (exists, ours, unexpired, unused), marks it
      used, runs the detector against the ISSUED challenge, and returns a verdict
      the frontend embeds into the DLC payload before signing.

Security posture (README §6): frames are read into RAM only, analysed, and
dropped — never written to disk/Mongo. Only the boolean verdict + confidence
leave the server. The check runs SERVER-SIDE — a client-reported "is_live:true"
would be trivially forged, so the browser never decides liveness.

Falls back to an honest 501 if the CV model isn't available in this environment
(e.g. a cloud deploy without the mediapipe extra) — is_implemented() gates it.
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from ai_service.db.mongo import get_db
from ai_service.utils.jwt_auth import get_current_citizen_id
from ai_service.utils.rate_limiter import biometric_limiter
from ai_service.vision.agent11_biometric.interface import (
    get_detector,
    is_implemented,
    liveness_claim,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents/biometric", tags=["agent11-biometric"])

MAX_FRAMES = 20                    # frontend sends ~10; bounds memory + GPU work
MAX_FRAME_BYTES = 1 * 1024 * 1024  # 1MB/frame ceiling (640x480 JPEG is ~50-150KB)
MAX_TOTAL_BYTES = 12 * 1024 * 1024 # hard cap on the whole burst — anti memory-DoS
CHALLENGE_TTL_SECONDS = 90         # capture window; an unused/failed nonce dies after this
LIVENESS_BIND_DAYS = 7             # a PASSED nonce lives this long so a (delayed/offline) DLC can bind to it
_CHALLENGES = ["blink", "turn_left", "turn_right"]


@router.post("/challenge")
async def issue_challenge(request: Request, citizen_id: str = Depends(get_current_citizen_id)):
    """Issues a random liveness action + a single-use nonce (short TTL). The
    client must perform THIS action; it can't choose it, and the nonce is only
    valid once — which is what stops a recorded burst being replayed."""
    biometric_limiter.check(biometric_limiter.get_client_ip(request))
    if not is_implemented():
        raise HTTPException(status_code=501, detail="Face liveness is not available in this environment.")

    challenge = secrets.choice(_CHALLENGES)
    nonce = secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc)
    await get_db()["biometric_challenges"].insert_one({
        "nonce": nonce,
        "citizenId": citizen_id,
        "challenge": challenge,
        "used": False,
        "createdAt": now,
        "expiresAt": now + timedelta(seconds=CHALLENGE_TTL_SECONDS),
    })
    return {"challenge": challenge, "nonce": nonce, "expires_in": CHALLENGE_TTL_SECONDS}


@router.post("/liveness")
async def check_liveness(
    request: Request,
    frames: list[UploadFile] = File(..., description="Short burst of camera frames (JPEG/PNG)"),
    nonce: str = Form(..., description="The nonce from POST /challenge"),
    citizen_id: str = Depends(get_current_citizen_id),
):
    """Validates the nonce, runs the liveness check against the issued challenge,
    and returns a verdict + a claim the frontend embeds into the DLC payload."""
    biometric_limiter.check(biometric_limiter.get_client_ip(request))
    if not is_implemented():
        raise HTTPException(status_code=501, detail="Face liveness is not available in this environment.")
    if not frames:
        raise HTTPException(status_code=400, detail="No frames provided.")
    if len(frames) > MAX_FRAMES:
        raise HTTPException(status_code=413, detail=f"Too many frames (max {MAX_FRAMES}).")

    # ── Consume the nonce ATOMICALLY: it must exist, be ours, unexpired, unused ──
    now = datetime.now(timezone.utc)
    claimed = await get_db()["biometric_challenges"].find_one_and_update(
        {"nonce": nonce, "citizenId": citizen_id, "used": False, "expiresAt": {"$gt": now}},
        {"$set": {"used": True, "usedAt": now}},
    )
    if not claimed:
        # unknown / not yours / expired / already used — all → reject (no leak of which)
        raise HTTPException(status_code=409, detail="Invalid or expired liveness challenge. Request a new one.")
    challenge = claimed["challenge"]

    # ── Read frames into RAM only (never persisted). Enforce a per-frame AND a
    # whole-burst byte cap so a caller can't OOM the box with 20 huge frames. ──
    frame_bytes: list[bytes] = []
    total = 0
    for f in frames:
        data = await f.read()
        if len(data) > MAX_FRAME_BYTES:
            raise HTTPException(status_code=413, detail="A frame exceeds the size limit.")
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            frame_bytes.clear()
            raise HTTPException(status_code=413, detail="Frame burst exceeds the total size limit.")
        frame_bytes.append(data)

    detector = get_detector()
    try:
        result = await detector.analyze(frame_bytes, challenge=challenge)
    except Exception as e:  # noqa: BLE001 — fail closed on ANY error (README §6.3)
        logger.warning("Liveness analysis failed; failing closed: %s", e)
        raise HTTPException(status_code=422, detail="Liveness could not be verified. Please try again.")
    finally:
        frame_bytes.clear()  # drop biometric bytes ASAP

    # ── Record the SERVER's verdict durably on the challenge record. This is what
    # closes the fabrication hole: /dlc/verify checks THIS, not the client's JSON.
    # A client that skips the camera and writes "verified:true" itself will have
    # no matching passed=true record, so its certificate is rejected.
    #
    # On a PASS, extend the record's lifetime to LIVENESS_BIND_DAYS so it survives
    # the (possibly offline, delayed) DLC submission that binds to it — the raw
    # 90s challenge TTL would otherwise delete it before verification. ──
    verdict = {"passed": bool(result.is_live), "confidence": round(result.confidence, 4), "verdictAt": now}
    if result.is_live:
        verdict["expiresAt"] = now + timedelta(days=LIVENESS_BIND_DAYS)
    await get_db()["biometric_challenges"].update_one(
        {"nonce": nonce, "citizenId": citizen_id}, {"$set": verdict},
    )

    # The claim carries the challenge + nonce so the signed DLC payload is bound
    # to THIS specific, single-use, server-verified liveness check.
    claim = liveness_claim(result)
    claim["challenge"] = challenge
    claim["nonce"] = nonce
    logger.info("Agent 11 liveness: citizen=%s challenge=%s is_live=%s", citizen_id, challenge, result.is_live)
    return {"is_live": result.is_live, "confidence": round(result.confidence, 4), "liveness_claim": claim}
