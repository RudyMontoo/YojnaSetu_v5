"""
internal_router.py — service-to-service endpoints Spring Boot calls INTO
ai_service (the reverse direction of utils/spring_client.py's outbound
calls). Gated by the same require_api_key (X-API-Key) dependency every
other service-level endpoint already uses — ai_service only has the one
shared secret (INTERNAL_API_KEY), no separate internal-key scheme needed.
"""
import logging

from fastapi import APIRouter, Depends

from ai_service.db.mongo import get_db
from ai_service.utils.auth import require_api_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/internal", tags=["internal"])


@router.delete("/citizen/{citizen_id}/data", dependencies=[Depends(require_api_key)])
async def delete_citizen_data(citizen_id: str):
    """
    DPDP Act erasure cascade — deletes every ai_service-owned document tied
    to this citizen_id. Called by Spring Boot's DELETE /api/v2/user/me
    AFTER it has already deleted its own collections (citizen_profiles,
    applications, users), so a failure here never leaves ai_service data
    orphaned behind an auth identity that's already gone — worst case is
    the opposite (ai_service data survives a Spring Boot failure), which
    Spring Boot's own erasure retries/audit trail can catch.

    reasoning_traces has no direct userId field (keyed by session_id) —
    resolved via this citizen's conversation_sessions first. nudge_log
    (Agent 6, not built yet) is included for when it exists; deleting from
    a collection that doesn't exist yet is a Mongo no-op, not an error.

    Idempotent: deleting an already-erased or never-existed citizen_id
    returns all-zero counts, not an error.
    """
    db = get_db()

    session_ids = [
        doc["sessionId"]
        async for doc in db["conversation_sessions"].find({"userId": citizen_id}, {"sessionId": 1})
    ]

    traces_deleted = 0
    if session_ids:
        traces_result = await db["reasoning_traces"].delete_many({"session_id": {"$in": session_ids}})
        traces_deleted = traces_result.deleted_count

    sessions_result = await db["conversation_sessions"].delete_many({"userId": citizen_id})
    nudge_result = await db["nudge_log"].delete_many({"citizen_id": citizen_id})

    logger.info(
        "DPDP erasure cascade: citizen_id=%s conversation_sessions=%d reasoning_traces=%d nudge_log=%d",
        citizen_id, sessions_result.deleted_count, traces_deleted, nudge_result.deleted_count,
    )

    return {
        "conversation_sessions_deleted": sessions_result.deleted_count,
        "reasoning_traces_deleted": traces_deleted,
        "nudge_log_deleted": nudge_result.deleted_count,
    }
