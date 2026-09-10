# SIH Credit Module — Work Distribution

**Team:** Rudra, Chirag (backend) · Charan, Ayush (frontend)
**Baseline:** branch `test`, 5 commits, 146 backend + 18 frontend tests green
**Window:** Day 1 done (2026-09-10). Days 2–11 below, Days 12–14 held for demo prep.

**Split as agreed:** frontend divided equally between Charan and Ayush; everything else 80% Rudra / 20% Chirag.

---

## What is already done — do not rebuild

| Area | State |
|---|---|
| EMI + moratorium math | Done, both stacks, agree to 6dp |
| `credit_products` catalogue + seeder | Done, 6 NSFDC schemes, official figures |
| Eligibility engine + explanations | Done, `POST /api/v2/sih/credit/eligibility` |
| Application lifecycle + state machine | Done, `/api/v2/sih/applications` |
| Branch-rep endpoints | Done, `/api/v2/branch/applications` |
| Role gating, `/error` 400-vs-403 fix | Done |
| Partner locator (OSM, nationwide, real) | **Already existed.** Extend, don't replace |
| API contract | [SIH-CREDIT-API.md](SIH-CREDIT-API.md) — build against it |

Frontend is currently **not** wired to any of the new endpoints. That is the first job.

---

# Frontend — Charan & Ayush

Split by feature area rather than by layer, so you don't collide in the same files. Shared work is explicitly halved at the bottom.

## Charan — the discovery half

*From "I need money" to "here is my scheme and what it costs."*

**C1. Repoint the catalogue and recommender at the server** — Days 2–3
Delete the hardcoded `NSFDC_SCHEMES` array in `frontend/src/lib/nsfdcSchemes.js`; fetch `GET /api/v2/sih/credit/products` instead. Replace the client-side `recommendScheme()` with `POST /eligibility`.
*Done when:* the ₹5 lakh ceiling can no longer be bypassed from devtools, and a rate change in Mongo shows up without a rebuild.

**C2. Guided eligibility flow (multi-step)** — Days 3–5
`GuidedEligibilityPage`: profile → project/course → cost. Drive the next step off `missingProfileData` from the response.
*Two things that carry real user consequence:*
- **Ask for `gender`.** It is what unlocks Mahila Samriddhi at 4% instead of Micro Finance at 6.5% — about ₹4,300 on a ₹90,000 loan.
- **`insufficient_data` is not a rejection.** Render it as "we need two more answers", never as "you don't qualify".

**C3. Scheme results** — Days 5–6
Render `matched[]` / `failed[]` verbatim (they are written to be read aloud). Show `marginMoney` prominently — the citizen's own contribution is the most common reason these applications stall at the branch. Distinguish `costExceedsCap` ("this scheme can't fund a project this size") from ordinary margin money.
Show `sourceNote` wherever `figuresVerified` is false — currently Mahila Samriddhi only.

**C4. EMI calculator on server quotes** — Day 7
Keep local `calculateEmi` for slider responsiveness; quote from `POST /emi` for anything the citizen acts on. The moratorium UI already exists.

**C5. Partner locator — pincode fallback** — Days 8–9
Geolocation is currently the only input path, so a denied permission or a desktop kills the feature. Add pincode/district entry. Depends on **R3**; build against a stub until it lands.

## Ayush — the commitment half

*From "I want this one" to "here is where my application stands."*

**A1. Application submission** — Days 2–4
`POST /api/v2/sih/applications` creates a `draft`; `/submit` commits it. Show `quotedTerms` on a confirmation screen before submit — this is the moment the citizen agrees to a repayment figure, so it must be the server's number, not the slider's.

**A2. Document upload** — Days 4–5
Depends on **R4**. Build against the contract; wire when it lands.

**A3. Beneficiary status timeline** — Days 5–7
Render `statusHistory` (append-only) as a timeline across the 8 statuses. When status is `missing_docs`, show `missingDocuments` as the primary call to action with a "documents supplied" button hitting `/documents-supplied`.
*Non-negotiable:* a `rejected` application must always display its `reasonCode` — the API guarantees one exists.

**A4. Branch-rep dashboard** — Days 7–10
Login, queue (`GET /branch/applications?partnerId=&status=`), filters, detail view, actions.
Build the reason-code dropdown from `GET /branch/applications/reason-codes` — do not hardcode it.
The API rejects a rejection without a reason and a `missing_docs` move without named documents; make the form enforce both so the rep never sees a 400.
Handle **409** properly: it means an illegal transition and the message names the legal moves. Show it, don't retry.

## Split evenly between you

