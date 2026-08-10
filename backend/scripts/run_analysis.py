"""End-to-end pipeline: pull values, detect changes, rank segments, write insights.

Idempotent within a run window: clears prior MetricChange + Insight rows for the
metrics it touches, then re-derives them.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select

from app.analysis.narratives import build_insight
from app.analysis.segments import rank_segments
from app.analysis.trends import DetectionConfig, detect
from app.db import SessionLocal
from app.models import Insight, Metric, MetricChange, MetricValue, Segment


def _values_df(db, metric_id: int) -> pd.DataFrame:
    rows = db.scalars(
        select(MetricValue).where(MetricValue.metric_id == metric_id).order_by(MetricValue.ts)
    ).all()
    if not rows:
        return pd.DataFrame(columns=["ts", "value"])
    data = []
    for r in rows:
        row = {"ts": r.ts, "value": r.value}
        row.update(r.dimensions or {})
        data.append(row)
    return pd.DataFrame(data)


def run():
    cfg = DetectionConfig()
    db = SessionLocal()
    try:
        metrics = db.scalars(select(Metric)).all()
        # clear previous analysis output
        db.execute(delete(Insight))
        db.execute(delete(Segment))
        db.execute(delete(MetricChange))
        db.commit()

        total = 0
        for m in metrics:
            df = _values_df(db, m.id)
            if df.empty:
                continue

            # detection runs on the metric's overall daily mean
            agg = df.groupby(pd.Grouper(key="ts", freq="D"))["value"].mean().reset_index()
            changes = detect(agg, cfg)
            if not changes:
                continue

            for ch in changes:
                row = MetricChange(metric_id=m.id, **ch)
                db.add(row)
                db.flush()

                # pick the best dimension to drill into (first non-ts/value column)
                dims = [c for c in df.columns if c not in ("ts", "value")]
                segments: list[dict] = []
                if dims:
                    segments = rank_segments(df, dimension=dims[0], window_days=ch["window_days"])
                    for s in segments:
                        db.add(Segment(change_id=row.id, **s))

                insight = build_insight(
                    metric={"name": m.name, "direction": m.direction},
                    change=ch,
                    segments=segments,
                )
                db.add(Insight(metric_id=m.id, change_id=row.id, **insight))
                total += 1

        db.commit()
        print(f"Wrote {total} insights across {len(metrics)} metrics.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
