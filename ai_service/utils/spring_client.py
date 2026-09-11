"""
spring_client.py — ai_service's client for Spring Boot's internal,
service-to-service endpoints (InternalProfileController.java), gated by a
shared-secret `X-Internal-Key` header rather than a citizen JWT (these
calls aren't on behalf of a browser session — CLAUDE.md: "FastAPI ->
Spring Boot only, service JWT").

INTERNAL_API_KEY here must equal Spring Boot's `app.internal-service-key` —
kept in sync manually per the memory note; rotate both together.
"""
import logging
import os

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 5.0


async def fetch_citizen_profile(citizen_id: str) -> dict:
    """GET /internal/profile/{userId} — returns the decrypted CitizenProfile
    dict, or {} if Spring Boot has no profile yet for this citizen (new
    citizen, profile not created) or the call fails for any reason. Never
    raises — callers (financial-plan, orchestrator/chat) should degrade
    gracefully to an empty profile rather than 500 on a Spring Boot hiccup."""
    base_url = os.getenv("SPRING_BOOT_INTERNAL_URL", "http://localhost:8080").rstrip("/")
    internal_key = os.getenv("INTERNAL_API_KEY", "").strip()

    if not internal_key:
        logger.warning("INTERNAL_API_KEY not set — cannot call Spring Boot internal profile endpoint.")
        return {}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            resp = await client.get(
                f"{base_url}/internal/profile/{citizen_id}",
                headers={"X-Internal-Key": internal_key},
            )
        if resp.status_code == 404:
            return {}
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        logger.warning("fetch_citizen_profile(%s) failed: %s: %s", citizen_id, e.__class__.__name__, e)
        return {}


async def patch_citizen_profile(citizen_id: str, updates: dict) -> bool:
    """PATCH /internal/profile/{userId} — writes chat-learned profile facts
    (CLAUDE.md: 'FastAPI writes session-end profile updates'). Spring Boot
    creates the profile if it doesn't exist yet and recalculates
    profileCompleteness. Never raises — profile learning is best-effort."""
    base_url = os.getenv("SPRING_BOOT_INTERNAL_URL", "http://localhost:8080").rstrip("/")
    internal_key = os.getenv("INTERNAL_API_KEY", "").strip()

    if not internal_key or not updates:
        return False

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            resp = await client.patch(
                f"{base_url}/internal/profile/{citizen_id}",
                headers={"X-Internal-Key": internal_key},
                json=updates,
            )
        resp.raise_for_status()
        return True
    except httpx.HTTPError as e:
        logger.warning("patch_citizen_profile(%s) failed: %s: %s", citizen_id, e.__class__.__name__, e)
        return False


async def check_credit_eligibility(payload: dict) -> dict | None:
    """POST /api/v2/sih/credit/eligibility — the real, authoritative eligibility
    engine (CreditEligibilityService), NOT something ai_service computes itself.
    The eligibility_assistant chat exists to collect these fields conversationally;
    it must never answer "you qualify" from the LLM's own reasoning — see that
    module's docstring for why (the exact P0 bug this project already fixed once:
    quoting a scheme figure that wasn't real).

    Public endpoint, no X-Internal-Key needed — same reasoning as
    fetch_credit_products(). Returns None on any failure; the caller must
    surface "couldn't check right now", never a guessed verdict."""
    base_url = os.getenv("SPRING_BOOT_INTERNAL_URL", "http://localhost:8080").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            resp = await client.post(f"{base_url}/api/v2/sih/credit/eligibility", json=payload)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        logger.warning("check_credit_eligibility() failed: %s: %s", e.__class__.__name__, e)
        return None


async def fetch_credit_products() -> list[dict]:
    """GET /api/v2/sih/credit/products — the real NSFDC scheme catalogue
    (CreditProductSeeder's data), NOT ai_service's own scheme JSON (which has
    historically carried stale figures — see CreditProductSeeder's own
    docstring). This is a permitAll public endpoint (CreditSchemeController),
    so no X-Internal-Key is needed, unlike the profile calls above. Never
    raises — callers (application_assistant.py) must degrade to "couldn't
    look that up" rather than 500 on a Spring Boot hiccup."""
    base_url = os.getenv("SPRING_BOOT_INTERNAL_URL", "http://localhost:8080").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            resp = await client.get(f"{base_url}/api/v2/sih/credit/products")
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        logger.warning("fetch_credit_products() failed: %s: %s", e.__class__.__name__, e)
        return []