- **API client layer** in `frontend/src/lib/api.js` — agree the shape once, then each add your own calls.
- **i18n** — each registers strings for their own screens via the existing `useAutoTranslate` static/dynamic split. Follow `CreditSchemesPage.jsx` — that page is already correct.
- **Mobile + component library** — Charan takes the discovery screens, Ayush the application/dashboard screens.

---

# Backend & everything else — Rudra 80% / Chirag 20%

## Rudra (80%)

**R1. Partner filtering by scheme** — Days 2–4
`channel_partners` collection mapping partner → schemes; extend `/api/v2/credit-partners/nearby` with `?schemeId=`. **Do not seed fake branches** — the existing endpoint returns real OSM data and refuses to invent NSFDC authorisation status. Hold that line.

**R2. Partner assignment on submit** — Day 4
Route a submitted application to a partner. `assignPartner` exists; the selection rule does not.

**R3. Pincode → coordinates lookup** — Day 5 *(unblocks C5)*
Ship the contract on Day 2 so Charan isn't blocked.

**R4. Document upload + storage** — Days 5–7 *(unblocks A2)*
Contract to Ayush on Day 2. Reuse the existing field-encryption service; size limits already exist for profile photos.

**R5. Consent entity** — Days 7–8
Purpose-scoped and revocable. Today it is a single `consentGivenAt` timestamp, which cannot answer "did this citizen consent to us pulling income proof for *this* application".

**R6. Controller-level tests (MockMvc)** — Days 8–9
There are none. The service layer is well covered, but the HTTP edge — auth gates, status codes, JSON binding — is not. I verified it by hand once; that does not survive a refactor.

**R7. Application workflow end-to-end over HTTP** — Day 9
Never exercised with a real JWT. Its 21 unit tests and the verified 403 gate are not the same thing.

**R8. Branch-rep accounts** — Day 10
`ROLE_BRANCH_REP` is enforced but nothing issues it. Reps need a way to exist and log in. *(Blocks A4's login; agree the auth shape with Ayush by Day 6.)*

**R9. Demo seed data** — Day 10–11
Applications across all 8 statuses so the timeline and queue aren't empty on stage.

## Chirag (20%)

Self-contained, clear boundaries, no shared files with R1–R9.

**G1. Overpass response caching** — Days 2–3
Every locator request hits OpenStreetMap live and Overpass rate-limits by IP. **A judging panel refreshing the page can get us throttled mid-demo.** This is the highest-value small task on the board.

**G2. Verify the NSFDC figures** — Days 3–4
The entire catalogue rests on one successful fetch of `nsfdc.nic.in/scheme`. Cross-checks against myScheme and socialjustice.gov.in both failed to return usable content.
Priority: **Mahila Samriddhi**, seeded `figuresVerified: false` — its 4% rate and 3-month moratorium come from State Channelising Agency listings that disagree with each other on tenure (3 / 3½ / 4 years) and moratorium (3 / 6 months).
Also chase Mahila Kisan and Nari Arthik Sashaktikaran, deliberately left unseeded rather than guessed.
*Update the seeder + `CreditProductSeederTest` with whatever you confirm, and flip `figuresVerified` only for figures from an official source.*

**G3. `ai_service` stale income ceiling** — Day 5
`ai_service/data/schemes/` still carries the superseded ₹3 lakh "double the poverty line" figure and one generic NSFDC entry quoting *₹15 lakh at 2–6%*, which contradicts the real catalogue. Correct or remove it so the chat side stops telling citizens something different from the credit module.

---

## Cross-team dependencies — agree these early

| Contract | Owner → Consumer | Needed by |
|---|---|---|
| Document upload shape | Rudra → Ayush | **Day 2** (stub), Day 7 (live) |
| Pincode lookup shape | Rudra → Charan | **Day 2** (stub), Day 5 (live) |
| Branch-rep auth shape | Rudra → Ayush | **Day 6** |
| Partner `schemeId` filter | Rudra → Charan | Day 4 |

Ship contracts as stubs on Day 2. Frontend should never wait on a backend implementation.

---

## Standing rules for this module

1. **Never show a citizen a number they could act on unless it is correct.** The EMI screen already shipped a wrong one; the whole first day went on fixing it.
2. **Never fabricate data.** Inherited from `CreditPartnerController`, which refuses to invent NSFDC authorisation status rather than guess. If we don't know, we say so.
3. **`unitCostCeiling` is not `maxLoanAmount`.** Different numbers in every scheme. Conflating them is the exact bug the original catalogue shipped.
4. **Money math and eligibility rules need tests to merge.** Everything else is judgement.
5. **Run it before calling it done.** Booting the app found three defects that 135 green unit tests missed, one of them repo-wide.
