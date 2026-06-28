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
    server → client: {"reply": "...", "intent": "...", "active_schemes": [...]}
    on error:        {"error": "..."} (connection stays open for retryable
                     errors like malformed JSON; closes on auth failure)

Token streaming (the "streams LLM tokens" part of the spec) is NOT
implemented yet — each turn sends one complete reply message. Streaming
needs the orchestrator graph's compose step to expose an async token
iterator, which is a deeper change than this transport wrapper; the
message protocol above is forward-compatible with adding
{"type": "token", ...} frames later.
"""
import json
import logging

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder

from ai_service.db.mongo import ensure_indexes, get_db
from ai_service.graph.chat_turn import run_chat_turn
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
                result = await run_chat_turn(
                    db,
                    citizen_id=citizen_id,
                    session_id=session_id,
                    message=message,
                    channel=payload.get("channel", "web"),
                    lang=payload.get("lang", "hi"),
                    profile=payload.get("profile") or spring_profile,
                )
                # jsonable_encoder: scheme docs carry datetime fields (lastUpdated) —
                # the REST path serializes them via Pydantic, but send_json is plain
                # json.dumps and crashes on datetime. Found by real WS test, not review.
                await websocket.send_json(jsonable_encoder(result))
            except Exception:
                # One failed turn shouldn't kill the connection — log it, tell the
                # citizen something went wrong, keep the session usable.
                logger.exception("[WS] chat turn failed for session %s", session_id)
                await websocket.send_json({"error": "Kuch galat ho gaya — please dobara try karein."})
    except WebSocketDisconnect:
        logger.info("[WS] session %s disconnected", session_id)
