"""Shared pytest fixtures/setup for the ai_service test suite.

These are FAST, self-contained tests: pure functions (security guards,
matchers, validators) and TestClient smoke tests that don't require Mongo,
Sarvam, or an LLM. Integration behavior against the live stack is still
verified per-session by hand (documented in docs/status/); this suite is
the regression net that runs in CI on every push.

The .env is loaded so anything reading SARVAM/GROQ keys at import time
doesn't blow up, but no test here makes a real external call.
"""
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=False)
