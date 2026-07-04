"""
ws_router.py — WSS /ws/session/{session_id}, CLAUDE.md's real target
surface for text chat ("Text chat WebSocket, streams LLM tokens"). The
REST endpoint POST /orchestrator/chat stays alive as the non-browser /
service-testing surface; both run the identical turn logic via
graph/chat_turn.py.

Auth: the httpOnly access_token cookie only — browsers cannot set custom
headers (X-API-Key) on a WebSocket handshake, so the citizen JWT is the
sole gate here, verified against Spring Boot's RS256 public key exactly
like the HTTP endpoints. Invalid/missing token → close 1008 (policy
violation) before any message is processed.

Message protocol (JSON both ways):
    client → server: {"message": "...", "lang": "hi", "channel": "web", "profile": {...}}
                     (lang/channel/profile optional, defaults hi/web/fetched-from-Spring-Boot)
    server → client, per turn:
        {"type": "token", "text": "..."}   0..N frames as the LLM generates
        {"type": "done", "reply": "...", "intent": "...", "active_schemes": [...]}
                     exactly one, authoritative — clients must replace any
                     accumulated token text with done.reply (a mid-stream
                     provider fallback can leave partial tokens behind)
    on error:        {"error": "..."} (connection stays open for retryable
                     errors like malformed JSON; closes on auth failure)

Tokens come from stream_chat_turn (graph/chat_turn.py), which taps LLM
calls inside the orchestrator's agent nodes via LangGraph
stream_mode="messages" — real generation-time tokens, not a re-chunked
finished reply.
"""
import json
import logging

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder

from ai_service.db.mongo import ensure_indexes, get_db
from ai_service.graph.chat_turn import stream_chat_turn
from ai_service.graph.session_summary import schedule_session_summary
from ai_service.utils.jwt_auth import citizen_id_from_websocket_cookies
from ai_service.utils.spring_client import fetch_citizen_profile

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

_indexes_ready = False


@router.websocket("/ws/session/{session_id}")
async def ws_session(websocket: WebSocket, session_id: str):
    global _indexes_ready

    try:
        citizen_id = citizen_id_from_websocket_cookies(websocket.cookies)
    except HTTPException as e:
        # Must accept before close to send a close code the client can read.
        await websocket.accept()
        await websocket.close(code=1008, reason=e.detail)
        return

    await websocket.accept()
    db = get_db()
    if not _indexes_ready:
        await ensure_indexes()
        _indexes_ready = True

    # Fetched once per connection, not per message — profile changes mid-conversation
    # are rare and the next connection picks them up.
    spring_profile = await fetch_citizen_profile(citizen_id)
    logger.info("[WS] session %s connected (citizen %s)", session_id, citizen_id)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
                message = payload["message"]
            except (json.JSONDecodeError, KeyError, TypeError):
                await websocket.send_json({"error": "Expected JSON: {\"message\": \"...\"}"})
                continue

            try:
                async for frame in stream_chat_turn(
                    db,
                    citizen_id=citizen_id,
                    session_id=session_id,
                    message=message,
                    channel=payload.get("channel", "web"),
                    lang=payload.get("lang", "hi"),
                    profile=payload.get("profile") or spring_profile,
                ):
                    # jsonable_encoder: scheme docs carry datetime fields (lastUpdated) —
                    # send_json is plain json.dumps and crashes on datetime. Token
                    # frames are cheap strings; only the done frame carries schemes.
                    await websocket.send_json(
                        frame if frame["type"] == "token" else jsonable_encoder(frame)
                    )
            except Exception:
                # One failed turn shouldn't kill the connection — log it, tell the
                # citizen something went wrong, keep the session usable.
                logger.exception("[WS] chat turn failed for session %s", session_id)
                await websocket.send_json({"error": "Kuch galat ho gaya — please dobara try karein."})
    except WebSocketDisconnect:
        logger.info("[WS] session %s disconnected", session_id)
    finally:
        # Session end on the web channel IS the socket closing (CLAUDE.md:
        # summary written at session end). Fire-and-forget — never blocks
        # the close, no-ops if nothing new was said since the last summary.
        schedule_session_summary(db, session_id)
