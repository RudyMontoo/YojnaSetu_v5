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

**Requires `ROLE_BRANCH_REP` or `ROLE_ADMIN`**, enforced by a path matcher in `SecurityConfig`. A rep only ever sees files assigned to their partner.

| Method | Path | Notes |
|---|---|---|
| `GET` | `/?partnerId=…&status=…` | Queue, newest submission first. `status` optional |
| `GET` | `/{id}?partnerId=…` | 404 if assigned elsewhere |
| `POST` | `/{id}/status` | Record a decision |
| `GET` | `/reason-codes` | The vocabulary — build the dropdown from this, don't hardcode it |

**`POST /{id}/status`:**

```json
{
  "partnerId": "partner-7",
  "status": "missing_docs",
  "reasonCode": "documents_incomplete",
  "note": "Income certificate is from 2019",
  "requestedDocuments": ["Caste certificate", "Income proof (current year)"]
}
```

Two rules the API enforces so the citizen's screen is never a dead end:

- `status: "rejected"` **requires** `reasonCode` → 400 without it. "Rejected, reason blank" is not producible.
- `status: "missing_docs"` **requires** a non-empty `requestedDocuments` → 400 without it. The list lands on the application's `missingDocuments` and clears automatically when verification resumes.

`reasonCode` values: `income_above_ceiling`, `category_not_eligible`, `documents_incomplete`, `documents_illegible`, `documents_mismatch`, `project_not_viable`, `existing_loan_default`, `duplicate_application`, `partner_funds_exhausted`, `applicant_withdrew`, `other`.

**Errors:** 400 malformed or missing a required reason · 404 not found / not this partner's · 409 illegal transition, message names the legal moves.

---

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

> **Known risk:** OpenStreetMap's Overpass rate-limits by IP and became unreachable during testing after repeated calls. Response caching is assigned (Chirag, G1) and is on the demo's critical path.

---

## Not built yet

Partner filtering by scheme (`?schemeId=`), the `Consent` entity, and document upload — all now built; this line is stale and kept as-is rather than silently rewritten (see repo-wide note on not trusting this doc's own status claims).

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
