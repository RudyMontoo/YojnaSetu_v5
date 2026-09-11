// v5.0 backend client — Spring Boot gateway (/api/v2) + FastAPI agents.
// Auth is the httpOnly cookie pair set by the OTP flow; no token ever
// touches JS. Everything rides the Vite proxy (same origin).

// timeoutMs: abort a hung request so the UI never spins forever. Default 45s
// (above the orchestrator's 30s agent budget); heavy calls like OCR can pass more.
async function request(path, { method = "GET", body, formData, timeoutMs = 45000 } = {}) {
  const opts = { method, credentials: "same-origin", headers: {} };
  if (formData) opts.body = formData;
  else if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }

  const controller = new AbortController();
  opts.signal = controller.signal;
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let res;
  try {
    res = await fetch(path, opts);
  } catch (e) {
    // Distinguish "we gave up waiting" from "network is down" — both otherwise
    // surface as an opaque "Failed to fetch" that tells the user nothing.
    const friendly = e.name === "AbortError"
      ? "The server took too long to respond. Please try again."
      : "Can't reach the server. Check your connection and try again.";
    const err = new Error(friendly);
    err.status = e.name === "AbortError" ? 408 : 0;
    throw err;
  } finally {
    clearTimeout(timer);
  }

  let data = null;
  try { data = await res.json(); } catch { /* non-JSON */ }
  if (!res.ok) {
    const msg = data?.error || data?.detail || `Request failed (${res.status})`;
    const err = new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
    err.status = res.status;
    throw err;
  }
  return data;
}

