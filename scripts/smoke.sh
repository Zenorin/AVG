#!/usr/bin/env bash
set -Eeuo pipefail
: "${PROD:?}"; : "${ACTIONS_BEARER:?}"
http(){ curl -sS -o /dev/null -w "%{http_code}" -L "$@"; }

echo "▶ health"
for p in /health /healthz /getHealth /health/; do
  c=$(http "$PROD$p"); [ "$c" = "200" ] || { echo "FAIL $p => $c"; exit 1; }
done && echo "OK health"

echo "▶ privacy"
for p in /privacy /getPrivacy /privacy/; do
  c=$(http "$PROD$p"); [ "$c" = "200" ] || { echo "FAIL $p => $c"; exit 1; }
done && echo "OK privacy"

echo "▶ derive-concepts unauth (401/403)"
for p in /derive-concepts /derive_concepts; do
  c=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "$PROD$p" \
       -H 'Content-Type: application/json' -d '{"album_info":{"title":"t","style":"s","lyrics":"l"}}')
  case "$c" in 401|403) : ;; *) echo "FAIL $p expect 401/403 got $c"; exit 1;; esac
done && echo "OK derive-concepts unauth"

echo "▶ derive-concepts auth (200)"
for p in /derive-concepts /derive_concepts; do
  c=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "$PROD$p" \
       -H "Authorization: Bearer $ACTIONS_BEARER" -H 'Content-Type: application/json' \
       -d '{"album_info":{"title":"t","style":"s","lyrics":"l"}}')
  [ "$c" = "200" ] || { echo "FAIL $p expect 200 got $c"; exit 1; }
done && echo "OK derive-concepts auth"

echo "✅ All smoke checks passed."
