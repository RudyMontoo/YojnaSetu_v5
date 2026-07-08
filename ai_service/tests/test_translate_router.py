"""translate_router — the cache-key derivation. The cache is the whole
efficiency story (each string translated once, ever), so the key must be
stable and language-scoped: same text + same lang → same key; different
lang → different key."""
from ai_service.routers.translate_router import _cache_id


def test_cache_id_is_stable():
    assert _cache_id("hi", "Load more") == _cache_id("hi", "Load more")


def test_cache_id_language_scoped():
    assert _cache_id("hi", "Load more") != _cache_id("ta", "Load more")


def test_cache_id_text_scoped():
    assert _cache_id("hi", "Load more") != _cache_id("hi", "Load less")


def test_cache_id_format():
    cid = _cache_id("bn", "Eligibility")
    assert cid.startswith("bn:")
    # sha1 hex is 40 chars
    assert len(cid.split(":", 1)[1]) == 40
