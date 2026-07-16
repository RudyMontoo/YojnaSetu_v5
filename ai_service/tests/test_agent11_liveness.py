"""
Deterministic tests for Agent 11's liveness DECISION logic
(vision/agent11_biometric/mediapipe_detector.py).

MediaPipe's real face detection needs a live camera face, which can't be a CI
fixture — so we script the FaceLandmarker's output and assert the security
logic on top of it: a static photo (identical frames → zero motion) is rejected,
a requested challenge must actually be performed, multi-face is rejected, and
everything fails CLOSED. This pins the exact anti-spoof reasoning that decides
whether a life certificate gets issued.

Needs mediapipe importable (for mp.Image); it does NOT need the model file or a
real face — the landmarker is replaced with a scripted fake.
"""
import asyncio
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

mp = pytest.importorskip("mediapipe")

from ai_service.vision.agent11_biometric.mediapipe_detector import MediaPipeLivenessDetector


def _jpeg() -> bytes:
    return cv2.imencode(".jpg", np.full((64, 64, 3), 200, np.uint8))[1].tobytes()


class _FakeLandmarker:
    """Returns a scripted result per detect() call, ignoring the image."""
    def __init__(self, results):
        self._results, self._i = results, 0

    def detect(self, _image):
        r = self._results[min(self._i, len(self._results) - 1)]
        self._i += 1
        return r


def _lm(x, y):
    return SimpleNamespace(x=x, y=y)


def _result(points, blink=0.05, yaw_matrix=None, faces=1):
    face = [_lm(px, py) for px, py in points]
    blend = [[SimpleNamespace(category_name="eyeBlinkLeft", score=blink),
              SimpleNamespace(category_name="eyeBlinkRight", score=blink)]]
    mats = [yaw_matrix] if yaw_matrix is not None else []
    return SimpleNamespace(face_landmarks=[face] * faces, face_blendshapes=blend,
                           facial_transformation_matrixes=mats)


def _detector_with(results):
    d = MediaPipeLivenessDetector("unused-model-path")
    d._landmarker = _FakeLandmarker(results)   # bypass real model load
    return d


_BASE = [(0.4, 0.4), (0.5, 0.5), (0.6, 0.6)]


def test_static_photo_rejected_by_motion():
    # 8 IDENTICAL frames = a still photo held to the camera → zero motion.
    results = [_result(_BASE) for _ in range(8)]
    r = asyncio.run(_detector_with(results).analyze([_jpeg()] * 8))
    assert r.is_live is False
    assert "motion" in r.checks.get("reason", "")


def test_live_face_with_blink_passes():
    # jittered landmarks (micro-motion) + one real blink frame, challenge=blink.
    results = []
    for i in range(8):
        pts = [(x + i * 0.01, y + i * 0.008) for x, y in _BASE]
        results.append(_result(pts, blink=0.8 if i == 4 else 0.05))
    r = asyncio.run(_detector_with(results).analyze([_jpeg()] * 8, challenge="blink"))
    assert r.is_live is True
    assert 0.0 < r.confidence <= 0.95
    assert r.checks["blink_detected"] is True


def test_challenge_not_performed_rejected():
    # live motion but NO blink, yet blink was the challenge → reject.
    results = [_result([(x + i * 0.01, y) for x, y in _BASE], blink=0.05) for i in range(8)]
    r = asyncio.run(_detector_with(results).analyze([_jpeg()] * 8, challenge="blink"))
    assert r.is_live is False
    assert "blink" in r.checks.get("reason", "")


def test_multiple_faces_rejected():
    results = [_result(_BASE, faces=2) for _ in range(8)]
    r = asyncio.run(_detector_with(results).analyze([_jpeg()] * 8))
    assert r.is_live is False
    assert "one face" in r.checks.get("reason", "")


def test_too_few_frames_rejected():
    r = asyncio.run(_detector_with([_result(_BASE)]).analyze([_jpeg()] * 3))
    assert r.is_live is False


def test_garbage_bytes_fail_closed():
    # unreadable frames → no face → reject, never crash.
    results = [_result(_BASE) for _ in range(8)]
    r = asyncio.run(_detector_with(results).analyze([b"not-an-image"] * 8))
    assert r.is_live is False
