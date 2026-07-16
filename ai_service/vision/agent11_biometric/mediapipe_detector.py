"""
mediapipe_detector.py — Agent 11's face-liveness detector (ACTIVE liveness).

Implements the LivenessDetector contract in interface.py using Google's official
MediaPipe FaceLandmarker. Chosen deliberately over the v5.0 doc's "IllumiNet /
MobileNetV3" because those weights don't exist anywhere we can verify — and
CLAUDE.md's own rule is that model provenance must be documented (README §6.5).
MediaPipe's `face_landmarker.task` is a published Google model (Apache-2.0), so
provenance is answerable. That resolves the biggest open unknown in the plan.

WHAT THIS DETECTS (be precise — a liveness check that overstates itself is worse
than none, because a certificate is issued on the back of it):

  ✅ Rejects a PRINTED PHOTO or a static image on a screen — a real face always
     has micro-motion and blinks; a still image has literally zero landmark
     variance across frames.
  ✅ Rejects "no face" / multiple faces / unreadable input (fails CLOSED).
  ✅ Confirms a requested ACTION was performed (blink / turn head) when a
     challenge is supplied — so it isn't just "a face moved".
  ❌ Does NOT reliably defeat a determined VIDEO REPLAY of the real pensioner.
     Beating that needs a trained anti-spoofing (PAD) model or Aadhaar Face RD —
     both outside solo reach. The randomised, short-TTL challenge raises the bar
     (an attacker needs a clip of *that* action, on demand) but does not close it.

Privacy: frames are analysed in RAM and never written to disk or Mongo — only the
boolean verdict + confidence leaves this module (README §6.1/6.2, DPDP).
"""
from __future__ import annotations

import asyncio
import logging
import math
import threading

import cv2
import numpy as np

from ai_service.vision.agent11_biometric.interface import LivenessDetector, LivenessResult

logger = logging.getLogger(__name__)

MODEL_VERSION = "mediapipe-face-landmarker-v1"

# ── Thresholds (tuned conservatively — when unsure, fail closed) ───────────────
_MIN_FRAMES = 6              # need a real burst; a single image can't show liveness
_MIN_FACE_RATIO = 0.6        # face must be found in most frames
_BLINK_CLOSED = 0.45         # blendshape score above this = eye closed
_BLINK_OPEN = 0.20           # ...and below this = open. Need both to call it a blink.
_MIN_MOTION = 0.0015         # mean landmark std-dev; a still photo is ~0. Live faces jitter.
_YAW_TURN_DEG = 12.0         # head rotation that counts as a deliberate turn


