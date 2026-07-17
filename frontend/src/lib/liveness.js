// liveness.js — Agent 11 client: camera burst capture + server liveness check.
//
// Flow: requestChallenge() -> the server picks a random action (blink / turn) and
// a single-use nonce -> captureFrames() records ~10 JPEG frames over ~2.5s while
// the citizen performs it -> checkLiveness() posts frames + nonce; the SERVER
// decides (client-side "is_live" would be trivially forged). On success the
// returned liveness_claim is embedded into the DLC payload before signing
// (see dlc.js generateCertificate).
//
// Privacy: frames go to our own server only, are analysed in RAM and never
// persisted (Agent 11 README §6). Nothing is stored on-device either.

async function request(path, opts = {}) {
  const res = await fetch(path, { credentials: 'same-origin', ...opts })
  let data = null
  try { data = await res.json() } catch { /* non-JSON */ }
  if (!res.ok) {
    const err = new Error(data?.detail || `Request failed (${res.status})`)
    err.status = res.status
    throw err
  }
  return data
}

// -> { challenge: "blink"|"turn_left"|"turn_right", nonce, expires_in }
// 501 => liveness not available in this deployment (caller may proceed without).
export function requestChallenge() {
  return request('/agents/biometric/challenge', { method: 'POST' })
}

// Hinglish instructions for each server-issued action.
export const CHALLENGE_TEXT = {
  blink: 'Palkein jhapkayein (blink) 👁️',
  turn_left: 'Sir dheere se BAAYIN (left) taraf ghumayein ⬅️',
  turn_right: 'Sir dheere se DAAYIN (right) taraf ghumayein ➡️',
}

export async function openCamera(videoEl) {
  const stream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
    audio: false,
  })
  videoEl.srcObject = stream
  await videoEl.play()
  return stream
}

export function closeCamera(stream) {
  try { stream?.getTracks().forEach(t => t.stop()) } catch { /* already stopped */ }
}

// Capture `count` JPEG frames off the live <video> over ~`durationMs`.
export async function captureFrames(videoEl, { count = 10, durationMs = 2500 } = {}) {
  const canvas = document.createElement('canvas')
  canvas.width = videoEl.videoWidth || 640
  canvas.height = videoEl.videoHeight || 480
  const ctx = canvas.getContext('2d')
  const frames = []
  const gap = durationMs / count
  for (let i = 0; i < count; i++) {
    ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height)
    const blob = await new Promise(r => canvas.toBlob(r, 'image/jpeg', 0.85))
    if (blob) frames.push(blob)
    if (i < count - 1) await new Promise(r => setTimeout(r, gap))
  }
  return frames
}

// -> { is_live, confidence, liveness_claim }
export function checkLiveness(frames, nonce) {
  const fd = new FormData()
  frames.forEach((blob, i) => fd.append('frames', blob, `frame${i}.jpg`))
  fd.append('nonce', nonce)
  return request('/agents/biometric/liveness', { method: 'POST', body: fd })
}
