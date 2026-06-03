"""
Jan Sahayak Router — Yojna Setu AI Service
Handles: helper registration, listing, appointment booking, accept/decline,
         admin verification, helper login, helper dashboard.
"""
import os, sqlite3, uuid, smtplib, logging, random, string
from pathlib import Path
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/sahayak", tags=["Jan Sahayak"])
logger = logging.getLogger(__name__)

# Secure upload directory — never served publicly
UPLOAD_DIR = Path(__file__).parent.parent / "secure_uploads" / "helper_docs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ── Database setup ─────────────────────────────────────────────────────────────
DB_PATH = Path(__file__).parent.parent / "sahayak.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jan_sahayaks (
            id              TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            email           TEXT NOT NULL UNIQUE,
            phone           TEXT NOT NULL,
            district        TEXT NOT NULL,
            state           TEXT NOT NULL,
            languages       TEXT NOT NULL,
            services        TEXT NOT NULL,
            bio             TEXT,
            rating          REAL DEFAULT 5.0,
            total_helped    INTEGER DEFAULT 0,
            is_available    INTEGER DEFAULT 1,
            is_verified     INTEGER DEFAULT 0,
            helper_code     TEXT UNIQUE,
            doc_path        TEXT,
            doc_type        TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS appointments (
            id              TEXT PRIMARY KEY,
            helper_id       TEXT NOT NULL,
            citizen_name    TEXT NOT NULL,
            citizen_phone   TEXT NOT NULL,
            citizen_email   TEXT,
            scheme_name     TEXT NOT NULL,
            message         TEXT,
            status          TEXT DEFAULT 'pending',
            token           TEXT NOT NULL UNIQUE,
            created_at      TEXT DEFAULT (datetime('now')),
            responded_at    TEXT,
            FOREIGN KEY (helper_id) REFERENCES jan_sahayaks(id)
        );
    """)
    # Migration: add helper_code column if it doesn't exist yet
    try:
        conn.execute("ALTER TABLE jan_sahayaks ADD COLUMN helper_code TEXT UNIQUE")
        conn.commit()
    except Exception:
        pass
    conn.close()

init_db()

# ── Constants ──────────────────────────────────────────────────────────────────
ALLOWED_DOC_TYPES = {"aadhaar", "pan", "voter_id", "driving_licence", "passport"}
ALLOWED_MIME      = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
MAX_FILE_BYTES    = 5 * 1024 * 1024   # 5 MB
ADMIN_SECRET      = os.getenv("ADMIN_SECRET", "yojna-admin-secret-change-me")

# ── SMTP config ────────────────────────────────────────────────────────────────
SMTP_HOST    = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT    = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER    = os.getenv("SMTP_USER", "")
SMTP_PASS    = os.getenv("SMTP_PASS", "")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


# ── Email helpers ──────────────────────────────────────────────────────────────
def _base_html(body: str) -> str:
    return f"""
    <div style="font-family:sans-serif;max-width:520px;margin:auto;background:#0d0e1c;color:#eee;
                border-radius:12px;padding:28px;border:1px solid rgba(255,107,53,0.3)">
      <div style="font-size:22px;font-weight:800;color:#ff6b35;margin-bottom:4px">Yojna Setu</div>
      <div style="font-size:13px;color:#aaa;margin-bottom:24px">Jan Sahayak Connect</div>
      {body}
      <p style="font-size:12px;color:#666;margin-top:28px">Yojna Setu — Empowering every Indian 🇮🇳</p>
    </div>"""


def _send(to: str, subject: str, html: str):
    if not SMTP_USER or not SMTP_PASS:
        logger.warning("SMTP not configured — skipping")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SMTP_USER
    msg["To"]      = to
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_USER, to, msg.as_string())
        logger.info(f"Email sent → {to}")
    except Exception as e:
        logger.error(f"Email failed: {e}")


def send_booking_email(helper_email: str, helper_name: str, appt: dict, token: str):
    accept_url  = f"{APP_BASE_URL}/sahayak/appointments/respond/{token}?action=accept"
    decline_url = f"{APP_BASE_URL}/sahayak/appointments/respond/{token}?action=decline"
    body = f"""
      <p>Namaste <strong>{helper_name}</strong> 🙏</p>
      <p>A citizen needs your help for a government scheme.</p>
      <div style="background:rgba(255,107,53,0.08);border:1px solid rgba(255,107,53,0.2);
                  border-radius:8px;padding:16px;margin:20px 0">
        <p style="margin:0 0 8px"><strong>Scheme:</strong> {appt['scheme_name']}</p>
        <p style="margin:0 0 8px"><strong>Citizen:</strong> {appt['citizen_name']}</p>
        <p style="margin:0 0 8px"><strong>Phone:</strong> {appt['citizen_phone']}</p>
        {f"<p style='margin:0'><strong>Message:</strong> {appt['message']}</p>" if appt.get('message') else ""}
      </div>
      <a href="{accept_url}" style="background:#22c55e;color:#fff;padding:12px 24px;
         border-radius:8px;text-decoration:none;font-weight:700">✅ Accept</a>
      &nbsp;&nbsp;
      <a href="{decline_url}" style="background:#ef4444;color:#fff;padding:12px 24px;
         border-radius:8px;text-decoration:none;font-weight:700">❌ Decline</a>
      <p style="margin-top:20px;font-size:13px;color:#aaa">
        Or manage from your dashboard:
        <a href="{FRONTEND_URL}/helper-login" style="color:#ff6b35">{FRONTEND_URL}/helper-login</a>
      </p>"""
    _send(helper_email, f"[Yojna Setu] Appointment Request — {appt['scheme_name']}", _base_html(body))


def send_citizen_notification(citizen_email: str, citizen_name: str, helper: dict,
                               accepted: bool, scheme_name: str):
    if not citizen_email:
        return
    if accepted:
        body = f"""
        <p>Great news, <strong>{citizen_name}</strong>! 🎉</p>
        <p><strong>{helper['name']}</strong> accepted your request for <strong>{scheme_name}</strong>.</p>
        <div style="background:rgba(34,197,94,0.1);border-radius:8px;padding:16px;margin:16px 0">
          <p style="margin:0 0 8px"><strong>Name:</strong> {helper['name']}</p>
          <p style="margin:0 0 8px"><strong>Phone:</strong> {helper['phone']}</p>
          <p style="margin:0"><strong>Location:</strong> {helper['district']}, {helper['state']}</p>
        </div>
        <p>They will call you soon. Please keep your phone available.</p>"""
        subject = "[Yojna Setu] Your Jan Sahayak is confirmed! ✅"
    else:
        body = f"""
        <p>Hello <strong>{citizen_name}</strong>,</p>
        <p><strong>{helper['name']}</strong> is unavailable for <strong>{scheme_name}</strong>.</p>
        <p><a href="{FRONTEND_URL}/helpers" style="color:#ff6b35">Choose another Jan Sahayak →</a></p>"""
        subject = f"[Yojna Setu] Appointment update for {scheme_name}"
    _send(citizen_email, subject, _base_html(body))


def send_verification_email(helper_email: str, helper_name: str, helper_code: str):
    """Email the unique helper login code after admin verification."""
    body = f"""
    <p>Namaste <strong>{helper_name}</strong> 🙏</p>
    <p>Congratulations! Your Jan Sahayak registration is <strong style="color:#4ade80">verified</strong>.</p>
    <p>Your unique Helper ID for logging into your dashboard:</p>
    <div style="text-align:center;margin:28px 0">
      <div style="display:inline-block;background:rgba(255,107,53,0.12);
                  border:2px solid rgba(255,107,53,0.4);border-radius:12px;padding:16px 36px">
        <div style="font-size:11px;color:#aaa;letter-spacing:2px;text-transform:uppercase;margin-bottom:6px">
          Your Helper ID
        </div>
        <div style="font-size:30px;font-weight:900;color:#ff6b35;letter-spacing:5px">
          {helper_code}
        </div>
      </div>
    </div>
    <p>Keep this ID secure — it is your login credential. Do not share it.</p>
    <a href="{FRONTEND_URL}/helper-login"
       style="display:inline-block;background:linear-gradient(135deg,#ff6b35,#e55a2b);
              color:#fff;padding:13px 28px;border-radius:8px;text-decoration:none;font-weight:700">
      Open My Dashboard →
    </a>
    <p style="margin-top:20px;font-size:13px;color:#aaa">
      Citizens in your area can now request your help.
    </p>"""
    _send(helper_email, "[Yojna Setu] ✅ Verified! Your Helper ID is inside", _base_html(body))


def _gen_helper_code() -> str:
    digits = ''.join(random.choices(string.digits, k=6))
    return f"YS-HELP-{digits}"


# ── Pydantic models ────────────────────────────────────────────────────────────
class AppointmentRequest(BaseModel):
    helper_id:      str
    citizen_name:   str
    citizen_phone:  str
    citizen_email:  Optional[str] = ""
    scheme_name:    str
    message:        Optional[str] = ""


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/register")
async def register_helper(
    name:      str        = Form(...),
    email:     str        = Form(...),
    phone:     str        = Form(...),
    district:  str        = Form(...),
    state:     str        = Form(...),
    languages: str        = Form(...),
    services:  str        = Form(...),
    bio:       str        = Form(""),
    doc_type:  str        = Form(...),
    document:  UploadFile = File(...),
):
    """Register a Jan Sahayak with mandatory ID document upload (is_verified=0 by default)."""
    if doc_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(400, f"Invalid doc_type. Choose: {', '.join(ALLOWED_DOC_TYPES)}")
    if document.content_type not in ALLOWED_MIME:
        raise HTTPException(400, "Only JPG, PNG, WebP or PDF files are accepted.")

    contents = await document.read()
    if len(contents) > MAX_FILE_BYTES:
        raise HTTPException(400, "File too large. Maximum 5MB.")

    ext       = Path(document.filename or "doc").suffix or (".pdf" if "pdf" in document.content_type else ".jpg")
    save_path = UPLOAD_DIR / f"{uuid.uuid4()}{ext}"
    with open(save_path, "wb") as f:
        f.write(contents)

    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO jan_sahayaks
              (id, name, email, phone, district, state, languages, services, bio,
               is_verified, doc_path, doc_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """, (str(uuid.uuid4()), name.strip(), email.strip().lower(), phone.strip(),
              district.strip(), state.strip(), languages, services, bio.strip(),
              str(save_path), doc_type))
        conn.commit()
        logger.info(f"Helper registered (pending): {email}")
        return {
            "success": True,
            "message": (f"Registration received, {name.split()[0]}! "
                        "Your document is under review. You'll receive your "
                        "unique Login ID by email once verified (within 24h)."),
            "status": "pending_verification",
        }
    except sqlite3.IntegrityError:
        save_path.unlink(missing_ok=True)
        raise HTTPException(409, "This email is already registered as a helper.")
    finally:
        conn.close()


