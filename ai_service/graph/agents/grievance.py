"""
grievance.py — Agent 5 (Grievance), first slice. Per CLAUDE.md the full
agent navigates pgportal.gov.in via browser-use (120s timeout) — that
automation half is NOT built yet (same honest split as Agent 3: fallback
first, automation composes on top later). What IS real today:

1. A grievance record persisted to the `grievances` collection — citizen's
   complaint, scheme, optional external application id, status "recorded".
   When portal automation lands it picks pending records up from here, so
   nothing filed today is lost.
2. Correct CPGRAMS (pgportal.gov.in) self-filing guidance with
   domain-whitelisted URLs only.

NPCI/SPARSH pension-status monitoring (the v5.0 doc's other Agent 5 duty)
requires institutional API access a solo dev doesn't have — scoped out,
mocked-swappable later, exactly as the rebuild plan flagged.

PII note: complaint text is masked (utils/pii_masker) BEFORE any LLM call,
and the stored record keeps the citizen's original text only in Mongo
(same trust level as conversation_sessions), never in logs.
"""
import logging
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from ai_service.graph.state import GraphState
from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument

from ai_service.utils.domain_whitelist import is_allowed_url

logger = logging.getLogger(__name__)

PGPORTAL_URL = "https://pgportal.gov.in"

