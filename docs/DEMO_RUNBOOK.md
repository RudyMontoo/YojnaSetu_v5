# Demo runbook — SIH PS 26092

One page. Follow it in order. Everything here was verified working on
2026-09-12.

---

## 1. Bring the stack up (5 min before you present)

Five things must be listening. Check all of them before you open a browser:

```bash
for p in 27017 8090 8000 11434 5173; do nc -z localhost $p && echo "$p up" || echo "$p DOWN"; done
```

| Port | What | Start it with |
|---|---|---|
| 27017 | MongoDB | `sudo systemctl start mongod` |
| 8090 | Spring gateway | `cd deploy/backend/spring-gateway && set -a && source .env && set +a && PORT=8090 mvn -o spring-boot:run` |
| 8000 | ai_service | `cd <repo root> && set -a && source ai_service/.env && set +a && SPRING_BOOT_INTERNAL_URL=http://localhost:8090 python3 -m uvicorn ai_service.main:app --port 8000` |
| 11434 | **Ollama** | `ollama serve` |
| 5173 | frontend | `cd frontend && GATEWAY_PORT=8090 npm run dev` |

**Why 8090 and not 8080:** an Airflow container holds 8080 on this machine.
If you free 8080, drop `PORT=` and `GATEWAY_PORT=` and everything defaults
back. Do **not** hand-edit `vite.config.js`.

**Ollama is not optional.** Gemini's free tier is 20 requests/day and is
routinely exhausted; Groq rate-limits under load. Ollama is the only
provider with no quota, and it is the last link in the fallback chain. If
it is down and the other two are throttled, the chat returns a 500 on
stage.

### One-command sanity check

```bash
curl -s localhost:5173/api/health                       # must say "Yojna Sarthi Gateway"
curl -s localhost:5173/api/v2/sih/credit/products | head -c 60   # must return JSON, not HTML
```

If `/api/health` returns `{"error":"API route not found"}` you are talking
to **Airflow**, not the gateway — the proxy port is wrong.

---

## 2. The demo path — rehearse this exact sequence

Open **http://localhost:5173/startgo** in a **fresh incognito window**
(a stale service worker will otherwise serve you an old build).

> **Use an SC applicant. Not ST.** NSFDC's mandate is Scheduled Castes
> only — ST is a different corporation (NSTFDC) — so every scheme correctly
> rejects an ST applicant. That is factually right and it looks broken.
> Know the answer, don't demo the path.

**Type (or tap the chips):**

1. `I want to start a small tea shop`
2. `The total cost would be about 1 lakh`
3. `My annual family income is 1.5 lakh`
4. `I am SC and a woman`

**What appears — this is your money shot:**

| Scheme | Rate | Monthly EMI |
|---|---|---|
| **MSY** | **6.0%** | **₹2,584** |
| MFS | 6.5% | ₹2,803 |
| AMFY | 15.0% | ₹3,238 |

**Say this out loud:** *"She's shown the 6% women-only scheme first. Run
the identical case as a man and MSY disappears — the best rate available to
her is 6.5%. On a portal that just lists schemes, she would never have
found the cheaper one. And these figures come from the backend's
eligibility engine, not from the language model — the model is structurally
incapable of producing a rupee figure."*

That one paragraph is your entire differentiation. Lead with it.

---

## 3. Questions you will be asked, and the honest answer

**"Where do these NSFDC figures come from?"**
Seeded from the problem statement's own parameters and NSFDC's public
scheme listing. Every product carries a `sourceNote`, and Mahila Samriddhi
is explicitly flagged `figuresVerified: false` because its 6% rate comes
from secondary sources, not NSFDC's own page. The branch confirms final
terms. *Don't overclaim this one — the flag is the answer.*

**"How does the application actually reach the bank?"**
It doesn't. It writes a tracked application record with a validated state
machine and an assigned branch. NSFDC's channel-partner roster isn't
publicly available, so the branch is chosen by the citizen from real
OpenStreetMap bank locations. Wiring a real partner needs an MoU, not more
code.

**"Is DigiLocker real?"**
The integration is built end-to-end against DigiLocker's published Partner
API and is switched off, because partner credentials need a business
registration. There's a simulation mode for demos where every response is
labelled `simulated: true` end to end, so nothing in the database can ever
be mistaken for a real verification.

**"Why only ~430 schemes, not thousands?"**
430 seeded and live. The discovery pipeline against myScheme.gov.in is
real and has been run live, but myScheme rate-limits to one request per two
seconds — a full ~4,700-scheme sync is a multi-hour background job, not
something we run mid-demo.

**"What stops the AI hallucinating a loan amount?"**
Architecture, not prompting. The model only extracts facts from what the
citizen said; the verdict and every figure come from a deterministic Java
service. We hit exactly this bug early — the UI quoted a scheme's
unit-cost ceiling as its loan cap, overstating one product by ₹15,000 and
another by ₹5 lakh — and the fix was to make the frontend structurally
incapable of being the source of a number.

**"Is it deployed?"**
Runs locally. Deployment config exists but a live public deployment isn't
part of this demo.

---

## 4. Known rough edges — don't let these surprise you

- **A submitted credit application doesn't appear in "track my
  application" yet.** `/status` and Profile still read the older welfare
  tracker collection. Submission works and is recorded; the citizen-facing
  timeline for it isn't built. Avoid clicking through to tracking after
  applying.
- **Voice replies fall back to gTTS.** Sarvam's TTS endpoint currently
  returns 400; speech-to-text works fine. Voice still functions, it just
  sounds less natural.
- **Aadhaar offline eKYC** parses a real UIDAI ZIP but reports
  `signatureVerified: false` without a production UIDAI certificate. Shown
  to the citizen as "not cryptographically verified in this deployment."
- **First response after a cold start is slow** (model warm-up). Send one
  throwaway message before the judges are watching.
