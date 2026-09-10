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
GROQ_FALLBACK_MODEL = "openai/gpt-oss-120b"  # llama-3.3-70b-versatile was retired from Groq's catalogue (confirmed via GET /v1/models, 2026-09-03) — this is Groq's current largest general-purpose model
# Local Ollama model for bulk/offline work. The free cloud tiers (Gemini 20/day,
# Groq's daily token cap) can't sustain a 1,300-scheme backfill; a local model
# has NO daily limit and no per-call cost, and structured eligibility-rule
# extraction is simple enough that a small 3B model handles it well. Opt in with
# prefer="ollama" (bulk callers) — it's NOT in the default chain, so interactive
# chat still prefers the sharper cloud models. Requires `ollama serve` running.
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Which provider interactive callers try FIRST. Env-driven rather than hardcoded
# because a provider outage is transient but costly: while Gemini was returning
# 503 on every call (2026-08-05), each chat turn paid a full failed round-trip
# before falling back to Groq — 2+ wasted calls per turn. Flipping this to "groq"
# via env removes that tax with no rebuild, and flips back when Gemini recovers.
DEFAULT_PREFER = os.getenv("LLM_PREFER", "gemini").strip().lower()


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


# Short code -> full name, for instructing a reply-composing prompt. Matches
# the frontend's language switcher (LANGUAGES in frontend/src/lib/i18n.jsx)
# and utils/sarvam.py's SARVAM_LANGUAGES keys, so a UI selection maps to
# both the text reply's language here and the TTS target elsewhere.
LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
}


def language_instruction(lang: str | None) -> str:
    """Builds the one line every reply-composing prompt should end its
    formatting instructions with.

    Real bug fixed 2026-09-10: every agent that composes a citizen-facing
    reply told the LLM to "reply in the SAME language the citizen's message
    is written in" — inferred purely from the message text/script, with
    state["lang"] (the language the citizen explicitly selected in the UI)
    captured into GraphState and persisted to Mongo, but never actually read
    by any prompt. A citizen who picked Tamil in the language switcher but
    typed in English, or whose STT transcript came back Romanized, got an
    English/Hinglish reply regardless of their selection — confirmed as the
    live "wrong language" complaint. Now the UI-selected language is the
    instruction, not a guess from the message; message-script inference is
    kept as the fallback only when lang is unset/unrecognized (e.g. very old
    sessions, or a caller that hasn't been updated to pass it)."""
    name = LANGUAGE_NAMES.get((lang or "").strip().lower())
    if name:
        return (
            f"Reply ONLY in {name}, in both meaning and script — the citizen selected {name} "
            f"in the app's language switcher, so reply in {name} even if their message itself "
            f"was typed or spoken in a different language."
        )
    return (
        "Reply in the SAME language and script the citizen's message is written in "
        "— never default to Hinglish if they didn't use it."
    )


def is_first_turn(messages: list[dict]) -> bool:
    """True only when `messages` holds nothing but the citizen's current
    message — i.e. this is truly the first turn of the session.

    Real bug fixed 2026-09-04, caught live: every reply-composing prompt
    (eligibility.py, small_talk.py) is a single flat string built ONLY from
    the current message — `ainvoke_with_fallback` has no notion of chat
    history, so the LLM has zero signal that a conversation is already under
    way. Told "You are Sathi, a friendly assistant... introduce yourself if
    greeted", it re-introduces itself nearly every turn — confirmed live: a
    citizen said "Hmm" and "दिखाओ बताओ यही" mid-conversation (after profile
    was already established and schemes already shown) and got a full
    "Namaste! Main Sathi hoon..." re-introduction both times. Callers should
    pass this into their prompt to explicitly suppress re-introduction after
    turn one, rather than trying to smuggle full history into every prompt."""
    return len(messages or []) <= 1


def get_llm(temperature: float = 0.3):
    """Returns a LangChain chat model: Gemini if GEMINI_API_KEY is set, else Groq.
    Kept for callers that just need *a* model and don't need call-time fallback."""
    llm = _gemini_llm(temperature) or _groq_llm(temperature)
    if llm is None:
        raise RuntimeError("Neither GEMINI_API_KEY nor GROQ_API_KEY is set — cannot construct an LLM client.")
    return llm


async def ainvoke_with_fallback(
    prompt: str, temperature: float = 0.3, prefer: str | None = None, tags: list[str] | None = None
):
    """Tries `prefer` first (defaults to LLM_PREFER env, else Gemini); on ANY error
    (invalid key, quota, timeout) falls back to the other provider. This is the call
    site every agent/node should use instead of get_llm().ainvoke() directly.

    Interactive, per-chat-turn callers (intent classifier, Agent 1/8 replies)
    should leave `prefer` unset so LLM_PREFER decides — one call per turn stays
    well under the 5rpm free-tier quota. Bulk callers (normalizer.py, processing
    hundreds of schemes concurrently) should pass prefer="ollama" (local, no
    quota, no cost) or prefer="groq". The chosen provider is tried first, then
    the remaining providers in a sensible fallback order — so a single call
    still succeeds even if the preferred provider is down/unconfigured.

    `tags`: real bug fixed 2026-09-04, caught live — chat_turn.py's token
    streamer only excludes the "intent_classifier" LangGraph NODE from what
    reaches the citizen, but extract_profile_facts() runs its OWN LLM call
    (raw JSON output, e.g. '{"age": 22, "state": "UP"}') from INSIDE the same
    "agent1_eligibility" node as the real reply — so its structured JSON
    tokens streamed straight into the chat UI ahead of the actual reply,
    showing up as a garbled "{}"-looking artifact. Node-name filtering can't
    tell these two calls apart since they share a node; callers that make an
    internal, non-reply LLM call (extraction, classification, anything whose
    output must never reach the citizen verbatim) must pass
    tags=["internal"] so the streamer can exclude by tag instead."""
    _factories = {"gemini": _gemini_llm, "groq": _groq_llm, "ollama": _ollama_llm}
    _label = {"gemini": "Gemini", "groq": "Groq", "ollama": "Ollama"}

    if prefer is None:
        prefer = DEFAULT_PREFER
    if prefer not in _factories:
        logger.warning("Unknown LLM preference %r — falling back to gemini", prefer)
        prefer = "gemini"

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
            return await llm.ainvoke(prompt, config={"tags": tags} if tags else None)
        except Exception as e:
            last_error = e
            logger.warning("%s call failed (%s: %s) — trying next provider", _label[key], e.__class__.__name__, e)

    if attempted:
        raise RuntimeError(f"All configured LLM providers failed; last error: {last_error}")
    raise RuntimeError("No LLM provider is configured (set GEMINI_API_KEY, GROQ_API_KEY, or OLLAMA_ENABLED).")
