"""
Yojna Sathi Agent — Adaptive Interview + Eligibility Matching
Phase 4 of Yojna Setu AI Service

This agent conducts a smart conversational interview to understand the user's
profile and then retrieves the most relevant government schemes from ChromaDB.

Key features:
- Multi-turn conversation with memory
- Adaptive follow-up questions
- Eligibility scoring per scheme
- Hinglish responses
"""
import os
import json
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

_env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

# ── Data structures ────────────────────────────────────────────────────────────
from dataclasses import dataclass, field, asdict

@dataclass
class UserProfile:
    """Built up during the interview."""
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None            # male / female / other
    state: Optional[str] = None
    district: Optional[str] = None
    caste_category: Optional[str] = None    # general / obc / sc / st
    income_lpa: Optional[float] = None      # annual income in lakhs
    occupation: Optional[str] = None        # farmer / student / unemployed / salaried / self_employed
    land_acres: Optional[float] = None      # if farmer
    education: Optional[str] = None        # none / primary / high_school / graduate / postgraduate
    disability: Optional[bool] = None
    is_bpl: Optional[bool] = None
    has_house: Optional[bool] = None
    has_bank_account: Optional[bool] = None
    marital_status: Optional[str] = None    # single / married / widowed
    num_children: Optional[int] = None
    is_ex_serviceman: Optional[bool] = None
    interests: list[str] = field(default_factory=list)  # health / education / housing / farming etc.

    def completion_pct(self) -> int:
        """How complete is the profile (0-100)?"""
        key_fields = ["age", "gender", "state", "caste_category",
                      "income_lpa", "occupation", "is_bpl"]
        filled = sum(1 for f in key_fields if getattr(self, f) is not None)
        return int((filled / len(key_fields)) * 100)

    def to_query_string(self) -> str:
        """Convert profile to a natural language query for ChromaDB."""
        parts = []
        if self.occupation: parts.append(self.occupation)
        if self.state:      parts.append(self.state)
        if self.caste_category and self.caste_category != "general":
            parts.append(self.caste_category.upper())
        if self.is_bpl:     parts.append("BPL below poverty line")
        if self.gender == "female": parts.append("women scheme")
        if self.age and self.age >= 60: parts.append("senior citizen pension")
        if self.disability: parts.append("disability handicap")
        if self.is_ex_serviceman: parts.append("ex-serviceman defence")
        if self.education in ("graduate", "postgraduate"): parts.append("scholarship fellowship")
        if self.has_house is False: parts.append("housing PMAY")
        if self.interests:  parts.extend(self.interests)
        return " ".join(parts) if parts else "government welfare scheme"


# ── Interview Question Engine ─────────────────────────────────────────────────
INTERVIEW_QUESTIONS = [
    {
        "id": "state",
        "question_en": "Aap kaun se state se hain? (Which state are you from?)",
        "question_hi": "आप किस राज्य से हैं?",
        "field": "state",
        "type": "text",
    },
    {
        "id": "age",
        "question_en": "Aapki umar kitni hai? (What is your age?)",
        "question_hi": "आपकी उम्र कितनी है?",
        "field": "age",
        "type": "number",
    },
    {
        "id": "gender",
        "question_en": "Aap mahila hain ya purush? (Are you female or male?)",
        "question_hi": "आप महिला हैं या पुरुष?",
        "field": "gender",
        "type": "choice",
        "choices": ["male", "female", "other"],
    },
    {
        "id": "caste_category",
        "question_en": "Aapki category kya hai? SC / ST / OBC / General",
        "question_hi": "आपकी श्रेणी क्या है? SC / ST / OBC / General",
        "field": "caste_category",
        "type": "choice",
        "choices": ["sc", "st", "obc", "general"],
    },
    {
        "id": "occupation",
        "question_en": "Aap kya kaam karte hain? (farmer / student / salaried / unemployed / self_employed)",
        "question_hi": "आप क्या काम करते हैं?",
        "field": "occupation",
        "type": "choice",
        "choices": ["farmer", "student", "salaried", "unemployed", "self_employed", "other"],
    },
    {
        "id": "income_lpa",
        "question_en": "Aapki family ki saal ki income kitni hai? (in lakhs, e.g. 1.5)",
        "question_hi": "आपके परिवार की वार्षिक आय कितनी है? (लाख में)",
        "field": "income_lpa",
        "type": "number",
    },
    {
        "id": "is_bpl",
        "question_en": "Kya aapke paas BPL ration card hai? (Yes/No)",
        "question_hi": "क्या आपके पास BPL राशन कार्ड है?",
        "field": "is_bpl",
        "type": "bool",
    },
    {
        "id": "has_house",
        "question_en": "Kya aapke paas khud ka pakka ghar hai? (Yes/No)",
        "question_hi": "क्या आपके पास अपना पक्का घर है?",
        "field": "has_house",
        "type": "bool",
    },
    {
        "id": "disability",
        "question_en": "Kya aap ya aapke parivaar mein koi divyang (disabled) hai? (Yes/No)",
        "question_hi": "क्या आप या परिवार में कोई दिव्यांग है?",
        "field": "disability",
        "type": "bool",
    },
    {
        "id": "is_ex_serviceman",
        "question_en": "Kya aap ya ghar mein koi ex-serviceman / veteran hai? (Yes/No)",
        "question_hi": "क्या आप या परिवार में कोई भूतपूर्व सैनिक है?",
        "field": "is_ex_serviceman",
        "type": "bool",
    },
]

