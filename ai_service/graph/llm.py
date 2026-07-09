"""
llm.py — Gemini 2.5 Flash client for the Orchestrator, with the existing
Groq path kept alive as a fallback rather than deleted (per the rebuild
plan: Gemini's cost/latency profile is unproven in this codebase, Groq is
the thing that's actually been working).

Fallback is at call time, not just construction time. Two real failure
modes hit during this rebuild, both handled here rather than left as a
surprise:
  1. An invalid GEMINI_API_KEY (confirmed via direct curl — genuine
     rejected key, not a client bug) — checking "is the env var non-empty"
     isn't enough.
  2. The current key is on Gemini's FREE TIER: 5 requests/minute for
     gemini-2.5-flash. Fine for interactive chat (one call per turn), but
     bulk operations (scheme migration/discovery normalizing hundreds of
     schemes) blow through that in seconds and then pay Google's suggested
     ~18s retry delay per call if the client retries internally — so
     max_retries is capped low here to fail fast onto Groq instead of
     stalling, and bulk callers should pass prefer="groq" to skip the
     Gemini attempt (and its quota burn) entirely.
"""
import logging
import os

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.5-flash"
GROQ_FALLBACK_MODEL = "llama-3.3-70b-versatile"
# Local Ollama model for bulk/offline work. The free cloud tiers (Gemini 20/day,
# Groq's daily token cap) can't sustain a 1,300-scheme backfill; a local model
# has NO daily limit and no per-call cost, and structured eligibility-rule
# extraction is simple enough that a small 3B model handles it well. Opt in with
# prefer="ollama" (bulk callers) — it's NOT in the default chain, so interactive
# chat still prefers the sharper cloud models. Requires `ollama serve` running.
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def _gemini_llm(temperature: float):
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        return None
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL, google_api_key=gemini_key, temperature=temperature, max_retries=0
    )


def _groq_llm(temperature: float):
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key:
        return None
    from langchain_groq import ChatGroq
    return ChatGroq(model=GROQ_FALLBACK_MODEL, groq_api_key=groq_key, temperature=temperature)


def _ollama_llm(temperature: float):
    # Disabled unless explicitly opted in via OLLAMA_ENABLED, so a stray local
    # daemon never silently intercepts interactive traffic. Bulk scripts set it.
    if os.getenv("OLLAMA_ENABLED", "").strip().lower() not in ("1", "true", "yes"):
        return None
    from langchain_community.chat_models import ChatOllama
    return ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=temperature)


def get_llm(temperature: float = 0.3):
    """Returns a LangChain chat model: Gemini if GEMINI_API_KEY is set, else Groq.
    Kept for callers that just need *a* model and don't need call-time fallback."""
    llm = _gemini_llm(temperature) or _groq_llm(temperature)
    if llm is None:
        raise RuntimeError("Neither GEMINI_API_KEY nor GROQ_API_KEY is set — cannot construct an LLM client.")
    return llm


async def ainvoke_with_fallback(prompt: str, temperature: float = 0.3, prefer: str = "gemini"):
    """Tries `prefer` first (default Gemini); on ANY error (invalid key, quota,
    timeout) falls back to the other provider. This is the call site every
    agent/node should use instead of get_llm().ainvoke() directly.

    Interactive, per-chat-turn callers (intent classifier, Agent 1/8 replies)
    should use the default prefer="gemini" — one call per turn stays well
    under the 5rpm free-tier quota. Bulk callers (normalizer.py, processing
    hundreds of schemes concurrently) should pass prefer="ollama" (local, no
    quota, no cost) or prefer="groq". The chosen provider is tried first, then
    the remaining providers in a sensible fallback order — so a single call
    still succeeds even if the preferred provider is down/unconfigured.
    """
    _factories = {"gemini": _gemini_llm, "groq": _groq_llm, "ollama": _ollama_llm}
    _label = {"gemini": "Gemini", "groq": "Groq", "ollama": "Ollama"}

    # preferred first, then the other two in a default order
    order = [prefer] + [p for p in ("gemini", "groq", "ollama") if p != prefer]

    last_error = None
    attempted = False
    for key in order:
        llm = _factories[key](temperature)
        if llm is None:
            continue  # provider not configured/enabled — skip silently
        attempted = True
        try:
            return await llm.ainvoke(prompt)
        except Exception as e:
            last_error = e
            logger.warning("%s call failed (%s: %s) — trying next provider", _label[key], e.__class__.__name__, e)

    if attempted:
        raise RuntimeError(f"All configured LLM providers failed; last error: {last_error}")
    raise RuntimeError("No LLM provider is configured (set GEMINI_API_KEY, GROQ_API_KEY, or OLLAMA_ENABLED).")
