"""Shared fixtures.

Agent tools run real SQLAlchemy queries, so the tests give them a real session
backed by in-memory SQLite rather than a hand-written fake. The models use
portable column types, so the same schema applies cleanly.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Insight, Metric, MetricValue


@pytest.fixture
def db():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, future=True)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def make_metric(db):
    def _make(name: str, **overrides) -> Metric:
        metric = Metric(
            name=name,
            owner=overrides.pop("owner", "platform"),
            unit=overrides.pop("unit", "hours"),
            direction=overrides.pop("direction", "lower_is_better"),
            description=overrides.pop("description", None),
            **overrides,
        )
        db.add(metric)
        db.commit()
        return metric

    return _make


@pytest.fixture
def add_values(db):
    """Attach a daily series to a metric, most recent value last."""

    def _add(metric: Metric, values: list[float], dimensions: list[dict] | None = None) -> None:
        end = datetime.utcnow()
        for offset, value in enumerate(reversed(values)):
            db.add(
                MetricValue(
                    metric_id=metric.id,
                    ts=end - timedelta(days=offset),
                    value=value,
                    dimensions=(dimensions[len(values) - 1 - offset] if dimensions else {}),
                )
            )
        db.commit()

    return _add


@pytest.fixture
def add_insight(db):
    def _add(metric: Metric, **overrides) -> Insight:
        insight = Insight(
            metric_id=metric.id,
            headline=overrides.pop("headline", "Something moved"),
            summary=overrides.pop("summary", "A summary."),
            evidence_json=overrides.pop("evidence_json", {"pattern": "spike", "delta_pct": 0.25}),
            severity=overrides.pop("severity", "info"),
            created_at=overrides.pop("created_at", datetime.utcnow()),
            **overrides,
        )
        db.add(insight)
        db.commit()
        return insight

    return _add
