// dlc.js — Agent 12 (Offline Survival Proof) client crypto.
//
// A pensioner's device generates an RSA-2048 keypair ONCE (WebCrypto), keeps
// the private key NON-EXTRACTABLE in IndexedDB (the closest a web PWA gets to
// a secure enclave), and registers the public key with the server while
// online. Then it can sign a "life certificate" fully offline — the signed
// proof is queued in IndexedDB and synced to the server when connectivity
// returns, or shown as a QR for someone with connectivity to submit.
//
// The private key never leaves the device. The server only ever sees the
// public key + signed proofs, and verifies each signature (see
// ai_service/routers/dlc_router.py).

import { ai } from './api'

const DB_NAME = 'yojna-dlc'
const DB_VERSION = 1
const KEY_STORE = 'keys'      // the device keypair (one record, id 'device')
const QUEUE_STORE = 'queue'   // proofs generated offline, awaiting server sync

// ── tiny IndexedDB promise wrapper ───────────────────────────────────────────
function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(KEY_STORE)) db.createObjectStore(KEY_STORE)
      if (!db.objectStoreNames.contains(QUEUE_STORE)) db.createObjectStore(QUEUE_STORE, { keyPath: 'nonce' })
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

function idb(store, mode, fn) {
  return openDb().then(db => new Promise((resolve, reject) => {
    const tx = db.transaction(store, mode)
    const result = fn(tx.objectStore(store))
    tx.oncomplete = () => resolve(result?._value !== undefined ? result._value : result)
    tx.onerror = () => reject(tx.error)
  }))
}

const reqValue = (request) => {
  const box = { _value: undefined }
  request.onsuccess = () => { box._value = request.result }
  return box
}

// ── device keypair ───────────────────────────────────────────────────────────
async function getStoredKeyPair() {
  return idb(KEY_STORE, 'readonly', s => reqValue(s.get('device')))
}

// A non-extractable CryptoKey pair is structured-cloneable → persists in
// IndexedDB directly; the raw private key bytes are never exposed to JS.
async function createKeyPair() {
  const keyPair = await crypto.subtle.generateKey(
    {
      name: 'RSASSA-PKCS1-v1_5',
      modulusLength: 2048,
      publicExponent: new Uint8Array([1, 0, 1]),
      hash: 'SHA-256',
    },
    false,               // private key NON-EXTRACTABLE (public stays exportable)
    ['sign', 'verify'],
  )
  const keyId = 'dev-' + crypto.randomUUID()
  await idb(KEY_STORE, 'readwrite', s => s.put({ keyPair, keyId, registered: false }, 'device'))
  return { keyPair, keyId, registered: false }
}

async function getOrCreateDevice() {
  return (await getStoredKeyPair()) || (await createKeyPair())
}

async function markRegistered() {
  const dev = await getStoredKeyPair()
  if (dev) await idb(KEY_STORE, 'readwrite', s => s.put({ ...dev, registered: true }, 'device'))
}

// Register the public key with the server (idempotent — safe to call again).
export async function registerDevice() {
  const dev = await getOrCreateDevice()
  const jwk = await crypto.subtle.exportKey('jwk', dev.keyPair.publicKey)
  // Trim to the fields the server's JWK importer wants.
  const pub = { kty: jwk.kty, n: jwk.n, e: jwk.e, alg: 'RS256', use: 'sig' }
  await ai.dlcRegisterKey(dev.keyId, pub)
  await markRegistered()
  return dev.keyId
}

// ── life certificate ─────────────────────────────────────────────────────────
function canonical(obj) {
  // Deterministic JSON (sorted keys, no spaces) so device and server sign/verify
  // over byte-identical strings.
  return JSON.stringify(obj, Object.keys(obj).sort())
}

// Sign a fresh life certificate. Works fully offline.
export async function generateCertificate(citizenId) {
  const dev = await getOrCreateDevice()
  const payloadObj = {
    citizenId,
    nonce: crypto.randomUUID(),
    generatedAt: new Date().toISOString(),
    type: 'liveness',
  }
  const payload = canonical(payloadObj)
  const sigBuf = await crypto.subtle.sign(
    'RSASSA-PKCS1-v1_5', dev.keyPair.privateKey, new TextEncoder().encode(payload),
  )
  const signature_b64 = btoa(String.fromCharCode(...new Uint8Array(sigBuf)))
  return { key_id: dev.keyId, payload, signature_b64, nonce: payloadObj.nonce }
}

async function queueProof(proof) {
  await idb(QUEUE_STORE, 'readwrite', s => s.put(proof))
}

export async function getQueueCount() {
  return idb(QUEUE_STORE, 'readonly', s => reqValue(s.count()))
}

// Submit a proof to the server; on any failure (offline, network) queue it.
export async function submitOrQueue(proof) {
  try {
    const res = await ai.dlcVerify(proof)
    await idb(QUEUE_STORE, 'readwrite', s => s.delete(proof.nonce)) // in case it was queued
    return { synced: true, result: res }
  } catch (err) {
    await queueProof(proof)
    return { synced: false, error: err }
  }
}

// Drain the offline queue — call on reconnect. A 409 (already submitted) or a
// terminal client error also clears the item so it doesn't wedge the queue.
export async function syncQueued() {
  const items = await idb(QUEUE_STORE, 'readonly', s => reqValue(s.getAll()))
  let synced = 0
  for (const proof of (items || [])) {
    try {
      await ai.dlcVerify(proof)
      await idb(QUEUE_STORE, 'readwrite', s => s.delete(proof.nonce))
      synced++
    } catch (err) {
      if (err.status === 409 || err.status === 403 || err.status === 400) {
        // Already recorded, or permanently invalid — drop it, don't retry forever.
        await idb(QUEUE_STORE, 'readwrite', s => s.delete(proof.nonce))
      }
      // 401/network/5xx: leave queued for the next reconnect.
    }
  }
  return synced
}

// Render a signed proof as a QR data-URL (lazy-loads the QR lib). The QR
// carries the full {key_id, payload, signature_b64} so a device with
// connectivity can scan and POST it to /agents/dlc/verify.
export async function proofToQrDataUrl(proof) {
  const QRCode = (await import('qrcode')).default
  return QRCode.toDataURL(JSON.stringify(proof), { errorCorrectionLevel: 'M', margin: 2, width: 240 })
}
