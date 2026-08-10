"""Read-only tools the LLM agent can call to answer KPI questions.

Each tool:
- Takes simple JSON-serializable kwargs
- Returns a small JSON-serializable dict the model can reason over
- Touches the same Postgres data the feed pipeline uses
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.segments import rank_segments
from app.analysis.trends import DetectionConfig, detect
from app.models import Insight, Metric, MetricValue


# ---------- helpers ----------

def _values_df(db: Session, metric: Metric, days: int = 60) -> pd.DataFrame:
    since = datetime.utcnow() - timedelta(days=days)
    rows = db.scalars(
        select(MetricValue)
        .where(MetricValue.metric_id == metric.id, MetricValue.ts >= since)
        .order_by(MetricValue.ts)
    ).all()
    if not rows:
        return pd.DataFrame(columns=["ts", "value"])
    data = []
    for r in rows:
        d = {"ts": r.ts, "value": r.value}
        d.update(r.dimensions or {})
        data.append(d)
    return pd.DataFrame(data)


_SYNONYMS = {
    "time": {"hours", "duration", "seconds", "minutes"},
    "hours": {"time", "duration"},
    "users": {"dau", "active"},
    "dau": {"users", "active"},
    "failures": {"errors", "fails", "failed"},
    "deploys": {"deployments", "deployment"},
    "deployment": {"deploys", "deployments"},
}


def _tokens(s: str) -> set[str]:
    import re
    return {t for t in re.split(r"[^a-z0-9]+", s.lower()) if t}


def _expand(tokens: set[str]) -> set[str]:
    out = set(tokens)
    for t in tokens:
        out |= _SYNONYMS.get(t, set())
    return out


def _find_metric(db: Session, name: str) -> Metric | None:
    metrics = db.scalars(select(Metric)).all()
    if not metrics:
        return None
    name_l = name.strip().lower()
    for m in metrics:
        if m.name.lower() == name_l:
            return m
    for m in metrics:
        ml = m.name.lower()
        if name_l in ml or ml in name_l:
            return m
    user_toks = _expand(_tokens(name))
    if not user_toks:
        return None
    best, best_score = None, 0
    for m in metrics:
        m_toks = _expand(_tokens(m.name))
        score = len(user_toks & m_toks)
        if score > best_score:
            best, best_score = m, score
    return best if best_score >= 1 else None


# ---------- tools ----------

def list_metrics(db: Session) -> dict[str, Any]:
    metrics = db.scalars(select(Metric).order_by(Metric.name)).all()
    return {
        "metrics": [
            {
                "name": m.name,
                "owner": m.owner,
                "unit": m.unit,
                "direction": m.direction,
                "description": m.description,
            }
            for m in metrics
        ]
    }


def get_metric_overview(db: Session, metric_name: str, days: int = 30) -> dict[str, Any]:
    m = _find_metric(db, metric_name)
    if not m:
        return {"error": f"No metric matches '{metric_name}'. Use list_metrics to see options."}
    df = _values_df(db, m, days=max(days, 60))
    if df.empty:
        return {"error": f"No data for {m.name}."}
    daily = df.groupby(pd.Grouper(key="ts", freq="D"))["value"].mean()
    recent = daily.iloc[-7:]
    prior = daily.iloc[-35:-7] if len(daily) >= 35 else daily.iloc[:-7]
    return {
        "name": m.name,
        "unit": m.unit,
        "direction": m.direction,
        "current_7d_avg": float(recent.mean()),
        "prior_28d_avg": float(prior.mean()) if not prior.empty else None,
        "delta_pct_vs_prior_28d": (
            float((recent.mean() - prior.mean()) / (abs(prior.mean()) or 1e-9))
            if not prior.empty else None
        ),
        "min": float(daily.min()),
        "max": float(daily.max()),
        "n_days": int(len(daily)),
    }


def explain_change(db: Session, metric_name: str, window_days: int = 7) -> dict[str, Any]:
    m = _find_metric(db, metric_name)
    if not m:
        return {"error": f"No metric matches '{metric_name}'."}
    df = _values_df(db, m, days=90)
    if df.empty:
        return {"error": f"No data for {m.name}."}

    agg = df.groupby(pd.Grouper(key="ts", freq="D"))["value"].mean().reset_index()
    cfg = DetectionConfig(window_days=window_days)
    changes = detect(agg, cfg)

    if not changes:
        return {
            "metric": m.name,
            "verdict": "no_significant_change",
            "message": f"No meaningful change detected in {m.name} over the last {window_days} days.",
        }

    out = []
    dims = [c for c in df.columns if c not in ("ts", "value")]
    for ch in changes:
        segs = rank_segments(df, dimension=dims[0], window_days=window_days) if dims else []
        out.append({**ch, "top_segments": segs})

    return {"metric": m.name, "direction": m.direction, "changes": out}


def list_recent_insights(db: Session, severity: str | None = None, limit: int = 10) -> dict[str, Any]:
    stmt = select(Insight, Metric.name).join(Metric, Metric.id == Insight.metric_id)
    if severity in {"info", "warn", "critical"}:
        stmt = stmt.where(Insight.severity == severity)
    stmt = stmt.order_by(Insight.created_at.desc()).limit(limit)

    items = []
    for ins, mname in db.execute(stmt).all():
        items.append({
            "metric": mname,
            "headline": ins.headline,
            "severity": ins.severity,
            "pattern": (ins.evidence_json or {}).get("pattern"),
            "delta_pct": (ins.evidence_json or {}).get("delta_pct"),
        })
    return {"insights": items, "count": len(items)}


def compare_segments(db: Session, metric_name: str, dimension: str, window_days: int = 7) -> dict[str, Any]:
    m = _find_metric(db, metric_name)
    if not m:
        return {"error": f"No metric matches '{metric_name}'."}
    df = _values_df(db, m, days=60)
    if df.empty or dimension not in df.columns:
        avail = [c for c in df.columns if c not in ("ts", "value")]
        return {"error": f"Dimension '{dimension}' not available for {m.name}. Available: {avail}."}
    segs = rank_segments(df, dimension=dimension, window_days=window_days, top_k=8)
    return {"metric": m.name, "dimension": dimension, "window_days": window_days, "segments": segs}


# ---------- registry exposed to the agent ----------

TOOL_REGISTRY: dict[str, Callable[..., dict]] = {
    "list_metrics": list_metrics,
    "get_metric_overview": get_metric_overview,
    "explain_change": explain_change,
    "list_recent_insights": list_recent_insights,
    "compare_segments": compare_segments,
}


# JSON schema for Ollama / OpenAI-compatible tool calling
TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "list_metrics",
            "description": "List all KPI metrics InsightFlow is tracking. Use this first when the user asks about what's available.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_metric_overview",
            "description": "Get the current state of one metric: recent 7-day average, prior 28-day baseline, % change, min/max.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric_name": {"type": "string", "description": "Metric name (partial match allowed)."},
                    "days": {"type": "integer", "description": "How many days of history to consider.", "default": 30},
                },
                "required": ["metric_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explain_change",
            "description": "Detect significant changes in a metric and return the top contributing segments. Use this when the user asks WHY a metric moved.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric_name": {"type": "string"},
                    "window_days": {"type": "integer", "default": 7},
                },
                "required": ["metric_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_recent_insights",
            "description": "Return pre-computed insights from the latest analysis pass. Use this for 'what should I worry about' style questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["info", "warn", "critical"]},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_segments",
            "description": "Rank segments (teams, projects, etc.) by their contribution to a metric's recent change.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric_name": {"type": "string"},
                    "dimension": {"type": "string", "description": "Dimension to break down by, e.g. 'team' or 'project'."},
                    "window_days": {"type": "integer", "default": 7},
                },
                "required": ["metric_name", "dimension"],
            },
        },
    },
]
