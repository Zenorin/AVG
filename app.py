import os
import re
import math
import json
from typing import List, Optional, Literal, Dict, Any

from fastapi import FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

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
# CORS
# -----------------------------

allowlist = [o.strip() for o in os.getenv("CORS_ALLOWLIST", "https://chat.openai.com").split(",") if o.strip()]
app = FastAPI(title=APP_NAME, version="0.3.1a")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowlist,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Data models
# -----------------------------

class AlbumInfo(BaseModel):
    title: str
    style: str
    lyrics: str

class DeriveConceptsRequest(BaseModel):
    album_info: AlbumInfo

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
# Utilities (heuristics, deterministic)
# -----------------------------

PALETTES = {
    "indie": ["muted teal", "burnt orange", "warm cream", "faded denim"],
    "pop": ["neon pink", "electric blue", "citrus yellow", "white"],
    "rock": ["charcoal", "crimson", "steel blue", "amber"],
    "lofi": ["soft beige", "sage", "dusty rose", "slate"],
}

LIGHTING_BANK = {
    "day": ["soft key from window", "gentle fill", "subtle rim"],
    "night": ["sodium-vapor key", "cool fill", "neon rim"],
}

DEFLT_LENS = 50


def _pick_palette(style: str) -> List[str]:
    style_key = style.lower()
    for k, v in PALETTES.items():
        if k in style_key:
            return v
    return ["neutral gray", "soft white", "warm amber"]


def _lighting_for_style(style: str) -> List[str]:
    if any(w in style.lower() for w in ["night", "noir"]):
        return LIGHTING_BANK["night"]
    return LIGHTING_BANK["day"]


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# -----------------------------
# Endpoints
# -----------------------------

@app.get("/health")
def health():
    return {"ok": True, "name": APP_NAME}


@app.post("/derive-concepts", response_model=DeriveConceptsResponse)
def derive_concepts(payload: DeriveConceptsRequest, _: bool = Security(require_bearer)):
    info = payload.album_info
    palette = _pick_palette(info.style)
    lighting = _lighting_for_style(info.style)

    base_id = _slug(info.title or "concept")
    concepts: List[Concept] = []

    variants = [
        ("A", "intimate, handheld realism"),
        ("B", "stylized, composed frames"),
        ("C", "kinetic, rhythmic cutting"),
    ]

    for code, flavor in variants:
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
        # MJ prompt; Sora-aligned anchors for palette/lighting
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
    brief = payload.brief.strip()
    sel = payload.selection

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
        "camera_move": "slow push-in",  # exactly one camera move
        "focus_transition": "rack to hands then back to eyes",
        "lighting_event": "subtle warm shift at contact (DS7)"
    }

    # DW: dynamic-weak (ambient)
    dw = {
        "micro_vfx": "soft breath in cold air",
        "ambient": "light crowd bokeh wobble",
    }

    # Timeline (beats / seconds / intensity)
    timeline = [
        TimelineBeat(t=0.0, beat="hold eye contact", intensity=0.3),
        TimelineBeat(t=0.8, beat="hands rise", intensity=0.5),
        TimelineBeat(t=1.4, beat="handoff contact", intensity=0.9),
        TimelineBeat(t=2.0, beat="settle (grip ~0.2s)", intensity=0.6),
        TimelineBeat(t=2.6, beat="micro smile + exhale", intensity=0.4),
    ]

    # Drafts (not for direct user display by GPT; EngineRender will be produced after QA)
    sora_draft = (
        "medium shot, eye-level, 85mm, shallow DOF; one camera move: slow push-in; subject: two 20s friends; "
        "background: winter street evening; action: hot pack handoff in a single beat; lighting: warm key, cool fill, rim; "
        "palette: " + ", ".join(sel.anchors.get("palette", [])) + "; timeline: 0.0 hold, 0.8 rise, 1.4 contact, 2.0 settle, 2.6 exhale; "
        "positives only; no clones; no watermark;"
    )
    veo_draft = sora_draft.replace("winter street evening", "city plaza dusk")

    scene = SceneDraft(
        st=st, ds=ds, dw=dw, timeline=timeline, drafts={"sora": sora_draft, "veo": veo_draft}
    )
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
    # AR lock
    if scene.st.get("ar") != "16:9":
        conflicts.append(HARD_CONFLICTS["ar_lock_missing"])

    # camera moves
    cm = scene.ds.get("camera_move", "")
    if any(k in cm for k in ["&", ",", "+"]):
        conflicts.append(HARD_CONFLICTS["multi_camera_moves"])

    # Weather↔VFX double-strong (heuristic: if micro_vfx mentions rain/snow + lighting_event mentions flash/strobe)
    if re.search(r"rain|snow|storm", json.dumps(scene.dw), re.I) and re.search(r"flash|strobe|intense", json.dumps(scene.ds), re.I):
        conflicts.append(HARD_CONFLICTS["weather_vfx_double_strong"])

    # Penetration limit (not modeled → assume within bounds unless payload flags it)
    if scene.ds.get("penetration_mm", 0) and scene.ds.get("penetration_mm", 0) > 2.0:
        conflicts.append(HARD_CONFLICTS["penetration_limit"])

    # Focal lock
    if not isinstance(scene.st.get("lens_mm"), (int, float)):
        conflicts.append(HARD_CONFLICTS["focal_not_locked"])

    # Digital crop (if provided)
    if scene.st.get("digital_crop_pct") and scene.st.get("digital_crop_pct") > 10:
        conflicts.append(HARD_CONFLICTS["digital_crop"])

    return conflicts


def _severity(story_match: float, coverage: float, conflicts: List[str]) -> Literal["info", "warn", "fail"]:
    # Threshold policy (fail if story_match<0.60 or coverage<0.70 or any hard conflict)
    if story_match < 0.60 or coverage < 0.70 or conflicts:
        # If conflicts exist, treat as fail (hard conflicts)
        return "fail"
    # Minor imperfections
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
        f"timeline: " + ", ".join([f"{b.t:.1f}s {b.beat}" for b in scene.timeline]) + "\n"
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