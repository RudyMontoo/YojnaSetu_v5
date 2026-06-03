"""
Test & Validation Script — Yojna Setu AI Service
Runs before every demo to verify all components are working.

Usage: python ai_service/test_retrieval.py
"""
import sys
import os
from pathlib import Path

# Ensure ai_service is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "
results = []


def check(label: str, fn):
    try:
        result = fn()
        print(f"  {PASS} {label}: {result}")
        results.append((label, True))
        return result
    except Exception as e:
        print(f"  {FAIL} {label}: {e}")
        results.append((label, False))
        return None


# ── 1. ChromaDB Validation ────────────────────────────────────────────────────
print("\n📦 1. ChromaDB Index")
import chromadb
from chromadb.utils import embedding_functions

chroma_dir = Path(__file__).parent / "chroma_db"
ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

def check_chroma():
    client = chromadb.PersistentClient(path=str(chroma_dir))
    col = client.get_collection("yojna_setu_schemes", embedding_function=ef)
    count = col.count()
    assert count > 400, f"Expected 419+ schemes, got {count}"
    return f"{count} schemes indexed"

check("ChromaDB index count", check_chroma)

def check_retrieval():
    client = chromadb.PersistentClient(path=str(chroma_dir))
    col = client.get_collection("yojna_setu_schemes", embedding_function=ef)
    res = col.query(query_texts=["farmer subsidy Rajasthan"], n_results=3)
    docs = res["documents"][0]
    assert len(docs) > 0, "No results for farmer query"
    return f"{len(docs)} docs retrieved for 'farmer subsidy Rajasthan'"

check("Semantic retrieval (farmer query)", check_retrieval)

def check_state_filter():
    client = chromadb.PersistentClient(path=str(chroma_dir))
    col = client.get_collection("yojna_setu_schemes", embedding_function=ef)
    res = col.query(
        query_texts=["housing scheme"],
        n_results=3,
        where={"state": {"$in": ["Maharashtra", "Central"]}}
    )
    return f"{len(res['documents'][0])} results with Maharashtra filter"

check("State filter works", check_state_filter)


# ── 2. PII Masker ─────────────────────────────────────────────────────────────
print("\n🔒 2. PII Masker")
from ai_service.utils.pii_masker import mask_pii

def check_aadhaar():
    masked, pii = mask_pii("Mera Aadhaar 9876 5432 1234 hai")
    assert "aadhaar" in pii and "XXXX" in masked
    return f"Detected: {pii}"

def check_pan():
    masked, pii = mask_pii("PAN card ABCDE1234F chahiye")
    assert "pan" in pii
    return f"Detected: {pii}"

def check_phone():
    masked, pii = mask_pii("9876543210 pe call karo")
    assert "phone" in pii
    return f"Detected: {pii}"

check("Aadhaar masking", check_aadhaar)
check("PAN masking", check_pan)
check("Phone masking", check_phone)


# ── 3. Yojna Sathi Agent ─────────────────────────────────────────────────────
print("\n🤖 3. Agent Interview Engine")
from ai_service.agent.yojna_sathi import UserProfile, get_next_question, parse_answer, score_eligibility

def check_interview_flow():
    p = UserProfile()
    answers = {
        "state": "Maharashtra", "age": "35", "gender": "mahila",
        "caste_category": "sc", "occupation": "kisan", "income_lpa": "1.2",
        "is_bpl": "ha", "has_house": "nahi hai", "disability": "no",
        "is_ex_serviceman": "no",
    }
    for _ in range(15):
        q = get_next_question(p)
        if not q:
            break
        parse_answer(q, answers.get(q["id"], "no"), p)
    return f"Completion: {p.completion_pct()}% | State: {p.state} | Gender: {p.gender} | BPL: {p.is_bpl}"

def check_negation_parsing():
    p = UserProfile()
    q = {"id": "has_house", "field": "has_house", "type": "bool", "question_en": ""}
    # Test complex Hinglish negation
    parse_answer(q, "mere paas nahi hai", p)
    assert p.has_house is False, f"Expected False, got {p.has_house}"
    parse_answer(q, "bilkul", p)
    assert p.has_house is True, f"Expected True, got {p.has_house}"
    return "Negation/affirmation parsing correct"

def check_eligibility_score():
    p = UserProfile(gender="female", caste_category="sc", is_bpl=True, occupation="farmer")
    score = score_eligibility("Benefit for SC women kisan farmers BPL", p)
    assert score >= 70, f"Expected >=70, got {score}"
    return f"SC+female+farmer+BPL score: {score}/100"

check("Interview flow (10 questions)", check_interview_flow)
check("Hinglish negation parsing", check_negation_parsing)
check("Eligibility scoring", check_eligibility_score)


# ── 4. RAG Chain ─────────────────────────────────────────────────────────────
print("\n🔗 4. RAG Chain (requires GROQ_API_KEY)")

