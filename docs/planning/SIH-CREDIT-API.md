# SIH Credit Module — API Contract

For Charan & Ayush. Every shape below was captured from the real serializer, not written from memory.

**Base:** `/api/v2/sih/credit` · **Auth:** none — public by design, same as the existing partner locator. A citizen must be able to learn what they qualify for and what it costs before creating an account. These endpoints read no profile and persist nothing.

**Backend source:** [`deploy/backend/spring-gateway/src/main/java/com/yojnasetu/gateway/credit/`](../../deploy/backend/spring-gateway/src/main/java/com/yojnasetu/gateway/credit/)

---

## `GET /products`

The scheme catalogue. **Replaces the hardcoded `NSFDC_SCHEMES` array in `frontend/src/lib/nsfdcSchemes.js`** — fetch this instead, so a rate correction doesn't need a frontend deploy.

```json
[{
  "id": "micro-finance",
  "code": "MFS",
  "name": "Micro Finance Scheme (MFS)",
  "type": "micro",
  "projectType": "small",
  "unitCostFloor": null,
  "unitCostCeiling": 140000,
  "maxLoanAmount": 125000,
  "interestRate": 6.5,
  "moratoriumMonths": 3,
  "maxTenureMonths": 36,
  "coveragePct": 90,
  "maxAnnualIncome": 500000,
  "categories": ["sc"],
  "womenOnly": false,
  "description": "For small income-generating activities — petty trade, tea shops, candle or papad making, goat rearing, beauty parlours and similar.",
  "sourceNote": "Figures from NSFDC's official scheme listing …",
  "sourceUrl": "https://nsfdc.nic.in/scheme",
  "figuresVerified": true,
  "active": true
}]
```

### `unitCostCeiling` ≠ `maxLoanAmount` — do not conflate them

These are **different numbers in every NSFDC scheme** and treating one as the other is a real bug we already shipped once:

| Scheme | Unit cost band | Max loan |
|---|---|---|
| Micro Finance (MFS) | up to ₹1.40 L | **₹1.25 L** |
| Term Loan (TL) | ₹1.40 L – ₹50 L | **₹45 L** |
| Udyam Nidhi (UNY) | up to ₹5 L | **₹4.50 L** |
| Aajeevika (AMFY) | up to ₹1.40 L | **₹1.25 L** |
| Mahila Samriddhi (MSY) | up to ₹1.40 L | **₹1.25 L** |
| Educational (ELS) | *no ceiling* | **₹40 L** |

`unitCostCeiling` gates **which scheme a project belongs to**. `maxLoanAmount` caps **the loan** after `coveragePct`. A ₹1.40 L project under MFS gets a ₹1.25 L loan, not ₹1.26 L — so margin money is ₹15,000, not ₹14,000.

`null` on either field means unbounded.

### Provenance

`figuresVerified: false` means the numbers came from a secondary source rather than NSFDC's own page. Right now that's **Mahila Samriddhi only** — NSFDC doesn't publish its beneficiary rate, so the 4% and the 3-month moratorium come from State Channelising Agency listings. Show `sourceNote` on any product where this is false. Don't hide the scheme; don't present it as settled either.

### `womenOnly`

NSFDC delivers the women's concession as **separate schemes**, not a discount on a general one. Mahila Samriddhi lends the same ₹1.25 L at **4%** where Micro Finance charges **6.5%**. Surface it prominently for women applicants — the engine already ranks it first for them.

---

## `POST /eligibility`

The guided flow's verdict.

**Request** — every field except `need` may be omitted; omission is an *unanswered question*, not a zero.

```json
{
  "need": "business",
  "estimatedCost": 100000,
  "annualIncome": 300000,
  "category": "sc",
  "gender": "female",
  "moratoriumMode": "capitalise"
}
```

| Field | Values |
|---|---|
| `need` | `business` \| `education` — **required** |
| `estimatedCost` | rupees, project or course cost |
| `annualIncome` | rupees, annual family income |
| `category` | e.g. `sc` (case-insensitive) |
| `gender` | `female` \| `male` \| `other` |
| `moratoriumMode` | `capitalise` (default) \| `service-interest` |

**Ask for `gender` in the guided flow.** Without it the engine cannot tell whether a woman is being shown the 4% women's scheme or the 6.5% general one, so it returns `insufficient_data` with `gender` in `missingProfileData` rather than guessing.

**Response** (trimmed schedule):

