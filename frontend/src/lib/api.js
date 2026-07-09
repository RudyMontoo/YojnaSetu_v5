// v5.0 backend client — Spring Boot gateway (/api/v2) + FastAPI agents.
// Auth is the httpOnly cookie pair set by the OTP flow; no token ever
// touches JS. Everything rides the Vite proxy (same origin).

async function request(path, { method = "GET", body, formData } = {}) {
  const opts = { method, credentials: "same-origin", headers: {} };
  if (formData) opts.body = formData;
  else if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
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
  sendOtp: (phone) => request("/api/v2/auth/otp/send", { method: "POST", body: { phone } }),
  verifyOtp: (phone, otp) => request("/api/v2/auth/otp/verify", { method: "POST", body: { phone, otp } }),
  logout: () => request("/api/v2/auth/logout", { method: "POST" }),
  giveConsent: () => request("/api/v2/consent", { method: "POST" }),
  getProfile: () => request("/api/v2/profile/me"),
  updateProfile: (updates) => request("/api/v2/profile/me", { method: "PATCH", body: updates }),
  deleteAccount: () => request("/api/v2/user/me", { method: "DELETE" }),
  listApplications: (status) => request(`/api/v2/applications${status ? `?status=${status}` : ""}`),
  createApplication: (schemeCode) => request("/api/v2/applications", { method: "POST", body: { schemeCode } }),
  updateApplication: (id, body) => request(`/api/v2/applications/${id}`, { method: "PATCH", body }),
  trending: (state) => request(`/api/v2/schemes/trending${state ? `?state=${state}` : ""}`),
  recentSchemes: () => request("/api/v2/schemes/recent"),
  listSchemes: ({ search, sector, page = 0, size = 24 } = {}) => {
    const params = new URLSearchParams({ page, size });
    if (search) params.set("search", search);
    if (sector) params.set("sector", sector);
    return request(`/api/v2/schemes?${params}`);
  },
};

export const ai = {
  chat: (message, sessionId) =>
    request("/orchestrator/chat", { method: "POST", body: { message, session_id: sessionId || null } }),
  financialPlan: () => request("/agents/financial-plan"),
  fileGrievance: (body) => request("/agents/grievance", { method: "POST", body }),
  // Agent 5 — grievance tracking loop
  listGrievances: () => request("/agents/grievances"),
  setCpgramsRef: (grievanceId, cpgramsRef) =>
    request(`/agents/grievance/${grievanceId}/cpgrams-ref`, { method: "POST", body: { cpgrams_ref: cpgramsRef } }),
  // Agent 6 — nudge preferences (WhatsApp)
  nudgeStatus: () => request("/agents/nudge/status"),
  setNudgeOptOut: (optedOut) => request("/agents/nudge/optout", { method: "POST", body: { opted_out: optedOut } }),
  // Agent 3 — read-only live portal reconnaissance
  portalRecon: (schemeCode) =>
    request("/agents/application/portal-recon", { method: "POST", body: { scheme_code: schemeCode } }),
  verifyPpo: (aadhaarFile, ppoFile) => {
    const fd = new FormData();
    fd.append("aadhaar_file", aadhaarFile);
    fd.append("ppo_file", ppoFile);
    return request("/agents/document/verify-ppo", { method: "POST", formData: fd });
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
