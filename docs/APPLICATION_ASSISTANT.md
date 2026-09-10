# Credit Application Assistant

Conversational, goal-directed slot-filling for starting an SC concessional
credit application by chat instead of a form — implemented across
`ai_service` (FastAPI) and `frontend` (React), handing off to a Spring
gateway endpoint that already exists and is already tested.

## Why a separate flow, not another orchestrator agent

`ai_service/graph/orchestrator.py`'s existing agents each answer one turn:
classify intent, compose a reply, done. Starting an application is not
one turn — it's a small state machine (pin a scheme, fill required slots,
summarize, wait for confirmation) that needs to survive across several
messages. Rather than bolt multi-turn state onto the orchestrator's
single-turn `ChatResponse` contract, the split is:

- **`credit_application` intent** (added to `graph/intent_classifier.py`)
  detects "I want to apply" and routes to
  `graph/agents/credit_application_intro.py` — a node whose ONLY job is a
  warm handoff reply. It does no slot-filling itself.
- **`POST /application-assistant/chat`** (`routers/application_assistant_router.py`)
  is where the real conversation happens, turn by turn, until a
  `structured_payload` comes back.
- The **frontend** (`ChatPage.jsx`) sees `intent === "credit_application"`
  in the orchestrator's response and flips a ref that routes every
  subsequent message to `applyChat()` instead of the normal chat send path
  — until a payload is confirmed, at which point it flips back.

Same `session_id` throughout; only the endpoint changes, so it reads one
continuous conversation, not two.

## Conversation schema

