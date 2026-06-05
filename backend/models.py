"""
Pydantic models shared across the voice-to-dashboard backend.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ─── Pipeline Stages ────────────────────────────────────────────────────────────

class PipelineStage(str, Enum):
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    PLANNING = "planning"
    QUERYING = "querying"
    RENDERING = "rendering"


class StageStatus(str, Enum):
    ACTIVE = "active"
    DONE = "done"
    ERROR = "error"


class PipelineEvent(BaseModel):
    stage: PipelineStage
    status: StageStatus
    detail: Optional[str] = None


# ─── Visualization ──────────────────────────────────────────────────────────────

class VizType(str, Enum):
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    AREA = "area"
    KPI = "kpi"
    TABLE = "table"


class VizSpec(BaseModel):
    type: VizType
    x_key: Optional[str] = None
    y_keys: list[str] = Field(default_factory=list)
    title: str = ""
    summary: str = ""


# ─── Query Result ────────────────────────────────────────────────────────────────

class QueryResult(BaseModel):
    rows: list[dict] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    viz_spec: VizSpec = Field(default_factory=lambda: VizSpec(type=VizType.TABLE))
    sql: str = ""
    transcript: str = ""


# ─── Health ──────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    db_orders_count: int = 0
    db_customers_count: int = 0
    db_products_count: int = 0
