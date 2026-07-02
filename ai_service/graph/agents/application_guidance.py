"""
application_guidance.py — Agent 3 (Application Guidance), first Phase 6
slice. Per the rebuild plan's own risk note, browser-use automation on
gov.in portals needs "a human-checklist fallback from day one" — this IS
that fallback, built first: step-by-step apply guidance a citizen can
follow themselves or take to a CSC. Browser automation composes on top of
this later; it doesn't replace it.

Two guidance sources, best first:
1. The curated playbook in routers/apply_guide.py's _SCHEME_GUIDES —
   11 hand-written guides (CSC steps, helplines, document lists) for the
   highest-volume central schemes. Exact, human-verified: always preferred.
2. LLM-composed steps grounded in the scheme's real Mongo doc
   (applyUrl/documents/eligibilityText) for the ~970 schemes with no
   playbook entry — with a plain template fallback when quota is dead.

Security: every applyUrl recommended to a citizen passes
utils/domain_whitelist.is_allowed_url() — a mis-scraped or poisoned scheme
doc must not steer citizens off government domains. Non-whitelisted URLs
are dropped with a warning, per CLAUDE.md's DomainBlockedError rule
(graceful failure, never a retry elsewhere).
"""
import logging

from motor.motor_asyncio import AsyncIOMotorDatabase

from ai_service.db.vector_search import scheme_vector_search
from ai_service.graph.llm import ainvoke_with_fallback
from ai_service.graph.state import GraphState
from ai_service.routers.apply_guide import _SCHEME_GUIDES
from ai_service.utils.domain_whitelist import is_allowed_url

logger = logging.getLogger(__name__)


def _find_playbook(scheme_name: str) -> dict | None:
    """Word-overlap match against the curated guides — names in Mongo and
    the playbook differ in casing/wording ('PM Kisan Samman Nidhi' vs
    'pmkisan'), so match on significant name words, not keys."""
    name_words = {w for w in scheme_name.lower().split() if len(w) > 3}
    if not name_words:
        return None
    best, best_overlap = None, 0
    for guide in _SCHEME_GUIDES.values():
        guide_words = {w for w in guide["name"].lower().split() if len(w) > 3}
        overlap = len(name_words & guide_words)
        if overlap > best_overlap:
            best, best_overlap = guide, overlap
    # require most of the shorter name to overlap — one shared word like
    # "yojana" must not match everything
    if best and best_overlap >= max(2, min(len(name_words), 2)):
        return best
    return None


def _best_name_match(query: str, candidates: list[dict]) -> dict:
    """Vector top-1 isn't reliable for apply requests naming a specific
    scheme — e.g. 'PM Kisan Samman Nidhi' cosine-ranked below an MP top-up
    scheme whose text mentions PM-Kisan repeatedly (real case, 2026-07-03).
    A citizen asking to apply names THE scheme they mean, so re-rank the
    top candidates by name-word overlap with the query before trusting
    embedding order."""
    q_words = {w for w in query.lower().split() if len(w) > 2}
    def overlap(c):
        n_words = {w for w in c.get("name", "").lower().split() if len(w) > 2}
        return len(q_words & n_words)
    best = max(candidates, key=overlap)
    return best if overlap(best) >= 2 else candidates[0]


