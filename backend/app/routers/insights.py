from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Insight, Metric
from app.schemas import InsightOut

router = APIRouter(prefix="/insights", tags=["insights"])


def _hydrate(insight: Insight, metric_name: str | None) -> InsightOut:
    return InsightOut(
        id=insight.id,
        metric_id=insight.metric_id,
        metric_name=metric_name,
        headline=insight.headline,
        summary=insight.summary,
        evidence_json=insight.evidence_json or {},
        suggested_followup=insight.suggested_followup,
        severity=insight.severity,
        created_at=insight.created_at,
    )


@router.get("", response_model=list[InsightOut])
def list_insights(
    severity: str | None = Query(None, pattern="^(info|warn|critical)$"),
    metric_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    stmt = select(Insight, Metric.name).join(Metric, Metric.id == Insight.metric_id)
    if severity:
        stmt = stmt.where(Insight.severity == severity)
    if metric_id:
        stmt = stmt.where(Insight.metric_id == metric_id)
    stmt = stmt.order_by(Insight.created_at.desc()).limit(limit)
    return [_hydrate(i, name) for i, name in db.execute(stmt).all()]


@router.get("/{insight_id}", response_model=InsightOut)
def get_insight(insight_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        select(Insight, Metric.name)
        .join(Metric, Metric.id == Insight.metric_id)
        .where(Insight.id == insight_id)
    ).first()
    if not row:
        raise HTTPException(404, "Insight not found")
    insight, name = row
    return _hydrate(insight, name)
