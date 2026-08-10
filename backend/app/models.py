from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db import Base


class Metric(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False, unique=True)
    owner = Column(String(64), nullable=False)
    unit = Column(String(32), nullable=True)
    direction = Column(String(16), nullable=False, default="neutral")  # higher_is_better | lower_is_better | neutral
    description = Column(Text, nullable=True)

    values = relationship("MetricValue", back_populates="metric", cascade="all, delete-orphan")
    changes = relationship("MetricChange", back_populates="metric", cascade="all, delete-orphan")
    insights = relationship("Insight", back_populates="metric", cascade="all, delete-orphan")


class MetricValue(Base):
    __tablename__ = "metric_values"

    id = Column(Integer, primary_key=True)
    metric_id = Column(Integer, ForeignKey("metrics.id", ondelete="CASCADE"), nullable=False, index=True)
    ts = Column(DateTime, nullable=False, index=True)
    value = Column(Float, nullable=False)
    dimensions = Column(JSON, nullable=False, default=dict)  # e.g., {"team": "alpha", "project": "X"}

    metric = relationship("Metric", back_populates="values")


class MetricChange(Base):
    __tablename__ = "metric_changes"

    id = Column(Integer, primary_key=True)
    metric_id = Column(Integer, ForeignKey("metrics.id", ondelete="CASCADE"), nullable=False, index=True)
    window_days = Column(Integer, nullable=False)
    delta = Column(Float, nullable=False)
    delta_pct = Column(Float, nullable=False)
    z_score = Column(Float, nullable=False)
    significance = Column(Float, nullable=False)  # 0..1
    pattern = Column(String(32), nullable=False)  # spike | drop | plateau | volatility
    detected_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    metric = relationship("Metric", back_populates="changes")
    segments = relationship("Segment", back_populates="change", cascade="all, delete-orphan")


class Segment(Base):
    __tablename__ = "segments"

    id = Column(Integer, primary_key=True)
    change_id = Column(Integer, ForeignKey("metric_changes.id", ondelete="CASCADE"), nullable=False, index=True)
    dimension = Column(String(64), nullable=False)
    value = Column(String(128), nullable=False)
    contribution = Column(Float, nullable=False)  # share of total delta, 0..1

    change = relationship("MetricChange", back_populates="segments")


class Insight(Base):
    __tablename__ = "insights"

    id = Column(Integer, primary_key=True)
    metric_id = Column(Integer, ForeignKey("metrics.id", ondelete="CASCADE"), nullable=False, index=True)
    change_id = Column(Integer, ForeignKey("metric_changes.id", ondelete="CASCADE"), nullable=True)
    headline = Column(String(256), nullable=False)
    summary = Column(Text, nullable=False)
    evidence_json = Column(JSON, nullable=False, default=dict)
    suggested_followup = Column(Text, nullable=True)
    severity = Column(String(16), nullable=False, default="info")  # info | warn | critical
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    metric = relationship("Metric", back_populates="insights")
