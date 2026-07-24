# Deploying Yojna Setu to Azure Container Apps

Three containers on **Azure Container Apps** (the Cloud Run equivalent — serverless,
scale-to-zero, native WebSockets for chat + voice):

```
Browser ──HTTPS──> frontend (nginx, EXTERNAL ingress, public URL)
                      │  reverse-proxies, single-origin
                      ├─ /api/*                    ─> spring-gateway (INTERNAL)
                      └─ /ws /agents /ocr /voice …  ─> ai-service     (INTERNAL)
                                                          │
                                    spring-gateway <──internal──> ai-service
                                                          │
                                              MongoDB Atlas M0 (external, free)
```

Only the frontend is publicly reachable; the two backends use **internal** ingress
(reachable only inside the Container Apps environment). Auth cookies stay
`httpOnly` + `SameSite` because everything is one origin behind the nginx proxy.

## Prerequisites
- `az login` done, on the **Azure for Students** subscription
- `az extension add --name containerapp`
- Resource providers registered: `Microsoft.App`, `Microsoft.ContainerRegistry`,
  `Microsoft.OperationalInsights` (done once — the deploy assumes these)
- **MongoDB Atlas M0** (free) — see below. This is the only thing you must create by hand.

## 1. MongoDB Atlas M0 (free, ~5 min)
1. https://cloud.mongodb.com → **Build a Database** → **M0** (free) → region **Mumbai (ap-south-1)**.
2. **Database Access** → add a user (username + password).
3. **Network Access** → Add IP → **Allow access from anywhere** (`0.0.0.0/0`).
   (Container Apps egress IPs are dynamic; lock this down later with a NAT gateway.)
4. **Connect → Drivers** → copy the `mongodb+srv://…` string, insert the password.
5. Paste it as `MONGODB_URI=` in `deploy/azure/.env.deploy`.

## 2. Fill secrets
`deploy/azure/.env.deploy` (gitignored) is already prefilled with the encryption
key, Aadhaar salt, internal key, and LLM keys reused from your local config — only
`MONGODB_URI` is blank. Fill it and you're set. Never commit this file.

## 3. Deploy
```bash
bash deploy/azure/deploy.sh
```
Builds all 3 images in the cloud (ACR), then create-or-updates the 3 apps and
wires their URLs together. First run ~10–20 min (the ai_service image is large).
Re-running redeploys the latest source. **After the first run**, copy the printed
`ACR=…` line into `.env.deploy` so redeploys reuse the same registry.

The script prints the public URL at the end.

## 4. Log in / verify
OTP delivery isn't wired yet, so the code prints to the Spring log (dev fallback):
```bash
az containerapp logs show -g yojna-setu -n spring-gateway --follow
```
Request an OTP in the UI, read it from the log, sign in. Smoke-test: catalogue
loads, chat replies, profile saves.

## Known limitations of THIS deploy (honest)
- **No Ollama in cloud** (`OLLAMA_ENABLED=0`): the local vision-OCR / bulk-LLM path
  is gone. Chat uses Gemini/Groq (free-tier quota). The Jan-Sahayak **Lens**
  (vision document verify) degrades — it needs the local vision model; expect a
  "couldn't read" response until a cloud vision model is wired.
- **JWT private key is baked into the Spring image** (private ACR). Fine for a
  demo; before real users, move it to a Container Apps **secret volume** and set
  `JWT_PRIVATE_KEY_PATH` at it, then rebuild without the `COPY keys/` line.
- **Atlas open to 0.0.0.0/0** — tighten before real users.
- **`min-replicas 1`** keeps latency low but always-on burns Student credit.
  Drop ai-service to `--min-replicas 0` to scale-to-zero (cold starts ~30–60s while
  torch/mediapipe load) if credit runs low.

## Teardown (stop all spend)
```bash
az group delete -n yojna-setu --yes --no-wait
```