export const gateway = {
  // identifier is { phone } or { email } — the backend accepts either channel.
  sendOtp: (identifier) => request("/api/v2/auth/otp/send", { method: "POST", body: identifier }),
  verifyOtp: (identifier, otp) => request("/api/v2/auth/otp/verify", { method: "POST", body: { ...identifier, otp } }),
  // Firebase phone login: send the Firebase ID token; backend verifies + issues our cookie.
  verifyPhone: (idToken) => request("/api/v2/auth/phone/verify", { method: "POST", body: { idToken } }),
  logout: () => request("/api/v2/auth/logout", { method: "POST" }),
  giveConsent: () => request("/api/v2/consent", { method: "POST" }),
  getProfile: () => request("/api/v2/profile/me"),
  updateProfile: (updates) => request("/api/v2/profile/me", { method: "PATCH", body: updates }),
  uploadProfilePhoto: (file) => {
    const fd = new FormData();
    fd.append("photo", file);
    return request("/api/v2/profile/me/photo", { method: "POST", formData: fd });
  },
  deleteProfilePhoto: () => request("/api/v2/profile/me/photo", { method: "DELETE" }),
  // Real bank-branch lookup (OpenStreetMap, proxied server-side — no CORS from browser)
  creditPartnersNearby: (lat, lng, radiusKm = 15) =>
    request(`/api/v2/credit-partners/nearby?lat=${lat}&lng=${lng}&radiusKm=${radiusKm}`),
  deleteAccount: () => request("/api/v2/user/me", { method: "DELETE" }),
  // Offline-help callback queue
  requestHelp: (payload) => request("/api/v2/help/request", { method: "POST", body: payload }),
  myHelpRequests: () => request("/api/v2/help/my-requests"),
  helpQueue: () => request("/api/v2/help/requests"),                                  // operator only
  claimHelp: (id) => request(`/api/v2/help/requests/${id}/claim`, { method: "POST" }), // operator only
  resolveHelp: (id) => request(`/api/v2/help/requests/${id}/resolve`, { method: "POST" }), // operator only
  // Become-a-helper onboarding
  applyHelper: (payload) => request("/api/v2/helper/apply", { method: "POST", body: payload }),
  myHelperApplication: () => request("/api/v2/helper/my-application"),
  helperApplications: () => request("/api/v2/helper/applications"),                             // admin only
  approveHelper: (id) => request(`/api/v2/helper/applications/${id}/approve`, { method: "POST" }), // admin only
  rejectHelper: (id) => request(`/api/v2/helper/applications/${id}/reject`, { method: "POST" }),   // admin only
  // Helper PORTAL auth (separate ID+password identity)
  helperLogin: (helperId, password) => request("/api/v2/helper-portal/login", { method: "POST", body: { helperId, password } }),
  helperMe: () => request("/api/v2/helper-portal/me"),
  helperChangePassword: (currentPassword, newPassword) => request("/api/v2/helper-portal/change-password", { method: "POST", body: { currentPassword, newPassword } }),
  helperLogout: () => request("/api/v2/helper-portal/logout", { method: "POST" }),
  // Registered kendras (Option B)
  kendrasNearby: (lat, lng) => request(`/api/v2/kendras/nearby?lat=${lat}&lng=${lng}`),
  registerKendra: (payload) => request("/api/v2/kendras", { method: "POST", body: payload }), // helper only
  myKendras: () => request("/api/v2/kendras/mine"),                                            // helper only
  deactivateKendra: (id) => request(`/api/v2/kendras/${id}/deactivate`, { method: "POST" }),   // helper only (own)
  // Admin: manage helpers + stats
  adminStats: () => request("/api/v2/helper/stats"),                                            // admin only
  adminHelpers: () => request("/api/v2/helper/helpers"),                                        // admin only
  deactivateHelper: (id) => request(`/api/v2/helper/helpers/${id}/deactivate`, { method: "POST" }),
  activateHelper: (id) => request(`/api/v2/helper/helpers/${id}/activate`, { method: "POST" }),
  resetHelperPassword: (id) => request(`/api/v2/helper/helpers/${id}/reset-password`, { method: "POST" }),
  // Helper workspace
  myHandled: () => request("/api/v2/help/my-handled"),                                          // helper only
  setAvailability: (available) => request("/api/v2/helper-portal/availability", { method: "POST", body: { available } }),
  // Admin oversight
  adminKendras: () => request("/api/v2/kendras/all"),                                            // admin only
  adminAllRequests: () => request("/api/v2/help/all"),                                           // admin only
  reopenRequest: (id) => request(`/api/v2/help/requests/${id}/reopen`, { method: "POST" }),      // admin only
  // Application Tracker — a REAL tracked application lifecycle (in_progress → submitted → approved/rejected/disbursed).
  // Never a bookmark; see savedSchemes below for that.
  listApplications: (status) => request(`/api/v2/applications${status ? `?status=${status}` : ""}`),
  createApplication: (schemeCode) => request("/api/v2/applications", { method: "POST", body: { schemeCode } }),
  updateApplication: (id, body) => request(`/api/v2/applications/${id}`, { method: "PATCH", body }),
  // Saved Schemes — a pure bookmark list, no lifecycle status. Separate collection from Applications above.
  listSavedSchemes: () => request("/api/v2/saved-schemes"),
  saveScheme: (schemeCode) => request("/api/v2/saved-schemes", { method: "POST", body: { schemeCode } }),
  unsaveScheme: (schemeCode) => request(`/api/v2/saved-schemes/${schemeCode}`, { method: "DELETE" }),
  trending: (state) => request(`/api/v2/schemes/trending${state ? `?state=${state}` : ""}`),
  recentSchemes: () => request("/api/v2/schemes/recent"),
  listSchemes: ({ search, sector, page = 0, size = 24 } = {}) => {
    const params = new URLSearchParams({ page, size });
    if (search) params.set("search", search);
    if (sector) params.set("sector", sector);
    return request(`/api/v2/schemes?${params}`);
  },
  // One scheme's full public record, by the schemeCode listSchemes returns.
  // Lets a detail page be opened directly (shared link, bookmark, refresh)
  // instead of only working when the record was carried in router state.
  schemeDetail: (schemeCode) => request(`/api/v2/schemes/${encodeURIComponent(schemeCode)}`),

  // ── SIH PS 26092 — SC concessional credit ────────────────────────────────
  // All three are public (SecurityConfig permits /api/v2/sih/credit/**) and
  // stateless: a guest can learn what they qualify for and what it costs
  // before creating an account. THIS is the source of truth for scheme
  // figures — never lib/nsfdcSchemes.js, whose hardcoded caps quoted the
  // project-cost ceiling as the loan cap (overstating Micro Finance by
  // ₹15,000 and Term Loan by ₹5 lakh, and hiding 3 of the 6 real schemes).
  creditProducts: () => request("/api/v2/sih/credit/products"),
  // body: { need: "business"|"education", estimatedCost, annualIncome,
  //         category, gender, moratoriumMode }. Every field is nullable —
  // the response's `insufficient_data` verdict names what's still missing
  // rather than guessing, so send whatever the citizen has given so far.
  checkEligibility: (body) => request("/api/v2/sih/credit/eligibility", { method: "POST", body }),
  emiQuote: (body) => request("/api/v2/sih/credit/emi", { method: "POST", body }),
};