```json
{
  "verdict": "eligible",
  "recommendations": [{
    "productId": "micro-finance",
    "code": "MFS",
    "name": "Micro Finance Scheme (MFS)",
    "type": "micro",
    "minLoanAmount": 5000,
    "maxLoanAmount": 140000,
    "interestRate": 6.5,
    "moratoriumMonths": 3,
    "maxTenureMonths": 36,
    "coveragePct": 90,
    "description": "...",
    "sourceNote": "...",
    "eligible": true,
    "matched": [
      "category 'sc' is eligible for this scheme",
      "annual family income ₹3,00,000 is within the ₹5,00,000 limit",
      "project cost ₹1,00,000 is fundable — this scheme covers 90%, so it can lend ₹90,000"
    ],
    "failed": [],
    "missingProfileData": [],
    "eligibleLoanAmount": 90000,
    "marginMoney": 10000,
    "costExceedsCap": false,
    "indicativeEmi": { /* EmiPlan — see below */ }
  }],
  "missingProfileData": [],
  "note": "Eligibility here is indicative. The Channel Partner branch makes the final decision..."
}
```

### The three verdicts

| `verdict` | Meaning | What the UI should do |
|---|---|---|
| `eligible` | At least one product matched | Show recommendations, lead with the first |
| `insufficient_data` | Nothing failed, but a needed answer is missing | **Ask for exactly the fields in `missingProfileData`.** Do not show a rejection |
| `not_eligible` | A real criterion failed | Show `failed[]` verbatim as the reason |

`insufficient_data` is the one to get right. "You haven't told us your income" is not "you don't qualify", and rendering it as a rejection turns an answerable question into a dead end.

**`missingProfileData` can be non-empty even when `verdict` is `eligible`** — and you should still ask. It's collected across *every* scheme assessed, not just the three returned, so it surfaces questions that could unlock a better product than the one shown. The classic case: a woman who hasn't stated her gender is quoted Micro Finance at 6.5% while Mahila Samriddhi would lend her the same amount at 4%. When this happens, `note` says so explicitly. Drive the next step of the multi-step form straight off this list.

**Ordering is by what the loan actually costs**, not the headline rate: eligible first, then least margin money, then lowest total repayment. Two schemes can quote the same rate and differ by tens of thousands once tenure and moratorium differ — Udyam Nidhi and Aajeevika are both 15%, but on a ₹90,000 loan Udyam Nidhi costs ₹16,764 more. Render in the order given.

### Fields worth building UI for

- **`marginMoney`** — the citizen's own contribution (`estimatedCost − eligibleLoanAmount`). Display it prominently. A ₹1,00,000 project yields a ₹90,000 loan and a ₹10,000 gap they must fund themselves; not showing this is why applications stall at the branch.
- **`costExceedsCap`** — `true` means the project is too big for this scheme, so the shortfall is *not* margin money. Word it differently: "this scheme can't fund a project this size", not "you need to contribute ₹X".
- **`matched` / `failed`** — pre-formatted, Indian-grouped, meant to be read aloud. Render as-is; they go through `useAutoTranslate` like any other dynamic string.
- **`indicativeEmi`** — quoted at the product's **maximum** tenure. It's a starting point, not the citizen's chosen plan — send them to the calculator to adjust.

`indicativeEmi` is `null` when `estimatedCost` wasn't supplied. Guard for it.

---

## `POST /emi`

Authoritative repayment quote. Keep computing client-side for slider responsiveness — but quote from here for anything the citizen is asked to act on.

```json
{ "principal": 90000, "annualRatePct": 6.5, "tenureMonths": 36,
  "moratoriumMonths": 3, "moratoriumMode": "capitalise" }
```

**Response — `EmiPlan`:**

```json
{
  "emi": 2803.4776615469586,
  "totalPayment": 100925.19581569052,
  "totalInterest": 10925.195815690517,
  "moratoriumInterest": 1470.436178385411,
  "moratoriumPayment": 0.0,
  "financedPrincipal": 91470.43617838541,
  "moratoriumMonths": 3,
  "moratoriumMode": "capitalise",
  "schedule": [
    { "month": 1, "phase": "moratorium", "emi": 0.0, "principalComponent": 0.0,
      "interestComponent": 487.5, "balance": 90487.5 },
    { "month": 4, "phase": "repayment", "emi": 2803.4776615469586,
      "principalComponent": 2308.012798914038, "interestComponent": 495.4648626329209,
      "balance": 89162.42337947138 }
  ]
}
```

Values are unrounded — round at render with `formatInr`.

- `schedule` spans the **whole loan life**: months `1..m` are `moratorium`, `m+1..m+n` are `repayment`. Month 1 is not the first instalment.
- `phase` and `moratoriumMode` use the exact string constants already exported from `frontend/src/lib/emiCalculator.js`, so a row from this API drops into the existing table component unmodified. There are tests pinning both.
- `totalInterest` is the full cost of credit against the **disbursed** amount, moratorium included — comparable across schemes and across modes.
- `financedPrincipal` is what the EMI is computed on: the inflated balance under `capitalise`, the original amount under `service-interest`.

**Validation** — 400 with `{"error": "..."}`: `principal` 1…100,000,000 · `annualRatePct` 0…100 · `tenureMonths` 1…480 · `moratoriumMonths` 0…120. An unknown `moratoriumMode` is rejected rather than defaulted, since silently quoting the wrong treatment is the bug class this module exists to prevent.

