#!/usr/bin/env bash
set -Eeuo pipefail

: "${PROD:?PROD not set}"; : "${ACTIONS_BEARER:?ACTIONS_BEARER not set}"

note(){ printf "\n\033[1m▶ %s\033[0m\n" "$*"; }
ok(){   printf "✅ %s\n" "$*"; }
fail(){ printf "❌ %s\n" "$*"; exit 1; }
http(){ curl -sS -L -H 'Accept: application/json' "$@"; }
code(){ curl -sS -o /dev/null -w "%{http_code}" "$@"; }

note "1) /privacy variants (200 기대)"
for p in /privacy "/privacy/" /privacy_privacy_get; do
  c=$(code -L "$PROD$p")
  [ "$c" = "200" ] || fail "$p => $c"
done
ok "privacy OK"

note "2) /openapi.json parse (3.1.0/3.1.1 기대)"
json="$(http "$PROD/openapi.json" || true)"
[ -n "${json:-}" ] || fail "empty body from /openapi.json"

openapi="$(python -c 'import sys,json; print(json.load(sys.stdin).get("openapi",""))' <<<"$json" 2>/dev/null || true)"
[ -n "$openapi" ] || fail "cannot parse /openapi.json (not JSON?)"
case "$openapi" in 3.1.0|3.1.1) : ;; *) fail "openapi version=$openapi" ;; esac

for must in getHealth getPrivacy deriveConcepts composeStills expandScene qaValidate; do
  echo "$json" | grep -q "\"operationId\": *\"$must\"" || fail "operationId missing: $must"
done
ok "openapi + operationIds OK"

note "3) /derive-concepts 무토큰 인증 거부 확인 (401 또는 403)"
c=$(code -X POST "$PROD/derive-concepts" -H 'Content-Type: application/json' -d '{"album_info":{"title":"t","style":"pop","lyrics":"l"}}')
case "$c" in 401|403) ok "no token => $c (expected)";; *) fail "expected 401/403, got $c";; esac

note "4) /derive-concepts 토큰 포함 200"
c=$(code -X POST "$PROD/derive-concepts" -H "Authorization: Bearer $ACTIONS_BEARER" -H 'Content-Type: application/json' -d '{"album_info":{"title":"t","style":"pop","lyrics":"l"}}')
[ "$c" = "200" ] || fail "expected 200, got $c"
ok "token => 200 OK"

ok "All smoke checks passed."
