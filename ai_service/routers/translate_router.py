"""
translate_router.py — POST /translate: on-the-fly UI + scheme-content
translation via Sarvam Mayura, aggressively cached so each unique string is
translated exactly once, ever.

Why this exists: the frontend's static-string dictionary (lib/i18n.jsx)
can only translate a fixed set of registered UI phrases — it can't touch
the 1,900+ dynamic scheme names / benefit texts that come from MongoDB
(mostly English, from MyScheme.gov.in). When a citizen switches the UI to
Hindi/Tamil/etc., those scheme strings need live machine translation. The
browser can't call Sarvam directly (can't hold the API key), so it batches
the visible strings to this endpoint.

Caching is the whole game: 1,931 schemes × 5 languages is a lot of calls,
but only ~24 schemes are visible per page and every result is stored in
the `translation_cache` collection keyed by (lang, text-hash). After the
first viewer of any string in any language, every later viewer is a pure
DB hit — no Sarvam call, no quota burn, no latency. English is a
pass-through (source language, never translated).

Auth: citizen JWT cookie (get_current_citizen_id) — same gate as the
catalogue itself, and it keeps a stranger from hammering our Sarvam quota
with arbitrary text.
"""
import asyncio
import hashlib
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from pymongo import ReplaceOne

from ai_service.db.mongo import get_db
from ai_service.utils.jwt_auth import get_current_citizen_id

logger = logging.getLogger(__name__)
router = APIRouter(tags=["translate"])

# Sarvam Mayura caps input length; scheme names/benefits are short, but a few
# eligibility blurbs run long — truncate defensively rather than 400.
_MAX_LEN = 900
_CACHE = "translation_cache"


class TranslateRequest(BaseModel):
    texts: list[str]
    target_lang: str  # 2-char: hi, bn, ta, te, mr, en...


class TranslateResponse(BaseModel):
    translations: list[str]  # parallel to request.texts


def _cache_id(lang: str, text: str) -> str:
    return f"{lang}:{hashlib.sha1(text.encode('utf-8')).hexdigest()}"


def _translate_one_sync(text: str, target_lang_code: str) -> str:
    from ai_service.utils.sarvam import sarvam_translate
    return sarvam_translate(text[:_MAX_LEN], source_language="en-IN", target_language=target_lang_code)


@router.post("/translate", response_model=TranslateResponse)
async def translate(req: TranslateRequest, citizen_id: str = Depends(get_current_citizen_id)):
    from ai_service.utils.sarvam import get_sarvam_lang_code

    lang = (req.target_lang or "en").split("-")[0]

    # English (or anything Sarvam doesn't know) → identity, no work.
    if lang == "en":
        return TranslateResponse(translations=list(req.texts))
    lang_code = get_sarvam_lang_code(lang)  # "hi" -> "hi-IN"; "unknown" if unsupported
    if lang_code == "unknown":
        return TranslateResponse(translations=list(req.texts))

    db = get_db()

    # Dedup: identical strings (repeated benefit lines, etc.) translate once.
    uniques = list({t for t in req.texts if t and t.strip()})
    result: dict[str, str] = {}

    if uniques:
        ids = [_cache_id(lang, t) for t in uniques]
        cached = {doc["_id"]: doc["translated"]
                  async for doc in db[_CACHE].find({"_id": {"$in": ids}})}
        misses = [t for t in uniques if _cache_id(lang, t) not in cached]

        # Fill hits
        for t in uniques:
            cid = _cache_id(lang, t)
            if cid in cached:
                result[t] = cached[cid]

        # Translate misses concurrently (bounded), then persist.
        if misses:
            sem = asyncio.Semaphore(5)

            async def _do(text: str):
                async with sem:
                    try:
                        translated = await asyncio.to_thread(_translate_one_sync, text, lang_code)
                    except Exception as e:
                        logger.warning("translate failed for %r (%s) — passing through: %s", text[:40], lang, e)
                        translated = text  # graceful: show original rather than an error
                    return text, translated

            done = await asyncio.gather(*[_do(t) for t in misses])
            to_store = []
            for text, translated in done:
                result[text] = translated
                # Only cache genuine translations, not pass-through failures —
                # so a transient Sarvam outage doesn't freeze English into the cache.
                if translated != text:
                    to_store.append({
                        "_id": _cache_id(lang, text),
                        "lang": lang, "source": text[:_MAX_LEN], "translated": translated,
                    })
            if to_store:
                try:
                    await db[_CACHE].bulk_write(
                        [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in to_store],
                        ordered=False,
                    )
                except Exception as e:
                    logger.warning("translation_cache write failed (non-fatal): %s", e)

    # Map back to the caller's original order (including any empties/dupes).
    return TranslateResponse(translations=[result.get(t, t) for t in req.texts])
