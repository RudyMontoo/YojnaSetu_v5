"""
interface.py — the code contract for Agent 11 (Biometric Assist / Face Liveness).

This file defines the SEAM between Agent 11 and the rest of Yojna Setu. The
platform (frontend capture -> this endpoint -> Agent 12's signed DLC payload)
is built against these types. The CV/ML engineer implements `LivenessDetector`
and registers it in `get_detector()`; nothing else in the codebase needs to
change. See README.md §3–§4 for the full contract.

Deliberately dependency-free (stdlib only) so importing the contract never
drags in heavy CV libraries — those live behind `get_detector()`, loaded only
when a real detector is wired.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class LivenessResult:
    """The ONLY thing allowed to leave the liveness check. No frames, no face
    embeddings, no landmark vectors — just the verdict (README.md §6 rule 1/2)."""

    is_live: bool
    confidence: float                 # 0.0–1.0; calibrated probability the subject is a live human
    model_version: str                # e.g. "illuminet-mnv3-v1" — provenance is mandatory (README §6.5)
    frames_analyzed: int = 0
    checks: dict = field(default_factory=dict)  # optional sub-signals, e.g. {"blink": true, "moire": false}

    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0,1], got {self.confidence}")


def liveness_claim(result: LivenessResult) -> dict:
    """Produces the `liveness` block that the frontend embeds INTO the DLC
    payload BEFORE Agent 12 signs it — so liveness is cryptographically bound
    to the certificate (README.md §3). This exact shape is what dlc_router's
    /verify will read (and eventually enforce)."""
    return {
        "verified": bool(result.is_live),
        "confidence": round(float(result.confidence), 4),
        "model_version": result.model_version,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


class LivenessDetector(ABC):
    """Implement this. Register your subclass in `get_detector()` below.

    Contract:
    - `analyze` gets a short burst of camera frames (JPEG/PNG bytes) — the
      client captures ~1–2s. It must NOT persist any frame anywhere.
    - It must return a `LivenessResult`, and must FAIL CLOSED: on any error,
      low confidence, or ambiguous input, return is_live=False (README §6.3).
    - It must return within Agent 11's 20s timeout budget (CLAUDE.md).
    """

    @abstractmethod
    async def analyze(self, frames: list[bytes], challenge: str | None = None) -> LivenessResult:
        """`challenge` (optional): a requested action the subject must perform —
        "blink" | "turn_left" | "turn_right". Supplying it makes this ACTIVE
        liveness (proves a specific action) rather than just "a face moved"."""
        raise NotImplementedError


class _UnimplementedDetector(LivenessDetector):
    """Fallback when the CV model isn't available (e.g. a cloud deploy without
    the mediapipe extra, or the model file missing). Fails closed — never
    silently passes a certificate through."""

    async def analyze(self, frames: list[bytes], challenge: str | None = None) -> LivenessResult:
        raise NotImplementedError(
            "Agent 11 face-liveness model is not available in this environment "
            "(mediapipe not installed or model file missing). See README.md."
        )


import os

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "face_landmarker.task")
_detector_singleton: LivenessDetector | None = None


def get_detector() -> LivenessDetector:
    """Returns the MediaPipe face-liveness detector (cached — the FaceLandmarker
    loads once). Falls back to _UnimplementedDetector (→ honest 501) if mediapipe
    isn't installed or the model file is absent, so a GPU-less cloud deploy
    degrades gracefully instead of crashing."""
    global _detector_singleton
    if _detector_singleton is not None:
        return _detector_singleton
    try:
        import mediapipe  # noqa: F401
        if not os.path.exists(_MODEL_PATH):
            raise FileNotFoundError(f"face_landmarker.task not found at {_MODEL_PATH}")
        from ai_service.vision.agent11_biometric.mediapipe_detector import MediaPipeLivenessDetector
        _detector_singleton = MediaPipeLivenessDetector(_MODEL_PATH)
    except Exception:
        _detector_singleton = _UnimplementedDetector()
    return _detector_singleton


def is_implemented() -> bool:
    """Lets the router return an honest 501 when the detector isn't available."""
    return not isinstance(get_detector(), _UnimplementedDetector)