async def build_apply_guidance(db: AsyncIOMotorDatabase, scheme_query: str, lang: str = "hi") -> dict:
    candidates = await scheme_vector_search(db, scheme_query, limit=5)
    if not candidates:
        return {
            "found": False,
            "reply": "Yeh scheme nahi mili. Scheme ka poora naam batayein, ya /orchestrator/chat par eligibility check karein.",
        }
    scheme = _best_name_match(scheme_query, candidates)
    name = scheme.get("name", "")

    apply_url = scheme.get("applyUrl", "")
    url_ok = is_allowed_url(apply_url)
    if apply_url and not url_ok:
        logger.warning("Agent 3: applyUrl for %r failed domain whitelist — dropping it: %s", name, apply_url)
        apply_url = ""

    playbook = _find_playbook(name)
    if playbook:
        steps = playbook.get("csc_steps_hi", [])
        reply_lines = [f"{name} ke liye apply karne ka tarika ({playbook.get('difficulty','')}, ~{playbook.get('time_to_apply','')}):"]
        reply_lines += [f"{i}. {s}" for i, s in enumerate(steps, 1)]
        docs = playbook.get("documents_for_csc", [])
        if docs:
            reply_lines.append("Documents: " + "; ".join(docs))
        if playbook.get("helpline"):
            reply_lines.append(f"Helpline: {playbook['helpline']} ({playbook.get('helpline_hours','')})")
        portal = playbook.get("apply_url") or playbook.get("official_portal") or ""
        if portal and is_allowed_url(portal):
            reply_lines.append(f"Online: {portal}")
        return {
            "found": True, "source": "curated_playbook", "scheme_code": scheme.get("schemeCode"),
            "scheme_name": name, "steps": steps, "documents": docs,
            "helpline": playbook.get("helpline"), "apply_url": portal,
            "reply": "\n".join(reply_lines),
        }

    # No playbook — compose from the scheme doc itself.
    docs = scheme.get("documents", [])
    reply = await _compose_guidance(scheme, apply_url, docs)
    return {
        "found": True, "source": "composed_from_scheme_doc", "scheme_code": scheme.get("schemeCode"),
        "scheme_name": name, "steps": [], "documents": docs,
        "helpline": None, "apply_url": apply_url,
        "reply": reply,
    }


async def _compose_guidance(scheme: dict, apply_url: str, docs: list) -> str:
    fallback = (
        f"{scheme.get('name','')} ke liye: "
        + (f"online apply karein: {apply_url}. " if apply_url else "apne najdeeki CSC centre jayein (/help/csc/nearby se dhundhein). ")
        + (f"Documents: {'; '.join(docs)}. " if docs else "Aadhaar aur bank passbook zaroor le jayein. ")
        + "Eligibility pehle check kar lein taaki CSC ka chakkar bekar na jaye."
    )
    prompt = f"""A citizen wants to apply for this Indian government scheme. Write clear, numbered application steps in simple Hinglish (4-6 steps max). Only use facts given below — do NOT invent portal URLs, helpline numbers, or documents not listed. If no apply URL is given, direct them to their nearest CSC centre.

Scheme: {scheme.get('name','')}
Benefit: {scheme.get('benefitAmount','')}
Eligibility: {scheme.get('eligibilityText','')[:600]}
Apply URL (government-verified): {apply_url or 'none — CSC route only'}
Required documents: {', '.join(docs) if docs else 'not specified — advise Aadhaar + bank passbook as baseline'}"""
    try:
        response = await ainvoke_with_fallback(prompt, temperature=0.3)
        return response.content.strip()
    except Exception as e:
        logger.warning("Agent 3 compose failed (%s) — template fallback", e.__class__.__name__)
        return fallback


async def run_application_guidance(state: GraphState, db: AsyncIOMotorDatabase) -> GraphState:
    """LangGraph node for the `application_request` intent."""
    messages = state.get("messages", [])
    last_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    # Prefer a scheme already surfaced this conversation (citizen says "apply
    # for the first one") over re-searching from the raw message.
    active = state.get("active_schemes") or []
    query = active[0].get("name") if active else last_user_message

    result = await build_apply_guidance(db, query, lang=state.get("lang", "hi"))

    state["reply"] = result["reply"]
    state.setdefault("agent_outputs", {})["agent3_guidance"] = {
        "found": result["found"], "source": result.get("source"), "scheme_code": result.get("scheme_code"),
    }
    state.setdefault("reasoning_trace", []).append({
        "agent_name": "agent3_guidance",
        "tool_called": "build_apply_guidance",
        "input": query[:120],
        "output": result.get("source") or "not_found",
        "reasoning": f"whitelist-checked applyUrl, playbook={'hit' if result.get('source')=='curated_playbook' else 'miss'}",
    })
    return state
