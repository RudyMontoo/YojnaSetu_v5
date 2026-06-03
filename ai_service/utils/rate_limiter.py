"""
rate_limiter.py — Shared sliding-window rate limiter for Yojna Setu AI Service.

Usage:
    from ai_service.utils.rate_limiter import RateLimiter
    limiter = RateLimiter(max_requests=20, window_seconds=60)
    # In a route:
    limiter.check(client_ip)   # raises HTTP 429 if exceeded
"""
import time
from collections import defaultdict
from fastapi import HTTPException, Request


class RateLimiter:
    """
    In-memory sliding-window rate limiter keyed by client IP.
    Thread-safe for single-process deployments (Uvicorn single worker).
    """

    def __init__(self, max_requests: int, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._store: dict[str, list[float]] = defaultdict(list)

    def check(self, ip: str) -> None:
        """
        Check rate limit for the given IP.
        Raises HTTP 429 if the limit is exceeded.
        """
        now = time.monotonic()
        window_start = now - self.window_seconds
        # Slide the window — drop timestamps older than the window
        self._store[ip] = [t for t in self._store[ip] if t > window_start]

        if len(self._store[ip]) >= self.max_requests:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Rate limit exceeded: max {self.max_requests} requests "
                    f"per {int(self.window_seconds)}s. Please slow down."
                ),
            )
        self._store[ip].append(now)

    def get_client_ip(self, request: Request) -> str:
        """Extract real client IP, respecting X-Forwarded-For from reverse proxies."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can be a comma-separated list; first is the real client
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


# ── Pre-built limiters for each route group ────────────────────────────────────
# Import these directly in each router — do NOT create new instances per request.

chat_limiter   = RateLimiter(max_requests=20, window_seconds=60)   # 20/min
agent_limiter  = RateLimiter(max_requests=20, window_seconds=60)   # 20/min
voice_limiter  = RateLimiter(max_requests=10, window_seconds=60)   # 10/min (expensive)
status_limiter = RateLimiter(max_requests=15, window_seconds=60)   # 15/min
ocr_limiter    = RateLimiter(max_requests=10, window_seconds=60)   # 10/min (heavy CPU)