Stored on the session document in `conversation_sessions.applicationContext`
(sibling to that collection's existing `messages` array):

```python
{
    "scheme_code": "micro-finance" | None,     # pinned once resolved
    "slots": {
        "_scheme_name": "Micro Finance Scheme (MFS)",  # display only, never sent to Spring
        "estimatedCost": 120000 | None,
        "annualIncome": 250000 | None,
        "verificationMode": "manual" | "offline" | None,  # ASKED, never assumed — see below
        "category": "sc" | None,                # defaults to "sc" in the payload if never stated
        "gender": "female" | None,               # only asked if it changes scheme eligibility
        "tenureMonths": 36 | None,                # optional — None is fine, form uses the scheme default
        "moratoriumMode": "capitalise" | None,    # optional, same as above
    },
    "missing_required": ["estimatedCost", "annualIncome", "verificationMode"],  # recomputed every turn
    "awaiting_confirmation": False,   # True once required slots are filled and the summary was shown
    "confirmed": False,               # True once the citizen said yes to the summary
}
```

Required slots: `estimatedCost`, `annualIncome`, `verificationMode`.
Everything else is optional and either defaulted (`category` → `"sc"`) or
left `None` for the eventual form to pre-fill sensibly
(`tenureMonths`/`moratoriumMode` from the scheme's own defaults).

### Why verificationMode is asked, not defaulted

`VerificationMode.java` has four modes but only two are available:
`MANUAL` (citizen uploads scans, branch rep verifies) and `OFFLINE`
(documents presented in person at a branch/CSC). `DIGILOCKER` and
`ACCOUNT_AGGREGATOR` are declared but gated off (`isAvailable() == false`)
and rejected by `CreditApplicationService.create()` — so this assistant
never offers them; proposing a route the server will refuse would be worse
than not mentioning it.

Between the two that *are* live, defaulting silently to `MANUAL` would
assume every applicant can photograph, scan, and upload their own caste and
income certificates. For this scheme's target group that assumption
excludes people, so the choice is a question the citizen answers, and it
appears in the confirmation summary they say yes to. Deterministic
extraction handles both answers in English and Hinglish, and treats a
branch/CSC mention as `OFFLINE` even when the sentence also contains
"upload" ("I'll go to the branch, they can upload it there").

### Turn logic (`ApplicationAssistant.process_message`)

1. No `scheme_code` pinned yet → try to resolve one from the message (a
   named scheme, or a pronoun reference to whatever scheme
   `schemesShown` last surfaced this session) → ask which scheme if it
   can't.
2. `awaiting_confirmation` and the message is affirmative → `confirmed=True`,
   build and return the payload.
3. `awaiting_confirmation` but NOT affirmative → treat as a correction, fall
   through to re-extract and re-summarize (never just re-asks the same
   question).
4. Merge new slots from this message (deterministic layer first, LLM layer
   only for what's still missing — see below).
5. Still missing required slots → ask for up to 2 of them.
6. Nothing missing → summarize and set `awaiting_confirmation=True`.

### Slot extraction — two layers, deterministic wins

`extract_slots_deterministic()` (pure regex, no LLM, fully unit-testable) is
tried first: explicit rupee/lakh amounts near an income/cost keyword,
category/gender keywords. Only if a required or optional slot is STILL
`None` after that does `_extract_slots_llm()` run — prompted to return
`null` for anything not explicitly stated, never to estimate. A
deterministic hit always wins over an LLM hit for the same key; the LLM
layer only ever fills gaps the regex layer left open.

This is the "never invents numbers" rule made structural, not just a prompt
instruction: the most explicit, provable extraction path runs first and
can't be silently overridden by a looser LLM read of the same sentence.

## Payload → Spring endpoint mapping

`ApplicationAssistant.build_payload()` outputs exactly `CreditApplicationController.create()`'s
request body shape (`deploy/backend/spring-gateway/.../CreditApplicationController.java`),
plus one extra frontend-only field:

| Payload key | Spring field | Source |
|---|---|---|
| `schemeCode` | *(not sent to Spring)* | routes the frontend to `/apply/:schemeCode` |
| `productId` | `productId` | `context.scheme_code` |
| `estimatedCost` | `estimatedCost` | required slot |
| `annualIncome` | `annualIncome` | required slot |
| `category` | `category` | optional slot, defaults `"sc"` |
| `tenureMonths` | `tenureMonths` | optional slot, `None` if unstated |
| `moratoriumMode` | `moratoriumMode` | optional slot, `None` if unstated |
| `verificationMode` | `verificationMode` | required slot — `"manual"` or `"offline"`, asked explicitly |

`partnerId`/`partnerName`/`partnerType` are deliberately NOT collected here
— `CreditApplicationService.assignPartner()` is a separate step, only valid
on a `DRAFT` application, and belongs to the (not-yet-built) application
form's own partner-selection UI, not this chat flow.

## Frontend handoff

```
ChatPage.jsx
  citizen: "Mujhe is scheme ke liye apply karna hai"
  → normal orchestrator turn (WS/REST) → intent === "credit_application"
  → applicationActiveRef.current = true

  every message after that:
  → ai.applyChat(message, sessionId, lang)  [frontend/src/lib/api.js]
  → POST /application-assistant/chat
  → { bot_reply, structured_payload }

  once structured_payload is present:
  → message bubble renders a "Continue with application" button
    (t('chat.continueApplication'))
  → onClick: navigate(`/apply/${payload.schemeCode}`, { state: payload })
  → applicationActiveRef.current = false
```

`/apply/:schemeId` (`frontend/src/pages/ApplyPage.jsx`) is currently a
**stub** — it reads `location.state` and displays the collected fields as
JSON with a "coming soon" message. The real pre-filled form (calling
`POST /api/v2/sih/applications` with this exact payload shape) is a
separate, not-yet-built page; this stub exists so the chat CTA has
somewhere real to land, and so the payload is visible/verifiable
end-to-end today.

## What's tested vs. hand-verified

`ai_service/tests/test_application_assistant.py` covers, without any
network/LLM call: deterministic slot extraction (English + Hinglish, cost
vs. income disambiguation, category/gender keywords, the "never invents a
bare number" rule), affirmative/negative detection, payload shape, and
`process_message()`'s scheme-resolution and confirmation branches with the
products-fetcher and LLM boundary faked.

**Not covered by these tests, and not yet run against a live LLM/Spring
instance in any environment with real credentials**: the LLM-composed
reply text itself (ask/summary phrasing), and the full round trip through
a real Spring gateway's `/api/v2/sih/credit/products`. Treat this as
implemented-and-unit-tested, not implemented-and-live-verified.
