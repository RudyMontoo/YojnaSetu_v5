"""
credit_faq.py — Credit-specific RAG: answers a citizen's questions about an
NSFDC concessional credit PRODUCT's own terms (interest rate, loan ceiling,
margin money, moratorium, tenure, income ceiling) — as opposed to
`credit_application` (they've already decided to apply) or `eligibility_query`
(general welfare scheme discovery, which only ever searches the `schemes`
collection and has never known `credit_products` exists).

Retrieval is NOT vector search. `credit_products` has no `embedding` field and
holds a handful of documents (the NSFDC schemes seeded by CreditProductSeeder,
see [[nsfdc-scheme-figures]] in the project's memory) — for a catalogue this
small and this precise, a keyword/code match against the actual seeded facts
is both simpler and more reliable than an embedding model: "term loan" and
"micro finance" are exact category names in this data, not fuzzy topics, and
a citizen asking about a specific NSFDC scheme needs the RIGHT product's
numbers, not the topically-closest one.

The composed reply is grounded ONLY in the matched product's real stored
fields — same discipline as rag_chain.py's NO_MATCH_RESPONSE and
eligibility.py's "never invent a criterion": the LLM is handed the exact
figures and told not to add or round anything, and any `figuresVerified:
false` product must be flagged to the citizen as provisional, never stated
as settled fact. Getting an interest rate or moratorium period wrong here is
not a cosmetic bug — it is the number a citizen budgets a loan repayment
against.
"""
import logging
import re

from motor.motor_asyncio import AsyncIOMotorDatabase

from ai_service.graph.llm import ainvoke_with_fallback, language_instruction
from ai_service.graph.state import GraphState

logger = logging.getLogger(__name__)

_NO_MATCH_REPLY = {
    "en": "I couldn't tell which NSFDC credit scheme you're asking about. We currently "
          "have: {names}. Could you name one, or tell me a bit about what you need the loan for?",
    "hi": "Maaf kijiye, main samajh nahi paaya aap kaunsi NSFDC credit scheme ke baare mein "
          "puch rahe hain. Abhi ye schemes hain: {names}. Kripya naam batayein, ya bataayein "
          "loan kis kaam ke liye chahiye.",
}
_DEFAULT_LANG = "hi"

_LLM_DOWN_PREFACE = {
    "en": "Here are the real figures for {names} (couldn't phrase this as a full reply right now):\n\n",
    "hi": "{names} ke figures yeh hain (abhi poora jawab nahi likh paaya):\n\n",
}


def _searchable_text(product: dict) -> str:
    parts = [
        product.get("name", ""),
        product.get("code", ""),
        product.get("type", ""),
        product.get("projectType", ""),
        product.get("description", ""),
    ]
    return " ".join(p for p in parts if p).lower()


_WORD_RE = re.compile(r"[a-zA-Z]+")

# Words too generic to identify a specific product on their own — every NSFDC
# product name contains at least one of these ("Term Loan", "Educational Loan
# Scheme", "Udyam Nidhi Yojana", ...), so they're excluded from the
# name-match bonus below rather than letting any product whose name happens
# to contain "loan" claim a strong match for a generic "loan" mention.
_GENERIC_NAME_WORDS = {"scheme", "yojana", "loan", "credit", "fund"}


def match_products(query: str, products: list[dict], top_k: int = 2) -> list[dict]:
    """Pure keyword-overlap scorer, no I/O — see module docstring for why
    this beats vector search for a catalogue this small and this exact.
    An exact code match (e.g. "MFS", "TL") is a much stronger signal than a
    word overlap, so it's weighted heavily rather than just counted once.

    Real case caught in live testing: "Term Loan ka interest rate kitna hai"
    scored Term Loan (code hit) correctly on top, but also pulled in Udyam
    Nidhi Yojana on the strength of the single shared word "loan" — a citizen
    asking about ONE scheme's rate does not want a second, unrelated
    scheme's numbers handed to the LLM alongside it. A weak trailing match
    is worse than no match at all here, unlike a topic-discovery search, so
    anything scoring below half the top match's score is dropped rather
    than filled out to top_k."""
    query_words = set(_WORD_RE.findall((query or "").lower()))
    if not query_words:
        return []

    scored = []
    for product in products:
        code = (product.get("code") or "").lower()
        # Generic words ("scheme", "loan"...) are excluded here too, not just
        # from the name-match bonus below — real case: "Aajeevika scheme kya
        # hai" matched Term Loan and Micro Finance Scheme on the shared,
        # meaningless word "scheme" with the SAME score as Aajeevika's own
        # genuinely relevant "aajeevika" hit, burying the right product in a
        # three-way tie.
        text_words = set(_WORD_RE.findall(_searchable_text(product))) - _GENERIC_NAME_WORDS
        overlap = len(query_words & text_words)
        code_hit = 5 if code and code in query_words else 0

        # A citizen typing the scheme's full name ("Term Loan") rather than
        # its code ("TL") deserves the same strong-match treatment — every
        # DISTINCTIVE word of the name (i.e. not a word shared by every
        # product's name) present in the query is as strong a signal as a
        # code match. Real case caught here: several product names carry
        # their own code in parentheses (e.g. "Udyam Nidhi Yojana (UNY)"),
        # which silently demanded the citizen also type the code verbatim
        # before this ever counted as a full-name match — dropped here too.
        name_words = (set(_WORD_RE.findall(product.get("name", "").lower()))
                      - _GENERIC_NAME_WORDS - ({code} if code else set()))
        name_hit = 5 if name_words and name_words.issubset(query_words) else 0

        score = overlap + code_hit + name_hit
        if score > 0:
            scored.append((score, product))

    scored.sort(key=lambda t: t[0], reverse=True)
    top_score = scored[0][0] if scored else 0
    relevance_floor = max(1, top_score / 2)
    return [p for score, p in scored[:top_k] if score >= relevance_floor]


