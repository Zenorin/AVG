#!/usr/bin/env bash
set -Eeuo pipefail

: "${PROD:?PROD not set}"; : "${ACTIONS_BEARER:?ACTIONS_BEARER not set}"

http_code(){ curl -sS -o /dev/null -w "%{http_code}" "$@"; }

echo "▶ privacy (200 기대)"
for p in /privacy "/privacy/" /privacy_privacy_get; do
  c=$(http_code -L "$PROD$p")
  [ "$c" = "200" ] || { echo "FAIL $p => $c"; exit 1; }
done
echo "OK privacy"

echo "▶ openapi.json (3.1.0/3.1.1 + 필수 operationId 6종)"
curl -sS -L -H 'Accept: application/json' "$PROD/openapi.json" > scripts/tmp/openapi.json

python - <<'PY'
import json, sys
with open("scripts/tmp/openapi.json","r") as f:
    d=json.load(f)
print("openapi:", d.get("openapi"))
ops = []
for m in d.get("paths",{}).values():
    if isinstance(m, dict):
        for p in m.values():
            if isinstance(p, dict):
                oid = p.get("operationId")
                if oid: ops.append(oid)
need = {"getHealth","getPrivacy","deriveConcepts","composeStills","expandScene","qaValidate"}
miss = need - set(ops)
if miss:
    print("MISSING:", sorted(miss)); sys.exit(2)
PY

echo "▶ derive-concepts (무토큰: 401 또는 403 기대)"
c=$(http_code -X POST "$PROD/derive-concepts" \
      -H 'Content-Type: application/json' \
      -d '{"album_info":{"title":"t","style":"pop","lyrics":"l"}}')
case "$c" in
  401|403) echo "OK $c" ;;
  *) echo "FAIL expect 401/403 got $c"; exit 1 ;;
esac

echo "▶ derive-concepts (토큰 포함: 200 기대)"
c=$(http_code -X POST "$PROD/derive-concepts" \
      -H "Authorization: Bearer $ACTIONS_BEARER" \
      -H 'Content-Type: application/json' \
      -d '{"album_info":{"title":"t","style":"pop","lyrics":"l"}}')
[ "$c" = "200" ] && echo "OK 200" || { echo "FAIL $c"; exit 1; }

echo "✅ All smoke checks passed."