# Procedural, safety-relevant filing steps — deliberately NOT LLM-composed
# (unlike the reply-composing agents' language_instruction() fix). A citizen
# following this to actually file a CPGRAMS grievance needs the portal name,
# button label, and time limit stated exactly, not paraphrased by a model on
# every call. Real bug fixed 2026-09-11: this used to be one Hinglish-only
# template regardless of state["lang"] — the same class of bug as every
# other reply-composing node, just needing a translated-template fix instead
# of language_instruction() since there's no LLM call here to instruct.
_GUIDANCE_TEMPLATES: dict[str, str] = {
    "en": (
        "Your grievance has been recorded (id: {gid}). Automatic portal filing isn't "
        "available yet, but you can file it yourself in about 10 minutes:\n"
        "1. Go to {portal} (CPGRAMS — the Government of India's official grievance portal)\n"
        "2. Click 'Lodge Public Grievance' and register with your mobile number\n"
        "3. Choose the Ministry/Department{dept_hint}\n"
        "4. Write your complaint — scheme name, application id{app_id_hint}, and what the problem is\n"
        "5. Keep the CPGRAMS registration number you get after submitting — that's what tracks "
        "your status. The response time limit is 30 days."
    ),
    "hi": (
        "Aapki shikayat record ho gayi hai (id: {gid}). Abhi portal par automatic filing "
        "available nahi hai, lekin aap khud 10 minute mein file kar sakte hain:\n"
        "1. {portal} par jayein (CPGRAMS — Government of India ka official grievance portal)\n"
        "2. 'Lodge Public Grievance' par click karke mobile number se register karein\n"
        "3. Ministry/Department chunein{dept_hint}\n"
        "4. Apni complaint likhein — scheme ka naam, application id{app_id_hint}, aur kya problem hai\n"
        "5. Submit ke baad milne wala CPGRAMS registration number sambhal kar rakhein — "
        "status tracking usi se hogi. Jawab aane ki time-limit 30 din hai."
    ),
    "bn": (
        "আপনার অভিযোগ রেকর্ড করা হয়েছে (আইডি: {gid})। এখনও পোর্টালে স্বয়ংক্রিয় ফাইলিং উপলব্ধ নেই, "
        "তবে আপনি নিজে প্রায় ১০ মিনিটে ফাইল করতে পারেন:\n"
        "১. {portal}-এ যান (CPGRAMS — ভারত সরকারের অফিসিয়াল অভিযোগ পোর্টাল)\n"
        "২. 'Lodge Public Grievance'-এ ক্লিক করে আপনার মোবাইল নম্বর দিয়ে রেজিস্টার করুন\n"
        "৩. মন্ত্রণালয়/বিভাগ বেছে নিন{dept_hint}\n"
        "৪. আপনার অভিযোগ লিখুন — স্কিমের নাম, আবেদন আইডি{app_id_hint}, এবং সমস্যাটি কী\n"
        "৫. জমা দেওয়ার পর পাওয়া CPGRAMS রেজিস্ট্রেশন নম্বরটি সংরক্ষণ করুন — এটি দিয়েই স্ট্যাটাস "
        "ট্র্যাক করা হবে। উত্তর দেওয়ার সময়সীমা ৩০ দিন।"
    ),
    "ta": (
        "உங்கள் புகார் பதிவு செய்யப்பட்டுள்ளது (ஐடி: {gid})। தானியங்கி போர்ட்டல் தாக்கல் இன்னும் "
        "கிடைக்கவில்லை, ஆனால் நீங்கள் சுமார் 10 நிமிடங்களில் நீங்களே தாக்கல் செய்யலாம்:\n"
        "1. {portal}-க்குச் செல்லவும் (CPGRAMS — இந்திய அரசின் அதிகாரப்பூர்வ புகார் போர்ட்டல்)\n"
        "2. 'Lodge Public Grievance'ஐ கிளிக் செய்து உங்கள் மொபைல் எண்ணுடன் பதிவு செய்யவும்\n"
        "3. அமைச்சகம்/துறையைத் தேர்ந்தெடுக்கவும்{dept_hint}\n"
        "4. உங்கள் புகாரை எழுதவும் — திட்டத்தின் பெயர், விண்ணப்ப ஐடி{app_id_hint}, மற்றும் "
        "என்ன பிரச்சனை என்பதை\n"
        "5. சமர்ப்பித்த பிறகு கிடைக்கும் CPGRAMS பதிவு எண்ணை பத்திரமாக வைத்துக் கொள்ளுங்கள் — "
        "அதன் மூலமே நிலை கண்காணிக்கப்படும். பதில் அளிக்கும் காலவரம்பு 30 நாட்கள்."
    ),
    "te": (
        "మీ ఫిర్యాదు నమోదు చేయబడింది (ఐడి: {gid})। ఇప్పటికీ పోర్టల్‌లో ఆటోమేటిక్ ఫైలింగ్ అందుబాటులో "
        "లేదు, కానీ మీరు సుమారు 10 నిమిషాల్లో మీరే దాఖలు చేయవచ్చు:\n"
        "1. {portal}కి వెళ్లండి (CPGRAMS — భారత ప్రభుత్వ అధికారిక ఫిర్యాదు పోర్టల్)\n"
        "2. 'Lodge Public Grievance' పై క్లిక్ చేసి మీ మొబైల్ నంబర్‌తో నమోదు చేసుకోండి\n"
        "3. మంత్రిత్వ శాఖ/విభాగాన్ని ఎంచుకోండి{dept_hint}\n"
        "4. మీ ఫిర్యాదు రాయండి — పథకం పేరు, దరఖాస్తు ఐడి{app_id_hint}, మరియు సమస్య ఏమిటి\n"
        "5. సమర్పించిన తర్వాత వచ్చే CPGRAMS నమోదు సంఖ్యను భద్రపరచుకోండి — దీని ద్వారానే స్థితిని "
        "ట్రాక్ చేస్తారు. సమాధానం ఇచ్చే గడువు 30 రోజులు."
    ),
    "mr": (
        "तुमची तक्रार नोंदवली गेली आहे (आयडी: {gid})। सध्या पोर्टलवर आपोआप फाइलिंग उपलब्ध नाही, "
        "पण तुम्ही स्वतः सुमारे 10 मिनिटांत फाइल करू शकता:\n"
        "1. {portal} वर जा (CPGRAMS — भारत सरकारचे अधिकृत तक्रार पोर्टल)\n"
        "2. 'Lodge Public Grievance' वर क्लिक करून तुमच्या मोबाइल नंबरने नोंदणी करा\n"
        "3. मंत्रालय/विभाग निवडा{dept_hint}\n"
        "4. तुमची तक्रार लिहा — योजनेचे नाव, अर्ज आयडी{app_id_hint}, आणि समस्या काय आहे\n"
        "5. सबमिट केल्यानंतर मिळणारा CPGRAMS नोंदणी क्रमांक जपून ठेवा — त्यानेच स्थिती ट्रॅक होईल. "
        "उत्तर देण्याची मुदत 30 दिवस आहे."
    ),
}
_DEFAULT_GUIDANCE_LANG = "hi"

# The "(if any)" clause for app_id_hint when no external application id was
# given — the only piece of _GUIDANCE that needs its own translation rather
# than being a proper noun/number dropped straight into the template.
_APP_ID_IF_ANY: dict[str, str] = {
    "en": " (if any)", "hi": " (agar hai)", "bn": " (থাকলে)",
    "ta": " (இருந்தால்)", "te": " (ఉంటే)", "mr": " (असल्यास)",
}