@router.post("/admin/verify/{helper_db_id}")
async def admin_verify_helper(helper_db_id: str, secret: str = Query(...)):
    """
    Admin endpoint: verifies a helper, generates unique YS-HELP-XXXXXX code,
    stores it in DB, and emails it to the helper.
    Protected by ADMIN_SECRET env var.
    """
    if secret != ADMIN_SECRET:
        raise HTTPException(403, "Forbidden.")
    conn = get_db()
    try:
        helper = conn.execute("SELECT * FROM jan_sahayaks WHERE id = ?", (helper_db_id,)).fetchone()
        if not helper:
            raise HTTPException(404, "Helper not found.")
        if helper["is_verified"]:
            return {"message": f"Already verified. Code: {helper['helper_code']}"}

        for _ in range(10):
            code = _gen_helper_code()
            if not conn.execute("SELECT id FROM jan_sahayaks WHERE helper_code = ?", (code,)).fetchone():
                break
        else:
            raise HTTPException(500, "Could not generate unique code, retry.")

        conn.execute("UPDATE jan_sahayaks SET is_verified = 1, helper_code = ? WHERE id = ?",
                     (code, helper_db_id))
        conn.commit()
        send_verification_email(helper["email"], helper["name"], code)
        logger.info(f"Helper verified: {helper['email']} → {code}")
        return {"success": True, "helper_code": code,
                "message": f"Verified. Code {code} sent to {helper['email']}."}
    finally:
        conn.close()


