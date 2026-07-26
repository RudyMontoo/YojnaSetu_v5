"""App-level smoke tests: the whole FastAPI app builds, every router mounts,
the expected routes exist, and the security-headers middleware fires. This is
the automated version of the "does `import ai_service.main` work and are the
routes wired" check that caught several real bugs this project (a decorator
still referencing a removed import, a route that silently stopped existing).

No Mongo / Sarvam / LLM: the app has no startup hooks, and these only touch
routes that return static data or reject before any I/O.
"""
from fastapi.testclient import TestClient

from ai_service.main import app

client = TestClient(app)

# Routes that must exist for the product to function — a regression that drops
# any of these (e.g. an import error taking a router down) fails loudly here.
EXPECTED_ROUTES = {
    "/",
    "/health",
    "/orchestrator/chat",
    "/agents/csc/alternatives",
    "/agents/financial-plan",
    "/agents/grievance",
    "/translate",
    "/ocr/scan",
    "/voice/conversation/answer",
    "/internal/citizen/{citizen_id}/data",
}


def _all_route_paths(routes):
    """Every route path in the app, recursing into included sub-routers.

    FastAPI >=0.140 no longer flattens `include_router()` routes into
    `app.routes`; each include becomes one `_IncludedRouter` mount (path=None)
    whose real routes hang off `.original_router`. Walk both that and the older
    flat/Mount layouts so this test works across FastAPI versions. (Router
    prefixes aren't reflected on the child `.path`, so HTTP assertions use the
    OpenAPI schema instead — this recursion is for prefix-less routes like WS.)
    """
    paths = set()
    for r in routes:
        p = getattr(r, "path", None)
        if p:
            paths.add(p)
        orig = getattr(r, "original_router", None)  # FastAPI >=0.140 _IncludedRouter
        if orig is not None and hasattr(orig, "routes"):
            paths |= _all_route_paths(orig.routes)
        elif not p and hasattr(r, "routes"):        # Mount / sub-app (older layout)
            paths |= _all_route_paths(r.routes)
    return paths


def test_expected_http_routes_are_mounted():
    # OpenAPI paths reflect every mounted HTTP route WITH its router prefix,
    # and are stable across FastAPI's internal route-storage changes.
    paths = set(app.openapi().get("paths", {}))
    missing = EXPECTED_ROUTES - paths
    assert not missing, f"expected routes missing from the app: {missing}"


def test_voice_websocket_route_mounted():
    # WebSocket routes aren't in the OpenAPI schema; find them by walking routes.
    paths = _all_route_paths(app.routes)
    assert "/ws/voice/{session_id}" in paths
    assert "/ws/session/{session_id}" in paths


def test_root_ok_and_security_headers_present():
    res = client.get("/")
    assert res.status_code == 200
    # SecurityHeadersMiddleware must stamp every response.
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in res.headers


def test_openapi_schema_builds():
    # A malformed route/response model would blow up schema generation.
    schema = app.openapi()
    assert schema["info"]["title"] == "Yojna Setu AI Service"