async def record_grievance(
    db: AsyncIOMotorDatabase,
    *,
    citizen_id: str,
    complaint_description: str,
    scheme_code: str | None = None,
    external_app_id: str | None = None,
    lang: str | None = None,
) -> dict:
    """Persists the grievance and returns the guidance reply. Never raises
    on scheme-lookup issues — a grievance about an unknown scheme is still
    a grievance worth recording."""
    scheme_name = None
    if scheme_code:
        scheme = await db["schemes"].find_one({"schemeCode": scheme_code}, {"name": 1})
        scheme_name = scheme.get("name") if scheme else None

    doc = {
        "citizenId": citizen_id,
        "schemeCode": scheme_code,
        "schemeName": scheme_name,
        "externalAppId": external_app_id,
        "complaint": complaint_description,
        "status": "recorded",  # recorded -> filed_on_portal (automation, later) -> resolved
        "statusHistory": [{"status": "recorded", "at": datetime.now(timezone.utc)}],
        "createdAt": datetime.now(timezone.utc),
    }
    result = await db["grievances"].insert_one(doc)
    gid = str(result.inserted_id)

    portal = PGPORTAL_URL if is_allowed_url(PGPORTAL_URL) else "pgportal.gov.in"
    key = (lang or "").strip().lower()
    template = _GUIDANCE_TEMPLATES.get(key, _GUIDANCE_TEMPLATES[_DEFAULT_GUIDANCE_LANG])
    if_any = _APP_ID_IF_ANY.get(key, _APP_ID_IF_ANY[_DEFAULT_GUIDANCE_LANG])
    reply = template.format(
        gid=gid[-8:],  # short suffix — full ObjectId is internal
        portal=portal,
        dept_hint=f" (scheme: {scheme_name})" if scheme_name else "",
        app_id_hint=f" ({external_app_id})" if external_app_id else if_any,
    )
    logger.info("Agent 5: grievance recorded id=%s scheme=%s", gid, scheme_code)
    return {"grievance_id": gid, "status": "recorded", "scheme_name": scheme_name, "reply": reply}


async def list_grievances(db: AsyncIOMotorDatabase, citizen_id: str) -> list[dict]:
    """Returns the citizen's OWN grievances, newest first — read-only, filtered
    to their citizenId. The status-tracking view for the grievance loop (analog
    of the applications status_check)."""
    if not citizen_id:
        return []
    cursor = (
        db["grievances"]
        .find(
            {"citizenId": citizen_id},
            {"schemeName": 1, "schemeCode": 1, "complaint": 1, "status": 1,
             "cpgramsRef": 1, "externalAppId": 1, "createdAt": 1, "statusHistory": 1},
        )
        .sort("createdAt", -1)
        .limit(50)
    )
    docs = await cursor.to_list(length=50)
    for d in docs:
        d["grievance_id"] = str(d.pop("_id"))
    return docs


async def attach_cpgrams_reference(
    db: AsyncIOMotorDatabase, citizen_id: str, grievance_id: str, cpgrams_ref: str
) -> dict | None:
    """After the citizen self-files on pgportal (CPGRAMS), they record the
    registration number back here → the grievance moves recorded ->
    filed_on_portal, closing the loop the recording path was designed for.

    Ownership-enforced: only updates a grievance that both matches the id AND
    belongs to the caller (returns None otherwise — no cross-citizen writes,
    no existence leak). Never files anything on the portal itself; this is the
    citizen reporting back the ref they already obtained by self-filing."""
    try:
        oid = ObjectId(grievance_id)
    except (InvalidId, TypeError):
        return None
    ref = (cpgrams_ref or "").strip()
    if not ref:
        return None

    now = datetime.now(timezone.utc)
    updated = await db["grievances"].find_one_and_update(
        {"_id": oid, "citizenId": citizen_id},  # ownership in the filter itself
        {
            "$set": {"status": "filed_on_portal", "cpgramsRef": ref, "filedOnPortalAt": now},
            "$push": {"statusHistory": {"status": "filed_on_portal", "at": now, "cpgramsRef": ref}},
        },
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        return None
    updated["grievance_id"] = str(updated.pop("_id"))
    return updated


async def run_grievance_agent(state: GraphState, db: AsyncIOMotorDatabase) -> GraphState:
    """LangGraph node for the `grievance` intent — records the complaint
    from the chat message itself (scheme resolved from active_schemes when
    the citizen was just discussing one)."""
    messages = state.get("messages", [])
    last_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    active = state.get("active_schemes") or []
    scheme_code = active[0].get("schemeCode") if active else None

    result = await record_grievance(
        db,
        citizen_id=state.get("citizen_id", ""),
        complaint_description=last_user_message,
        scheme_code=scheme_code,
        lang=state.get("lang"),
    )

    state["reply"] = result["reply"]
    state.setdefault("agent_outputs", {})["agent5_grievance"] = {
        "grievance_id": result["grievance_id"], "status": result["status"],
    }
    state.setdefault("reasoning_trace", []).append({
        "agent_name": "agent5_grievance",
        "tool_called": "record_grievance",
        "input": (scheme_code or "no-scheme") + " | " + last_user_message[:80],
        "output": f"recorded {result['grievance_id'][-8:]}",
        "reasoning": "persisted to grievances collection; portal automation pending — self-filing guidance given",
    })
    return state
