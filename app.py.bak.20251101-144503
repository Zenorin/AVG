import os
import re
import json
from typing import List, Optional, Literal, Dict, Any
from fastapi.responses import JSONResponse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
import logging

from pydantic import BaseModel, Field

from fastapi import Request

from starlette.middleware.proxy_headers import ProxyHeadersMiddleware

# -----------------------------
# Boot
# -----------------------------
load_dotenv()

APP_NAME = "DirectorOS Actions API (v0.3.1a)"
security = HTTPBearer(auto_error=True)

# -----------------------------
# Auth dependency (Bearer)
# -----------------------------
def require_bearer(credentials: HTTPAuthorizationCredentials = Security(security)):
    expected = os.getenv("ACTIONS_BEARER", "").strip()
    if not expected:
        raise HTTPException(status_code=500, detail="Server misconfigured: ACTIONS_BEARER not set")
    if credentials is None or credentials.credentials != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

# -----------------------------
# FastAPI & CORS
# -----------------------------
allowlist = [o.strip() for o in os.getenv("CORS_ALLOWLIST", "https://chat.openai.com").split(",") if o.strip()]

app = FastAPI(title=APP_NAME, version="0.3.1a", openapi_url="/_openapi.json")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowlist,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.add_middleware(ProxyHeadersMiddleware)
def custom_openapi():
    app.openapi_schema = None
    schema = get_openapi(
        title=APP_NAME,
        version="0.3.1a",
        routes=app.routes,
    )
    prod = os.getenv("PUBLIC_BASE_URL", "https://avg-production.up.railway.app/").rstrip("/") + "/"
    schema["servers"] = [
        {"url": prod, "description": "Production (Railway)"},
        {"url": "http://localhost:8000/", "description": "Local dev"},
    ]
    app.openapi_schema = schema
    return app.openapi_schema

app.openapi = custom_openapi

# -----------------------------
# Data models
# -----------------------------
class AlbumInfo(BaseModel):
    title: str
    style: str
    lyrics: str

class Controls(BaseModel):
    variants: int = Field(default=3, ge=1, le=6)
    palette_override: Optional[List[str]] = None
    lighting_override: Optional[List[str]] = None

class DeriveConceptsRequest(BaseModel):
    album_info: AlbumInfo
    controls: Optional[Controls] = None

class Concept(BaseModel):
    id: str
    title: str
    logline: str
    style: str
    cast: List[str] = Field(default_factory=list)
    anchors: Dict[str, List[str]] = Field(default_factory=dict)  # palette, lighting, props
    storyline: str

class DeriveConceptsResponse(BaseModel):
    concepts: List[Concept]

class ComposeStillsRequest(BaseModel):
    selection: Concept
    count: int = Field(3, ge=1, le=6)

class MJPrompt(BaseModel):
    id: str
    prompt: str
    ar: str = "16:9"
    notes: Dict[str, Any] = Field(default_factory=dict)

class ComposeStillsResponse(BaseModel):
    stills: List[MJPrompt]

class ExpandSceneRequest(BaseModel):
    brief: str
    selection: Concept
    image_url: Optional[str] = None
    duration_sec: float = 3.0
    beats: int = Field(default=5, ge=1, le=12)

class TimelineBeat(BaseModel):
    t: float  # seconds
    beat: str
    intensity: float = Field(ge=0.0, le=1.0)

class SceneDraft(BaseModel):
    st: Dict[str, Any]
    ds: Dict[str, Any]
    dw: Dict[str, Any]
    timeline: List[TimelineBeat]
    drafts: Dict[str, str]  # {"veo": "...", "sora": "..."}

class ExpandSceneResponse(BaseModel):
    scene: SceneDraft

class QAValidateRequest(BaseModel):
    scene: SceneDraft
    engine: Literal["SORA", "VEO"] = "SORA"

class QAReport(BaseModel):
    story_match_score: float
    coverage_score: float
    conflicts: List[str]
    severity: Literal["info", "warn", "fail"]

class QAValidateResponse(BaseModel):
    engine_render: str
    report: QAReport

