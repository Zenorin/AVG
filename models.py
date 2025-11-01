# models.py
from __future__ import annotations

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field


# -----------------------------
# Domain Models
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
    anchors: Dict[str, List[str]] = Field(default_factory=dict)
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
    t: float
    beat: str
    intensity: float = Field(ge=0.0, le=1.0)


class SceneDraft(BaseModel):
    st: Dict[str, Any]
    ds: Dict[str, Any]
    dw: Dict[str, Any]
    timeline: List[TimelineBeat]
    drafts: Dict[str, str]


class QAReport(BaseModel):
    story_match_score: float
    coverage_score: float
    conflicts: List[str]
    severity: Literal["info", "warn", "fail"]


class QAValidateRequest(BaseModel):
    scene: SceneDraft
    engine: Literal["SORA", "VEO"] = "SORA"


class QAValidateResponse(BaseModel):
    engine_render: str
    report: QAReport


# ★ 여기가 포인트: 엔드포인트가 반환하는 정확한 스키마
class ExpandSceneResponse(BaseModel):
    scene: SceneDraft
