"""
dlc_router.py — Agent 12 (Offline Survival Proof), the verifiable core.

The problem: a pensioner must periodically prove they're alive (Digital Life
Certificate / DLC) or their pension stops. In low-connectivity areas they
can't reach the pension portal on the day it's due. Agent 12 lets the device
generate a cryptographically-signed "I am alive" proof OFFLINE, which is
verified by the server whenever connectivity returns — either the device
syncs its own queued proofs on reconnect, or it shows the proof as a QR code
that someone with connectivity (a CSC operator, a relative) scans and submits.

Trust model, honestly scoped for a web PWA (not a native app):
- The device generates an RSA-2048 keypair once (WebCrypto). The PRIVATE key
  is non-extractable and lives only in the browser's IndexedDB — the closest
  a PWA gets to a secure enclave (the v5.0 plan's own risk note says so).
- The PUBLIC key is registered here once, while online.
- Each life certificate is a small JSON payload signed with RSASSA-PKCS1-v1_5
  + SHA-256. The server verifies the signature against the registered public
  key, so a proof can't be forged or altered after signing — and crucially,
  the signature is created at proof time on the device, so a valid signature
  is real evidence the keyholder acted, even if it's verified days later.

Replay protection: every proof carries a client nonce; a nonce already seen
for that citizen is rejected, so a captured proof can't be re-submitted to
fake a later life check.

DELIBERATELY NOT built here (honest gaps, same class as Agent 5's NPCI):
- Bluetooth / WiFi-Direct peer transfer — not a web-platform API; the QR code
  is the web-appropriate substitute for offline peer-to-peer handoff.
- Real SPARSH / pension-department acceptance — needs institutional
  integration a solo project doesn't have; this verifies and records the
  proof in our own system, which is the swappable handoff point.
"""
import json
import logging
from datetime import datetime, timedelta, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from fastapi import APIRouter, Depends, HTTPException
from jwt.algorithms import RSAAlgorithm
from pydantic import BaseModel

from ai_service.db.mongo import get_db
from ai_service.utils.jwt_auth import get_current_citizen_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents/dlc", tags=["agent12-dlc"])

# A life certificate is valid for this long before a fresh one is due. Real
# pension DLC cadence is annual; kept short-ish here so "next due" is a
# meaningful, testable field rather than a year away.
DLC_VALID_DAYS = 365


class RegisterKeyRequest(BaseModel):
    key_id: str            # client-chosen id for this device key
    public_key_jwk: dict   # WebCrypto exported public key (RSA, JWK form)


class VerifyProofRequest(BaseModel):
    key_id: str
    # The exact canonical JSON string the device signed (sign-what-you-see:
    # the server verifies the signature over THIS string, then parses it).
    payload: str
    signature_b64: str     # base64 RSASSA-PKCS1-v1_5 / SHA-256 signature


def _canonical_public_key(jwk: dict):
    """Import a WebCrypto RSA public JWK into a cryptography public key.
    Raises HTTPException(400) on anything malformed rather than 500."""
    try:
        if jwk.get("kty") != "RSA":
            raise ValueError("only RSA keys are accepted")
        key = RSAAlgorithm.from_jwk(json.dumps(jwk))
        # PyJWT's from_jwk base64url-decodes leniently — a garbage modulus
        # produces a tiny (e.g. 56-bit) "key" rather than an error. Reject
        # anything below a real RSA-2048 at registration, so a corrupt key is
        # caught now instead of silently registered and failing every later
        # verify. (The spec is RSA-2048.)
        if key.key_size < 2048:
            raise ValueError(f"RSA key too small ({key.key_size}-bit) — 2048-bit minimum")
        return key
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid public key JWK: {e}")


