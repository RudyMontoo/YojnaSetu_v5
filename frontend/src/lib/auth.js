// ── Local Session Helpers ──────────────────────────────────────────────────
// Used by ProfilePage etc. for quick access to cached user info.
// Supabase is the source of truth — this is just a local cache.

export function getLocalUser() {
    try { return JSON.parse(localStorage.getItem('yojna_user') || 'null') } catch { return null }
}

/**
 * True when nobody is signed in — i.e. an action that needs an identity
 * (apply, save, track, download) should show the login prompt first.
 *
 * Browsing, eligibility and the EMI calculator deliberately never call this:
 * they work for everyone.
 */
export function isGuest() {
    return !getLocalUser()
}

export function setLocalUser(user) {
    localStorage.setItem('yojna_user', JSON.stringify(user))
}

export function clearLocalUser() {
    localStorage.removeItem('yojna_user')
    localStorage.removeItem('yojna_token')
    localStorage.removeItem('yojna_profile')
}
