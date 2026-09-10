# PRD v2 — SIH 2026 SC Concessional Credit Access Platform

**Supersedes:** the v1 PRD circulated in chat.
**Basis:** direct reading of the code in this repo. Not the README, and not the former `docs/status/*` progress files — those overstated what existed and have since been deleted for that reason.
**Scope of this document:** what the code actually does today, where it is wrong, and what the four of us build in the next 14 days.

---

## 0. Why v2 exists

v1 was written as if this were greenfield. It is not. Roughly half of F1–F4 already has code on `main`, and v1 would have had us *rebuild* the one part that is genuinely good while leaving a citizen-facing arithmetic bug in place.

Three corrections to v1's premises, each verifiable in the tree:

| v1 said | Code says |
|---|---|
| Build a partner locator, seed 5–10 fake partners in one state | [`CreditPartnerController.java`](../../deploy/backend/spring-gateway/src/main/java/com/yojnasetu/gateway/controller/CreditPartnerController.java) already serves **real** nationwide bank branches from OSM Overpass with haversine distance. Seeding fakes would be a downgrade. |
| Backend lives at `backend/` | It lives at [`deploy/backend/spring-gateway/`](../../deploy/backend/spring-gateway/). Spring Boot 3.2.3, Java 17 — confirmed in `pom.xml`. |
| Add an EMI calculator with moratorium support | An EMI calculator exists and **the moratorium is a lie in the UI** — see §2.1. This is the single most important thing in this document. |

**Standing rule for this module, adopted from the one thing the existing credit code does right:** never fabricate a number or a status a citizen could act on. `CreditPartnerController` refuses to invent NPA data and labels unknown banks `Unclassified` rather than guessing. Hold that line everywhere.

---

## 1. What actually exists today (verified by reading)