---

---

# Applications — `/api/v2/sih/applications`

**Auth required.** The owner is always taken from the JWT, never from the body — an application can only be created for, or read by, the caller.

## Lifecycle

```
draft ──▶ submitted ──▶ under_verification ──▶ forwarded ──▶ sanctioned ──▶ disbursed
                 │             │    ▲                 │            │
                 │             ▼    │                 │            │
                 │        missing_docs               │            │
                 │             │                      │            │
                 └─────────────┴──────────────────────┴────────────┴──▶ rejected
```

`rejected` and `disbursed` are terminal. Anything not drawn is refused with **409** and a message naming what *is* allowed — `disbursed → draft` is rejected, not silently accepted.

A citizen may hold **one live application per scheme**. Terminal ones don't block, so a rejected applicant who fixes their documents can apply again.

| Method | Path | Notes |
|---|---|---|
| `GET` | `/` | Their applications, newest first |
| `GET` | `/{id}` | 404 if it isn't theirs — deliberately indistinguishable from a genuine miss |
| `POST` | `/` | Creates a `draft` → **201** |
| `POST` | `/{id}/partner` | Choose/change the branch. **Draft only** |
| `POST` | `/{id}/submit` | `draft → submitted`. **Requires a branch** |
| `POST` | `/{id}/documents-supplied` | `missing_docs → under_verification` |

### Choosing a branch — `POST /{id}/partner`

```json
{ "partnerId": "osm-123", "partnerName": "Bank of Baroda, Connaught Place", "partnerType": "PSB" }
```

Feed these straight from the locator result. **There is no auto-assignment** — NSFDC's partner roster isn't publicly obtainable, so picking a branch on the citizen's behalf would mean inventing one that has no idea the application exists.

Three rules, all verified against the running app:

- **Submitting without a branch is a 400.** An unassigned application lands in nobody's queue and would sit at `submitted` forever looking like progress.
- **A provably wrong channel is a 400**, naming the right ones: *"Micro Finance Scheme (MFS) is not offered by a Micro-finance institution. It is delivered through: State Channelising Agency, Public Sector Bank, …"*. This matters because the branch determines the rate — 6.5% via an SCA, 15% via an NBFC-MFI.
- **An undetermined type (`Unclassified` or omitted) is allowed.** "We can't tell what this branch is" is not grounds to block someone from applying. Only a provable mismatch is refused.

Changing branch after submission is a **409** — a rep may already be working the file.

**`POST /` request:**

```json
{
  "productId": "micro-finance",
  "estimatedCost": 100000,
  "annualIncome": 300000,
  "category": "sc",
  "tenureMonths": 36,
  "moratoriumMode": "capitalise",
  "verificationMode": "manual",
  "partnerId": "partner-7",
  "partnerName": "SBI Kanpur Nagar"
}
```

Only `productId` and `estimatedCost` are required. `tenureMonths` defaults to the product maximum, `moratoriumMode` to `capitalise`, `verificationMode` to `manual`.

`verificationMode` accepts `manual` and `offline`. `digilocker` and `account_aggregator` exist in the enum but return **400** — the integrations aren't built, and recording a verification that never happened would be worse than refusing.

**Response — `CreditApplication`:**

```json
{
  "id": "...", "userId": "...",
  "productId": "micro-finance", "productCode": "MFS", "productName": "Micro Finance Scheme (MFS)",
  "estimatedCost": 100000, "requestedAmount": 90000, "marginMoney": 10000,
  "declaredAnnualIncome": 300000, "declaredCategory": "sc",
  "quotedTerms": {
    "interestRate": 6.5, "tenureMonths": 36, "moratoriumMonths": 3,
    "moratoriumMode": "capitalise",
    "emi": 2803.47, "totalInterest": 10925.19, "totalPayment": 100925.19
  },
  "status": "draft",
  "statusHistory": [
    { "status": "draft", "at": "...", "byUserId": "...", "byRole": "CITIZEN",
      "reasonCode": null, "note": null, "requestedDocuments": null }
  ],
  "assignedPartnerId": "partner-7", "assignedPartnerName": "SBI Kanpur Nagar",
  "missingDocuments": [],
  "verificationMode": "manual",
  "createdAt": "...", "updatedAt": "...", "submittedAt": null
}
```

`quotedTerms` is a **snapshot taken at creation**, not recomputed on read. If a rate in `credit_products` is corrected next week, this citizen's file still shows what they were actually told.

`statusHistory` is append-only — render it directly as the status timeline.

---

# Branch rep — `/api/v2/branch/applications`

**Requires `ROLE_BRANCH_REP` or `ROLE_ADMIN`**, enforced by a path matcher in `SecurityConfig`. A rep only ever sees files assigned to their own partner.