# -----------------------------
# Utilities
# -----------------------------
PALETTES = {
    "indie": ["muted teal", "burnt orange", "warm cream", "faded denim"],
    "pop": ["neon pink", "electric blue", "citrus yellow", "white"],
    "rock": ["charcoal", "crimson", "steel blue", "amber"],
    "lofi": ["soft beige", "sage", "dusty rose", "slate"],
    "city pop": ["aqua", "coral", "lemon", "white"],
    "winter": ["soft beige", "sage", "dusty rose", "slate"],
}
LIGHTING_BANK = {
    "day": ["soft key from window", "gentle fill", "subtle rim"],
    "night": ["sodium-vapor key", "cool fill", "neon rim"],
    "dusk": ["warm low sun", "soft fill", "edge rim"],
}
DEFLT_LENS = 50

def _pick_palette(text: str) -> List[str]:
    s = text.lower()
    for k, v in PALETTES.items():
        if k in s:
            return v
    return ["neutral gray", "soft white", "warm amber"]

def _lighting_for_style(text: str) -> List[str]:
    s = text.lower()
    if any(w in s for w in ["night", "neon"]):
        return LIGHTING_BANK["night"]
    if any(w in s for w in ["dusk", "sunset", "twilight"]):
        return LIGHTING_BANK["dusk"]
    return LIGHTING_BANK["day"]

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

# -----------------------------
# Endpoints
# -----------------------------
@app.get("/health")
def health():
    return {"ok": True, "name": APP_NAME, "version": "0.3.1a"}

@app.get("/privacy")
def privacy():
    return FileResponse("privacy.html", media_type="text/html")

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")

@app.post("/derive-concepts", response_model=DeriveConceptsResponse)
def derive_concepts(payload: DeriveConceptsRequest, _: bool = Security(require_bearer)):
    info = payload.album_info
    controls = payload.controls or Controls()

    text = f"{info.style} {info.lyrics}"
    palette = controls.palette_override or _pick_palette(text)
    lighting = controls.lighting_override or _lighting_for_style(text)

    base_id = _slug(info.title or "concept")
    concepts: List[Concept] = []

    base_variants = [
        ("A", "intimate, handheld realism"),
        ("B", "stylized, composed frames"),
        ("C", "kinetic, rhythmic cutting"),
        ("D", "graphic, silhouette-driven"),
        ("E", "dreamy, soft diffusion"),
        ("F", "contrasty, neon noir"),
    ]
    for code, flavor in base_variants[:controls.variants]:
        concepts.append(
            Concept(
                id=f"{base_id}-{code.lower()}",
                title=f"{info.title} — {code}",
                logline=f"{flavor} take inspired by lyrics; one clear action per shot; character-first.",
                style=info.style,
                cast=["lead (20s)", "friend (20s)"],
                anchors={
                    "palette": palette,
                    "lighting": lighting,
                    "props": ["phone", "jacket", "hot pack"],
                },
                storyline="Meet-cute to parting micro-journey aligned to chorus/bridge beats.",
            )
        )

    return DeriveConceptsResponse(concepts=concepts)

@app.post("/compose-stills", response_model=ComposeStillsResponse)
def compose_stills(payload: ComposeStillsRequest, _: bool = Security(require_bearer)):
    sel = payload.selection
    count = payload.count

    frames = [
        ("wide establishing", "24 mm", "deep DOF", "fixed camera"),
        ("medium portrait", "85 mm", "shallow DOF", "slow push-in"),
        ("detail/insert", "50 mm", "macro-ish DOF", "fixed camera"),
        ("over-the-shoulder", "50 mm", "shallow DOF", "pan left"),
        ("profile two-shot", "35 mm", "medium DOF", "tilt up"),
        ("cutaway prop", "70 mm", "shallow DOF", "fixed camera"),
    ]

    stills: List[MJPrompt] = []
    for i in range(min(count, len(frames))):
        label, lens, dof, move = frames[i]
        prompt = (
            f"{label}, {sel.style} look, natural skin texture, {dof}, {lens}, one camera move: {move}; "
            f"palette: {', '.join(sel.anchors.get('palette', []))}; lighting: {', '.join(sel.anchors.get('lighting', []))}; "
            f"wardrobe: muted casual; texture: subtle grain; no watermark; --ar 16:9"
        )
        stills.append(
            MJPrompt(
                id=f"mj-{i+1}",
                prompt=prompt,
                ar="16:9",
                notes={"framing": label, "lens": lens, "move": move},
            )
        )

    return ComposeStillsResponse(stills=stills)

