<!-- ░░░░░░░░░░░░░░░░░░░░░░░░░  YOJNA SETU  ░░░░░░░░░░░░░░░░░░░░░░░░░ -->

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0d1b3e,45:1a3a6e,100:ff9933&height=210&section=header&text=Yojna%20Setu&fontSize=76&fontColor=ffffff&animation=fadeIn&fontAlignY=36&desc=%E0%A4%B8%E0%A5%87%E0%A4%A4%E0%A5%81%20%E2%80%94%20the%20bridge%20between%20a%20citizen%20and%20their%20rights&descAlignY=58&descSize=18" width="100%"/>

<a href="https://github.com/RudyMontoo/YojnaSetu_v5">
  <img src="https://readme-typing-svg.demolab.com/?font=Poppins&weight=600&size=21&pause=1200&color=FF9933&center=true&vCenter=true&width=820&lines=3%2C500%2B+welfare+schemes.+22+languages.+One+conversation.;Discover+%E2%86%92+Apply+%E2%86%92+Track+%E2%86%92+Get+paid.;Voice-first.+WhatsApp-native.+DPDP-2023+compliant." alt="tagline"/>
</a>

<br/><br/>

![Schemes](https://img.shields.io/badge/Schemes-3%2C500%2B-ff9933?style=for-the-badge)
![Languages](https://img.shields.io/badge/Languages-22-138808?style=for-the-badge)
![Agents](https://img.shields.io/badge/AI_Agents-13-000080?style=for-the-badge)
![Compliance](https://img.shields.io/badge/DPDP_Act-2023-blue?style=for-the-badge)

![Python](https://img.shields.io/badge/Python_3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?style=flat-square&logo=langchain&logoColor=white)
![Spring](https://img.shields.io/badge/Spring_Boot_3.2-6DB33F?style=flat-square&logo=springboot&logoColor=white)
![React](https://img.shields.io/badge/React_PWA-61DAFB?style=flat-square&logo=react&logoColor=black)
![MongoDB](https://img.shields.io/badge/MongoDB-47A248?style=flat-square&logo=mongodb&logoColor=white)

</div>

<br/>

<!-- ─────────────────────────────  THE HOOK  ───────────────────────────── -->

<div align="center">

### A 62-year-old farmer in Uttar Pradesh opens WhatsApp and types in Hindi.

</div>

```text
👵  "main UP ka kisan hoon, meri saalana aay 1.5 lakh hai. mujhe kya milega?"

🏛️  Namaste! Aapke liye ye yojnayein hain —
    • PM Kisan Samman Nidhi        →  ₹6,000 / saal, seedhe khaate mein
    • Natural Farming Mission      →  ₹15,000 / hectare
    • Agriculture Infrastructure Fund

    Kaunsi ke liye apply karna hai? Main step-by-step bataunga. 📄
```

<div align="center">

**That's it. No portal. No form. No English. No middleman.**
Just a conversation that ends with money in a bank account.

</div>

---

## 🎯 Why Yojna Setu exists

> [!NOTE]
> India runs **3,500+ welfare schemes** worth *lakhs of crores*. The people they were built for — farmers, students, widows, the elderly, daily-wage workers — often **never find them.** Buried in portals they can't navigate, written in a language that isn't theirs, gated behind forms and jargon and information they don't have.

Yojna Setu closes that gap with **one multilingual conversation.** It takes a citizen from *"what am I even eligible for?"* → discovery → application guidance → document checks → grievance tracking → and, for pensioners, **fully-offline proof-of-life** — all in their own language, by voice or WhatsApp.

Not a search engine over scheme PDFs. A **fleet of 13 specialised AI agents** that actually reason about *your* situation against *real, structured* government data.

---

## ✨ What makes it different

<table>
<tr>
<td width="50%" valign="top">

### 🗣️ Speaks your language — literally
22 Indian languages, **voice-first**. Real-time speech in and out via Pipecat + Sarvam (Saaras v3 STT, Bulbul v3 TTS) — the *same* 13-agent brain answers whether you type, talk, or WhatsApp.

</td>
<td width="50%" valign="top">

### 🤖 13 agents, not one chatbot
A LangGraph `StateGraph` routes each message to the right specialist — eligibility, discovery, comparison, financial planning, grievances — each grounded in Mongo data, never hallucinating a scheme.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 📶 Works when the network doesn't
Pensioners prove they're alive **offline** — an RSA-2048 key signed in the browser (WebCrypto), turned into a QR + sync-on-reconnect. No connectivity required to survive.

</td>
<td width="50%" valign="top">

### 🔒 Built for real citizen data
DPDP-2023 compliant from day one: AES-256 field encryption, SHA-256 Aadhaar hashing (never raw), httpOnly RS256 JWTs, append-only audit logs, PII stripped from every log line.

</td>
</tr>
</table>

---

## 🏗️ Architecture at a glance

```mermaid
graph TD
    classDef fe fill:#61DAFB,stroke:#0b3,stroke-width:1px,color:#000
    classDef gw fill:#6DB33F,stroke:#333,stroke-width:1px,color:#fff
    classDef ai fill:#FF9933,stroke:#333,stroke-width:1px,color:#000
    classDef db fill:#47A248,stroke:#333,stroke-width:1px,color:#fff

    U((👤 Citizen)) -->|voice · text · WhatsApp · scan| FE[React PWA]:::fe
    FE -->|REST · auth/profile/apps| GW[Spring Boot Gateway<br/>OTP → RS256 JWT httpOnly]:::gw
    FE -->|WebSocket · chat + voice — DIRECT| ORC[FastAPI Orchestrator<br/>LangGraph StateGraph]:::ai

    GW <-->|X-Internal-Key| ORC
    GW --> DB[(MongoDB<br/>schemes · profiles · apps<br/>grievances · audit …)]:::db
    ORC --> DB

    ORC --> A1[Eligibility]:::ai
    ORC --> A7[Financial Plan]:::ai
    ORC --> A8[Comparison]:::ai
    ORC --> A3[Application Guidance]:::ai
    ORC --> A5[Grievance Loop]:::ai
    ORC --> MORE[…9 more agents]:::ai

    A1 -->|Atlas Vector Search| DB
```

> [!IMPORTANT]
> **Voice goes *straight* to FastAPI over WebSocket — never through Spring Boot.** Spring is thread-per-connection (blocking); 100 concurrent voice calls would exhaust its pool. FastAPI is async ASGI and holds thousands of sockets natively. REST (auth, data) stays on Spring; every WebSocket lives on FastAPI. That split is the backbone of the whole system.

---

## 🛰️ The 13-agent fleet

| # | Agent | What it does for the citizen |
|:--:|---|---|
| 🧭 | **Orchestrator** | Reads intent, routes to the right specialist, screens for prompt-injection first |
| 1 | **Eligibility** | Vector-searches real schemes + scores them against *your* profile |
| 2 | **Discovery** | Keeps the catalogue fresh — 3,500+ schemes with structured eligibility rules |
| 3 | **Application Guidance** | Step-by-step how-to-apply + reads the *live* government form for you |
| 4 | **Document Verify** | PPO ↔ Aadhaar name/DOB mismatch check for pensioners |
| 5 | **Grievance** | Files & tracks complaints; guides CPGRAMS self-filing, records the reference |
| 6 | **Nudge** | WhatsApp reminders when you start an application but don't finish it |
| 7 | **Financial Planning** | Your total yearly benefit across all schemes, ranked by effort |
| 8 | **Comparison** | Two schemes, side by side, grounded in real data |
| 9 | **CSC Assist** | Helps operators find document alternatives — honest "no substitute" when true |
| 10 | **Analytics** | Aggregate drop-off / demand insights for administrators |
| 11 | **Biometric Assist** | Face-liveness for at-home proof-of-life *(pension release — in progress)* |
| 12 | **Offline Survival Proof** | RSA-signed Digital Life Certificate that works with **zero network** |

---

## 📱 Inside the app

<table>
<tr>
<td width="50%"><img src="docs/screenshots/home.png" alt="Home"/></td>
<td width="50%"><img src="docs/screenshots/sathi.png" alt="Sathi chat"/></td>
</tr>
<tr>
<td valign="top"><b>🏠 Home — <i>Namaste, Bharat</i></b><br/>The landing: <i>Find My Scheme</i> or explore all, a live feed of newly-added schemes across states, and a one-tap door to Sathi (chat or voice).</td>
<td valign="top"><b>💬 Sathi — the AI guide</b><br/>Ask about any scheme by <b>voice or text in any Indian language</b>. One message routes through the 13-agent LangGraph brain — eligibility, financial planning, comparison, grievances — grounded in real data.</td>
</tr>
<tr>
<td width="50%"><img src="docs/screenshots/schemes.png" alt="Schemes catalogue"/></td>
<td width="50%"><img src="docs/screenshots/status.png" alt="Status tracker"/></td>
</tr>
<tr>
<td valign="top"><b>📚 Schemes — Yojana Catalogue</b><br/>All <b>4,901 central & state schemes</b>, searchable with sector filters (Agriculture, Housing, Health, Pension…). Each card shows the real benefit + eligibility, extracted into structured rules.</td>
<td valign="top"><b>📊 Status — Application Tracker</b><br/>Every saved application through its lifecycle (Saved → In&nbsp;Progress → Submitted → Approved → Disbursed), plus <b>My Grievances</b> with their CPGRAMS reference numbers.</td>
</tr>
<tr>
<td width="50%"><img src="docs/screenshots/lens.png" alt="Jan-Sahayak Lens"/></td>
<td valign="top"><b>🔎 Lens — Jan-Sahayak (Agent 4)</b><br/>Scan an <b>Aadhaar, PAN, Voter ID, Ration Card, Passport or DL</b> — the ID is auto-detected by a local vision model that reads any Indian script. <b>Never saved to a server — processed in memory only.</b></td>
</tr>
</table>

<sub>Not shown: real-time voice call, offline Digital Life Certificate with face-liveness (Pension Seva), WhatsApp nudges, and the CSC-operator dashboard.</sub>

---

## 🎬 One citizen journey, end to end

```mermaid
sequenceDiagram
    participant C as 👤 Citizen
    participant G as Spring Gateway
    participant O as FastAPI Orchestrator
    participant D as MongoDB

    C->>G: OTP login
    G-->>C: httpOnly RS256 JWT 🍪
    C->>O: "kaunsi yojana milegi?" (cookie)
    O->>O: verify JWT · screen injection · classify intent
    O->>D: vector search + eligibility score
    D-->>O: real matching schemes
    O-->>C: grounded reply — schemes + benefits
    C->>G: Save application
    C->>O: "meri application ka status?"
    O->>D: read citizen's own applications
    O-->>C: "PM Kisan — submitted ✓"
    Note over C,O: Later — Agent 6 pings on WhatsApp:<br/>"you left one half-finished 👀"
```

---

## 🧠 The intelligence layer

> [!TIP]
> **Three LLMs, one graceful chain.** Every reasoning call tries **Gemini 2.5 Flash** first → falls back to **Groq (Llama-3.3-70B)** on quota → then to a **local Ollama** model, so the app *never* hard-fails on a dead quota. Bulk jobs (extracting eligibility rules for thousands of schemes) run entirely on the free local model — ₹0, no limits.

- **Retrieval** — MongoDB Atlas `$vectorSearch` in prod, brute-force cosine locally · `all-MiniLM-L6-v2` (384-dim)
- **Grounding** — agents answer *only* from real Mongo scheme docs; a scheme it can't cite, it won't invent
- **Guardrails** — prompt-injection screen + PII masking on **every** input before it reaches any model

---

## 🛠️ Tech stack

<details open>
<summary><b>Expand full stack</b></summary>

<br/>

| Layer | Technology |
|---|---|
| **Orchestration** | LangGraph `StateGraph` · shared turn-logic across REST / WebSocket / voice |
| **AI service** | FastAPI · Python 3.12 · async ASGI |
| **Gateway** | Spring Boot 3.2 · Java 17 · OTP auth · Bucket4j rate limiting |
| **Database** | MongoDB (Atlas prod / Docker dev) |
| **Auth** | Phone OTP → RS256 JWT in httpOnly · `SameSite=Strict` cookies |
| **Crypto** | AES-256-GCM fields · SHA-256+salt Aadhaar/PPO · RSA-2048 WebCrypto (offline DLC) |
| **Voice** | Pipecat · Sarvam Saaras v3 (STT) · Bulbul v3 (TTS) · server-side VAD |
| **Messaging** | Twilio WhatsApp (Business API) |
| **Frontend** | React + Vite · installable PWA · code-split routes · Framer Motion |
| **Testing** | 90 pytest + 15 JUnit · CI on every push |

</details>

---

## 🚀 Run it locally

<details>
<summary><b>Step-by-step</b></summary>

<br/>

**Prerequisites:** Python 3.12 · Node 18+ · Java 17 · Maven · Docker

```bash
# 1 — database
docker run -d --name yojna-mongo -p 27017:27017 mongo:7

# 2 — AI service (run from repo root)
cd ai_service && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill GEMINI/GROQ/SARVAM keys + MONGODB_URI
cd .. && uvicorn ai_service.main:app --reload --port 8000

# 3 — gateway
cd deploy/backend/spring-gateway
mvn spring-boot:run -Dspring-boot.run.profiles=local

# 4 — frontend
cd frontend && npm install && npm run dev
```

> 🌐 App → `localhost:5173` · API docs → `localhost:8000/docs` · Gateway → `localhost:8080`

</details>

---

## 🛡️ Security & compliance

| Guarantee | How |
|---|---|
| **No PII in the clear** | AES-256-GCM on name/dob/phone before every write |
| **Aadhaar never stored raw** | SHA-256 + server salt, one-way, never decrypted |
| **No tokens in JavaScript** | RS256 JWT lives only in httpOnly cookies |
| **Nothing leaks to logs** | PII-redaction filter strips Aadhaar/phone/PAN/email from every log line |
| **Voice is ephemeral** | Audio processed in memory, never written to disk — only the transcript persists |
| **Right to erasure** | DPDP cascade wipes a citizen across every collection in seconds |

---

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:ff9933,50:1a3a6e,100:0d1b3e&height=120&section=footer&text=Jan%20Jan%20ko%20Yojana%20se%20Jodo&fontSize=22&fontColor=ffffff&fontAlignY=68" width="100%"/>

<sub>Built for social good · every scheme sourced from verifiable Indian government public portals</sub>

</div>