**`partnerId` is not a request parameter you control for a rep — do not send it, and do not let the UI imply it's a choice.** It used to be caller-supplied (`?partnerId=`), which meant any logged-in rep could read, and act on, another partner's queue simply by naming its id — a real IDOR, fixed this session. The scope is now resolved server-side from the rep's own account (`BranchRep.partnerId`). `partnerId` is still accepted on the wire, but for a rep it is **silently ignored**, not validated against — the response is always their own branch's data regardless of what's sent. Only `ROLE_ADMIN` may still supply `partnerId` explicitly, for cross-partner oversight.

| Method | Path | Notes |
|---|---|---|
| `GET` | `/?status=…` | Queue, newest submission first. `status` optional. Scope is always the caller's own branch |
| `GET` | `/{id}` | 404 if assigned elsewhere |
| `POST` | `/{id}/status` | Record a decision. **`BANK_BRANCH` reps only** — see below |
| `GET` | `/reason-codes` | The vocabulary — build the dropdown from this, don't hardcode it |

An account with no `partnerId` at all (shouldn't normally happen for a `BANK_BRANCH` rep, but is exactly the normal state for an assist-only helper's account) gets **403** on `GET /` / `GET /{id}` with a message saying the account isn't attached to a lending branch — not an empty list, which would look like "no applications" rather than "wrong kind of account for this screen".

**`POST /{id}/status`:**

```json
{
  "status": "missing_docs",
  "reasonCode": "documents_incomplete",
  "note": "Income certificate is from 2019",
  "requestedDocuments": ["Caste certificate", "Income proof (current year)"]
}
```

Three rules the API enforces so the citizen's screen is never a dead end:

- **Only a `BANK_BRANCH` rep may call this at all.** A CSC operator, NGO/SHG worker, or field agent gets **403** with a message naming their role — assist-only helpers can help assemble a file and upload documents, never decide one. See "Assisted access" below for why.
- `status: "rejected"` **requires** `reasonCode` → 400 without it. "Rejected, reason blank" is not producible.
- `status: "missing_docs"` **requires** a non-empty `requestedDocuments` → 400 without it. The list lands on the application's `missingDocuments` and clears automatically when verification resumes.

`reasonCode` values: `income_above_ceiling`, `category_not_eligible`, `documents_incomplete`, `documents_illegible`, `documents_mismatch`, `project_not_viable`, `existing_loan_default`, `duplicate_application`, `partner_funds_exhausted`, `applicant_withdrew`, `other`.

**Errors:** 400 malformed or missing a required reason · 403 an assist-only helper attempted a decision, or the account has no branch scope at all · 404 not found / not this partner's · 409 illegal transition, message names the legal moves.

---

# Partner locator — `/api/v2/credit-partners/nearby`

Public. Returns **real** bank branches from OpenStreetMap.

Takes **either** live coordinates **or** a PIN code, plus an optional `schemeId`:

```
GET /nearby?lat=28.6294&lng=77.2189&radiusKm=5
GET /nearby?pincode=110001&radiusKm=5
GET /nearby?pincode=110001&schemeId=micro-finance
```

Coordinates win if both are given (more precise than a PIN code centroid). `radiusKm` defaults to 15, capped at 25.

**Why the pincode path exists (C5):** geolocation was the only way in, so a denied browser permission — or a desktop without GPS, which is what a CSC operator sits at — killed the feature outright. Offer the PIN code field as soon as `navigator.geolocation` errors, not as a hidden fallback.

```json
{
  "partners": [
    { "name": "Bank of Baroda", "type": "PSB", "lat": 28.6289, "lng": 77.2174, "distanceKm": 0.2 }
  ],
  "locationLabel": "New Delhi, Delhi",
  "note": "Real bank locations from OpenStreetMap. \"Unclassified\" entries are not confirmed NSFDC Channel Partners…"
}
```

`type` is `PSB`, `RRB` or `Unclassified`. **`Unclassified` does not mean "not a partner"** — it means we can't tell from the name. Never render it as a negative. Show `note` verbatim; it is the honesty boundary on data we don't have.

### `schemeId` — why this matters more than it looks

NSFDC funds a scheme at one rate to the channel partner, and **the partner sets its own rate to the citizen**. The same micro-finance money is **6.5% through a State Channelising Agency and 15% through an NBFC-MFI**. Walking into the wrong branch more than doubles the interest on an identical loan, so pass `schemeId` whenever the citizen has picked a scheme.

Extra response fields when `schemeId` is supplied:

```json
{
  "schemeId": "micro-finance",
  "schemeName": "Micro Finance Scheme (MFS)",
  "schemeChannels": ["SCA", "PSB", "RRB", "COOPERATIVE"],
  "channelsNotOnMap": ["State Channelising Agency", "Co-operative bank or society"],
  "schemeNote": "Micro Finance Scheme (MFS) is also delivered through … which usually lends at the scheme's lowest rate."
}
```

Each partner gains **`deliversScheme`**, which is three-state and must be rendered as three states:

