"""
application_assistant_router.py — POST /application-assistant/chat.

Deliberately its own endpoint, not folded into /orchestrator/chat: the SC
credit application flow is goal-directed slot-filling with its own state
(scheme_code, slots, missing_required, awaiting_confirmation, confirmed),
not a single classify-and-reply turn. The orchestrator's `credit_application`
intent (graph/agents/credit_application_intro.py) only detects the citizen
wants to start one and hands off — every turn after that, ChatPage.jsx calls
this endpoint directly, keyed by the SAME session_id so it reads/writes the
same conversation_sessions document (field: applicationContext), not a
separate session space.

Auth: get_current_citizen_id, same as every other citizen-scoped endpoint —
a browser can never hold a service secret, and this only ever acts on the
caller's own session data.
"""
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ai_service.db.mongo import get_db
from ai_service.services.application_assistant import ApplicationAssistant
from ai_service.utils.jwt_auth import get_current_citizen_id
from ai_service.utils.rate_limiter import chat_limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/application-assistant", tags=["application-assistant"])


class ApplyChatRequest(BaseModel):
    message: str
    session_id: str
    language: str = "en"


class ApplyChatResponse(BaseModel):
    bot_reply: str
    structured_payload: dict | None = None


@router.post("/chat", response_model=ApplyChatResponse)
async def apply_chat(req: ApplyChatRequest, citizen_id: str = Depends(get_current_citizen_id)):
    chat_limiter.check_key(citizen_id)
    db = get_db()

    session = await db["conversation_sessions"].find_one({"sessionId": req.session_id}) or {}
    context = session.get("applicationContext") or {}

    # "Is scheme ke liye" only resolves against a scheme genuinely surfaced
    # earlier THIS session (schemesShown, written by chat_turn.py's
    # _persist_turn) — never guessed from a bare pronoun with nothing to
    # anchor it to. Most recent shown scheme wins.
    shown = session.get("schemesShown") or []
    if shown and not context.get("scheme_code"):
        context["_last_shown_scheme_code"] = shown[-1]

    assistant = ApplicationAssistant()
    result = await assistant.process_message(req.message, req.language, context)

    await db["conversation_sessions"].update_one(
        {"sessionId": req.session_id},
        {
            "$set": {
                "sessionId": req.session_id,
                "userId": citizen_id,
                "applicationContext": result["context"],
            },
            "$push": {
                "messages": {"$each": [
                    {"role": "user", "content": req.message},
                    {"role": "assistant", "content": result["bot_reply"]},
                ]}
            },
        },
        upsert=True,
    )

    if result["structured_payload"]:
        logger.info(
            "Application assistant: payload confirmed for citizen %s, scheme %s",
            citizen_id, result["context"].get("scheme_code"),
        )

    return ApplyChatResponse(bot_reply=result["bot_reply"], structured_payload=result["structured_payload"])
