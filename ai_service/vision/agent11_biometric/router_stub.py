"""
router_stub.py — the FastAPI surface for Agent 11, wired but disabled.

This is intentionally NOT mounted in ai_service/main.py yet — the pensioner
vertical launches as a post-deployment feature update (README.md §7). When the
CV engineer implements the detector, mount this router and the endpoint goes
live with zero other changes.

Auth, multipart handling, the frames->detector call, and the fail-closed
contract are all already here. The ONLY thing missing is the model behind
`get_detector()`. Until `is_implemented()` is true, the endpoint returns an
honest 501 rather than pretending to check liveness.
"""
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ai_service.utils.jwt_auth import get_current_citizen_id
from ai_service.vision.agent11_biometric.interface import (
    get_detector,
    is_implemented,
    liveness_claim,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents/biometric", tags=["agent11-biometric"])

MAX_FRAMES = 60           # ~2s at 30fps — bounds memory; reject floods
MAX_FRAME_BYTES = 2 * 1024 * 1024  # 2MB/frame ceiling


@router.post("/liveness")
async def check_liveness(
    frames: list[UploadFile] = File(..., description="Short burst of camera frames (JPEG/PNG)"),
    citizen_id: str = Depends(get_current_citizen_id),
):
    """Runs the face-liveness check on an in-memory burst of frames and returns
    a result the frontend embeds into the DLC payload before signing.

    Returns 501 until a real detector is registered (README.md §7 Phase A)."""
    if not is_implemented():
        raise HTTPException(
            status_code=501,
            detail=(
                "Face liveness (Agent 11) is not implemented yet. The Digital Life "
                "Certificate currently issues without a liveness gate; this endpoint "
                "activates in a later feature update. See ai_service/vision/agent11_biometric/README.md."
            ),
        )

    if not frames:
        raise HTTPException(status_code=400, detail="No frames provided.")
    if len(frames) > MAX_FRAMES:
        raise HTTPException(status_code=413, detail=f"Too many frames (max {MAX_FRAMES}).")

    # Read frames into memory ONLY. Never write to disk/GCS/Mongo (README §6.1).
    frame_bytes: list[bytes] = []
    for f in frames:
        data = await f.read()
        if len(data) > MAX_FRAME_BYTES:
            raise HTTPException(status_code=413, detail="A frame exceeds the size limit.")
        frame_bytes.append(data)

    detector = get_detector()
    try:
        result = await detector.analyze(frame_bytes)
    except Exception as e:  # noqa: BLE001 — fail closed on ANY error (README §6.3)
        logger.warning("Liveness analysis failed for citizen; failing closed: %s", e)
        raise HTTPException(status_code=422, detail="Liveness could not be verified. Please try again.")
    finally:
        frame_bytes.clear()  # drop biometric bytes ASAP

    # Return only the verdict block — no frames, no biometric template leaves here.
    return {
        "is_live": result.is_live,
        "confidence": round(result.confidence, 4),
        "liveness_claim": liveness_claim(result),  # <- frontend embeds this into the DLC payload, then signs
    }