| Value | Meaning | Render as |
|---|---|---|
| `true` | This type is a confirmed channel for the scheme | ✅ can process this loan |
| `false` | It provably is not (e.g. a PSB for an MFI-only scheme) | ❌ not for this scheme |
| `null` | Branch type couldn't be determined | *say nothing* — not a negative |

Results are ordered confirmed → unknown → provably-not, then by distance. A nearer branch that can't deliver the loan isn't more useful than a further one that can. **Render in the order given.**

**`channelsNotOnMap` is not a footnote.** A State Channelising Agency is a government corporation, not a tagged bank branch, so it can never appear in these results — and it's usually the cheapest route. Without surfacing `schemeNote`, an empty partner list reads as "no help near you" when the best option simply isn't on this map. Show it prominently, **including when the list is empty**.

`schemeNote` is also returned on a `502`, because when OpenStreetMap is down this guidance is the part that's still true and still useful.

An unknown `schemeId` returns **400**.

### Error codes — three failures that must read differently

| Code | Meaning | What to tell the citizen |
|---|---|---|
| `400` | Neither coordinates nor pincode, or the pincode isn't 6 digits | They can fix this by retyping |
| `404` | Well-formed pincode, but not one in use | "Check the PIN code" |
| `503` | Our PIN code lookup is down | **"Try again shortly"** — do *not* say the PIN code is wrong |
| `502` | The OpenStreetMap bank lookup is down | "Try again shortly" |

The 404/503 split is deliberate. They read identically in code but are opposite messages: one says *you* typed something wrong, the other says *we* are broken. Telling someone their real PIN code doesn't exist because a third-party service was slow is exactly the kind of small lie this module avoids — this was a live bug, found by running it.

> **Resolved (G1):** results are now cached ~20 minutes per ~1km grid cell, so several people searching the same area in a short window don't each spend a fresh Overpass call. Configurable via `app.overpass.cache-ttl-minutes`. The remaining risk is a genuinely cold cache during the very first demo query of a session — acceptable, not eliminated.

---

# Consent — `/api/v2/sih/consents`

**Required before `POST /{id}/submit`.** Calling submit without `PARTNER_SHARING` consent on file returns **403** with a message naming the consent needed — build the consent step into the flow *before* the citizen reaches submit, don't wait for the 403 to tell you.

| Method | Path | Notes |
|---|---|---|
| `GET` | `/purposes` | The exact wording to render — never paraphrase it in the UI |
| `GET` | `/` | Everything this citizen has ever granted or withdrawn |
| `POST` | `/` | Grant one |
| `DELETE` | `/{purpose}?applicationId=…` | Withdraw. Always **200**, even if there was nothing to withdraw |

**`GET /purposes` response** — six fixed purposes, this is the full list:

```json
[
  { "purpose": "profile_storage", "statement": "I agree that Yojna Sarthi may store my personal and family details to check which schemes I qualify for." },
  { "purpose": "credit_eligibility", "statement": "I agree that my income, category and project details may be used to check my eligibility for concessional credit schemes." },
  { "purpose": "partner_sharing", "statement": "I agree that my application and the documents I upload may be shared with the Channel Partner branch I have chosen, so that they can process my loan." },
  { "purpose": "document_verification", "statement": "I agree that the documents I upload may be opened and checked by the branch representative handling my application." },
  { "purpose": "digilocker_fetch", "statement": "I agree that Yojna Sarthi may fetch my issued documents from DigiLocker." },
  { "purpose": "account_aggregator_fetch", "statement": "I agree that my bank statement information may be fetched through an Account Aggregator to verify my income." }
]
```

`digilocker_fetch` and `account_aggregator_fetch` are listed for completeness — nothing in the product currently asks for them, since neither integration is built (see "Not built yet").

**`POST /` request:**

```json
{ "purpose": "partner_sharing", "applicationId": "app-1" }
```

`applicationId` is optional — omit it for an account-wide grant (e.g. `profile_storage`), include it to scope the consent to one application (`partner_sharing` should always be scoped: a citizen consenting to share *this* file with *this* branch is not consenting for every future application too).

**Response — `Consent`:**

```json
{
  "id": "...", "userId": "...", "purpose": "partner_sharing", "applicationId": "app-1",
  "statement": "I agree that my application and the documents I upload may be shared with the Channel Partner branch I have chosen, so that they can process my loan.",
  "grantedAt": "...", "revokedAt": null, "ip": "..."
}
```

`statement` is a **copy** taken at grant time, not a live pointer to `ConsentPurpose` — render this field, not a re-fetch of `/purposes`, so what's shown always matches what was actually agreed to even if the wording is revised later.

Re-granting after a withdrawal writes a **new** row rather than clearing the old one — a citizen's consent history is granted → withdrew → granted again, three facts, never one flag flipped twice. `GET /` returns all of them; render newest first and show withdrawn ones struck through, don't hide them.

---

# Documents — `/api/v2/sih/applications/{id}/documents`

