"""
eligibility_assistant_router.py — POST /eligibility-assistant/chat.

Deliberately PUBLIC, no auth dependency — unlike application_assistant_router
(which requires get_current_citizen_id), this is the same "learn before you
sign up" surface as CreditSchemeController's /eligibility endpoint in Spring
Boot: a citizen must be able to find out what they qualify for before
creating an account. Rate-limited by IP instead of citizen_id since there is
no citizen_id yet.

Stateless: the client holds `context` between turns (see
services/eligibility_assistant.py's module docstring for why) and sends it
back each request. Nothing is written to Mongo here.
"""
import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

from ai_service.services.eligibility_assistant import EligibilityAssistant
from ai_service.utils.rate_limiter import chat_limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/eligibility-assistant", tags=["eligibility-assistant"])


class EligibilityChatRequest(BaseModel):
    message: str
    language: str = "en"
    context: dict = {}


class EligibilityChatResponse(BaseModel):
    bot_reply: str
    context: dict
    results: dict | None = None


@router.post("/chat", response_model=EligibilityChatResponse)
async def eligibility_chat(req: EligibilityChatRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    chat_limiter.check(client_ip)

    assistant = EligibilityAssistant()
    result = await assistant.process_message(req.message, req.language, req.context)

    if result["results"]:
        logger.info("Eligibility assistant: results returned (verdict=%s)", result["results"].get("verdict"))

    return EligibilityChatResponse(
        bot_reply=result["bot_reply"], context=result["context"], results=result["results"],
    )