export const ai = {
  chat: (message, sessionId) =>
    request("/orchestrator/chat", { method: "POST", body: { message, session_id: sessionId || null } }),
  // SC credit application assistant — separate goal-directed slot-filling flow,
  // not a single orchestrator turn. Called every turn once ChatPage sees the
  // orchestrator return intent === 'credit_application' for this session; see
  // ai_service/routers/application_assistant_router.py.
  applyChat: (message, sessionId, language) =>
    request("/application-assistant/chat", { method: "POST", body: { message, session_id: sessionId, language } }),
  financialPlan: () => request("/agents/financial-plan"),
  fileGrievance: (body) => request("/agents/grievance", { method: "POST", body }),
  // Agent 5 — grievance tracking loop
  listGrievances: () => request("/agents/grievances"),
  setCpgramsRef: (grievanceId, cpgramsRef) =>
    request(`/agents/grievance/${grievanceId}/cpgrams-ref`, { method: "POST", body: { cpgrams_ref: cpgramsRef } }),
  // Agent 6 — nudge preferences (WhatsApp)
  nudgeStatus: () => request("/agents/nudge/status"),
  setNudgeOptOut: (optedOut) => request("/agents/nudge/optout", { method: "POST", body: { opted_out: optedOut } }),
  // Agent 3 — read-only live portal reconnaissance (opens a live gov portal — slow)
  portalRecon: (schemeCode) =>
    request("/agents/application/portal-recon", { method: "POST", body: { scheme_code: schemeCode }, timeoutMs: 90000 }),
  // Agent 4 — scan one doc: verify validity + match against profile, get read-back fields
  // (image upload + OCR/Gemini vision — give it 90s before we give up)
  verifyDocument: (file) => {
    const fd = new FormData()
    fd.append("file", file)
    return request("/agents/document/verify", { method: "POST", formData: fd, timeoutMs: 90000 })
  },
  verifyPpo: (aadhaarFile, ppoFile) => {
    const fd = new FormData();
    fd.append("aadhaar_file", aadhaarFile);
    fd.append("ppo_file", ppoFile);
    return request("/agents/document/verify-ppo", { method: "POST", formData: fd, timeoutMs: 90000 });
  },
  cscAlternatives: (schemeCode, missingDocType) =>
    request("/agents/csc/alternatives", {
      method: "POST",
      body: { scheme_code: schemeCode, missing_doc_type: missingDocType },
    }),
  translate: (texts, targetLang) =>
    request("/translate", { method: "POST", body: { texts, target_lang: targetLang } }),
  // Agent 12 — Offline Survival Proof (Digital Life Certificate)
  dlcRegisterKey: (keyId, publicKeyJwk) =>
    request("/agents/dlc/register-key", { method: "POST", body: { key_id: keyId, public_key_jwk: publicKeyJwk } }),
  dlcVerify: (proof) => request("/agents/dlc/verify", { method: "POST", body: proof }),
  dlcStatus: () => request("/agents/dlc/status"),
};