def _format_product_facts(product: dict) -> str:
    """Renders exactly the fields a citizen would ask about, and nothing this
    module doesn't actually have — no invented "processing fee" or
    "prepayment penalty" line just because a real loan product usually has
    one; CreditProduct doesn't model those, so this doesn't claim to know them."""
    lines = [f"{product.get('name', 'Unknown scheme')} ({product.get('code', '')})"]
    if product.get("unitCostFloor") is not None or product.get("unitCostCeiling") is not None:
        floor = product.get("unitCostFloor")
        ceiling = product.get("unitCostCeiling")
        band = f"₹{floor:,}" if floor else "no floor"
        band += f" to ₹{ceiling:,}" if ceiling else " (no ceiling)"
        lines.append(f"- Project unit cost this scheme covers: {band}")
    lines.append(f"- Maximum loan amount: ₹{product.get('maxLoanAmount', 0):,}")
    lines.append(f"- Interest rate: {product.get('interestRate', '?')}% per annum")
    lines.append(f"- Loan covers {product.get('coveragePct', '?')}% of project cost — the citizen "
                  f"must contribute the rest as margin money")
    lines.append(f"- Moratorium: {product.get('moratoriumMonths', '?')} months; "
                 f"max tenure: {product.get('maxTenureMonths', '?')} months")
    lines.append(f"- Annual family income ceiling: ₹{product.get('maxAnnualIncome', 0):,}")
    if product.get("categories"):
        lines.append(f"- Eligible categories: {', '.join(product['categories'])}")
    if product.get("womenOnly"):
        lines.append("- This scheme is for women applicants only")
    if product.get("channelPartnerTypes"):
        lines.append(f"- Delivered through: {', '.join(product['channelPartnerTypes'])}")
    if not product.get("figuresVerified", True):
        lines.append("- IMPORTANT: these figures are NOT independently verified against NSFDC's own "
                      "published page — tell the citizen to treat them as provisional and confirm with "
                      "the lending branch before relying on them")
    return "\n".join(lines)


async def run_credit_faq_agent(state: GraphState, db: AsyncIOMotorDatabase) -> GraphState:
    messages = state.get("messages", [])
    last_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    lang_key = (state.get("lang") or "").strip().lower()

    products = await db["credit_products"].find({"active": True}).to_list(length=50)
    matched = match_products(last_user_message, products)

    if not matched:
        names = ", ".join(p.get("name", "") for p in products) or "no schemes configured yet"
        reply = _NO_MATCH_REPLY.get(lang_key, _NO_MATCH_REPLY[_DEFAULT_LANG]).format(names=names)
        state["reply"] = reply
        state["active_schemes"] = []
        state.setdefault("agent_outputs", {})["credit_faq"] = {"matched_count": 0}
        state.setdefault("reasoning_trace", []).append({
            "agent_name": "credit_faq",
            "tool_called": "match_products",
            "input": last_user_message[:200],
            "output": "no_match",
            "reasoning": f"{len(products)} active credit_products, none scored above 0",
        })
        return state

    facts = "\n\n".join(_format_product_facts(p) for p in matched)
    prompt = f"""You are the SC Concessional Credit Assistant, answering a citizen's question about \
an NSFDC credit scheme's actual terms.

Citizen's message: "{last_user_message}"

Use ONLY these real, verified figures. Do NOT invent, round, or estimate any number not listed here. \
If a figure is marked provisional/unverified, say so plainly rather than stating it as settled fact.

{facts}

{language_instruction(lang_key)} Write a short, direct reply (3-5 sentences) answering their specific \
question using these figures. If they asked about margin money, explain it is the share of project cost \
NOT covered by the loan. End by mentioning they can start an application if they're ready."""

    # Falls back to the raw facts, not the "which scheme?" no-match message —
    # a product WAS found here, the LLM call is what failed, so the honest
    # fallback is the real figures without the LLM's prose, not a message
    # that implies nothing was matched at all.
    names = ", ".join(p.get("name", "") for p in matched)
    fallback_reply = _LLM_DOWN_PREFACE.get(lang_key, _LLM_DOWN_PREFACE[_DEFAULT_LANG]).format(names=names) + facts
    try:
        response = await ainvoke_with_fallback(prompt, temperature=0.1)
        reply = response.content.strip() or fallback_reply
    except Exception as e:
        logger.warning("credit_faq LLM call failed (%s) — falling back", e.__class__.__name__)
        reply = fallback_reply

    state["reply"] = reply
    state["active_schemes"] = matched
    state.setdefault("agent_outputs", {})["credit_faq"] = {
        "matched_count": len(matched),
        "matched_codes": [p.get("code") for p in matched],
    }
    state.setdefault("reasoning_trace", []).append({
        "agent_name": "credit_faq",
        "tool_called": "match_products + llm_compose",
        "input": last_user_message[:200],
        "output": f"{len(matched)} product(s): {[p.get('code') for p in matched]}",
        "reasoning": "keyword/code match against credit_products, not vector search — see module docstring",
    })
    return state
