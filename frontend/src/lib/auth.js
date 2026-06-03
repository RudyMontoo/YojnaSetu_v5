// ── Local Session Helpers ──────────────────────────────────────────────────
// Used by ProfilePage, OnboardingPage etc. for quick access to cached user info.
// Supabase is the source of truth — this is just a local cache.

export function getLocalUser() {
    try { return JSON.parse(localStorage.getItem('yojna_user') || 'null') } catch { return null }
}

export function setLocalUser(user) {
    localStorage.setItem('yojna_user', JSON.stringify(user))
}

export function clearLocalUser() {
    localStorage.removeItem('yojna_user')
    localStorage.removeItem('yojna_token')
    localStorage.removeItem('yojna_profile')
}
