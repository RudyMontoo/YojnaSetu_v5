"""
mongo.py — Async MongoDB connection layer for the v5.0 rebuild.

Replaces the in-memory session dicts scattered across rag_chain.py /
agent_router.py with real persistence. Points at MONGODB_URI, which is a
local Docker container in dev (docker run --name yojna-mongo -p 27017:27017
mongo:7) and Atlas (Mumbai region) in production — the code does not care
which, since both speak the same wire protocol.

$vectorSearch (Atlas Search) is NOT available on local/community MongoDB.
Code that needs vector similarity should go through db.vector_search, which
falls back to brute-force cosine locally and only uses $vectorSearch when
MONGODB_HAS_ATLAS_SEARCH=true is set (i.e. once a real Atlas cluster with a
search index exists).
"""
import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def get_db() -> AsyncIOMotorDatabase:
    """Returns the singleton Mongo database handle, creating the client on first use."""
    global _client, _db
    if _db is None:
        uri = os.getenv("MONGODB_URI")
        # Fail fast in production rather than silently connecting to a local
        # dev DB that isn't there (security-audit prompt 3.1). Dev keeps the
        # localhost convenience default.
        if not uri:
            if os.getenv("ENVIRONMENT", "development").lower().startswith("prod"):
                raise RuntimeError("MONGODB_URI is not set — refusing to start in production.")
            uri = "mongodb://localhost:27017"
        db_name = os.getenv("MONGODB_DB", "yojnasetu")
        _client = AsyncIOMotorClient(uri)
        _db = _client[db_name]
        logger.info(f"MongoDB connected: db={db_name}")
    return _db


async def ensure_indexes() -> None:
    """
    Creates the indexes CLAUDE.md documents for the collections this phase touches.
    Idempotent — safe to call on every startup.
    """
    db = get_db()
    await db["citizen_profiles"].create_index("userId", unique=True)
    await db["citizen_profiles"].create_index([("state", 1), ("category", 1), ("isBpl", 1)])
    await db["schemes"].create_index("schemeCode", unique=True)
    await db["schemes"].create_index([("state", 1)])
    await db["conversation_sessions"].create_index("sessionId", unique=True)
    await db["conversation_sessions"].create_index("userId")
    await db["reasoning_traces"].create_index("session_id")
    # trend_events per CLAUDE.md: TTL 30 days + compound for the 7-day aggregation.
    # Deviation from CLAUDE.md's schema noted: keyed by scheme_code, not scheme_id —
    # vector-search results (where "search" events originate) project _id out, and
    # scheme_code is the stable public identifier everywhere else in the API.
    # These indexes are created HERE ONLY — the Java TrendEvent model deliberately
    # declares none, to avoid the IndexOptionsConflict boot failure that two services
    # creating the same index under different names causes (found 2026-07-03).
    await db["trend_events"].create_index("at", expireAfterSeconds=30 * 24 * 3600)
    await db["trend_events"].create_index([("scheme_code", 1), ("user_state", 1), ("at", -1)])
    # nudge_log (Agent 6) per CLAUDE.md: TTL 90 days + a per-citizen dedup lookup.
    await db["nudge_log"].create_index("sent_at", expireAfterSeconds=90 * 24 * 3600)
    await db["nudge_log"].create_index([("citizen_id", 1), ("scheme_id", 1), ("message_type", 1), ("sent_at", -1)])
    logger.info("MongoDB indexes ensured")