@app.post("/expand-scene", response_model=ExpandSceneResponse)
def expand_scene(payload: ExpandSceneRequest, _: bool = Security(require_bearer)):
    sel = payload.selection
    duration = float(payload.duration_sec)
    beats_n = int(payload.beats)

    # ST: static foundations
    st = {
        "ar": "16:9",
        "framing": "medium shot, eye-level",
        "lens_mm": 85,
        "dof": "shallow",
        "base_lighting": sel.anchors.get("lighting", ["soft key", "gentle fill", "rim"]),
    }

    # DS: dynamic-strong (single primary action + one camera move)
    ds = {
        "primary_action": "hot pack handoff (one clean beat)",
        "camera_move": "slow push-in",
        "focus_transition": "rack to hands then back to eyes",
        "lighting_event": "subtle warm shift at contact (DS7)",
    }

    # DW: dynamic-weak (ambient)
    dw = {
        "micro_vfx": "soft breath in cold air",
        "ambient": "light crowd bokeh wobble",
    }

    # 기본 비트 텍스트
    base_beats = [
        "hold eye contact",
        "hands rise",
        "handoff contact",
        "settle (grip ~0.2s)",
        "micro smile + exhale",
    ]
    beats_txt = base_beats[:beats_n] if beats_n <= len(base_beats) else base_beats + [f"beat {i}" for i in range(len(base_beats)+1, beats_n+1)]

    # 타임라인: 균등 분할
    timeline: List[TimelineBeat] = []
    for i, bt in enumerate(beats_txt):
        t = 0.0 if beats_n == 1 else (duration * i / (beats_n - 1))
        intensity_seq = [0.3, 0.5, 0.9, 0.6, 0.4]
        intensity = float(intensity_seq[i] if i < len(intensity_seq) else 0.5)
        timeline.append(TimelineBeat(t=round(t, 2), beat=bt, intensity=intensity))

    # 타임라인 문자열
    timeline_str = ", ".join([f"{b.t:.1f}s {b.beat}" for b in timeline])

    sora_draft = (
        "medium shot, eye-level, 85mm, shallow DOF; one camera move: slow push-in; subject: two 20s friends; "
        "background: winter street evening; action: hot pack handoff in a single beat; "
        f"palette: {', '.join(sel.anchors.get('palette', []))}; "
        f"timeline: {timeline_str}; "
        "positives only; no clones; no watermark;"
    )
    veo_draft = sora_draft.replace("winter street evening", "city plaza dusk")

    scene = SceneDraft(st=st, ds=ds, dw=dw, timeline=timeline, drafts={"sora": sora_draft, "veo": veo_draft})
    return ExpandSceneResponse(scene=scene)

# -----------------------------
# QA & Finalization
# -----------------------------
HARD_CONFLICTS = {
    "ar_lock_missing": "Missing AR 16:9 lock",
    "multi_camera_moves": "Multiple camera moves detected",
    "weather_vfx_double_strong": "Weather↔VFX double-strong forbidden",
    "penetration_limit": "Penetration exceeds 0.2 cm",
    "focal_not_locked": "Focal length not locked or invalid",
    "digital_crop": "DigitalCropInShot > 10%",
}

def _keyword_score(brief: str, draft: str) -> float:
    words = set(re.findall(r"[a-zA-Z]+", brief.lower()))
    if not words:
        return 0.7
    hits = sum(1 for w in words if w in draft.lower())
    return min(1.0, 0.5 + 0.5 * (hits / max(1, len(words))))