def _decode(frame: bytes):
    arr = np.frombuffer(frame, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return None if img is None else cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def _yaw_from_matrix(matrix) -> float:
    """Head yaw (left/right) in degrees from the 4x4 facial transformation matrix."""
    m = np.array(matrix).reshape(4, 4)
    # standard rotation-matrix -> yaw extraction
    return math.degrees(math.atan2(-m[2][0], math.sqrt(m[2][1] ** 2 + m[2][2] ** 2)))


class MediaPipeLivenessDetector(LivenessDetector):
    """Frame-burst active-liveness via MediaPipe FaceLandmarker.

    `challenge` (optional): "blink" | "turn_left" | "turn_right". When given, the
    subject must actually perform it — that's what makes this ACTIVE liveness
    rather than "we saw a face".
    """

    def __init__(self, model_path: str):
        self._model_path = model_path
        self._landmarker = None
        self._lock = threading.Lock()  # MediaPipe landmarker isn't thread-safe

    def _get_landmarker(self):
        if self._landmarker is None:
            from mediapipe.tasks.python import BaseOptions, vision
            self._landmarker = vision.FaceLandmarker.create_from_options(
                vision.FaceLandmarkerOptions(
                    base_options=BaseOptions(model_asset_path=self._model_path),
                    running_mode=vision.RunningMode.IMAGE,
                    num_faces=2,  # detect >1 so we can REJECT multi-face input
                    output_face_blendshapes=True,
                    output_facial_transformation_matrixes=True,
                )
            )
        return self._landmarker

    async def analyze(self, frames: list[bytes], challenge: str | None = None) -> LivenessResult:
        try:
            return await asyncio.to_thread(self._analyze_sync, frames, challenge)
        except Exception as e:  # noqa: BLE001 — ANY failure fails closed (README §6.3)
            logger.warning("liveness analysis error, failing closed: %s: %s", e.__class__.__name__, e)
            return LivenessResult(is_live=False, confidence=0.0, model_version=MODEL_VERSION,
                                  frames_analyzed=len(frames), checks={"error": e.__class__.__name__})

    def _analyze_sync(self, frames: list[bytes], challenge: str | None = None) -> LivenessResult:
        import mediapipe as mp

        n = len(frames)
        if n < _MIN_FRAMES:
            return LivenessResult(False, 0.0, MODEL_VERSION, n,
                                  {"reason": f"need >= {_MIN_FRAMES} frames, got {n}"})

        blink_scores: list[float] = []
        yaws: list[float] = []
        landmark_sets: list[np.ndarray] = []
        faces_found = 0
        multi_face = False

        with self._lock:
            lm = self._get_landmarker()
            for raw in frames:
                rgb = _decode(raw)
                if rgb is None:
                    continue
                res = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
                if not res.face_landmarks:
                    continue
                if len(res.face_landmarks) > 1:
                    multi_face = True
                faces_found += 1

                pts = np.array([[p.x, p.y] for p in res.face_landmarks[0]], dtype=np.float32)
                landmark_sets.append(pts)

                if res.face_blendshapes:
                    by = {b.category_name: b.score for b in res.face_blendshapes[0]}
                    blink_scores.append(max(by.get("eyeBlinkLeft", 0.0), by.get("eyeBlinkRight", 0.0)))
                if res.facial_transformation_matrixes:
                    yaws.append(_yaw_from_matrix(res.facial_transformation_matrixes[0]))

        face_ratio = faces_found / n
        if multi_face:
            return LivenessResult(False, 0.0, MODEL_VERSION, n,
                                  {"reason": "more than one face in frame", "face_ratio": round(face_ratio, 2)})
        if face_ratio < _MIN_FACE_RATIO:
            return LivenessResult(False, 0.0, MODEL_VERSION, n,
                                  {"reason": "no consistent face detected", "face_ratio": round(face_ratio, 2)})

        # ── Motion: THE anti-photo signal. A still image has ~zero variance. ──
        motion = 0.0
        if len(landmark_sets) >= 2:
            k = min(len(s) for s in landmark_sets)
            stack = np.stack([s[:k] for s in landmark_sets])       # (frames, points, 2)
            motion = float(np.mean(np.std(stack, axis=0)))

        blinked = bool(blink_scores) and max(blink_scores) > _BLINK_CLOSED and min(blink_scores) < _BLINK_OPEN
        yaw_range = (max(yaws) - min(yaws)) if yaws else 0.0
        turned_left = bool(yaws) and (max(yaws) - min(yaws)) > _YAW_TURN_DEG and max(yaws) > _YAW_TURN_DEG / 2
        turned_right = bool(yaws) and (max(yaws) - min(yaws)) > _YAW_TURN_DEG and min(yaws) < -_YAW_TURN_DEG / 2

        checks = {
            "face_ratio": round(face_ratio, 2),
            "motion": round(motion, 5),
            "blink_detected": blinked,
            "yaw_range_deg": round(yaw_range, 1),
            "challenge": challenge,
        }

        # A static photo can never pass this, regardless of challenge.
        if motion < _MIN_MOTION:
            checks["reason"] = "no micro-motion across frames — looks like a still image"
            return LivenessResult(False, 0.0, MODEL_VERSION, n, checks)

        # ── Challenge gate: the requested action must actually have happened ──
        if challenge:
            performed = {"blink": blinked, "turn_left": turned_left, "turn_right": turned_right}.get(challenge)
            if performed is None:
                checks["reason"] = f"unknown challenge {challenge!r}"
                return LivenessResult(False, 0.0, MODEL_VERSION, n, checks)
            checks["challenge_performed"] = bool(performed)
            if not performed:
                checks["reason"] = f"challenge '{challenge}' not performed"
                return LivenessResult(False, 0.0, MODEL_VERSION, n, checks)

        # Confidence from independent signals — never a flat 1.0; this is evidence, not proof.
        conf = 0.5
        if blinked:
            conf += 0.25
        if yaw_range > _YAW_TURN_DEG:
            conf += 0.10
        conf += min(0.15, motion * 20)
        conf = min(conf, 0.95)

        return LivenessResult(True, round(conf, 3), MODEL_VERSION, n, checks)
