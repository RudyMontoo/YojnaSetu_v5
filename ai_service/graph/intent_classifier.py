"""
intent_classifier.py — the Orchestrator's entry node.

Classifies the citizen's message into one of the intents from CLAUDE.md's
routing table, then the graph's conditional edges dispatch to the matching
agent node. Only "eligibility_query" and "comparison" have real agents
behind them this session (Agent 1, Agent 8) — everything else routes to an
honest "not built yet" placeholder rather than silently mishandling it.
"""
import json
import logging

from ai_service.graph.llm import ainvoke_with_fallback
from ai_service.graph.state import GraphState
from ai_service.utils.injection_guard import check_injection
from ai_service.utils.pii_masker import mask_pii

logger = logging.getLogger(__name__)

INTENTS = [
    "eligibility_query",
    "credit_application",
    "credit_eligibility",
    "credit_faq",
    "application_request",
    "grievance",
    "comparison",
    "financial_plan",
    "document_verify",
    "status_check",
    "csc_assist",
    "small_talk",
]

_CLASSIFY_PROMPT = """You are an intent classifier for Yojna Sarthi, an Indian government welfare scheme assistant.
Classify the citizen's message into exactly one of these intents:
- eligibility_query: asking what schemes they qualify for, or describing their situation to find schemes
- credit_application: wants to START/FILL an application for a SPECIFIC SC concessional credit scheme they've already named or that was just shown to them (e.g. "isके liye apply karna hai", "Micro Finance Scheme ke liye application shuru karo", "I want to apply for this scheme") — NOT a general "how do I apply" question with no scheme in mind
- credit_eligibility: wants to know which SC concessional CREDIT/LOAN scheme they qualify for, or is answering questions in that matching flow — they need money for a business or education and don't know which scheme fits, e.g. "I want to open a tea shop, what loan can I get", "mujhe business ke liye loan chahiye", "kaunsi loan scheme milegi mujhe", or a bare answer to a question just asked about project cost / annual income / category / gender in a loan context — NOT general welfare-scheme discovery (that's eligibility_query, which covers pensions, scholarships, housing etc.), NOT a named scheme's terms (credit_faq), NOT starting an application for an already-chosen scheme (credit_application)
- credit_faq: asking about an NSFDC concessional credit SCHEME'S OWN TERMS — interest rate, loan amount/ceiling, margin money, moratorium, tenure, income ceiling — e.g. "Term Loan ka interest rate kitna hai", "Micro Finance scheme mein kitna loan milega", "margin money kya hota hai" — NOT wanting to start applying (that's credit_application) and NOT a general welfare-scheme discovery question (that's eligibility_query)
- application_request: wants general guidance on HOW to apply for any scheme (not credit-specific slot-filling) — e.g. "PM Kisan ke liye kaise apply karein", "what's the process to apply"
- grievance: complaint about a rejected/stuck/missing payment or application
- comparison: comparing two or more specific schemes against each other
- financial_plan: wants total benefit calculation across all schemes they qualify for
- document_verify: uploading or asking about a document (Aadhaar, income cert, etc.)
- status_check: checking status of an application they already submitted
- csc_assist: a CSC operator asking for help on behalf of a citizen
- small_talk: greeting (hello/namaste/hi), thanks, goodbye, "who are you / what can you do", or chit-chat with NO facts about their situation and NO scheme question

Only pick eligibility_query if the message actually asks about schemes or gives situation facts (state, occupation, income, age, etc.). A bare greeting is small_talk, never eligibility_query.

Examples:
- "Mujhe is scheme ke liye apply karna hai" -> credit_application
- "Micro Finance Scheme ke liye application shuru karo" -> credit_application
- "I want to apply for this scheme" -> credit_application
- "Aajeevika loan ke liye form fill karna hai" -> credit_application
- "I want to open a tea shop, which loan can I get" -> credit_eligibility
- "mujhe business ke liye loan chahiye, kaunsi scheme milegi" -> credit_eligibility
- "the total cost of the project would be around 5 lakh" -> credit_eligibility
- "my annual family income is 3 lakh" -> credit_eligibility
- "Term Loan ka interest rate kitna hai" -> credit_faq
- "Udyam Nidhi mein maximum kitna loan milta hai" -> credit_faq
- "margin money kya hota hai" -> credit_faq
- "PM Kisan ke liye kaise apply karein" -> application_request
- "Scholarship ke liye apply karne ka process kya hai" -> application_request

Message (may be in Hindi, Hinglish, or English): "{message}"

Respond with ONLY a JSON object: {{"intent": "<one of the labels above>"}}"""


async def classify_intent(state: GraphState) -> GraphState:
    messages = state.get("messages", [])
    last_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

    sanitized, blocked, reason = check_injection(last_user_message)
    if blocked:
        logger.warning("Injection guard blocked message: %s", reason)
        state["intent"] = "blocked"
        state["reply"] = "Maaf kijiye, aapka message process nahi ho saka. Kripya dobara try karein."
        return state

    masked, pii_found = mask_pii(sanitized)
    if pii_found:
        logger.info("PII masked before LLM call: %s", pii_found)

    prompt = _CLASSIFY_PROMPT.format(message=masked)
    response = await ainvoke_with_fallback(prompt, temperature=0.0)
    raw = response.content.strip()

    intent = "eligibility_query"  # safe default — most messages are implicitly eligibility queries
    try:
        cleaned = raw.strip("`").removeprefix("json").strip()
        parsed = json.loads(cleaned)
        candidate = parsed.get("intent", "")
        if candidate in INTENTS:
            intent = candidate
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Intent classifier returned non-JSON, defaulting to eligibility_query: %r", raw)

    state["intent"] = intent
    state.setdefault("reasoning_trace", []).append({
        "agent_name": "orchestrator.intent_classifier",
        "tool_called": "llm_classify",
        "input": masked[:500],
        "output": intent,
        "reasoning": raw[:500],
    })
    return state
