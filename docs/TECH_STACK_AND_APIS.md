# Yojna Sarthi — APIs, Services & Open-Source Stack

Every external service and major open-source library this project actually uses.
Generated from real code: `ai_service/requirements.txt`, `frontend/package.json`,
`deploy/backend/spring-gateway/pom.xml`, `deploy/azure/deploy.sh`, and the `.env` files.

Last verified: 2026-08-03

---

## 1. External APIs / Paid & Freemium Services

| # | Service | What it does here | Where it's used | Cost tier | Status |
|---|---|---|---|---|---|
| 1 | **Brevo** (SMTP relay) | Email OTP login **and** Agent 6 nudge reminder emails | `ai_service/utils/email_sender.py`, `EmailService.java` | Free (300 emails/day) | ✅ LIVE |
| 2 | **Google Gemini 2.5 Flash** | Main LLM — orchestrator, all agent reasoning, scheme normalisation | `langchain-google-genai` across `ai_service/graph/` | Free tier / pay-as-you-go | ✅ LIVE |
| 3 | **Groq** | Fast LLM fallback / alternate inference | `langchain-groq` | Free tier | ✅ configured |
| 4 | **Sarvam AI** | Indian-language voice — **Saaras v3** (STT) + **Bulbul v3** (TTS) | `ai_service/routers/voice_ws_router.py` | Paid credits | ✅ LIVE |
| 5 | **MongoDB Atlas** | Primary database + **Atlas Vector Search** for scheme retrieval | Both backends | M0 free / M10 | ✅ LIVE |
| 6 | **Firebase Authentication** | Phone-number login (Google sends the SMS — no DLT/SIM needed) | `frontend` (firebase JS), `firebase-admin` in Spring | Free (Spark) | ✅ LIVE |
| 7 | **Microsoft Azure** | Hosting — Container Apps, Container Registry (ACR), Blob backups | `deploy/azure/deploy.sh` | Student credits | ✅ LIVE |
| 8 | **Twilio (WhatsApp)** | Agent 6 nudges — *fallback channel only* | `ai_service/utils/whatsapp_sender.py` | Pay-per-msg | ⚠️ Dry-run (needs WhatsApp Business approval) |
| 9 | **MyScheme.gov.in** | Primary scheme source — sitemap scrape, 1,230+ schemes | `ai_service/discovery/` | Free / public | ✅ LIVE |
| 10 | **PIB RSS** | New-scheme detection within ~60 min of announcement | `discovery/sources/pib_rss` | Free / public | ⚠️ config pending |
| 11 | **data.gov.in** | Open Government Data API | `DATAGOVIN_API_KEY` | Free API key | ❌ Not a scheme source (holds stats *about* schemes) |
| 12 | **Ollama** (self-hosted) | Local no-quota LLM for bulk jobs (rules backfill, discovery) | `OLLAMA_ENABLED` | Free (runs on own machine) | ✅ optional |
| 13 | **YouTube Data API** | Scheme explainer video lookup | `YOUTUBE_API_KEY` | Free quota | ✅ configured |
| 14 | **CPGRAMS / pgportal.gov.in** | Grievance filing guidance (read-only, self-file) | Agent 5 | Free / public | ✅ guidance path |

> **Deliberately NOT used:** DLT/SMS gateways, WhatsApp Business API, paid OCR APIs, LiveKit, OpenAI.

---

## 2. Open-Source — Python Backend (`ai_service`)

### AI / Agent Framework
| Package | Version | Purpose |
|---|---|---|
| `langgraph` | 1.1.6 | **13-agent StateGraph orchestrator** — the core of the system |
| `langchain` | 1.2.15 | LLM tool/chain abstractions |
| `langchain-core` | 1.4.8 | Shared primitives |
| `langchain-community` | 0.4.1 | Community integrations |
| `langchain-google-genai` | 4.2.6 | Gemini client |
| `langchain-groq` | 1.1.2 | Groq client |

### Vector Search / Embeddings
| Package | Version | Purpose |
|---|---|---|
| `sentence-transformers` | 5.4.1 | 384-dim scheme embeddings (open-source, runs locally) |
| `chromadb` | 1.5.7 | Local vector store (dev; Atlas Vector Search in prod) |
| `numpy` | 2.4.4 | Array ops |

### Web / API
| Package | Version | Purpose |
|---|---|---|
| `fastapi` | 0.135.3 | AI service — REST + WebSockets |
| `uvicorn[standard]` | 0.44.0 | ASGI server |
| `pydantic` | 2.13.1 | Request/response validation |
| `python-multipart` | 0.0.26 | File uploads |
| `motor` | 3.7.1 | Async MongoDB driver |
| `pyjwt[crypto]` | 2.13.0 | Verifies Spring Boot's RS256 JWT |
| `requests` | 2.33.1 | HTTP client |
| `python-dotenv` | 1.2.2 | Env loading |

### Voice (real-time)
| Package | Version | Purpose |
|---|---|---|
| `pipecat-ai[sarvam,silero]` | 1.5.0 | Streaming voice pipeline (STT → LangGraph → TTS) |

