# Agent 11 — Biometric Assist (Face Liveness)

> **Status: NOT STARTED — handoff spec for the CV/ML engineer picking this up.**
> Everything the rest of Yojna Setu needs from this module is already defined
> as a code contract (`interface.py`) and a wired-but-disabled endpoint
> (`router_stub.py`). Your job is to fill in the model behind that contract.
> If you keep the interface, the rest of the platform plugs in with zero
> changes.

---

## 1. What this agent does (in one line)

Confirm that a **real, live human face** is in front of the camera during a
pensioner's annual proof-of-life — not a printed photo, a phone screen, a
video replay, or a mask.

## 2. Why it exists (the real-world problem)

Every pensioner in India must prove once a year they're still alive to keep
receiving their pension — the **Digital Life Certificate (DLC / Jeevan
Pramaan)**. Today that often means an elderly person physically travelling to
a bank or pension office for a fingerprint/iris scan. For a 75-year-old in a
village, that trip is the entire barrier.

Yojna Setu lets them do it from home on a phone camera. But "from home on a
camera" opens an obvious fraud: a family member holds up a **photo or video of
a deceased relative** to keep collecting the pension. **Agent 11 is the
anti-spoofing gate that stops exactly that** — it answers "is a genuine living
person here right now?"

## 3. How it fits the system (the integration contract — DO NOT change lightly)

Agent 11 pairs with **Agent 12 (Offline Survival Proof)**, which is already
built and verified (`ai_service/routers/dlc_router.py`, `frontend/src/lib/dlc.js`):

```
Agent 11 (liveness: "yes, a live person")  ──►  Agent 12 (RSA-sign + issue the certificate)
   "the PERSON is real"                          "the CERTIFICATE is real / unforged"
```

**The crucial design rule:** the liveness result must be **embedded inside the
DLC payload that Agent 12 signs**, so it's cryptographically bound to the
certificate and can't be swapped in later. Agent 12's signed payload today is:

```json
{ "citizenId": "...", "nonce": "...", "generatedAt": "2026-07-09T..." }
```

After Agent 11 lands, the frontend adds your result before signing:

```json
{
  "citizenId": "...", "nonce": "...", "generatedAt": "...",
  "liveness": {
    "verified": true,
    "confidence": 0.97,
    "model_version": "illuminet-mnv3-v1",
    "checked_at": "2026-07-09T..."
  }
}
```

