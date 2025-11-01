#!/usr/bin/env bash
set -Eeuo pipefail
: "${PROD:?}"; : "${ACTIONS_BEARER:?}"

json(){ python - <<'PY'
import json,sys; print(json.dumps(json.load(sys.stdin),ensure_ascii=False,indent=2))
PY
}

echo "▶ getPrivacy"
curl -sS "$PROD/privacy" | head -n 3 || true

echo "▶ deriveConcepts"
curl -sS -X POST "$PROD/derive-concepts" \
  -H "Authorization: Bearer $ACTIONS_BEARER" -H "Content-Type: application/json" \
  -d '{"album_info":{"title":"Winter Solace","style":"melancholic, cinematic, minor key, slow tempo","lyrics":"In the hush of falling snow, our hands met then let go; silence filled the space we used to know."}}' \
  > scripts/tmp/dc.json
cat scripts/tmp/dc.json | json

python - <<'PY'
import json; d=json.load(open("scripts/tmp/dc.json"))
c=d["concepts"][0]
sel={"id":c["id"],"title":c["title"],"logline":c["logline"],"style":c["style"],
     "anchors":c.get("anchors",{}),"cast":c.get("cast",[]),"storyline":c["storyline"]}
open("scripts/tmp/sel.json","w").write(json.dumps(sel))
print("[OK] sel.json")
PY

echo "▶ composeStills"
python - <<'PY'
import json
sel=json.load(open("scripts/tmp/sel.json"))
open("scripts/tmp/compose.json","w").write(json.dumps({"selection":sel,"count":3}))
PY
curl -sS -X POST "$PROD/compose-stills" \
  -H "Authorization: Bearer $ACTIONS_BEARER" -H "Content-Type: application/json" \
  --data-binary @scripts/tmp/compose.json | json

echo "▶ expandScene"
python - <<'PY'
import json
sel=json.load(open("scripts/tmp/sel.json"))
open("scripts/tmp/expand.json","w").write(json.dumps({"brief":"hot pack handoff","selection":sel,"duration_sec":3,"beats":5}))
PY
curl -sS -X POST "$PROD/expand-scene" \
  -H "Authorization: Bearer $ACTIONS_BEARER" -H "Content-Type: application/json" \
  --data-binary @scripts/tmp/expand.json > scripts/tmp/es.json
cat scripts/tmp/es.json | json

echo "▶ qaValidate"
python - <<'PY'
import json
scene=json.load(open("scripts/tmp/es.json"))["scene"]
open("scripts/tmp/qa.json","w").write(json.dumps({"scene":scene,"engine":"SORA"}))
PY
curl -sS -X POST "$PROD/qa-validate" \
  -H "Authorization: Bearer $ACTIONS_BEARER" -H "Content-Type: application/json" \
  --data-binary @scripts/tmp/qa.json | python - <<'PY'
import json,sys; d=json.load(sys.stdin)
print("----- EngineRender -----"); print(d["engine_render"])
r=d["report"]; print("\n[QA] severity:", r["severity"], "story_match:", r["story_match_score"], "coverage:", r["coverage_score"])
PY