### OCR & Documents
| Package | Version | Purpose |
|---|---|---|
| `easyocr` | 1.7.2 | **Primary OCR engine** — Aadhaar / income certs (open-source) |
| `opencv-python-headless` | 4.13.0.92 | Image preprocessing |
| `pillow` | 12.2.0 | Image handling |
| `pypdf` | 6.10.2 | PDF parsing |
| `pdf2image` | 1.17.0 | PDF → image (needs `poppler-utils`) |
| `python-magic` | 0.4.27 | **Real file-byte MIME sniffing** (security rule #2) |

### Computer Vision
| Package | Version | Purpose |
|---|---|---|
| `mediapipe` | 0.10.35 | **Agent 11** — FaceLandmarker liveness detection (Google, open-source) |

### Scraping
| Package | Version | Purpose |
|---|---|---|
| `beautifulsoup4` | 4.14.3 | HTML parsing |
| `lxml` | 6.0.4 | Fast XML/HTML backend |

### Messaging & Testing
| Package | Version | Purpose |
|---|---|---|
| `twilio` | 9.10.9 | WhatsApp nudges (fallback) |
| `pytest` | 9.1.1 | Test suite (104 tests) |
| `pytest-asyncio` | 1.4.0 | Async tests (`asyncio_mode=auto`) |

---

## 3. Open-Source — Java Gateway (Spring Boot 3.2 / Java 17)

| Dependency | Purpose |
|---|---|
| `spring-boot-starter-web` | REST API (`/api/v2/*`) |
| `spring-boot-starter-webflux` | Reactive HTTP client → FastAPI |
| `spring-boot-starter-data-mongodb` | MongoDB ODM |
| `spring-boot-starter-security` | Auth + filter chain |
| `spring-boot-starter-validation` | Bean validation |
| `spring-boot-starter-mail` | **Brevo SMTP** — email OTP |
| `spring-security-crypto` | Password / hash utilities |
| `jjwt-api` + `jjwt-impl` + `jjwt-jackson` | **RS256 JWT** signing (httpOnly cookies) |
| `firebase-admin` | Verifies Firebase phone-login tokens |
| `twilio` | WhatsApp SDK |
| `bucket4j_jdk11-core` | **Rate limiting** (3 OTP/hour per phone) |
| `lombok` | Boilerplate reduction |
| `spring-boot-starter-test` | JUnit 5 tests |

---

## 4. Open-Source — Frontend (React 19 PWA)

### Core
| Package | Version | Purpose |
|---|---|---|
| `react` / `react-dom` | 19.2.0 | UI framework |
| `vite` | 7.3.1 | Build tool / dev server |
| `react-router-dom` | 7.13.1 | Routing (13 pages) |
| `axios` | 1.13.6 | REST client → Spring Boot |
| `vite-plugin-pwa` | 1.3.0 | **PWA / offline support** (needed by Agent 12) |
| `@vitejs/plugin-legacy` | 7.2.1 | Old-browser support (low-end Android) |

### Voice
| Package | Version | Purpose |
|---|---|---|
| `@pipecat-ai/client-js` | 1.12.0 | Voice client (lazy-loaded chunk) |
| `@pipecat-ai/websocket-transport` | 1.7.0 | WS transport → FastAPI |

### UI / Visuals
| Package | Version | Purpose |
|---|---|---|
| `tailwindcss` | — | Styling |
| `framer-motion` | 12.34.3 | Animations |
| `lucide-react` | 0.576.0 | Icon set |
| `three` + `@react-three/fiber` + `@react-three/drei` | 0.185 / 9.6 / 10.7 | 3D visuals |
| `qrcode` | 1.5.4 | **Agent 12** — offline DLC QR generation |

### Auth
| Package | Version | Purpose |
|---|---|---|
| `firebase` | 12.16.0 | Phone-number login (client SDK) |

### Tooling
`eslint` 9.39, `eslint-plugin-react-hooks`, `eslint-plugin-react-refresh`, `terser`, `globals`

---

## 5. Browser-Native APIs (no library, zero cost)

| API | Used for |
|---|---|
| **WebCrypto (RSA-2048)** | Agent 12 — offline DLC signing |
| **MediaRecorder** | Voice capture |
| **Service Worker / Cache API** | PWA offline queue |
| **IndexedDB** | Offline nudge/DLC queue |
| **getUserMedia** | Agent 11 camera liveness |

---

## 6. Security (all open-source / self-hosted — no paid vendor)

| Mechanism | Implementation |
|---|---|
| PII encryption at rest | **AES-256 Fernet** (`cryptography`) — name, dob, phone |
| Aadhaar handling | **SHA-256 + server-side salt**, raw UID never stored |
| Auth tokens | **RS256 JWT** in httpOnly cookies (60-min access, 7-day refresh) |
| File-upload safety | `python-magic` byte-signature MIME check |
| Prompt injection | Custom `injection_guard.py` |
| PII in logs | Custom masking middleware |
| Rate limiting | Bucket4j |

---

## 7. Cost Summary

| Category | Monthly |
|---|---|
| Brevo email | ₹0 (free tier) |
| Firebase phone auth | ₹0 (Spark) |
| MongoDB Atlas | ₹0 (M0 dev) |
| Azure hosting | ₹0 (student credits) |
| Gemini / Groq | ₹0–low (free tier) |
| Sarvam voice | paid credits (only cost) |
| **All open-source libraries** | **₹0** |

The project runs on **one paid API (Sarvam)**; everything else is free-tier or open-source.
