"""
vector_search.py — swappable scheme similarity search.

Production target (per CLAUDE.md) is MongoDB Atlas Vector Search via a
$vectorSearch aggregation stage against a 384-dim `embedding` field. That
requires an Atlas Search index, which does not exist on local/community
MongoDB (this session's dev environment: docker run mongo:7). So this module
tries $vectorSearch first and transparently falls back to brute-force
in-Python cosine similarity — fine at our current scale (~300 schemes for
one pilot state) and correct in shape for when a real Atlas cluster lands.

Callers should not need to know which path executed.
"""
import logging

from motor.motor_asyncio import AsyncIOMotorDatabase

from ai_service.db.embeddings import cosine_similarity, embed_text
from ai_service.utils.states import state_match_variants

logger = logging.getLogger(__name__)

VECTOR_INDEX_NAME = "schemes_vector_index"  # must match the Atlas Search index name once created

# Below this cosine-similarity score, a "match" isn't a real topical match —
# vector search always returns its closest available candidates even when
# none of them are actually relevant (confirmed real case, 2026-09-03: "small
# business related to medical" matched an education/dropout-support scheme).
# Without a floor, evaluate_eligibility() would honestly-but-misleadingly
# score an irrelevant scheme as "not eligible" rather than say there's no
# good match. 0.35 is a reasonable starting default for all-MiniLM-L6-v2
# normalized embeddings on short queries — not empirically tuned against
# this catalogue yet; adjust once real query/match pairs can be reviewed.
MIN_RELEVANCE_SCORE = 0.35


def _state_filter_clause(state_filter: str) -> dict:
    """Matches the citizen's state in EITHER representation (2-char code or
    full name) plus central schemes (state=None). Real bug fixed here
    2026-07-03: profiles carry codes ("UP") but scheme docs carry full names
    ("Uttar Pradesh") — the old exact-match filter silently excluded every
    state scheme from every citizen's results."""
    return {"$or": [{"state": {"$in": state_match_variants(state_filter)}}, {"state": None}]}


async def scheme_vector_search(
    db: AsyncIOMotorDatabase,
    query_text: str,
    state_filter: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """Returns the top `limit` schemes most similar to query_text."""
    query_vec = embed_text(query_text)

    try:
        return await _atlas_vector_search(db, query_vec, state_filter, limit)
    except Exception as e:
        logger.info(f"$vectorSearch unavailable ({e.__class__.__name__}: {e}) — falling back to brute-force cosine")
        return await _bruteforce_vector_search(db, query_vec, state_filter, limit)


async def _atlas_vector_search(
    db: AsyncIOMotorDatabase, query_vec: list[float], state_filter: str | None, limit: int
) -> list[dict]:
    # Real bug fixed 2026-09-04, caught live: `$vectorSearch`'s own `limit` capped
    # results to the requested display count (e.g. 15) BEFORE the state `$match`
    # ran — so with ~5,000 schemes spread across many states, the top-15 GLOBAL
    # semantic matches for a query like "scheme related to student" easily landed
    # mostly outside the citizen's state, leaving as few as 2 after filtering.
    # Fetch a wide pool from $vectorSearch, filter by state, THEN trim to `limit`
    # — filtering must never happen after an already-small cap.
    pool_size = max(limit * 20, 100)
    pipeline = [
        {
            "$vectorSearch": {
                "index": VECTOR_INDEX_NAME,
                "path": "embedding",
                "queryVector": query_vec,
                "numCandidates": pool_size,
                "limit": pool_size,
            }
        },
    ]
    if state_filter:
        pipeline.append({"$match": _state_filter_clause(state_filter)})
    pipeline.append({"$project": {"embedding": 0, "_id": 0, "_similarity": {"$meta": "vectorSearchScore"}}})

    cursor = db["schemes"].aggregate(pipeline)
    results = await cursor.to_list(length=pool_size)
    if not results:
        raise RuntimeError("empty result — likely no Atlas Search index configured")
    relevant = [r for r in results if r.get("_similarity", 0) >= MIN_RELEVANCE_SCORE]
    return relevant[:limit]


async def _bruteforce_vector_search(
    db: AsyncIOMotorDatabase, query_vec: list[float], state_filter: str | None, limit: int
) -> list[dict]:
    mongo_filter = {}
    if state_filter:
        mongo_filter = _state_filter_clause(state_filter)

    scored = []
    cursor = db["schemes"].find(mongo_filter)
    async for doc in cursor:
        emb = doc.get("embedding")
        if not emb:
            continue
        score = cosine_similarity(query_vec, emb)
        scored.append((score, doc))

    scored = [(score, doc) for score, doc in scored if score >= MIN_RELEVANCE_SCORE]
    scored.sort(key=lambda t: t[0], reverse=True)
    top = scored[:limit]
    for score, doc in top:
        doc["_similarity"] = round(score, 4)
        doc.pop("embedding", None)
        doc.pop("_id", None)
    return [doc for _, doc in top]
