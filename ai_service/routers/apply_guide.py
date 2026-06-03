"""
Guided Application Wizard — Yojna Setu
========================================
When a user is found eligible for a scheme, instead of dumping them
on a complex govt website, this router gives them a clear, step-by-step
guide in their OWN language:

  1. What documents to bring (offline CSC mode)
  2. Nearest CSC locator link
  3. Scheme helpline number
  4. What ID the CSC will give them (to use in status tracker later)
  5. Expected time to receive benefit

Multilingual: steps are auto-translated using Sarvam Mayura API
based on the user's state. Tamil users see Tamil, Bengali users see
Bengali — not just Hinglish.

Endpoints:
  GET /apply/guide     — full application guide for a scheme
  GET /apply/schemes   — list all supported schemes with mode
"""

import logging
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/apply", tags=["Application Guide"])

# In-memory translation cache: (scheme_key, lang_code) → translated fields
_translation_cache: dict[tuple, dict] = {}


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEME APPLICATION DATABASE
# ═══════════════════════════════════════════════════════════════════════════════
# application_mode: "online" | "offline_csc" | "offline_bank" | "hybrid"
# difficulty:       "easy" | "medium" | "hard"
# tracking_id_type: what ID the CSC/office gives after applying
# tracking_scheme_key: matches the key in status_tracker.py

