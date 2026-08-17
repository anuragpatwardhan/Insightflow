from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.suppression import is_suppressed, restore, suppress
from app.db import get_db
from app.models import Metric, MetricValue
from app.schemas import MetricOut, MetricValuePoint, SuppressionOut, SuppressRequest

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _suppression_out(metric: Metric) -> SuppressionOut:
    return SuppressionOut(
        metric_id=metric.id,
        suppressed=is_suppressed(metric),
        suppressed_until=metric.suppressed_until,
        suppression_reason=metric.suppression_reason,
    )


@router.get("", response_model=list[MetricOut])
def list_metrics(
    include_suppressed: bool = Query(
        True,
        description="Suppressed metrics are listed by default so they remain manageable.",
    ),
    db: Session = Depends(get_db),
):
    metrics = db.scalars(select(Metric).order_by(Metric.name)).all()
    if include_suppressed:
        return metrics
    return [m for m in metrics if not is_suppressed(m)]


@router.get("/{metric_id}", response_model=MetricOut)
def get_metric(metric_id: int, db: Session = Depends(get_db)):
    m = db.get(Metric, metric_id)
    if not m:
        raise HTTPException(404, "Metric not found")
    return m


@router.get("/{metric_id}/series", response_model=list[MetricValuePoint])
def get_series(
    metric_id: int,
    days: int = Query(60, ge=1, le=365),
    db: Session = Depends(get_db),
):
    if not db.get(Metric, metric_id):
        raise HTTPException(404, "Metric not found")
    since = datetime.utcnow() - timedelta(days=days)
    rows = db.scalars(
        select(MetricValue)
        .where(MetricValue.metric_id == metric_id, MetricValue.ts >= since)
        .order_by(MetricValue.ts)
    ).all()
    return [MetricValuePoint(ts=r.ts, value=r.value) for r in rows]


@router.post("/{metric_id}/suppress", response_model=SuppressionOut)
def suppress_metric(
    metric_id: int,
    req: SuppressRequest | None = None,
    db: Session = Depends(get_db),
):
    """Mute a noisy metric. An empty body suppresses indefinitely."""
    metric = db.get(Metric, metric_id)
    if not metric:
        raise HTTPException(404, "Metric not found")

    body = req or SuppressRequest()
    try:
        suppress(metric, days=body.days, reason=body.reason)
    except ValueError as e:
        # Surfaced as a 400 rather than a 500: the caller asked for something
        # invalid, they did not hit a bug.
        raise HTTPException(400, str(e))

    db.commit()
    db.refresh(metric)
    return _suppression_out(metric)


@router.delete("/{metric_id}/suppress", response_model=SuppressionOut)
def restore_metric(metric_id: int, db: Session = Depends(get_db)):
    """Bring a suppressed metric back into the feed."""
    metric = db.get(Metric, metric_id)
    if not metric:
        raise HTTPException(404, "Metric not found")
    if metric.suppressed_at is None:
        raise HTTPException(404, "Metric is not suppressed")

    restore(metric)
    db.commit()
    db.refresh(metric)
    return _suppression_out(metric)