groq_key = os.getenv("GROQ_API_KEY")
if not groq_key or groq_key == "your_groq_api_key_here":
    print(f"  {WARN}  GROQ_API_KEY not set — skipping LLM tests")
else:
    from ai_service.rag_chain import build_rag_chain, invoke_with_memory, get_chromadb_count

    def check_rag_basic():
        chain = build_rag_chain()
        reply = invoke_with_memory(chain, "housing scheme for poor families", session_id="test-rag")
        assert len(reply) > 20, "Reply too short"
        return f"Reply: {reply[:80]}..."

    def check_rag_no_match():
        chain = build_rag_chain()
        reply = invoke_with_memory(chain, "alien spaceship scheme xyz123", session_id="test-nomatch")
        assert "myscheme" in reply.lower() or "maafi" in reply.lower(), "No-match guard didn't fire"
        return "No-match guard triggered correctly"

    def check_rag_memory():
        chain = build_rag_chain()
        invoke_with_memory(chain, "I am a farmer from Bihar", session_id="test-mem")
        reply2 = invoke_with_memory(chain, "what schemes am I eligible for?", session_id="test-mem")
        return f"Memory reply: {reply2[:80]}..."

    check("Basic RAG reply (Groq)", check_rag_basic)
    check("No-match guard", check_rag_no_match)
    check("Conversation memory", check_rag_memory)


# ── 5. API Key Status ────────────────────────────────────────────────────────
print("\n🔑 5. API Key Status")
print(f"  {'✅' if os.getenv('GROQ_API_KEY') and os.getenv('GROQ_API_KEY') != 'your_groq_api_key_here' else '❌'} GROQ_API_KEY")
print(f"  {'✅' if os.getenv('SARVAM_API_KEY') else WARN} SARVAM_API_KEY (optional — falls back to gTTS/Whisper)")


# ── 6. Help & Discovery ───────────────────────────────────────────────────────
print("\n🗺️  6. Help & Discovery")
from ai_service.routers.help_discovery import (
    _DOC_GUIDES, _fallback_centres, _haversine_km, _SUPPORTED_DOCS
)

def check_doc_guide_income():
    guide = _DOC_GUIDES["income_certificate"]
    assert "youtube_url" in guide,       "Missing youtube_url"
    assert "official_portal" in guide,   "Missing official_portal"
    assert "how_to_get" in guide,        "Missing how_to_get"
    assert len(guide["documents_needed"]) > 0, "No documents_needed"
    return f"income_certificate → portal={guide['official_portal']}"

def check_doc_guide_all_keys():
    missing = [k for k in _SUPPORTED_DOCS if k not in _DOC_GUIDES]
    assert not missing, f"Missing guide entries for: {missing}"
    return f"{len(_SUPPORTED_DOCS)} document types all have valid guide data"

def check_csc_fallback_delhi():
    centres = _fallback_centres(28.6139, 77.2090, state="Delhi", radius_km=50)
    assert len(centres) > 0, "No fallback results for Delhi"
    for c in centres:
        assert c.distance_km >= 0,    "Negative distance"
        assert c.osm_maps_url.startswith("https://"), "Bad OSM URL"
        assert len(c.services) > 0,   "No services listed"
    return f"{len(centres)} CSC centres found for Delhi (closest: {centres[0].name}, {centres[0].distance_km} km)"

def check_csc_haversine():
    # Mumbai to Pune is ~120 km
    dist = _haversine_km(19.0759, 72.8776, 18.5204, 73.8567)
    assert 110 < dist < 130, f"Expected ~120 km Mumbai-Pune, got {dist:.1f}"
    return f"Haversine Mumbai→Pune: {dist:.1f} km ✓"

def check_csc_fallback_no_state():
    # Without a state, should return closest from national pool
    centres = _fallback_centres(26.8467, 80.9462, state=None, radius_km=5)
    # Lucknow is in pool — should match
    assert len(centres) > 0, "Expected at least 1 result near Lucknow"
    return f"National pool fallback: {centres[0].name}"

check("doc guide — income_certificate data valid",   check_doc_guide_income)
check("doc guide — all document types present",      check_doc_guide_all_keys)
check("CSC fallback — Delhi (known seed data)",      check_csc_fallback_delhi)
check("CSC haversine distance calculation",          check_csc_haversine)
check("CSC fallback — no state given (national pool)", check_csc_fallback_no_state)


# ── Summary ───────────────────────────────────────────────────────────────────
total  = len(results)
passed = sum(1 for _, ok in results if ok)
failed = total - passed

print(f"\n{'='*50}")
print(f"📊 Results: {passed}/{total} passed", end="")
if failed:
    print(f"  ({failed} FAILED ❌)")
    for label, ok in results:
        if not ok:
            print(f"   → FAILED: {label}")
else:
    print("  🎉 All checks passed!")
print(f"{'='*50}\n")

sys.exit(0 if failed == 0 else 1)
