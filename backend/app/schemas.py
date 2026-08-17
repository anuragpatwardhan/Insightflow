from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class MetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    owner: str
    unit: str | None = None
    direction: str
    description: str | None = None


class SegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dimension: str
    value: str
    contribution: float


class InsightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    metric_id: int
    metric_name: str | None = None
    headline: str
    summary: str
    evidence_json: dict[str, Any]
    suggested_followup: str | None = None
    severity: str
    created_at: datetime


class MetricValuePoint(BaseModel):
    ts: datetime
    value: float


class SuppressRequest(BaseModel):
    """Omit `days` to suppress indefinitely."""

    days: float | None = None
    reason: str | None = None


class SuppressionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metric_id: int
    suppressed: bool
    suppressed_until: datetime | None = None
    suppression_reason: str | None = None


class FeedbackRequest(BaseModel):
    helpful: bool
    note: str | None = None


class FeedbackOut(BaseModel):
    insight_id: int
    helpful: bool
    note: str | None = None
    feedback_at: datetime


class FeedbackSummary(BaseModel):
    """Aggregate quality signal. `rated` excludes insights nobody judged."""

    total: int
    rated: int
    helpful: int
    not_helpful: int
    helpful_rate: float | None = None