@router.post("/helper/login")
async def helper_login(helper_code: str = Form(...)):
    """Helper logs in with their YS-HELP-XXXXXX code."""
    conn = get_db()
    try:
        h = conn.execute(
            "SELECT * FROM jan_sahayaks WHERE helper_code = ? AND is_verified = 1",
            (helper_code.strip().upper(),)
        ).fetchone()
        if not h:
            raise HTTPException(401, "Invalid Helper ID or account not yet verified.")
        helper = dict(h)
        helper["languages"] = helper["languages"].split(",") if helper["languages"] else []
        helper["services"]  = helper["services"].split(",")  if helper["services"]  else []
        helper.pop("doc_path", None)
        return {"success": True, "helper": helper}
    finally:
        conn.close()


@router.get("/helper/dashboard/{helper_db_id}")
async def helper_dashboard(helper_db_id: str):
    """Return helper profile + their appointments for the dashboard."""
    conn = get_db()
    try:
        h = conn.execute(
            "SELECT * FROM jan_sahayaks WHERE id = ? AND is_verified = 1", (helper_db_id,)
        ).fetchone()
        if not h:
            raise HTTPException(404, "Helper not found.")

        appts = conn.execute("""
            SELECT id, citizen_name, citizen_phone, citizen_email,
                   scheme_name, message, status, created_at, responded_at
            FROM appointments WHERE helper_id = ?
            ORDER BY created_at DESC
        """, (helper_db_id,)).fetchall()

        helper = dict(h)
        helper["languages"] = helper["languages"].split(",") if helper["languages"] else []
        helper["services"]  = helper["services"].split(",")  if helper["services"]  else []
        helper.pop("doc_path", None)

        apts_list = [dict(a) for a in appts]
        stats = {
            "total":    len(apts_list),
            "pending":  sum(1 for a in apts_list if a["status"] == "pending"),
            "accepted": sum(1 for a in apts_list if a["status"] == "accepted"),
            "declined": sum(1 for a in apts_list if a["status"] == "declined"),
        }
        return {"helper": helper, "appointments": apts_list, "stats": stats}
    finally:
        conn.close()