`interface.py`'s `liveness_claim(result)` produces exactly that `liveness`
block. The server side (`dlc_router.py`'s `/verify`) can then optionally
**reject** a certificate whose `liveness.verified` isn't `true` — a one-line
policy check we'll add once your model is trusted. **Until then Agent 12 works
without liveness** (a deliberate staged rollout — see §7).

## 4. The interface you implement

See [`interface.py`](interface.py). You implement one class:

```python
class LivenessDetector(ABC):
    async def analyze(self, frames: list[bytes]) -> LivenessResult: ...
```

- **Input**: a short burst of camera frames (JPEG/PNG bytes) or a short video
  clip decoded to frames — the client captures ~1–2 seconds. Keep the
  captured window short; elderly users won't hold still long.
- **Output**: a `LivenessResult` (`is_live`, `confidence` 0.0–1.0,
  `model_version`, `checks` dict, `frames_analyzed`).
- Register your implementation in `get_detector()` — that's the single seam
  the endpoint calls.

Then flip the endpoint in [`router_stub.py`](router_stub.py) from its 501
stub to calling your detector, and mount it in `ai_service/main.py`.

## 5. Model options (this is the actual unknown — resolve FIRST)

The v5.0 doc names **IllumiNet / MobileNetV3**. **Whether trained weights
exist from the old "Jeevan-Setu" project is UNRESOLVED** — the Yojna Setu team
does not have them. Your first task is to answer this, because it decides
everything:

- **If trained weights exist** → wrap them behind `LivenessDetector`, done in
  days. Ask the team to hunt for a `.pt`/`.onnx`/`.tflite` file or the repo.
- **If they DON'T exist** → this becomes a real ML project: you need a
  **face anti-spoofing (FAS) / presentation-attack-detection (PAD)** model
  trained on a labelled dataset of genuine faces vs. print/replay/mask
  attacks. Reasonable starting points:
  - **Public datasets**: CASIA-FASD, Replay-Attack, MSU-MFSD, OULU-NPU,
    CelebA-Spoof (check licenses for a govt-adjacent use case).
  - **Pretrained baselines**: MiniFASNet (Silent-Face-Anti-Spoofing),
    DeepPixBiS, or a MobileNetV3 backbone fine-tuned for binary live/spoof.
  - **Lightweight active-liveness fallback** (no heavy model): challenge-
    response — "blink now", "turn head left" — via MediaPipe FaceMesh
    landmarks. Weaker against video replay but ships fast and runs on-device.
  Recommend the team a paid Aadhaar-style **Face RD** integration only if
  institutional access is available (it usually isn't for a solo/student
  team — same constraint as SPARSH/NPCI elsewhere in this project).

## 6. Non-negotiable rules (inherit Yojna Setu's security posture)

These mirror the platform's existing rules — a reviewer WILL check them:

1. **Biometric frames are NEVER persisted.** Process in-memory only; never
   write frames to disk, GCS, or Mongo. This matches CLAUDE.md's voice-audio
   rule ("processed in-memory, never written to disk — only the result") and
   DPDP Act 2023. Only the `LivenessResult` (a boolean + a float + a version
   string) may leave the function.
2. **No raw biometric template stored.** No face embeddings, no landmark
   vectors retained past the request. The certificate keeps `liveness.verified`
   + `confidence` only.
3. **Fail closed.** On any model error, low confidence, or ambiguous input,
   return `is_live=False` — never wave a certificate through on uncertainty.
   A false "live" is pension fraud; a false "not live" just asks the user to
   retry.
4. **Endpoint auth**: citizen JWT cookie (`get_current_citizen_id`), same as
   every other citizen-scoped route. The stub already wires this.
5. **Model provenance must be documented** — where weights came from, license,
   training data. No mystery binaries in a govt-facing product.

## 7. Staged rollout (why the rest of the app already works without you)

The pensioner vertical launches **after** the main Yojna Setu deployment, as a
feature update — so this module is on its own timeline and blocks nothing:

- **Phase A (today)**: Agent 12 issues certificates WITHOUT liveness. The
  `liveness` block is absent; the server doesn't require it.
- **Phase B (your work lands)**: frontend captures frames → calls your
  `/agents/biometric/liveness` → embeds the `liveness` block in the signed
  payload. Server still only *records* it.
- **Phase C (trusted)**: flip the one-line policy in `dlc_router.py`'s
  `/verify` to **reject** `liveness.verified != true`. Now liveness is
  mandatory. Do this only after real-world false-accept/false-reject testing.

## 8. Acceptance criteria (what "done" means)

- [ ] Model provenance question (§5) answered in writing.
- [ ] `LivenessDetector.analyze()` implemented; `get_detector()` returns it.
- [ ] `/agents/biometric/liveness` returns a real `LivenessResult` (no more 501).
- [ ] A **printed photo** and a **phone-screen video replay** of a face are
      both correctly rejected (`is_live=False`) — demonstrate with a recorded test.
- [ ] A genuine live face passes. Report false-accept & false-reject rates on a
      held-out set.
- [ ] No frame ever touches disk/Mongo/GCS (grep-checkable + a test).
- [ ] Runs within the agent's **20s** timeout budget (CLAUDE.md agent table);
      target well under that on a mid-range phone.
- [ ] `liveness_claim()` output validates against the DLC payload shape in §3.

## 9. Files in this folder

| File | Purpose |
|---|---|
| `README.md` | This spec — the handoff brief. |
| `interface.py` | The code contract: `LivenessResult`, `LivenessDetector` ABC, `get_detector()`, `liveness_claim()`. Implement against this. |
| `router_stub.py` | FastAPI endpoint, wired for auth, returns **501** until a detector exists. Flip it on when ready. |
| `requirements.txt` | Candidate CV/ML deps — **kept OUT of the main service** `requirements.txt` on purpose (heavy, and this module isn't deployed yet). |

## 10. Questions for the Yojna Setu team (Rudra)

- Do trained IllumiNet/MobileNetV3 liveness weights exist anywhere from
  Jeevan-Setu? (This unblocks everything — see §5.)
- Target devices? (Low-end Android is the realistic pensioner device — rules
  out anything that needs a GPU.)
- Is any Aadhaar Face RD / institutional biometric API access available, or is
  this fully self-hosted? (Decides §5's path.)
