"""
session_summary.py — writes conversation_sessions.summary at session end,
per the CLAUDE.md schema ("summary: string (written by Gemini at session
end)").

"Session end" on the web channel is the WebSocket disconnect —
routers/ws_router.py schedules this fire-and-forget when the socket
closes, so the citizen never waits on it and a summary failure never
breaks anything. Re-connects to the same session_id are fine: the summary
is simply rewritten when that connection ends too, covering the new turns
(summarizedMessageCount guards against re-summarizing an unchanged
session, e.g. connect-then-leave without chatting).

The REST path (POST /orchestrator/chat) has no end-of-session event, so
sessions used purely over REST don't get summaries — acceptable, since
the browser UI is WS-first with REST as a per-turn fallback.
"""
import asyncio
import logging
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from ai_service.graph.llm import ainvoke_with_fallback
from ai_service.utils.pii_masker import mask_pii

logger = logging.getLogger(__name__)

_MAX_TRANSCRIPT_CHARS = 6000  # keep the summary call cheap; old turns matter less

_SUMMARY_PROMPT = """Summarize this Yojna Setu conversation between a citizen and Sathi (a government welfare scheme assistant) in 2-3 sentences, in English.

Cover: the citizen's situation (state, occupation, income etc. if mentioned), which schemes were discussed, and any pending next step (e.g. "wants to apply for PM Kisan", "asked to compare two schemes").

Transcript:
{transcript}

Respond with ONLY the summary text — no preamble, no bullet points."""


async def write_session_summary(db: AsyncIOMotorDatabase, session_id: str) -> bool:
    """Summarize one session's transcript and persist it. Returns True if a
    summary was written. Never raises."""
    try:
        session = await db["conversation_sessions"].find_one({"sessionId": session_id})
        if not session:
            return False
        messages = session.get("messages") or []
        if len(messages) < 2:
            return False  # nothing to summarize (connected but never chatted)
        if session.get("summarizedMessageCount") == len(messages):
            return False  # already summarized exactly this transcript

        lines = []
        for m in messages:
            role = "Citizen" if m.get("role") == "user" else "Sathi"
            masked, _ = mask_pii(m.get("content") or "")
            lines.append(f"{role}: {masked}")
        transcript = "\n".join(lines)[-_MAX_TRANSCRIPT_CHARS:]

        response = await ainvoke_with_fallback(
            _SUMMARY_PROMPT.format(transcript=transcript), temperature=0.2, prefer="groq"
        )
        summary = response.content.strip()
        if not summary:
            return False

        await db["conversation_sessions"].update_one(
            {"sessionId": session_id},
            {"$set": {
                "summary": summary,
                "summarizedMessageCount": len(messages),
                "summarizedAt": datetime.now(timezone.utc),
            }},
        )
        logger.info("[SESSION-SUMMARY] wrote summary for %s (%d messages)", session_id, len(messages))
        return True
    except Exception as e:
        logger.warning("session summary failed for %s (non-fatal): %s: %s",
                       session_id, e.__class__.__name__, e)
        return False


_background_tasks: set = set()


def schedule_session_summary(db: AsyncIOMotorDatabase, session_id: str) -> None:
    """Fire-and-forget hook for the WS disconnect path."""
    task = asyncio.create_task(write_session_summary(db, session_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