@router.get("/helpers")
async def list_helpers(state: str = "", district: str = "", limit: int = 20):
    """List verified + available helpers (helper_code never returned)."""
    conn = get_db()
    try:
        q, p = "SELECT * FROM jan_sahayaks WHERE is_available=1 AND is_verified=1", []
        if state:
            q += " AND LOWER(state)=LOWER(?)"; p.append(state)
        if district:
            q += " AND LOWER(district)=LOWER(?)"; p.append(district)
        q += " ORDER BY total_helped DESC, rating DESC LIMIT ?"; p.append(limit)

        helpers = []
        for r in conn.execute(q, p).fetchall():
            h = dict(r)
            h["languages"] = h["languages"].split(",") if h["languages"] else []
            h["services"]  = h["services"].split(",")  if h["services"]  else []
            h.pop("doc_path", None)
            h.pop("helper_code", None)   # Never expose login credential publicly
            helpers.append(h)
        return {"helpers": helpers, "total": len(helpers)}
    finally:
        conn.close()


@router.post("/appointments/request")
async def request_appointment(data: AppointmentRequest):
    conn = get_db()
    try:
        helper = conn.execute("SELECT * FROM jan_sahayaks WHERE id=?", (data.helper_id,)).fetchone()
        if not helper:
            raise HTTPException(404, "Helper not found.")
        appt_id, token = str(uuid.uuid4()), str(uuid.uuid4())
        conn.execute("""
            INSERT INTO appointments
              (id, helper_id, citizen_name, citizen_phone, citizen_email, scheme_name, message, token)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (appt_id, data.helper_id, data.citizen_name, data.citizen_phone,
              data.citizen_email or "", data.scheme_name, data.message or "", token))
        conn.commit()
        send_booking_email(helper["email"], helper["name"], {
            "scheme_name": data.scheme_name, "citizen_name": data.citizen_name,
            "citizen_phone": data.citizen_phone, "message": data.message,
        }, token)
        return {"success": True, "appointment_id": appt_id,
                "message": f"Request sent to {helper['name']}. They will respond shortly.",
                "helper_name": helper["name"]}
    finally:
        conn.close()


@router.get("/appointments/respond/{token}")
async def respond_to_appointment(token: str, action: str):
    if action not in ("accept", "decline"):
        raise HTTPException(400, "Invalid action.")
    conn = get_db()
    try:
        appt = conn.execute("SELECT * FROM appointments WHERE token=?", (token,)).fetchone()
        if not appt:
            raise HTTPException(404, "Appointment not found.")
        if appt["status"] != "pending":
            return {"message": f"Already {appt['status']}."}

        status = "accepted" if action == "accept" else "declined"
        conn.execute("UPDATE appointments SET status=?, responded_at=? WHERE token=?",
                     (status, datetime.utcnow().isoformat(), token))
        if status == "accepted":
            conn.execute("UPDATE jan_sahayaks SET total_helped=total_helped+1 WHERE id=?",
                         (appt["helper_id"],))
        conn.commit()

        helper = conn.execute("SELECT * FROM jan_sahayaks WHERE id=?", (appt["helper_id"],)).fetchone()
        if appt["citizen_email"]:
            send_citizen_notification(appt["citizen_email"], appt["citizen_name"],
                                      dict(helper), status == "accepted", appt["scheme_name"])

        if status == "accepted":
            return {"title": "✅ Accepted!",
                    "message": f"Call {appt['citizen_name']} at {appt['citizen_phone']} to schedule."}
        return {"title": "Declined", "message": "The citizen will be notified."}
    finally:
        conn.close()


@router.get("/appointments/status/{appointment_id}")
async def get_appointment_status(appointment_id: str):
    conn = get_db()
    try:
        a = conn.execute("SELECT status, responded_at FROM appointments WHERE id=?",
                         (appointment_id,)).fetchone()
        if not a:
            raise HTTPException(404, "Not found.")
        return {"status": a["status"], "responded_at": a["responded_at"]}
    finally:
        conn.close()
