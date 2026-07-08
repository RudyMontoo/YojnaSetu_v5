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


def test_expected_http_routes_are_mounted():
    paths = {getattr(r, "path", None) for r in app.routes}
    missing = EXPECTED_ROUTES - paths
    assert not missing, f"expected routes missing from the app: {missing}"


def test_voice_websocket_route_mounted():
    # WebSocket routes carry a path too; the live-voice endpoint must be present.
    paths = {getattr(r, "path", None) for r in app.routes}
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