_SCHEME_GUIDES: dict[str, dict] = {

    "pmkisan": {
        "name": "PM Kisan Samman Nidhi",
        "name_hi": "प्रधानमंत्री किसान सम्मान निधि",
        "benefit_hi": "Har 4 mahine mein ₹2000 — saal mein ₹6000 seedha bank mein",
        "application_mode": "hybrid",   # online OR via CSC
        "difficulty": "easy",
        "time_to_apply": "15–20 minute",
        "helpline": "155261",
        "helpline_hours": "Subah 8 baje se raat 10 baje tak",
        "official_portal": "https://pmkisan.gov.in",
        "apply_url": "https://pmkisan.gov.in/RegistrationForm.aspx",
        "documents_for_csc": [
            "Aadhaar Card (original + photocopy)",
            "Bank Passbook (photocopy — IFSC clearly visible)",
            "Khasra / Khatauni (land record, kisi bhi kisan seva kendra se milega)",
            "Mobile number (OTP ke liye)",
        ],
        "csc_steps_hi": [
            "Nazdiki CSC centre jayein",
            "CSC operator ko PM Kisan registration ke liye bolein",
            "Aadhaar, bank passbook, aur khasra document de dein",
            "Operator form bharega aur aapko acknowledgement slip milegi",
            "Slip mein registration number save karein",
        ],
        "tracking_id_type": "Aadhaar Number",
        "tracking_id_hint": "CSC se wapas aane ke baad apna Aadhaar number Status Tracker mein daalein — 3–5 din mein verify ho jayega",
        "tracking_scheme_key": "pmkisan",
        "expected_benefit_time": "Pehla installment registration ke 2–3 mahine baad",
        "important_note_hi": "Sirf woh kisan apply kar sakte hain jinke paas khud ki zameen ho. Bataahi wali zameen pe yeh nahi milta.",
    },

    "pmayg": {
        "name": "PM Awas Yojana — Gramin",
        "name_hi": "प्रधानमंत्री आवास योजना — ग्रामीण",
        "benefit_hi": "Pakka ghar banane ke liye ₹1.20 lakh (maidan) ya ₹1.30 lakh (pahaadi ilaka)",
        "application_mode": "offline_csc",
        "difficulty": "medium",
        "time_to_apply": "30–45 minute",
        "helpline": "1800-11-6446",
        "helpline_hours": "Somvar se Shaniwar, subah 9 se shaam 6 baje",
        "official_portal": "https://pmayg.nic.in",
        "apply_url": "https://pmayg.nic.in",
        "documents_for_csc": [
            "Aadhaar Card (sabhi parivar members ka)",
            "Ration Card (BPL hona zaroori hai)",
            "Bank Passbook (PMAY installment isi mein aata hai)",
            "Mnarega Job Card (agar hai to — prefer karte hain)",
            "Passport photo (2 copies)",
            "Purane ghar ki photo (agar hai to)",
        ],
        "csc_steps_hi": [
            "Apne Gram Panchayat office ya nazdiki CSC centre jayein",
            "Pradhan ya CSC operator se PMAY-Gramin form maangein",
            "Sabhi documents attach karke jama karein",
            "Gram Sabha mein naam confirm hogi (15–30 din lagta hai)",
            "'Awaas App' se apna registration number track karein",
        ],
        "tracking_id_type": "Registration Number (10 digit)",
        "tracking_id_hint": "Acknowledgement slip par ek 10-digit registration number hoga — ise Status Tracker mein daalein",
        "tracking_scheme_key": "pmayg",
        "expected_benefit_time": "Selection ke baad 6–12 mahine mein ghar milta hai, 3 installments mein",
        "important_note_hi": "Yeh sirf un logon ke liye hai jinke paas pakka ghar nahi hai aur jo SECC 2011 survey mein registered hain.",
    },

    "nrega": {
        "name": "MGNREGS — Mahatma Gandhi National Rural Employment Guarantee",
        "name_hi": "मनरेगा — महात्मा गांधी राष्ट्रीय ग्रामीण रोजगार गारंटी",
        "benefit_hi": "Saal mein 100 din ka kaam aur ₹200–350/din ki majdoori seedha bank mein",
        "application_mode": "offline_csc",
        "difficulty": "easy",
        "time_to_apply": "20–30 minute",
        "helpline": "1800-345-22-44",
        "helpline_hours": "24x7",
        "official_portal": "https://nrega.nic.in",
        "apply_url": "https://nrega.nic.in",
        "documents_for_csc": [
            "Aadhaar Card",
            "Bank Passbook",
            "Passport photo (2 copies)",
            "Parivar ke sabhi members ki list (jitne log kaam karenge)",
        ],
        "csc_steps_hi": [
            "Gram Panchayat office jayein — yahi sahi jagah hai MGNREGA ke liye",
            "Job Card ke liye application form maangein",
            "Form bharen — apne parivar ke sabhi members ke naam likhein",
            "Aadhaar aur photo attach karein",
            "15 din mein Job Card mil jata hai — is par ek unique number hoga",
        ],
        "tracking_id_type": "Job Card Number",
        "tracking_id_hint": "Job Card par likha number Status Tracker mein daalen — kaam ki status track ho jayegi",
        "tracking_scheme_key": "nrega",
        "expected_benefit_time": "Job Card milne ke baad 15 din ke andar kaam milna chahiye (guarantee hai)",
        "important_note_hi": "Sirf Gramin (village) areas ke residents ke liye. Shehar mein rehne wale apply nahi kar sakte.",
    },

    "pmjay": {
        "name": "Ayushman Bharat PM-JAY",
        "name_hi": "आयुष्मान भारत प्रधानमंत्री जन आरोग्य योजना",
        "benefit_hi": "Parivar ko saal mein ₹5 lakh tak ka free hospital treatment",
        "application_mode": "offline_csc",
        "difficulty": "easy",
        "time_to_apply": "10–15 minute",
        "helpline": "14555",
        "helpline_hours": "24x7",
        "official_portal": "https://pmjay.gov.in",
        "apply_url": "https://beneficiary.nha.gov.in",
        "documents_for_csc": [
            "Aadhaar Card",
            "Ration Card (SECC 2011 mein naam hona zaroori hai)",
        ],
        "csc_steps_hi": [
            "Ayushman Bharat helpline 14555 pe call karke eligibility check karein (free hai)",
            "Ya CSC centre jayein aur Aadhaar + Ration Card dekhayein",
            "Agar eligible hain to Golden Card (Ayushman Card) usi din banta hai",
            "Yeh card kisi bhi empanelled sarkари hospital mein use hota hai",
        ],
        "tracking_id_type": "Ayushman Card Number / Aadhaar",
        "tracking_id_hint": "Aadhaar number se beneficiary.nha.gov.in pe ya Status Tracker mein check karein",
        "tracking_scheme_key": "pmjay",
        "expected_benefit_time": "Card banate hi turant valid ho jata hai",
        "important_note_hi": "Pehle 14555 pe call karke check karein ki aapka parivaar eligible hai ya nahi — CSC se pehle.",
    },

    "nsp": {
        "name": "National Scholarship Portal",
        "name_hi": "राष्ट्रीय छात्रवृत्ति पोर्टल",
        "benefit_hi": "SC/ST/OBC/Minority students ke liye ₹2,000–₹20,000 scholarship per year",
        "application_mode": "online",
        "difficulty": "medium",
        "time_to_apply": "30–45 minute",
        "helpline": "0120-6619540",
        "helpline_hours": "Somvar–Shaniwar, subah 10 se shaam 6 baje",
        "official_portal": "https://scholarships.gov.in",
        "apply_url": "https://scholarships.gov.in/fresh/newstudentRegistration",
        "documents_for_csc": [
            "Aadhaar Card",
            "Bank Passbook (student ke naam par hona chahiye)",
            "School/College Bonafide Certificate",
            "Pichle saal ki marksheet",
            "Caste Certificate (SC/ST/OBC ke liye)",
            "Income Certificate (parent ka)",
            "Passport photo",
        ],
        "csc_steps_hi": [
            "scholarships.gov.in kholein",
            "'Student Registration' pe click karein",
            "Aadhaar OTP se register karein",
            "Sahi scholarship category chunein (pre-matric / post-matric / merit)",
            "Saari jankari bharen aur documents upload karein",
            "Application ID save karein — isi se track hoga",
        ],
        "tracking_id_type": "Application ID",
        "tracking_id_hint": "Submit ke baad screen par Application ID dikhega — screenshot lein aur Status Tracker mein daalen",
        "tracking_scheme_key": "nsp",
        "expected_benefit_time": "5–6 mahine (October mein apply hota hai, March mein paisa aata hai)",
        "important_note_hi": "Deadline zaroor check karein — NSP scholarship sirf October-November mein khulta hai.",
    },

    "pmuy": {
        "name": "PM Ujjwala Yojana",
        "name_hi": "प्रधानमंत्री उज्ज्वला योजना",
        "benefit_hi": "BPL parivaar ki mahilaon ko free LPG gas connection + chulha",
        "application_mode": "offline_csc",
        "difficulty": "easy",
        "time_to_apply": "15–20 minute",
        "helpline": "1906",
        "helpline_hours": "24x7",
        "official_portal": "https://pmuy.gov.in",
        "apply_url": "https://pmuy.gov.in",
        "documents_for_csc": [
            "Aadhaar Card (mahila ke naam par)",
            "Ration Card (BPL)",
            "Bank Passbook (mahila ke naam par)",
            "Passport photo",
            "Address proof",
        ],
        "csc_steps_hi": [
            "Nazdiki LPG gas agency (Indane/HP/Bharat) ya CSC centre jayein",
            "Ujjwala Yojana ke liye form maangein",
            "Mahila ke naam par sab documents jama karein",
            "Agency connection approve karegi aur delivery date degi",
            "Application ID ya reference number note kar lein",
        ],
        "tracking_id_type": "Application / Reference Number",
        "tracking_id_hint": "Form submit karte waqt ek reference number milega — Status Tracker mein daalen",
        "tracking_scheme_key": "pmuy",
        "expected_benefit_time": "Connection approval ke 15–30 din mein cylinder aur chulha deliver hota hai",
        "important_note_hi": "Sirf un gharon ke liye jahan pehle se koi LPG connection nahi hai. Mahila ka account hona zaroori hai.",
    },

    "pmjdy": {
        "name": "PM Jan Dhan Yojana",
        "name_hi": "प्रधानमंत्री जन धन योजना",
        "benefit_hi": "Zero balance bank account + RuPay debit card + ₹2 lakh accident insurance + overdraft",
        "application_mode": "offline_bank",
        "difficulty": "easy",
        "time_to_apply": "20–30 minute",
        "helpline": "1800-11-0001",
        "helpline_hours": "24x7",
        "official_portal": "https://pmjdy.gov.in",
        "apply_url": "https://pmjdy.gov.in",
        "documents_for_csc": [
            "Aadhaar Card",
            "Ek passport size photo",
            "Mobile number",
        ],
        "csc_steps_hi": [
            "Nazdiki nationalized bank jayein (SBI, PNB, Bank of Baroda, etc.)",
            "Jan Dhan account kholne ke liye PMJDY form maangein",
            "Aadhaar aur photo de dein",
            "Same day account khul jata hai, passbook turant milti hai",
            "RuPay ATM card 2–3 hafte mein aata hai",
        ],
        "tracking_id_type": "Bank Account Number",
        "tracking_id_hint": "Jan Dhan account khulne ke baad account number passbook mein hoga — isi number se sabhi government benefits seedhe aate hain",
        "tracking_scheme_key": None,  # No separate status tracker needed
        "expected_benefit_time": "Account usi din khul jata hai",
        "important_note_hi": "Yeh account zero balance pe challta hai — koi minimum balance nahi chahiye.",
    },

    "pmmvy": {
        "name": "PM Matru Vandana Yojana",
        "name_hi": "प्रधानमंत्री मातृ वंदना योजना",
        "benefit_hi": "Pehle bacche ke liye pregnant mahila ko ₹5,000 (3 installments mein)",
        "application_mode": "offline_csc",
        "difficulty": "easy",
        "time_to_apply": "20 minute",
        "helpline": "7998-799-804",
        "helpline_hours": "Somvar–Shaniwar, subah 9 se shaam 6 baje",
        "official_portal": "https://wcd.nic.in/schemes/pradhan-mantri-matru-vandana-yojana",
        "apply_url": "https://wcd.nic.in",
        "documents_for_csc": [
            "Aadhaar Card (mahila ka)",
            "Bank Passbook (mahila ke naam par — joint bhi chalega)",
            "MCP Card (Mother and Child Protection Card — Anganwadi se milega)",
            "Pati ka Aadhaar",
        ],
        "csc_steps_hi": [
            "Nazdiki Anganwadi kendra ya CSC centre jayein",
            "Form 1-A bharen (pehle installment ke liye LMP date ke baad)",
            "Bank details aur Aadhaar jama karein",
            "Anganwadi worker documents verify karegi",
            "Ek registration number milega — save karein",
        ],
        "tracking_id_type": "Registration Number",
        "tracking_id_hint": "Anganwadi se milne wala registration number sambhal ke rakhein — ismein teen installments track chunein",
        "tracking_scheme_key": None,
        "expected_benefit_time": "Har installment delivery ke baad bank mein aata hai (₹1000 + ₹2000 + ₹2000)",
        "important_note_hi": "Sirf pehle bacche ke liye. Doosre bacche ke liye PMMVY nahi milta (unless beti ho).",
    },

    "mudra": {
        "name": "PM Mudra Yojana",
        "name_hi": "प्रधानमंत्री मुद्रा योजना",
        "benefit_hi": "Chhote business ke liye ₹50,000 se ₹10 lakh tak ka loan (bina guarantee ke)",
        "application_mode": "offline_bank",
        "difficulty": "medium",
        "time_to_apply": "1–2 din (bank approval mein 2–4 hafte)",
        "helpline": "1800-180-1111",
        "helpline_hours": "Somvar–Shaniwar, subah 9 se shaam 6 baje",
        "official_portal": "https://mudra.org.in",
        "apply_url": "https://mudra.org.in",
        "documents_for_csc": [
            "Aadhaar Card",
            "PAN Card",
            "Bank Passbook (6 mahine ki statement)",
            "Business ka proof (dukan ki photo, rent agreement, etc.)",
            "2 passport size photos",
            "Loan amount ka usage plan (business plan — simple mein likhein)",
        ],
        "csc_steps_hi": [
            "Nazdiki bank ya microfinance institution jayein",
            "Mudra loan ke liye form maangein — Teen prakar hain: Shishu (50K), Kishore (5L), Tarun (10L)",
            "Business plan simple likhein — kya kaam karte ho, kitna kamaate ho, loan kisliye chahiye",
            "Bank apna check karega, aur 2–4 hafte mein approve ya reject karega",
            "Approval ke baad loan number milega",
        ],
        "tracking_id_type": "Loan Account Number",
        "tracking_id_hint": "Bank se loan milne ke baad ek Loan Account Number milega — ise sambhal ke rakhein",
        "tracking_scheme_key": None,
        "expected_benefit_time": "Application ke 2–4 hafte baad loan milta hai",
        "important_note_hi": "Shishu (₹50,000 tak) sabse aasaan hai pehli baar ke liye. Pehle chhota loan lo, chukao, phir bada lo.",
    },

    "pmfby": {
        "name": "PM Fasal Bima Yojana",
        "name_hi": "प्रधानमंत्री फसल बीमा योजना",
        "benefit_hi": "Fasal barbad hone par insurance — loss ka 80-90% wapas milta hai",
        "application_mode": "hybrid",
        "difficulty": "medium",
        "time_to_apply": "20–30 minute (kharif ya rabi ke season mein)",
        "helpline": "1800-200-7710",
        "helpline_hours": "Subah 8 se raat 8 baje",
        "official_portal": "https://pmfby.gov.in",
        "apply_url": "https://pmfby.gov.in",
        "documents_for_csc": [
            "Aadhaar Card",
            "Bank Passbook",
            "Khasra / Khatauni (kaunsi zameen, kitni acres)",
            "Fasal ka naam aur bunai ka time (cropping season)",
        ],
        "csc_steps_hi": [
            "Bank, CSC, ya online pmfby.gov.in se apply karein",
            "Sowing period ke andar (fasal bone ke 2 hafte mein) apply karna zaroori hai",
            "Premium bhugtan hoga (bahut kam hai — urea ke daam se bhi kam)",
            "Policy number milega",
            "Agar fasal barbad ho to 72 ghante mein 1800-200-7710 pe claim karein",
        ],
        "tracking_id_type": "Policy Number",
        "tracking_id_hint": "Policy number sambhal ke rakhein — claim karte waqt aur status check mein kaam aata hai",
        "tracking_scheme_key": None,
        "expected_benefit_time": "Claim approve hone ke 15–30 din mein paise bank mein",
        "important_note_hi": "DEADLINE BAHUT ZAROORI HAI — fasal bone ke 2 hafte ke andar apply karna padta hai. Baad mein nahi hoga.",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class ApplicationStep(BaseModel):
    step_no: int
    instruction: str   # Translated instruction in user's language


class ApplicationGuide(BaseModel):
    scheme_key: str
    scheme_name: str
    scheme_name_hi: str
    benefit: str                             # Benefit text in user's language
    application_mode: str
    difficulty: str
    time_to_apply: str
    helpline: str
    helpline_hours: str
    official_portal: str
    apply_url: str
    language_code: str                       # Language this guide is in (e.g. 'ta-IN')
    language_name: str                       # Human-readable (e.g. 'Tamil')
    documents_needed: list[str]              # Translated document names
    steps: list[ApplicationStep]
    tracking_id_type: str
    tracking_id_hint: str
    tracking_scheme_key: Optional[str]
    status_tracker_url: Optional[str]
    csc_locator_hint: str
    expected_benefit_time: str
    important_note: Optional[str] = None


class SchemeSummary(BaseModel):
    scheme_key: str
    scheme_name: str
    scheme_name_hi: str
    benefit_hi: str
    application_mode: str
    difficulty: str
    helpline: str
    apply_guide_url: str          # /apply/guide?scheme_key=...


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

_SUPPORTED_SCHEMES = sorted(_SCHEME_GUIDES.keys())

_MODE_LABELS = {
    "online":       "Online (ghar se phone pe apply ho sakta hai)",
    "offline_csc":  "CSC Centre (nazdiki Common Service Centre jayein)",
    "offline_bank": "Bank (nazdiki bank branch jayein)",
    "hybrid":       "Online ya CSC dono se ho sakta hai",
}

_LANG_NAMES = {
    "hi-IN": "Hindi", "ta-IN": "Tamil", "te-IN": "Telugu",
    "bn-IN": "Bengali", "mr-IN": "Marathi", "kn-IN": "Kannada",
    "ml-IN": "Malayalam", "gu-IN": "Gujarati", "pa-IN": "Punjabi",
    "or-IN": "Odia", "en-IN": "English",
}


import re as _re

def _clean_for_translation(text: str) -> str:
    """
    Simplify text before sending to Sarvam Mayura.
    Parenthetical clauses often confuse the model into producing question forms.
    We strip them or convert to a dash-separated clause instead.
    """
    # Remove content inside parentheses entirely if it's a long clause
    cleaned = _re.sub(r'\(([^)]{30,})\)', '', text)  # drop long parentheticals
    cleaned = _re.sub(r'\s{2,}', ' ', cleaned).strip()   # normalise whitespace
    return cleaned or text   # fallback to original if result is empty


def _translate_guide(guide: dict, lang_code: str) -> dict:
    """
    Translate all user-facing text in a guide to the given language.
    Uses Sarvam Mayura. Results are cached in-memory per (scheme, lang).
    Falls back to Hinglish on any error.
    """
    if lang_code == "hi-IN":
        # Already in Hindi/Hinglish — no translation needed
        return {
            "benefit":              guide["benefit_hi"],
            "steps":                guide["csc_steps_hi"],
            "documents":            guide["documents_for_csc"],
            "tracking_hint":        guide["tracking_id_hint"],
            "csc_hint":             "Nazdiki CSC dundhne ke liye app mein 'CSC Locator' kholen. Apna location share karein.",
            "expected_benefit":     guide["expected_benefit_time"],
            "important_note":       guide.get("important_note_hi"),
        }

    try:
        from ai_service.utils.sarvam import sarvam_translate, SARVAM_API_KEY
        if not SARVAM_API_KEY:
            raise ValueError("No SARVAM_API_KEY")

        def tr(text: str) -> str:
            """Clean + translate a single string hi-IN → target language."""
            if not text:
                return text
            clean = _clean_for_translation(text)
            return sarvam_translate(
                clean,
                source_language="hi-IN",
                target_language=lang_code,
                # Note: 'colloquial' mode is not supported by Sarvam Mayura v1
                # The cleaned source text + formal mode gives correct imperative output
            )

        # Translate each step individually for accuracy
        translated_steps = [tr(s) for s in guide["csc_steps_hi"]]
        translated_docs   = [tr(d) for d in guide["documents_for_csc"]]

        return {
            "benefit":          tr(guide["benefit_hi"]),
            "steps":            translated_steps,
            "documents":        translated_docs,
            "tracking_hint":    tr(guide["tracking_id_hint"]),
            "csc_hint":         tr("Nazdiki CSC dundhne ke liye app mein 'CSC Locator' kholen. Apna location share karein."),
            "expected_benefit": tr(guide["expected_benefit_time"]),
            "important_note":   tr(guide["important_note_hi"]) if guide.get("important_note_hi") else None,
        }

    except Exception as e:
        logger.warning(f"Translation to {lang_code} failed: {e} — falling back to Hinglish")
        return {
            "benefit":          guide["benefit_hi"],
            "steps":            guide["csc_steps_hi"],
            "documents":        guide["documents_for_csc"],
            "tracking_hint":    guide["tracking_id_hint"],
            "csc_hint":         "Nazdiki CSC dundhne ke liye app mein 'CSC Locator' kholen. Apna location share karein.",
            "expected_benefit": guide["expected_benefit_time"],
            "important_note":   guide.get("important_note_hi"),
        }


@router.get("/guide", response_model=ApplicationGuide)
async def get_application_guide(
    scheme_key: str = Query(..., description=f"Scheme key. Supported: {', '.join(_SUPPORTED_SCHEMES)}"),
    state: Optional[str] = Query(None, description="User's state — auto-selects language (e.g. 'Tamil Nadu' → Tamil)"),
    language: Optional[str] = Query(None, description="Override language code (e.g. 'ta-IN', 'bn-IN'). Overrides state."),
):
    """
    Get a step-by-step application guide for a government scheme.

    Guide is returned in the user's regional language:
    - Tamil Nadu → Tamil, West Bengal → Bengali, Maharashtra → Marathi, etc.
    - Hinglish fallback if Sarvam API is unavailable.
    - Pass ?language=ta-IN to override language explicitly.
    """
    key = scheme_key.lower().strip()
    if key not in _SCHEME_GUIDES:
        raise HTTPException(
            status_code=404,
            detail=f"Guide not found for '{scheme_key}'. Supported: {', '.join(_SUPPORTED_SCHEMES)}"
        )

    guide = _SCHEME_GUIDES[key]

    # ── Determine target language code ────────────────────────────────────────
    if language:
        lang_code = language  # explicit override
    elif state:
        from ai_service.utils.sarvam import get_language_for_state, get_sarvam_lang_code
        lang_code = get_sarvam_lang_code(get_language_for_state(state))
    else:
        lang_code = "hi-IN"

    # ── Translate (with cache) ───────────────────────────────────────────────
    cache_key = (key, lang_code)
    if cache_key not in _translation_cache:
        _translation_cache[cache_key] = _translate_guide(guide, lang_code)
    translated = _translation_cache[cache_key]

    # ── Build steps ──────────────────────────────────────────────────────────
    steps = [
        ApplicationStep(step_no=i + 1, instruction=step)
        for i, step in enumerate(translated["steps"])
    ]

    # ── Status tracker URL ───────────────────────────────────────────────────
    status_tracker_url = None
    if guide.get("tracking_scheme_key"):
        status_tracker_url = f"/status/check (scheme_key={guide['tracking_scheme_key']})"

    return ApplicationGuide(
        scheme_key=key,
        scheme_name=guide["name"],
        scheme_name_hi=guide["name_hi"],
        benefit=translated["benefit"],
        application_mode=guide["application_mode"],
        difficulty=guide["difficulty"],
        time_to_apply=guide["time_to_apply"],
        helpline=guide["helpline"],
        helpline_hours=guide["helpline_hours"],
        official_portal=guide["official_portal"],
        apply_url=guide["apply_url"],
        language_code=lang_code,
        language_name=_LANG_NAMES.get(lang_code, lang_code),
        documents_needed=translated["documents"],
        steps=steps,
        tracking_id_type=guide["tracking_id_type"],
        tracking_id_hint=translated["tracking_hint"],
        tracking_scheme_key=guide.get("tracking_scheme_key"),
        status_tracker_url=status_tracker_url,
        csc_locator_hint=translated["csc_hint"],
        expected_benefit_time=translated["expected_benefit"],
        important_note=translated["important_note"],
    )


@router.get("/schemes", response_model=list[SchemeSummary])
async def list_supported_schemes():
    """
    List all schemes for which application guides are available.
    Returns a summary with the apply_guide_url to deep-link into the wizard.
    """
    return [
        SchemeSummary(
            scheme_key=key,
            scheme_name=val["name"],
            scheme_name_hi=val["name_hi"],
            benefit_hi=val["benefit_hi"],
            application_mode=val["application_mode"],
            difficulty=val["difficulty"],
            helpline=val["helpline"],
            apply_guide_url=f"/apply/guide?scheme_key={key}",
        )
        for key, val in _SCHEME_GUIDES.items()
    ]