# Conditional questions (only asked if certain profile fields indicate relevance)
CONDITIONAL_QUESTIONS = [
    {
        "id": "land_acres",
        "condition": lambda p: p.occupation == "farmer",
        "question_en": "Kitni zameen hai aapke paas? (in acres)",
        "question_hi": "आपके पास कितनी जमीन है? (एकड़ में)",
        "field": "land_acres",
        "type": "number",
    },
    {
        "id": "education",
        "condition": lambda p: p.occupation == "student" or (p.age and p.age < 30),
        "question_en": "Aapki education kya hai? (high_school / graduate / postgraduate)",
        "question_hi": "आपकी शिक्षा क्या है?",
        "field": "education",
        "type": "choice",
        "choices": ["primary", "high_school", "graduate", "postgraduate"],
    },
    {
        "id": "num_children",
        "condition": lambda p: p.marital_status == "married" or (p.gender == "female" and p.age and p.age > 18),
        "question_en": "Aapke kitne bacche hain? (number)",
        "question_hi": "आपके कितने बच्चे हैं?",
        "field": "num_children",
        "type": "number",
    },
]


def get_next_question(profile: UserProfile) -> Optional[dict]:
    """Return the next unanswered question for this profile."""
    for q in INTERVIEW_QUESTIONS:
        if getattr(profile, q["field"]) is None:
            return q
    # Check conditional questions
    for q in CONDITIONAL_QUESTIONS:
        if q["condition"](profile) and getattr(profile, q["field"]) is None:
            return q
    return None  # Interview complete


# ── Hinglish affirmation / negation word lists ──────────────────────────────
AFFIRMATIONS = {
    "yes", "y", "ha", "haan", "han", "hā", "haa", "1", "true",
    "bilkul", "zaroor", "sahi", "theek", "okay", "ok",
    "हाँ", "हां", "बिल्कुल", "ठीक",
}
NEGATIONS = {
    "no", "n", "nahi", "nahin", "nhi", "na", "naa", "0", "false",
    "never", "bilkul nahi", "nope",
    "नहीं", "ना", "नहि",
    # phrases like "mere paas nahi", "hamare yahan nahi"
    "nahi hai", "nahin hai", "nhi hai", "paas nahi", "pas nahi",
}