**Frontend — [`CreditSchemesPage.jsx`](../../frontend/src/pages/CreditSchemesPage.jsx), 342 lines, three tabs:**
- Recommender tab → calls `recommendScheme()` from [`nsfdcSchemes.js`](../../frontend/src/lib/nsfdcSchemes.js). Pure client-side, hardcoded array of 3 schemes.
- Calculator tab → calls `calculateEmi()` from [`emiCalculator.js`](../../frontend/src/lib/emiCalculator.js). Pure client-side.
- Locator tab → the only tab that talks to a server. `gateway.creditPartnersNearby(lat, lng)`.
- i18n is wired properly, including a genuinely thoughtful split between static labels and request-time dynamic strings ([CreditSchemesPage.jsx:76-78](../../frontend/src/pages/CreditSchemesPage.jsx#L76-L78)). **v1's "add i18n to SIH screens" task is already done for this page.**

**Backend — Spring gateway:**
- `GET /api/v2/credit-partners/nearby` — real, working, `permitAll` in [`SecurityConfig.java:74`](../../deploy/backend/spring-gateway/src/main/java/com/yojnasetu/gateway/config/SecurityConfig.java#L74).
- `Application` model + `ApplicationController` — exists, but models *welfare-scheme tracking*, not a *loan workflow*. See §2.4.
- Auth: OTP + JWT, httpOnly cookies, field encryption, rate-limit filter, audit log. Solid. **v1's "reuse JwtAuthFilter/JwtUtils" is correct and needs no work.**
- Roles exist (`CITIZEN`, `HELPER`, `CSC_OPERATOR`, `ADMIN`) but are enforced by hand inside controllers, e.g. [`HelpRequestController.java:39-41`](../../deploy/backend/spring-gateway/src/main/java/com/yojnasetu/gateway/controller/HelpRequestController.java#L39-L41), not in `SecurityConfig`.

**Python — `ai_service/`:** has a real eligibility engine, [`eligibility_rules_engine.py`](../../ai_service/graph/agents/eligibility_rules_engine.py). It is well-built: it separates "scheme has no such rule" from "citizen's profile lacks the field" from "no rules extracted at all", and returns `matched`/`failed` lists that read back as plain sentences. **This is exactly the explainability F1 asks for — and the NSFDC credit path does not use it.** Two disjoint eligibility systems in one repo.

**Test reality — the number that should worry us most:**

| Stack | Tests | Covering the credit module |
|---|---|---|
| Frontend | **none** — no test runner in `package.json` at all | none |
| Java | 2 files, both security utils | none |
| Python | 22 files, substantive | none |

The EMI math — the number a citizen makes a borrowing decision on — has **zero** tests, in the stack with **zero** test infrastructure.

---

## 2. Defects to fix (found by reading code, ranked)

### 2.1 The moratorium is displayed but never calculated — **P0, correctness**

[`calculateEmi(principal, annualRatePct, tenureMonths)`](../../frontend/src/lib/emiCalculator.js#L11) takes **no moratorium parameter**. There is nowhere for it to enter the math.

Yet the UI tells the citizen, at [CreditSchemesPage.jsx:174-176](../../frontend/src/pages/CreditSchemesPage.jsx#L174-L176):

> `{scheme.interestRate}% p.a. · {scheme.moratoriumMonths}-month moratorium before EMIs begin · repayment schedule below starts counting from month 1 after the moratorium ends.`

So the page asserts a moratorium is in effect, and the schedule below it is computed as if the loan started today with no moratorium at all. Interest accruing during the moratorium is silently dropped.

**Concrete failure:** Micro Finance Scheme, ₹1,40,000 at 6.5% with a 3-month moratorium. Under capitalisation the principal should become ₹1,42,287 (₹2,287 of accrued interest; ₹2,275 if accrued simple rather than compounded). The page omits it entirely and computes every EMI against the un-capitalised ₹1,40,000, so both the monthly figure and the total are understated. The citizen budgets against a number no lender will honour.

This is the exact opposite of the honesty standard the partner locator sets two files away. **Fix before anything else is built on top.**

### 2.2 The recommender is client-side, unranked, and single-result — P1

- **Bypassable.** The ₹5L ceiling is enforced at [nsfdcSchemes.js:57](../../frontend/src/lib/nsfdcSchemes.js#L57), in the browser. Anyone can edit state and get a recommendation they aren't eligible for. There is no server-side check anywhere.
- **Un-updatable.** Rates and caps are a hardcoded JS array. A rate change requires a frontend deploy.
- **Never returns 1–3 schemes** as F1 requires. The three filter branches at [nsfdcSchemes.js:68-74](../../frontend/src/lib/nsfdcSchemes.js#L68-L74) are mutually exclusive and each scheme has a distinct `forProjectType`, so it always returns exactly one. The variable is named `ranked` but nothing is ranked.
- **`coveragePct` is dead data.** All three schemes carry `coveragePct: 90`, and it is displayed — but the recommender never applies it. A citizen with a ₹1,00,000 project is never told the loan covers ₹90,000 and they must find ₹10,000 themselves. That margin-money gap is the most common reason these applications actually fail.
- **No cap warning.** A ₹80,00,000 project cost is routed to Term Loan (₹50L cap) with no indication the scheme cannot fund it.

### 2.3 Locator: no scheme filter, no fallback, incomplete partner taxonomy — P1

- The endpoint takes `lat`/`lng`/`radiusKm` only. F3 requires partners **eligible for the selected scheme**; there is no scheme parameter and no partner→scheme mapping data.
- `classify()` ([CreditPartnerController.java:72-82](../../deploy/backend/spring-gateway/src/main/java/com/yojnasetu/gateway/controller/CreditPartnerController.java#L72-L82)) detects PSB and RRB. It cannot detect **SCA or NBFC-MFI** — two of the four channel-partner types in the problem statement. OSM `amenity=bank` largely does not contain them.
- Geolocation is the only input path ([CreditSchemesPage.jsx:222](../../frontend/src/pages/CreditSchemesPage.jsx#L222)). Permission denied or desktop-without-GPS ⇒ the feature is completely unusable. No pincode/district entry.
- **Demo risk:** every request hits Overpass live with no caching. Overpass rate-limits by IP. A judging panel refreshing the page can get us throttled mid-demo.

### 2.4 `Application` cannot express a loan workflow — P1

[`Application.java`](../../deploy/backend/spring-gateway/src/main/java/com/yojnasetu/gateway/model/Application.java):
- Statuses are `in_progress | submitted | approved | rejected | disbursed` ([ApplicationController.java:39](../../deploy/backend/spring-gateway/src/main/java/com/yojnasetu/gateway/controller/ApplicationController.java#L39)). F4 needs `draft, submitted, under_verification, missing_docs, forwarded, sanctioned, rejected, disbursed`.
- No `assignedPartnerId`, no `missingDocuments`, no reason codes, no verification mode. A branch rep has nothing to act on.
- Status transitions are unvalidated — any valid status can jump to any other. `disbursed → draft` is accepted.
- **`@CompoundIndex(name = "user_scheme_unique", ..., unique = true)` on `(userId, schemeId)`** ([Application.java:26](../../deploy/backend/spring-gateway/src/main/java/com/yojnasetu/gateway/model/Application.java#L26)) means **a citizen who is rejected can never re-apply to that scheme.** Correct for bookmarking welfare schemes; wrong for loans, where reapplication after fixing documents is the normal path.

### 2.5 Consent is one boolean, not a record — P2

`CitizenProfile.consentGivenAt` is a single timestamp set by `POST /api/v2/consent`. There is no record of *what* was consented to, for *what purpose*, or any way to revoke. F4 requires per-verification-action consent. A single global flag cannot answer "did this citizen consent to us pulling their income proof for this specific loan application."

### 2.6 Minor: `isBpl` handled inconsistently in the Python engine — P3

[`eligibility_rules_engine.py:113-115`](../../ai_service/graph/agents/eligibility_rules_engine.py#L113-L115) uses `if requires_bpl is not True` while the structurally identical `isRural` and `hasLand` blocks below use `is None`. A scheme with `isBpl: false` is therefore treated as having no BPL rule. Probably harmless in practice, but it is an undocumented asymmetry in code that otherwise handles these cases with real care. Add a comment or normalise it.

---

## 3. Target architecture

The governing decision: **move credit scheme data and eligibility to the server; keep the good parts where they are.**

```
credit_products (Mongo, NEW)          ← rates/caps/moratorium, editable without deploy
        │
        ▼
CreditEligibilityService (Java, NEW)  ← ports the Python engine's matched/failed/
        │                                missing_profile_data explainability shape
        ├─► POST /api/v2/sih/eligibility
        └─► POST /api/v2/sih/emi       ← moratorium-correct amortisation, server-side

channel_partners (Mongo, NEW)         ← scheme→partner mapping ONLY
        │                                (no fabricated branches; joins onto OSM results)
        ▼
GET /api/v2/credit-partners/nearby?schemeId=…   ← extend the existing endpoint, don't replace

CreditApplication (Mongo, NEW collection)  ← separate from `applications`; do NOT
                                              retrofit the welfare model (§2.4)
```

**Why a new `CreditApplication` collection rather than extending `Application`:** the unique index and the status vocabulary are both correct for what `Application` currently does. Changing them risks the working welfare tracker for no benefit. Two collections, two lifecycles.

**Why port the eligibility engine to Java rather than call Python:** the credit rules are deterministic arithmetic over 3 products. There is no LLM in the path, so there is no reason to add a network hop and a second failure mode. Reuse the *shape* of `evaluate_eligibility()`'s return value — `{verdict, matched, failed, missing_profile_data}` — because that shape is what makes the explanation honest.

**EMI stays computable on the client too** (instant slider feedback), but the server is authoritative and the client calls the shared implementation. Both must be moratorium-correct.

### Moratorium semantics — decide explicitly, do not leave implied

Two modes, both must be supported and labelled in the UI:
- **Capitalised (default):** interest accrues during moratorium and is added to principal. EMI is computed on `P × (1 + r)^m`.
- **Interest-servicing:** citizen pays interest-only during moratorium; principal is untouched; EMI computed on original `P`.

The current UI implies neither and computes neither.

---

## 4. Work distribution

Same four people, re-scoped against what exists.

### Backend — Rudra & Chirag

**Day 1–2 (blocking, do first):**
1. **Fix the EMI moratorium bug.** Both modes above. Ship the corrected function *and* its tests before touching anything else.
2. **Stand up a frontend test runner** (Vitest — Vite is already the bundler, near-zero config). Currently there is none. The EMI fix is the first thing it tests.
3. `CreditProduct` entity + repo + seed from `nsfdcSchemes.js`'s existing values, which are honestly sourced from the problem statement and carry the right caveat comment. Keep that comment.

**Day 3–6:**
4. `CreditEligibilityService` + `POST /api/v2/sih/eligibility`. Returns `matched`/`failed`/`missing_profile_data` per §3. Must apply `coveragePct` and emit the margin-money gap. Must return up to 3 schemes with a real ranking rationale.
5. `POST /api/v2/sih/emi` — server-authoritative, both moratorium modes, amortisation schedule.
6. Unit tests for both. This is the part v1 got right: eligibility logic must be unit-tested.

**Day 7–10:**
7. `CreditApplication` + explicit state machine (allowed-transition map, reject invalid transitions with 409 — the current controller accepts any→any).
8. `ChannelPartner` scheme-mapping collection; extend `/nearby` with `?schemeId=`. Add a **response cache** (§2.3 demo risk) and a pincode fallback path.
9. Branch-rep endpoints: queue, detail, status update with reason code, request-documents.

**Day 11–12:**
10. `ROLE_BRANCH_REP`; move role checks into `SecurityConfig` matchers for `/api/v2/sih/**` and `/api/v2/branch/**` rather than adding more hand-rolled controller checks.
11. `Consent` entity — purpose-scoped, revocable, one record per verification action.
12. API contract doc for the frontend pair. **Write this by Day 3 in stub form** so Charan & Ayush aren't blocked waiting on implementations.

### Frontend — Charan & Ayush

**Do not rebuild `CreditSchemesPage`.** It is coherent, i18n-complete, and its honesty disclosures are a feature. Refactor it in place.

**Day 1–4 (unblocked, no backend dependency):**
1. **Moratorium UI:** mode selector (capitalised / interest-servicing), and a schedule that visibly shows the moratorium months distinctly from the EMI months. Right now the note claims a behaviour the table doesn't show.
2. **Margin-money display:** loan amount vs project cost vs the citizen's 10% contribution. Currently `coveragePct` is shown as a stat and never applied.
3. **Locator fallback:** pincode/district input when geolocation is denied or unavailable.
4. Cap-exceeded warning when project cost > scheme max.

**Day 5–9:**
5. Repoint recommender + EMI at the new endpoints; keep client-side EMI for slider responsiveness, treat server as truth on submit.
6. Multi-step `GuidedEligibilityPage` — profile → project → education. Feed `missing_profile_data` back as "we need these three fields", which the Python engine's return shape already supports conceptually.
7. Application submission + document upload.

**Day 10–13:**
8. Beneficiary status timeline; branch-rep queue + detail + actions.
9. Hindi/English strings for all new screens via the existing `useAutoTranslate` pattern — follow the static/dynamic split already used on this page.

---

## 5. Non-functional requirements (revised)

- **Correctness of money figures outranks every other requirement in this module.** Any number a citizen could budget against is either computed correctly or not shown.
- **No fabricated data.** Inherited from `CreditPartnerController`'s existing stance. If we don't know a partner's NSFDC authorisation status, we say so.
- Test gates: EMI math and eligibility rules require unit tests to merge. Currently neither has any.
- Auth/JWT/field-encryption/audit-log: reuse as-is, no work needed.
- Perf: cache Overpass responses; do not add heavy assets to these flows.

---

## 6. Explicitly out of scope

DigiLocker / Account Aggregator (architecture slide only, labelled "planned"), map rendering in the locator (list + Directions link is sufficient and already works), analytics dashboards, and any chatbot involvement in the credit path — the credit flow is deliberately a form, not a conversation.

---

## 7. Scheme data — resolved 2026-09-10

Question 1 below was checked and the answer was **no, the figures were wrong**. Recorded here because the corrections change what the module can claim.

**The database had none of this.** Local Mongo has no `yojnasetu` database at all; the seed data in `ai_service/data/schemes/` contains exactly one NSFDC entry — a generic "NSFDC Loans" umbrella quoting *₹15 lakh at 2–6%* — and zero hits for Micro Finance Scheme, Term Loan, Educational Loan, Mahila Samriddhi, Mahila Kisan, Shilpi Samriddhi or Green Business. The catalogue the PS is about did not exist in this repo outside a hardcoded frontend array.

**Corrections made**, from [nsfdc.nic.in/scheme](https://nsfdc.nic.in/scheme) (retrieved 2026-09-10):

| | Previously seeded | Actual |
|---|---|---|
| MFS max loan | ₹1,40,000 | **₹1,25,000** (₹1.40 L is the *unit cost* ceiling) |
| Term Loan max loan | ₹50,00,000 | **₹45,00,000** (₹50 L is the unit cost ceiling) |
| ELS max loan | ₹20,00,000 | **₹40,00,000**, tenure 12 years not 10 |
| Schemes present | 3 | **6** — added Udyam Nidhi, Aajeevika, Mahila Samriddhi |
| Women's rate | none modelled | **4% vs 6.5%**, as a women-only scheme |

The root error was treating each scheme's **unit-cost ceiling as its maximum loan**. Those are different numbers throughout NSFDC's catalogue; conflating them overstated MFS borrowing by ₹15,000 and Term Loan by ₹5 lakh, and understated margin money by the same amount. `CreditProductSeederTest` now pins every figure so this can't silently return.

**Income ceiling ₹5 lakh is correct** — revised w.e.f. 07.01.2026, up from the older ₹3 lakh "double the poverty line". The `ai_service` seed data still carries the superseded figure.

**Still unverified:** NSFDC does not publish Mahila Samriddhi's beneficiary rate. The 4% and 3-month moratorium come from State Channelising Agency listings, which disagree with each other on tenure (3 vs 3½ vs 4 years) and moratorium (3 vs 6 months). Seeded with `figuresVerified: false` and a per-product caveat rather than omitted — a women's concessional rate is a defining feature of this scheme family, and leaving it out would quote women a rate they need not pay.

### Remaining open questions

1. **Mahila Samriddhi's real terms** — needs confirmation from an SCA or NSFDC circular before demo.
2. **Mahila Kisan Yojana and Nari Arthik Sashaktikaran / Mahila Adhikarita** exist but no figures are published on any page I could reach. Not seeded rather than guessed.
3. **Moratorium default** — capitalised is proposed and implemented as the default; confirm against scheme documents.
4. **Is there any obtainable SCA/NBFC-MFI list?** If not, the locator honestly covers PSB/RRB only and says so, rather than mislabelling private banks.
