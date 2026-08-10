from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Metric, MetricValue
from app.schemas import MetricOut, MetricValuePoint

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", response_model=list[MetricOut])
def list_metrics(db: Session = Depends(get_db)):
    return db.scalars(select(Metric).order_by(Metric.name)).all()


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
