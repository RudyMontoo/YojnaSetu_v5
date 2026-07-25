#!/usr/bin/env bash
# smoke_test.sh — post-deploy sanity check against the LIVE public URL.
#
# Exercises the real user path (browser → frontend nginx → backends), not the
# internal services directly, so it catches the class of bug that unit tests
# miss: a broken nginx proxy hop, a backend that won't boot, an auth gate that
# silently opened or slammed shut, a stale revision. Runs the ~7 checks you'd
# otherwise curl by hand after every deploy.
#
# Usage:
#   ./deploy/azure/smoke_test.sh                 # derive URL from az (needs .env.deploy)
#   ./deploy/azure/smoke_test.sh https://yojsarthi.in
#   BASE=https://yojsarthi.in ./deploy/azure/smoke_test.sh
#
# Exit 0 = all passed; non-zero = at least one check failed (count = failures).

set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Resolve BASE URL ──────────────────────────────────────────────────────────
BASE="${1:-${BASE:-}}"
if [ -z "$BASE" ]; then
  [ -f "$HERE/.env.deploy" ] && set -a && . "$HERE/.env.deploy" && set +a
  RG="${RG:-yojna-setu}"
  FQDN="$(az containerapp show -g "$RG" -n frontend --query properties.configuration.ingress.fqdn -o tsv 2>/dev/null)"
  [ -n "$FQDN" ] && BASE="https://$FQDN"
fi
if [ -z "$BASE" ]; then
  echo "ERROR: no BASE url (pass as arg, set BASE=, or ensure az + .env.deploy resolve the frontend FQDN)"; exit 2
fi
BASE="${BASE%/}"
echo "==> Smoke test against: $BASE"
echo

PASS=0; FAIL=0
# code CHECK: METHOD PATH EXPECTED [DESC] — asserts the HTTP status equals EXPECTED.
check() {
  local method="$1" path="$2" expected="$3" desc="${4:-$2}" extra=("${@:5}")
  local got
  got="$(curl -s -o /dev/null -w '%{http_code}' -X "$method" --max-time 25 "${extra[@]}" "$BASE$path")"
  if [ "$got" = "$expected" ]; then
    printf "  \033[32mPASS\033[0m  %-6s %-42s %s\n" "$method" "$path" "($got) $desc"; PASS=$((PASS+1))
  else
    printf "  \033[31mFAIL\033[0m  %-6s %-42s expected %s, got %s — %s\n" "$method" "$path" "$expected" "$got" "$desc"; FAIL=$((FAIL+1))
  fi
}

JSON=(-H "Content-Type: application/json")

# 1) Frontend PWA is served
check GET  "/"                                   200 "frontend PWA served"
# 2) Spring gateway alive + auth gate intact (no cookie => rejected)
check GET  "/api/v2/profile/me"                  403 "profile requires auth (gateway up)"
check GET  "/api/v2/schemes/trending"            403 "trending requires auth"
# 3) OTP send works, then the anti-bombing throttle kicks in on immediate resend
SMOKE_EMAIL="smoke-$(date +%s)@example.com"
check POST "/api/v2/auth/otp/send"               200 "OTP send (first)"      "${JSON[@]}" --data "{\"email\":\"$SMOKE_EMAIL\"}"
check POST "/api/v2/auth/otp/send"               429 "OTP resend throttled"  "${JSON[@]}" --data "{\"email\":\"$SMOKE_EMAIL\"}"
# 4) ai-service reachable through the proxy + auth gate intact
check POST "/api/ai/orchestrator/chat"           403 "chat requires auth (ai-service up)" "${JSON[@]}" --data "{}"
check POST "/api/ai/agents/document/verify-ppo"  403 "Lens verify requires auth"

echo
echo "==> $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && echo "==> SMOKE OK" || echo "==> SMOKE FAILED"
exit "$FAIL"
