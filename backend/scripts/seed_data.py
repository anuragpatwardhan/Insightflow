"""Generate 90 days of synthetic operational data for 4 metrics.

Inject realistic patterns so the analysis pipeline has something to find:
- ticket_resolution_hours: gradual spike in last 7d driven by Project X
- daily_active_users: drop in last 5d on the Mobile team
- deployment_failures: volatility increase in last week
- nps_score: stable plateau
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete

from app.db import SessionLocal
from app.models import Insight, Metric, MetricChange, MetricValue, Segment

rng = np.random.default_rng(42)
DAYS = 90
TEAMS = ["alpha", "bravo", "charlie", "delta"]
PROJECTS = ["Project X", "Project Y", "Project Z"]


def _series(base: float, noise: float, n: int, drift: float = 0.0) -> np.ndarray:
    trend = np.linspace(0, drift, n)
    return base + trend + rng.normal(0, noise, n)


def _write_metric(db, name, owner, unit, direction, description):
    m = Metric(name=name, owner=owner, unit=unit, direction=direction, description=description)
    db.add(m)
    db.flush()
    return m


def _emit(db, metric_id, ts, value, dims):
    db.add(MetricValue(metric_id=metric_id, ts=ts, value=float(value), dimensions=dims))


def seed():
    db = SessionLocal()
    try:
        # wipe in dependency order
        db.execute(delete(Insight))
        db.execute(delete(Segment))
        db.execute(delete(MetricChange))
        db.execute(delete(MetricValue))
        db.execute(delete(Metric))
        db.commit()

        now = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        days = [now - timedelta(days=i) for i in range(DAYS - 1, -1, -1)]

        # 1) ticket_resolution_hours — spike in last week driven by Project X
        m1 = _write_metric(
            db, "ticket_resolution_hours", "support_ops", "hours", "lower_is_better",
            "Mean hours from ticket open to resolution.",
        )
        for project in PROJECTS:
            base = {"Project X": 12.0, "Project Y": 9.0, "Project Z": 10.0}[project]
            for i, ts in enumerate(days):
                value = rng.normal(base, 1.2)
                if project == "Project X" and i >= DAYS - 7:
                    value += rng.uniform(3.5, 5.5)  # backlog spike
                _emit(db, m1.id, ts, max(value, 0.5), {"project": project})

        # 2) daily_active_users — drop in last 5 days on Mobile team
        m2 = _write_metric(
            db, "daily_active_users", "growth", "users", "higher_is_better",
            "Distinct users active per day per team segment.",
        )
        for team in TEAMS:
            base = {"alpha": 4200, "bravo": 3100, "charlie": 2700, "delta": 1900}[team]
            for i, ts in enumerate(days):
                value = rng.normal(base, base * 0.04)
                if team == "alpha" and i >= DAYS - 5:
                    value *= rng.uniform(0.78, 0.85)
                _emit(db, m2.id, ts, max(value, 0), {"team": team})

        # 3) deployment_failures — volatility increase in last week
        m3 = _write_metric(
            db, "deployment_failures", "platform", "count", "lower_is_better",
            "Failed deploys per day across services.",
        )
        for team in TEAMS[:3]:
            base = 2.0
            for i, ts in enumerate(days):
                noise = 0.6 if i < DAYS - 7 else 2.8
                value = max(0, rng.normal(base, noise))
                _emit(db, m3.id, ts, value, {"team": team})

        # 4) nps_score — plateau after prior volatility
        m4 = _write_metric(
            db, "nps_score", "product", "score", "higher_is_better",
            "Rolling NPS, daily.",
        )
        for i, ts in enumerate(days):
            if i < DAYS - 21:
                value = rng.normal(42, 6)
            else:
                value = rng.normal(45, 0.8)  # flattened
            _emit(db, m4.id, ts, value, {})

        db.commit()
        print(f"Seeded {DAYS} days for 4 metrics.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
