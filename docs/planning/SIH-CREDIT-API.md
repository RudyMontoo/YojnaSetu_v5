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
| `POST` | `/{id}/submit` | `draft → submitted` |
| `POST` | `/{id}/documents-supplied` | `missing_docs → under_verification` |

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

## Not built yet

Partner filtering by scheme (`/api/v2/credit-partners/nearby?schemeId=`), the `Consent` entity, and document upload. `GET /api/v2/credit-partners/nearby?lat=&lng=&radiusKm=` already works today and is unchanged.
