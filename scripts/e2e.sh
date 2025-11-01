#!/usr/bin/env bash
set -Eeuo pipefail
: "${PROD:?}"; : "${ACTIONS_BEARER:?}"

step(){ printf "\n\033[1m▶ %s\033[0m\n" "$*"; }
mkdir -p scripts/tmp

step "Phase 1 — derive-concepts"
curl -sS -X POST "$PROD/derive-concepts" \
  -H "Authorization: Bearer $ACTIONS_BEARER" \
  -H "Content-Type: application/json" \
  -d '{"album_info":{"title":"Winter Love","style":"pop ballad","lyrics":"snow and warm hands"}}' \
  > scripts/tmp/DC.json

python - <<'PY'
import json,sys
d=json.load(open("scripts/tmp/DC.json"))
c=d["concepts"][0]
sel={"id":c["id"],"title":c["title"],"logline":c["logline"],"style":c["style"],
     "anchors":c.get("anchors",{}),"cast":c.get("cast",[]),"storyline":c["storyline"]}
open("scripts/tmp/SEL.json","w").write(json.dumps(sel))
print("[OK] selection -> scripts/tmp/SEL.json")
PY

step "Phase 3 — expand-scene"
python - <<'PY'
import json
sel=json.load(open("scripts/tmp/SEL.json"))
payload={"brief":"hot pack handoff","selection":sel,"duration_sec":3,"beats":5}
open("scripts/tmp/ES_payload.json","w").write(json.dumps(payload))
print("[OK] ES payload -> scripts/tmp/ES_payload.json")
PY

curl -sS -X POST "$PROD/expand-scene" \
  -H "Authorization: Bearer $ACTIONS_BEARER" \
  -H "Content-Type: application/json" \
  --data-binary @scripts/tmp/ES_payload.json \
  > scripts/tmp/ES.json

step "Phase 4 — qa-validate"
python - <<'PY'
import json
scene=json.load(open("scripts/tmp/ES.json"))["scene"]
payload={"scene":scene,"engine":"SORA"}
open("scripts/tmp/QV_payload.json","w").write(json.dumps(payload))
print("[OK] QV payload -> scripts/tmp/QV_payload.json")
PY

curl -sS -X POST "$PROD/qa-validate" \
  -H "Authorization: Bearer $ACTIONS_BEARER" \
  -H "Content-Type: application/json" \
  --data-binary @scripts/tmp/QV_payload.json \
  > scripts/tmp/QV.json

python - <<'PY'
import json
d=json.load(open("scripts/tmp/QV.json"))
print("----- EngineRender -----")
print(d["engine_render"])
r=d["report"]
print("\n[QA] severity:", r["severity"], "story_match:", r["story_match_score"], "coverage:", r["coverage_score"])
PY