@router.post("/register-key")
async def register_key(req: RegisterKeyRequest, citizen_id: str = Depends(get_current_citizen_id)):
    """Register this device's public key (once, while online). Re-registering
    the same key_id updates it (e.g. after a key rotation). The private key
    never leaves the device."""
    _canonical_public_key(req.public_key_jwk)  # validate before storing
    db = get_db()
    await db["dlc_keys"].update_one(
        {"citizenId": citizen_id, "keyId": req.key_id},
        {"$set": {
            "citizenId": citizen_id, "keyId": req.key_id,
            "publicKeyJwk": req.public_key_jwk, "algo": "RS256",
            "registeredAt": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    logger.info("[DLC] key registered citizen=%s key=%s", citizen_id, req.key_id)
    return {"registered": True, "key_id": req.key_id}


@router.post("/verify")
async def verify_proof(req: VerifyProofRequest, citizen_id: str = Depends(get_current_citizen_id)):
    """Verify a signed life certificate against the citizen's registered key,
    then record it. Rejects a bad signature, an unknown key, a payload whose
    citizenId doesn't match the caller, or a replayed nonce."""
    db = get_db()

    key_doc = await db["dlc_keys"].find_one({"citizenId": citizen_id, "keyId": req.key_id})
    if not key_doc:
        raise HTTPException(status_code=404, detail="No registered key for this key_id — register the device first.")

    public_key = _canonical_public_key(key_doc["publicKeyJwk"])

    # 1) Signature must verify over the EXACT payload string the device signed.
    import base64
    try:
        signature = base64.b64decode(req.signature_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="signature_b64 is not valid base64")
    try:
        public_key.verify(
            signature, req.payload.encode("utf-8"),
            padding.PKCS1v15(), hashes.SHA256(),
        )
    except InvalidSignature:
        logger.warning("[DLC] signature REJECTED citizen=%s key=%s", citizen_id, req.key_id)
        raise HTTPException(status_code=401, detail="Signature does not verify — proof rejected.")

    # 2) Payload must be well-formed and belong to this citizen (a valid
    #    signature over someone else's payload is still not their proof).
    try:
        payload = json.loads(req.payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Signed payload is not valid JSON.")
    if payload.get("citizenId") != citizen_id:
        raise HTTPException(status_code=403, detail="Proof citizenId does not match the authenticated citizen.")
    nonce = payload.get("nonce")
    if not nonce:
        raise HTTPException(status_code=400, detail="Proof payload missing a nonce (replay protection).")

    # 3) Replay protection — a nonce already recorded for this citizen can't be reused.
    if await db["dlc_proofs"].find_one({"citizenId": citizen_id, "nonce": nonce}):
        raise HTTPException(status_code=409, detail="This proof was already submitted (replay).")

    now = datetime.now(timezone.utc)
    # The signed timestamp is when the citizen actually generated the proof
    # (possibly offline, days ago); verifiedAt is when it reached the server.
    generated_at = payload.get("generatedAt")
    await db["dlc_proofs"].insert_one({
        "citizenId": citizen_id, "keyId": req.key_id, "nonce": nonce,
        "generatedAt": generated_at, "verifiedAt": now,
        "payload": payload, "status": "verified",
    })
    next_due = now + timedelta(days=DLC_VALID_DAYS)
    logger.info("[DLC] proof VERIFIED citizen=%s key=%s nonce=%s", citizen_id, req.key_id, nonce)
    return {
        "verified": True,
        "generated_at": generated_at,
        "verified_at": now.isoformat(),
        "next_due": next_due.isoformat(),
    }


@router.get("/status")
async def dlc_status(citizen_id: str = Depends(get_current_citizen_id)):
    """Whether the citizen has a registered device and a currently-valid life
    certificate, and when the next one is due."""
    db = get_db()
    has_key = await db["dlc_keys"].count_documents({"citizenId": citizen_id}) > 0
    latest = await db["dlc_proofs"].find_one(
        {"citizenId": citizen_id}, sort=[("verifiedAt", -1)]
    )
    if not latest:
        return {"device_registered": has_key, "has_valid_certificate": False, "last_verified_at": None, "next_due": None}

    # Motor returns naive UTC datetimes — make it tz-aware before comparing
    # against an aware now() (else TypeError).
    verified_at = latest["verifiedAt"]
    if verified_at.tzinfo is None:
        verified_at = verified_at.replace(tzinfo=timezone.utc)
    next_due = verified_at + timedelta(days=DLC_VALID_DAYS)
    return {
        "device_registered": has_key,
        "has_valid_certificate": next_due > datetime.now(timezone.utc),
        "last_verified_at": verified_at.isoformat(),
        "next_due": next_due.isoformat(),
    }