| Method | Path | Who | Notes |
|---|---|---|---|
| `POST` | `.../{id}/documents` (multipart) | Citizen | `file` + optional `documentType` |
| `GET` | `.../{id}/documents` | Citizen | List, no content |
| `GET` | `.../{id}/documents/{documentId}` | Citizen | Downloads the file |
| `DELETE` | `.../{id}/documents/{documentId}` | Citizen | Citizen-only, every rep type |
| `GET` | `/api/v2/branch/applications/{id}/documents` | Rep / authorized helper | Read-only |
| `GET` | `/api/v2/branch/applications/{id}/documents/{documentId}` | Rep / authorized helper | Downloads |
| `POST` | `/api/v2/branch/applications/{id}/documents` (multipart) | **Assist-only helper only** | Uploads on the citizen's behalf — see below |
| `GET` | `/api/v2/sih/documents/limits` | Anyone | Limits, for pre-upload validation |

**`GET /limits` response** — call this once and validate client-side before the citizen picks a file, rather than letting a doomed upload run and fail on the server:

```json
{ "maxBytes": 8388608, "maxPerApplication": 20, "acceptedTypes": ["application/pdf", "image/jpeg", "image/png"] }
```

Content type is verified server-side by magic bytes, not by trusting the filename or the browser's declared `Content-Type` — an upload that lies about its type is rejected regardless of what the extension says.

**Upload response — `LoanDocument`** (content never echoed back, `content` is always `null` here):

```json
{
  "id": "...", "applicationId": "app-1", "userId": "citizen-1",
  "documentType": "caste_certificate", "filename": "caste_cert.pdf",
  "contentType": "application/pdf", "sizeBytes": 214532, "content": null,
  "uploadedAt": "..."
}
```

**Who can upload for whom — this is the accessibility answer.** A `BANK_BRANCH` rep may read documents on files assigned to their branch and may **never** upload or delete — evidence a lender can edit is not evidence. An assist-only helper (`CSC`/`NGO_SHG`/`FIELD_AGENT`) may **read and upload**, but only on an application the citizen has explicitly authorized them for (see the Assisted access section below), and may never delete. This is deliberate: the applicants this scheme targets frequently cannot photograph and upload a caste certificate themselves — someone does it with them — and the alternative (the helper typing the citizen's password instead) is worse, because it hides the same action from the audit trail. Every helper upload is recorded under the helper's own login, not the citizen's, so `GET /{id}/activity` shows who actually attached each file.

Deleting is citizen-only, full stop, for every rep type — removing evidence is not assistance.

**Errors:** 400 file too large / wrong type / already at the 20-document cap · 403 a branch rep (not assist-only) attempted the helper-upload endpoint, or an unauthorized helper attempted anything · 404 not the citizen's application, or not a file the caller has a claim to.

---

# Notifications — `/api/v2/notifications`

The inbox for whatever status changes on an application the caller owns — always scoped to the JWT principal, never to a parameter.

| Method | Path | Notes |
|---|---|---|
| `GET` | `/` | Full inbox, newest first |
| `GET` | `/unread-count` | `{ "unread": 3 }` — cheap enough to poll for a badge |
| `POST` | `/{id}/read` | Mark one read. 404 if it isn't the caller's |

In-app records are always written first, before any SMS/email attempt — the inbox is never empty just because a phone carrier dropped an SMS. A recipient who can't be resolved at all (no phone, no email, no account) doesn't silently vanish; it raises an internal alert instead of failing quietly.

---

## Assisted access, accountability, and offline identity verification

Added to answer a real gap: the portal originally issued accounts to one kind
of helper (a bank branch rep), assumed a citizen could always self-serve
DigiLocker/OTP flows, and gave a citizen no way to see who had touched their
own file. Three additions, all under `/api/v2/sih/applications/{id}/*` unless
noted:

- **`RepType`** (`BANK_BRANCH`/`CSC`/`NGO_SHG`/`FIELD_AGENT`) on `BranchRep`.
  Only `BANK_BRANCH` can record a credit decision
  (`POST /api/v2/branch/applications/{id}/status`); the other three can help
  assemble a file and upload documents, never decide one. Enforced
  server-side in `BranchRepController`, not by hiding UI.
- **`POST /{id}/assist`** / **`DELETE /{id}/assist`** — a citizen names a
  helper by the ID on their card (`repId`, not the internal document ID) and
  can withdraw it at any time. `GET /{id}/assist` lists everyone ever
  authorized, revocations included. An assist-only helper's ONLY claim to a
  file is a live authorization here — no institutional access the way a
  branch rep has via `partnerId`.
- **`GET /{id}/activity`** — the citizen's own copy of the audit trail: who
  was authorized, who read a document and when, who uploaded what, who
  recorded which status change. Actors are named in words
  ("R. Devi (CSC operator, CSC Ranchi)"), never as an internal ID.
- **`POST /{id}/report-misuse`** / **`GET /sih/misuse-reports`** — an
  unofficial fee, a requested OTP, wrong details entered, documents used
  elsewhere. No proof required; an unidentifiable helper doesn't block the
  report. Every filing raises an `agent_alerts` row `AlertNotifier` already
  polls and emails — see `MisuseReportService`'s javadoc for why the alert
  carries only IDs, never the citizen's own words.
- **`POST /{id}/aadhaar-ekyc`** (citizen) / **`POST /api/v2/branch/applications/{id}/aadhaar-ekyc`**
  (authorized helper) — upload UIDAI's offline eKYC ZIP (`file` +
  `shareCode` form fields) instead of a live DigiLocker/OTP flow. Needs no
  network at the moment of verification; the resident (or a CSC operator
  helping them) downloads the file once, at a CSC if necessary. Server-side
  signature verification against a real UIDAI certificate is not switched on
  in any deployment yet — `AadhaarEkycRecord.signatureVerified` is honestly
  `false` until `UIDAI_CERT_PATH` is configured; the extraction, masking, and
  encryption all work regardless. See `AadhaarOfflineEkycService`'s javadoc.