def parse_answer(question: dict, raw_answer: str, profile: UserProfile) -> UserProfile:
    """Parse a raw text answer and update the profile."""
    raw = raw_answer.strip().lower()
    field = question["field"]
    qtype = question["type"]

    if qtype == "bool":
        # Check negations first (longer phrases), then affirmations
        is_negation = any(neg in raw for neg in sorted(NEGATIONS, key=len, reverse=True))
        is_affirm   = any(aff in raw for aff in sorted(AFFIRMATIONS, key=len, reverse=True))
        if is_negation:
            val = False
        elif is_affirm:
            val = True
        else:
            val = False  # safe default
        setattr(profile, field, val)

    elif qtype == "number":
        import re
        nums = re.findall(r"\d+\.?\d*", raw)
        if nums:
            val = float(nums[0])
            setattr(profile, field, int(val) if field in ("age", "num_children") else val)

    elif qtype == "choice":
        choices = question.get("choices", [])
        # Expanded Hinglish keyword maps
        HINGLISH_MAPS = {
            "gender": {
                "mahila": "female", "aurat": "female", "ladki": "female",
                "stri": "female", "woman": "female", "girl": "female",
                "purush": "male", "aadmi": "male", "ladka": "male",
                "mard": "male", "man": "male", "boy": "male",
            },
            "caste_category": {
                "anusuchit jati": "sc", "anusuchit": "sc", "scheduled caste": "sc",
                "janjati": "st", "adivasi": "st", "tribal": "st", "scheduled tribe": "st",
                "pichhda": "obc", "other backward": "obc",
                "samanya": "general", "gen": "general", "unreserved": "general",
                "open": "general",
            },
            "occupation": {
                "kisan": "farmer", "kheti": "farmer", "agriculture": "farmer",
                "khet": "farmer", "farming": "farmer",
                "naukri": "salaried", "job": "salaried", "service": "salaried",
                "sarkari": "salaried", "private": "salaried",
                "padhai": "student", "college": "student", "school": "student",
                "vidyarthi": "student",
                "business": "self_employed", "dukan": "self_employed",
                "vyapar": "self_employed", "self": "self_employed",
                "berozgar": "unemployed", "koi kaam nahi": "unemployed",
                "unemployed": "unemployed", "ghar baithe": "unemployed",
            },
        }
        mapping = HINGLISH_MAPS.get(field, {})
        matched = False
        # Try longest keyword match first to avoid partial false matches
        for kw in sorted(mapping.keys(), key=len, reverse=True):
            if kw in raw:
                setattr(profile, field, mapping[kw])
                matched = True
                break
        if not matched:
            # Try direct choice match
            for c in choices:
                if c in raw:
                    setattr(profile, field, c)
                    matched = True
                    break
        if not matched:
            # Fallback: store raw
            setattr(profile, field, raw_answer.strip())

    else:  # text
        setattr(profile, field, raw_answer.strip().title())

    return profile


# ── Eligibility Scorer ─────────────────────────────────────────────────────────
def score_eligibility(scheme_text: str, profile: UserProfile) -> int:
    """
    Rough eligibility score 0-100 by checking profile against scheme text.
    Higher = more likely eligible.
    """
    text = scheme_text.lower()
    score = 50  # Base score

    # Category matching
    if profile.caste_category == "sc" and ("sc" in text or "scheduled caste" in text):
        score += 20
    if profile.caste_category == "st" and ("st" in text or "tribal" in text or "adivasi" in text):
        score += 20
    if profile.caste_category == "obc" and "obc" in text:
        score += 15

    # BPL matching
    if profile.is_bpl and "bpl" in text:
        score += 15

    # Gender matching
    if profile.gender == "female" and ("women" in text or "mahila" in text or "girl" in text):
        score += 15

    # Occupation matching
    if profile.occupation == "farmer" and ("kisan" in text or "farmer" in text or "agriculture" in text):
        score += 20
    if profile.occupation == "student" and ("student" in text or "scholarship" in text):
        score += 20

    # Age matching
    if profile.age and profile.age >= 60 and ("senior" in text or "60" in text or "elderly" in text):
        score += 20
    if profile.age and profile.age < 18 and ("child" in text or "minor" in text):
        score += 10

    # State matching
    if profile.state and profile.state.lower() in text:
        score += 10

    # Disability
    if profile.disability and ("disability" in text or "divyang" in text or "handicap" in text):
        score += 20

    # Housing
    if profile.has_house is False and ("housing" in text or "awas" in text or "ghar" in text):
        score += 15

    return min(score, 100)


if __name__ == "__main__":
    # Quick test of the interview flow
    profile = UserProfile()
    print("👋 Yojna Sathi Interview Simulation\n" + "="*40)

    mock_answers = {
        "state": "Maharashtra",
        "age": "35",
        "gender": "mahila",
        "caste_category": "sc",
        "occupation": "kisan",
        "income_lpa": "1.2",
        "is_bpl": "ha",
        "has_house": "no",
        "disability": "no",
        "is_ex_serviceman": "no",
        "land_acres": "2",
    }

    for _ in range(15):  # max 15 questions
        q = get_next_question(profile)
        if not q:
            break
        ans = mock_answers.get(q["id"], "no")
        print(f"Q: {q['question_en']}")
        print(f"A: {ans}")
        parse_answer(q, ans, profile)
        print(f"   → {q['field']} = {getattr(profile, q['field'])}")
        print()

    print(f"\n📊 Profile completion: {profile.completion_pct()}%")
    print(f"🔍 Search query: '{profile.to_query_string()}'")
    print(f"\nEligibility score sample:")
    mock_scheme = "Benefit for SC women kisan farmers BPL"
    print(f"  Scheme: '{mock_scheme}' → Score: {score_eligibility(mock_scheme, profile)}")
