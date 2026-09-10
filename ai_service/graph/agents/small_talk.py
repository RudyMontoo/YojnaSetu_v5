"""
small_talk.py — node for greetings/thanks/chit-chat ("hello", "namaste",
"who are you"). Exists because the classifier previously had no such label:
"hello" got forced into eligibility_query, vector search returned the 5
nearest schemes to the word "hello" (i.e. random ones, wrong state
included), and the composer presented them as personalized — confidently
wrong. This node answers warmly and invites the citizen to share facts,
but attaches ZERO scheme cards and never claims to have searched anything.
"""
import logging

from ai_service.graph.llm import ainvoke_with_fallback, is_first_turn, language_instruction
from ai_service.graph.state import GraphState

logger = logging.getLogger(__name__)

_PROMPT = """You are Sathi, the friendly assistant of Yojna Sarthi, which helps Indian citizens discover government welfare schemes they qualify for.

The citizen sent a greeting or casual message (not a scheme question): "{message}"

{intro_instruction}

Reply in 1-2 warm sentences. {language_hint} Do NOT mention, list, or invent any scheme names. Do not claim you searched anything."""

_FIRST_TURN_INSTRUCTION = "This is the very first message of the conversation — introduce yourself briefly, and invite them to tell you their state, occupation and yearly income so you can find matching schemes."
_LATER_TURN_INSTRUCTION = "This conversation is already under way — you have already introduced yourself earlier, so do NOT reintroduce yourself or re-explain who you are. Just respond naturally and briefly to what they said."

# Static fallback used only when the LLM call itself fails (all providers
# down/unconfigured) — a greeting must never error out. Per-language so an
# LLM outage doesn't also silently override the citizen's language
# selection, which is exactly what a bare Hinglish string did before.
_FALLBACK_REPLIES = {
    "en": "Namaste! I'm Sathi — your companion for government schemes. Tell me your state, "
          "occupation, and yearly income, and I'll find matching schemes for you.",
    "hi": "Namaste! Main Sathi hoon — sarkari yojnaon ka aapka saathi. "
          "Apna state, kaam aur saalana income bataiye, main aapke liye schemes dhundhta hoon.",
    "bn": "নমস্তে! আমি সাথী — সরকারি প্রকল্পের জন্য আপনার সঙ্গী। আপনার রাজ্য, পেশা এবং বার্ষিক "
          "আয় জানান, আমি আপনার জন্য উপযুক্ত প্রকল্প খুঁজে দেব।",
    "ta": "வணக்கம்! நான் சாத்தி — அரசு திட்டங்களுக்கான உங்கள் துணை. உங்கள் மாநிலம், தொழில் "
          "மற்றும் ஆண்டு வருமானத்தை சொல்லுங்கள், உங்களுக்கான திட்டங்களைக் கண்டறிகிறேன்.",
    "te": "నమస్తే! నేను సాథి — ప్రభుత్వ పథకాల కోసం మీ సహచరుడిని. మీ రాష్ట్రం, వృత్తి మరియు వార్షిక "
          "ఆదాయం చెప్పండి, మీకు సరిపోయే పథకాలను కనుగొంటాను.",
    "mr": "नमस्कार! मी साथी — सरकारी योजनांसाठी तुमचा सोबती. तुमचे राज्य, व्यवसाय आणि वार्षिक "
          "उत्पन्न सांगा, मी तुमच्यासाठी योग्य योजना शोधतो.",
}
_DEFAULT_FALLBACK_LANG = "hi"


async def run_small_talk(state: GraphState) -> GraphState:
    messages = state.get("messages", [])
    last_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    lang = (state.get("lang") or "").strip().lower()
    fallback_reply = _FALLBACK_REPLIES.get(lang, _FALLBACK_REPLIES[_DEFAULT_FALLBACK_LANG])

    intro_instruction = _FIRST_TURN_INSTRUCTION if is_first_turn(messages) else _LATER_TURN_INSTRUCTION

    try:
        response = await ainvoke_with_fallback(
            _PROMPT.format(
                message=last_user_message, intro_instruction=intro_instruction,
                language_hint=language_instruction(lang),
            ),
            temperature=0.5,
        )
        reply = response.content.strip() or fallback_reply
    except Exception:  # a greeting must never error out — static fallback
        logger.exception("small_talk LLM call failed, using static reply")
        reply = fallback_reply

    state["reply"] = reply
    state["active_schemes"] = []
    state.setdefault("reasoning_trace", []).append({
        "agent_name": "orchestrator.small_talk",
        "tool_called": "none",
        "input": last_user_message[:200],
        "output": "greeting reply, no retrieval",
        "reasoning": "small_talk intent — scheme search deliberately skipped",
    })
    return state