### Request/response shapes for the section above

**`POST /{id}/assist` request** — the ID the citizen reads off the helper's own card or badge, not any internal ID they'd have no way to know:

```json
{ "helperRepId": "CSC-JH-201", "note": "helped me at the CSC in Ranchi" }
```

Response is the full `AssistAuthorization` row (`id`, `applicationId`, `citizenId`, `helperId`, `helperName`, `helperType`, `helperOrganisation`, `grantedAt`, `revokedAt`, `note`) — useful for confirming what was just granted, but **`GET /{id}/assist` returns a different, simpler shape**, built for rendering a "who's helping me" list directly:

```json
[
  {
    "helperId": "h-1", "name": "R. Devi", "type": "csc", "typeLabel": "CSC operator",
    "organisation": "CSC Ranchi", "grantedAt": "...", "revokedAt": null, "active": true
  }
]
```

Revoked entries stay in the list (`active: false`, `revokedAt` set) — render them struck through, don't filter them out; the point of the endpoint is that the history is the record, not just who currently has access. `DELETE /{id}/assist?helperId=h-1` revokes one; omitting `helperId` revokes every live authorization on the file at once (the panic button).

**`GET /{id}/activity` response** — a merged, newest-first timeline from four different sources (authorizations, status history, document uploads, and document reads pulled from the audit log), because no single source knows the whole story on its own:

```json
[
  { "at": "...", "actorId": "h-1", "actor": "R. Devi (CSC operator, CSC Ranchi)", "action": "assist_granted", "detail": "You allowed them to help with this application" },
  { "at": "...", "actorId": "h-1", "actor": "R. Devi (CSC operator, CSC Ranchi)", "action": "document_uploaded", "detail": "caste_certificate.pdf" },
  { "at": "...", "actorId": "rep-9", "actor": "A. Kumar (Branch representative, SBI Kanpur Nagar)", "action": "document_viewed", "detail": null },
  { "at": "...", "actorId": "rep-9", "actor": "A. Kumar (Branch representative, SBI Kanpur Nagar)", "action": "status_changed", "detail": "under_verification" }
]
```

`action` is a **stable machine key to localize in the UI** (`assist_granted`, `assist_revoked`, `status_changed`, `document_uploaded`, `document_viewed`) — build the citizen-facing sentence from `action` + `actor` + `detail` in the frontend's own copy, don't render `action` verbatim. `actorId` is included specifically so a "report misuse" button next to an entry can pre-fill `reportedHelperId`. The citizen themselves shows as `"You"`; an actor that can't be resolved to a known account shows as `"A staff member"`, never a raw internal ID.

**`POST /{id}/report-misuse` request:**

```json
{ "reportedHelperId": "h-1", "category": "unofficial_fee", "description": "asked for ₹200 to submit the form" }
```

`category` — the real vocabulary, fetch it from `GET /api/v2/sih/misuse-reports/categories` rather than hardcoding: `unofficial_fee`, `credential_request`, `wrong_details`, `data_misuse`, `no_service`, `other`. `reportedHelperId` is optional — a citizen who doesn't know or remember who touched their file can still file a report; the alert this raises is still useful even naming nobody. Response is the created `MisuseReport` (`status` starts `"open"`, moves through `"reviewing"` to `"resolved"` — internal-only for now, no citizen-facing status-update endpoint exists yet). `GET /api/v2/sih/misuse-reports` lists everything the calling citizen has ever filed.

**`POST /{id}/aadhaar-ekyc` response — `AadhaarEkycRecord`** (`encryptedPhoto` never echoed back; fetch the photo separately):

