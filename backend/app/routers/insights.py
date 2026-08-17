from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.suppression import is_suppressed
from app.db import get_db
from app.models import Insight, Metric
from app.schemas import FeedbackOut, FeedbackRequest, FeedbackSummary, InsightOut

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
    include_suppressed: bool = Query(
        False,
        description="Include insights whose metric is currently suppressed.",
    ),
    db: Session = Depends(get_db),
):
    stmt = select(Insight, Metric).join(Metric, Metric.id == Insight.metric_id)
    if severity:
        stmt = stmt.where(Insight.severity == severity)
    if metric_id:
        stmt = stmt.where(Insight.metric_id == metric_id)
    stmt = stmt.order_by(Insight.created_at.desc()).limit(limit)

    rows = db.execute(stmt).all()
    if not include_suppressed:
        # Filtered in Python rather than SQL because expiry is a comparison
        # against "now" that has to agree with is_suppressed, and duplicating
        # that rule in a WHERE clause is how the two drift apart.
        rows = [(i, m) for i, m in rows if not is_suppressed(m)]

    return [_hydrate(i, m.name) for i, m in rows]


@router.get("/feedback/summary", response_model=FeedbackSummary)
def feedback_summary(db: Session = Depends(get_db)):
    """How well the insight generator is doing, by the only judge that counts.

    Declared before /{insight_id} so the literal path is matched first —
    otherwise "feedback" would be parsed as an insight id.
    """
    insights = db.scalars(select(Insight)).all()
    rated = [i for i in insights if i.helpful is not None]
    helpful = sum(1 for i in rated if i.helpful)
    return FeedbackSummary(
        total=len(insights),
        rated=len(rated),
        helpful=helpful,
        not_helpful=len(rated) - helpful,
        # None rather than 0.0 when nothing is rated: "no data" and "nothing was
        # useful" are very different signals.
        helpful_rate=(helpful / len(rated)) if rated else None,
    )


@router.post("/{insight_id}/feedback", response_model=FeedbackOut)
def submit_feedback(insight_id: int, req: FeedbackRequest, db: Session = Depends(get_db)):
    """Record whether an insight was useful. Re-rating replaces the old verdict."""
    insight = db.get(Insight, insight_id)
    if not insight:
        raise HTTPException(404, "Insight not found")

    insight.helpful = req.helpful
    insight.feedback_note = (req.note or "").strip() or None
    insight.feedback_at = datetime.utcnow()
    db.commit()
    db.refresh(insight)

    return FeedbackOut(
        insight_id=insight.id,
        helpful=insight.helpful,
        note=insight.feedback_note,
        feedback_at=insight.feedback_at,
    )


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