def _coverage_score(scene: SceneDraft) -> float:
    have = 0
    total = 6
    have += 1 if scene.st.get("ar") == "16:9" else 0
    have += 1 if scene.st.get("lens_mm") else 0
    have += 1 if scene.ds.get("primary_action") else 0
    have += 1 if scene.ds.get("camera_move") else 0
    have += 1 if scene.timeline else 0
    have += 1 if scene.dw.get("micro_vfx") else 0
    return have / total

def _detect_conflicts(scene: SceneDraft) -> List[str]:
    conflicts = []
    if scene.st.get("ar") != "16:9":
        conflicts.append(HARD_CONFLICTS["ar_lock_missing"])

    cm = scene.ds.get("camera_move", "")
    if any(k in cm for k in ["&", ",", "+"]):
        conflicts.append(HARD_CONFLICTS["multi_camera_moves"])

    if re.search(r"rain|snow|storm", json.dumps(scene.dw), re.I) and re.search(r"flash|strobe|intense", json.dumps(scene.ds), re.I):
        conflicts.append(HARD_CONFLICTS["weather_vfx_double_strong"])

    if scene.ds.get("penetration_mm", 0) and scene.ds.get("penetration_mm", 0) > 2.0:
        conflicts.append(HARD_CONFLICTS["penetration_limit"])

    if not isinstance(scene.st.get("lens_mm"), (int, float)):
        conflicts.append(HARD_CONFLICTS["focal_not_locked"])

    if scene.st.get("digital_crop_pct") and scene.st.get("digital_crop_pct") > 10:
        conflicts.append(HARD_CONFLICTS["digital_crop"])

    return conflicts

def _severity(story_match: float, coverage: float, conflicts: List[str]) -> Literal["info", "warn", "fail"]:
    if story_match < 0.60 or coverage < 0.70 or conflicts:
        return "fail"
    if story_match < 0.8 or coverage < 0.85:
        return "warn"
    return "info"

def _render_engine_block(engine: str, scene: SceneDraft) -> str:
    header = f"[BEGIN EngineRender {engine}]"
    footer = f"[END EngineRender {engine}]"
    body = (
        f"framing: {scene.st.get('framing')}; lens: {scene.st.get('lens_mm')}mm; DOF: {scene.st.get('dof')}; AR: {scene.st.get('ar')}\n"
        f"subject: two friends (20s), key prop: hot pack; background: winter street evening\n"
        f"action: {scene.ds.get('primary_action')} (one beat); camera_move: {scene.ds.get('camera_move')}\n"
        f"timeline: {', '.join([f'{b.t:.1f}s {b.beat}' for b in scene.timeline])}\n"
        f"lighting: " + ", ".join(scene.st.get('base_lighting', [])) + ". palette: muted warm neutrals.\n"
        f"safety: no clones; no watermark; penetration ≤ 0.2 cm; single camera move; focal locked.\n"
    )
    return "\n".join([header, body, footer])

@app.post("/qa-validate", response_model=QAValidateResponse)
def qa_validate(payload: QAValidateRequest, _: bool = Security(require_bearer)):
    scene = payload.scene
    engine = payload.engine

    story_match = _keyword_score(
        brief=json.dumps({"st": scene.st, "ds": scene.ds}),
        draft=scene.drafts.get("sora" if engine == "SORA" else "veo", ""),
    )
    coverage = _coverage_score(scene)
    conflicts = _detect_conflicts(scene)
    sev = _severity(story_match, coverage, conflicts)

    engine_render = _render_engine_block(engine, scene)

    report = QAReport(
        story_match_score=round(story_match, 3),
        coverage_score=round(coverage, 3),
        conflicts=conflicts,
        severity=sev,
    )

    return QAValidateResponse(engine_render=engine_render, report=report)

@app.get("/openapi.json", include_in_schema=False)
def serve_openapi_json():
    return JSONResponse(custom_openapi())

@app.get("/openapi.yaml", include_in_schema=False)
def serve_openapi_yaml():
    return FileResponse("openapi_local.yaml", media_type="application/yaml")