```json
{
  "id": "...", "applicationId": "app-1", "citizenId": "...",
  "referenceId": "...", "maskedUid": "XXXXXXXX1234",
  "name": "...", "dob": "...", "gender": "...", "careOf": "...", "addressOneLine": "...",
  "signaturePresent": true, "signatureVerified": false,
  "extractedAt": "...", "uploadedByUserId": "...", "uploadedByRole": "CITIZEN"
}
```

`signatureVerified: false` is honest, not broken — no deployment has `UIDAI_CERT_PATH` configured yet, so this is always `false` regardless of whether the underlying file was genuine. **Do not render this as a red flag to the citizen** — it describes the platform's current capability, not their document. The photo is fetched separately via `GET .../aadhaar-ekyc/{recordId}/photo` (returns `image/jpeg` directly).

### The helper's own worklist — `GET /api/v2/branch/assist`

An assist-only helper's equivalent of the branch rep queue — every application a citizen has currently authorized them to help with, requires `ROLE_BRANCH_REP`:

```json
{
  "helperType": "csc",
  "canRecordDecisions": false,
  "assignments": [
    {
      "applicationId": "app-1", "grantedAt": "...",
      "productName": "Micro Finance Scheme (MFS)", "status": "missing_docs",
      "requestedAmount": 90000, "missingDocuments": ["Caste certificate"]
    }
  ]
}
```

`canRecordDecisions` is included so the UI can decide, once, whether to render status-change controls at all — but the server enforces the same rule independently on `POST /api/v2/branch/applications/{id}/status` (**403** for any non-`BANK_BRANCH` type), so hiding the button is a courtesy, not the actual security boundary. `assignments` degrades gracefully to just `applicationId`/`grantedAt` if the underlying application can't be loaded — a helper's worklist should never fail outright over one broken row.

### Becoming an assist-only helper — `/api/v2/sih/branch-rep-applications`

Before this, every `BranchRep` account — bank branch or assist-only — was admin-issued, with no path for a CSC operator, NGO/SHG worker, or field agent to ever request one themselves. This closes that gap, mirroring `HelperApplication`'s KYC and credential-minting pattern (assist-only helpers are still a different model from `Helper`, the general-scheme volunteer role — this is specifically the credit module's own rep type). Requires the citizen to be logged in (`ROLE_CITIZEN`); admin endpoints check `ROLE_ADMIN` in the handler, same convention as `HelperApplicationController`, not a path matcher.

- `POST /` — citizen applies. Body: `{fullName, phone, aadhaar, pan, repType, organisation, workProofDetail}`. `repType` must be `csc`, `ngo_shg`, or `field_agent` — **`bank_branch` is refused with 400**, since a branch representative is appointed by their lending Channel Partner, not self-applied. **400** on a malformed PAN/Aadhaar or a missing `organisation` (the CSC code, NGO/SHG name, or district worked from); **409** if the citizen already has a pending or approved application (a rejected one may be re-applied for). Returns `{success, status: "pending", aadhaarVerified}` — `aadhaarVerified` reflects only the Verhoeff checksum on the typed number, same honesty caveat as the offline eKYC flow above: it is not proof of identity.
- `GET /mine` — the citizen's own application, or `{"status": "none"}`.
- `GET /pending` — admin only (**403** otherwise). List of applications with PII decrypted for review.
- `GET /pending/count` — admin only. `{"pending": <count>}`, for a dashboard badge.
- `POST /{id}/approve` — admin only. Mints a `BranchRep` login: `repId` is prefixed by type (`CSC-`, `NGO-`, `FA-`) followed by a random unique token, plus a temporary password. Emails the credentials via a dedicated `sendBranchRepCredentials` method (deliberately **not** a reuse of the general helper's `sendCredentials` — that one is hardcoded to say "Helper" and link to `/helper`, the wrong role name and the wrong login page for this account). Returns `{success, status: "approved", repId, tempPassword, emailedTo}` — the credentials are always returned in the response too, so an admin can relay them by hand if email delivery fails or isn't configured; a minted credential must never simply be lost.
- `POST /{id}/reject` — admin only. `{success, status: "rejected"}`.

---

## Not built yet

- **DigiLocker** and **Account Aggregator** verification. `VerificationMode.DIGILOCKER`/`.ACCOUNT_AGGREGATOR` exist in the enum and are rejected with **400** if requested (`isAvailable() == false`) — this is deliberate, not an oversight, so a request for either fails loudly instead of silently recording a verification that never happened. `ConsentPurpose.DIGILOCKER_FETCH`/`.ACCOUNT_AGGREGATOR_FETCH` exist for the same reason: the shape is ready, the integration is not.
- **UIDAI signature verification** on offline eKYC — extraction/masking/storage all work today; only the cryptographic signature check against a real UIDAI certificate is pending `UIDAI_CERT_PATH` being configured in a deployment.
- **Everything in this document has zero frontend integration as of this writing.** Every endpoint above is implemented, tested, and — as of this session — verified live against a real LLM/Mongo/Spring boot, but no React page calls any of them yet. This is the actual critical path for demo day, not any backend gap.
