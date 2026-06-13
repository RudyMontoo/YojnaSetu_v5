# Yojna Setu — Deployment Guide

> **Full-stack deployment:** React.js (Vercel) + Spring Boot Gateway (Railway) + FastAPI AI Hub (Railway)

---

## 📁 Structure

```
deploy/
├── frontend/          → Vite React 18 → Vercel
├── backend/
│   ├── ai-hub/       → FastAPI (Python) → Railway Service 1
│   └── spring-gateway/ → Spring Boot (Java 17) → Railway Service 2
```

---

## 🐍 Step 1 — Deploy FastAPI AI Hub (Railway)

1. Push `deploy/backend/ai-hub/` to your testing repo
2. On Railway: **New Project → Deploy from GitHub** → select `deploy/backend/ai-hub`
3. Set **Environment Variables:**
   ```
   GROQ_API_KEY=your_groq_key        # console.groq.com (free)
   SARVAM_API_KEY=your_sarvam_key    # optional, for multilingual wizard
   ```
4. Railway auto-detects `Procfile` → deploys FastAPI
5. Note the URL: `https://your-ai-hub.railway.app`

---

## ☕ Step 2 — Deploy Spring Boot Gateway (Railway)

1. Push `deploy/backend/spring-gateway/` to your testing repo
2. On Railway: **New Project → Deploy from GitHub** → select `deploy/backend/spring-gateway`
3. Railway uses `Dockerfile` to build the Spring Boot jar
4. Set **Environment Variables:**
   ```
   FASTAPI_URL=https://your-ai-hub.railway.app
   FRONTEND_URL=https://your-app.vercel.app
   JWT_SECRET=any-long-random-string-here
   ```
5. Note the URL: `https://your-gateway.railway.app`

> **Note:** `pom.xml` uses Maven. Railway will run `mvn package -DskipTests` automatically.

---

## ⚛️ Step 3 — Deploy React Frontend (Vercel)

1. Push `deploy/frontend/` to your testing repo
2. On Vercel: **New Project → Import from GitHub** → select `deploy/frontend`
3. **Build Settings** (Vercel auto-detects Vite):
   - Build Command: `npm run build`
   - Output Directory: `dist`
4. Set **Environment Variable:**
   ```
   VITE_API_URL=https://your-gateway.railway.app
   ```
5. Deploy → get your Vercel URL! 🎉

---

## 🔑 API Keys Needed

| Key | Where to Get | Cost |
|-----|-------------|------|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | **Free** |
| `SARVAM_API_KEY` | [dashboard.sarvam.ai](https://dashboard.sarvam.ai) | Free tier |

---

## 🧪 Local Testing

```bash
# 1. Start FastAPI AI Hub
cd deploy/backend/ai-hub
pip install -r requirements.txt
GROQ_API_KEY=xxx uvicorn main:app --port 8001
# → http://localhost:8001/docs

# 2. Start Spring Boot Gateway  
cd deploy/backend/spring-gateway
FASTAPI_URL=http://localhost:8001 ./mvnw spring-boot:run
# → http://localhost:8080/api/health

# 3. Start React Frontend
cd deploy/frontend
VITE_API_URL=http://localhost:8080 npm run dev
# → http://localhost:5173
```

---

## 🗃️ What's in the Deploy (vs Full Project)

| Feature | Deploy Version | Full Project |
|---------|---------------|-------------|
| Chat (Groq Llama 70B) | ✅ | ✅ |
| Agent Interview | ✅ | ✅ |
| Status Tracker (6 portals) | ✅ | ✅ |
| Multilingual Apply Guide | ✅ (Sarvam) | ✅ |
| CSC Locator (OSM) | ✅ | ✅ |
| Voice (Whisper/Sarvam STT) | ❌ (GPU needed) | ✅ |
| ChromaDB Vector Search | ❌ (replaced by Groq) | ✅ |
| Spring Boot Auth (JWT) | ✅ | (planned) |
| PII Masking | ✅ (in AI Hub) | ✅ |
