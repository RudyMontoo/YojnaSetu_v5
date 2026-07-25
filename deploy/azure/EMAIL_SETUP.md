# Email deliverability — move OTP mail off Gmail SMTP

**Why:** login OTP currently sends via Gmail SMTP. Gmail caps ~500/day and
unauthenticated bulk mail from a personal account lands in Spam/Promotions —
at pilot scale, real users silently can't log in. A transactional provider on
an **authenticated `yojsarthi.in` sender** (SPF + DKIM + DMARC) fixes both the
cap and inbox placement.

The code is already provider-agnostic SMTP — **no code change needed**. This is
a provider signup + DNS + `.env.deploy` update, then redeploy.

---

## 1. Pick a provider (recommended: Brevo)

| Provider | Free tier | Notes |
|---|---|---|
| **Brevo** (ex-Sendinblue) | 300 emails/day | Easiest domain auth, India-friendly, SMTP relay. Recommended. |
| Resend | 3,000/mo (100/day) | Very dev-friendly, clean dashboard. |
| SendGrid | 100/day | Works, more onboarding friction. |

300/day is plenty for OTP at pilot scale (each login = 1 email).

## 2. Authenticate the domain (the part that fixes deliverability)

In the provider dashboard: **Senders / Domains → add `yojsarthi.in` → Authenticate**.
It will show you records to add. In **GoDaddy → yojsarthi.in → DNS → Records**, add:

- **SPF** (TXT, host `@`): the provider's include, e.g. `v=spf1 include:spf.brevo.com ~all`
  *(if an SPF TXT already exists, merge the include into it — do NOT add a second SPF record)*
- **DKIM** (CNAME or TXT, host as shown, e.g. `brevo1._domainkey`, `brevo2._domainkey`): copy the exact values from the dashboard.
- **DMARC** (TXT, host `_dmarc`): start relaxed — `v=DMARC1; p=none; rua=mailto:rudrashr27@gmail.com`
- Any **verification TXT** the provider asks for.

Then click **Verify** in the dashboard. DNS can take minutes to a few hours to
propagate — verification passes once it does. Check with:
`dig TXT yojsarthi.in +short` and `dig CNAME brevo1._domainkey.yojsarthi.in +short`

## 3. Get SMTP credentials

Dashboard → **SMTP & API → SMTP**. You'll get: host, port (587), login, and an
SMTP key (password). Create a **verified sender** like `no-reply@yojsarthi.in`.

## 4. Update `deploy/azure/.env.deploy` (gitignored — never commit)

Set these keys in `.env.deploy` (values come from the Brevo SMTP page — do **not**
paste any real key into this doc or any tracked file):

- `SMTP_HOST` → `smtp-relay.brevo.com`
- `SMTP_PORT` → `587`
- `SMTP_USERNAME` → the SMTP login the Brevo dashboard shows
- `SMTP_PASSWORD` → the generated Brevo SMTP key *(secret — .env.deploy only)*
- `MAIL_FROM` → `no-reply@yojsarthi.in`
- `MAIL_FROM_NAME` → `Yojna Sarthi`
- `MAIL_ENABLED` → `true`  *(only after the domain shows fully authenticated)*

## 5. Redeploy the gateway + verify

```
./deploy/azure/deploy.sh            # or just roll spring-gateway
```
Then send yourself an OTP from the live sign-in page and confirm:
- it arrives in **Inbox** (not Spam),
- From shows **Yojna Sarthi <no-reply@yojsarthi.in>**,
- Subject is "Your Yojna Sarthi login code" (OTP is in the body, not the subject).

Deliverability check: paste the received mail's headers into
[mail-tester.com](https://www.mail-tester.com) — aim for 9–10/10 (green SPF/DKIM/DMARC).

---

### Notes
- The Spring code (`EmailService`) already: names the From header, keeps the OTP
  out of the subject, and enforces a per-recipient send throttle (30s / 5-per-hour).
- Once WhatsApp OTP ships (deferred to after 1st week of Aug), email stays as the
  universal fallback channel — keep this configured regardless.
