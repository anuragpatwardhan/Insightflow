"""Insight narrative generation.

Rule-based templates produce a (headline, summary, followup, severity) tuple
from a metric + change + segments. Optional Ollama pass rephrases the summary
without touching the numbers.
"""
from __future__ import annotations

import json

import httpx
from jinja2 import Template

from app.config import settings

_HEADLINES = {
    "spike": "{{ metric }} jumped {{ pct }}% over the last {{ window }} days",
    "drop": "{{ metric }} fell {{ pct }}% over the last {{ window }} days",
    "plateau": "{{ metric }} has flattened over the last {{ window }} days",
    "volatility": "{{ metric }} became more volatile over the last {{ window }} days",
}

_SUMMARIES = {
    "spike": (
        "{{ metric }} increased by {{ pct }}% versus the prior {{ baseline }}-day baseline "
        "(z={{ z }}). {% if segments %}{{ top_segment.value }} drove "
        "{{ top_segment_pct }}% of the change.{% endif %}"
    ),
    "drop": (
        "{{ metric }} decreased by {{ pct }}% versus the prior {{ baseline }}-day baseline "
        "(z={{ z }}). {% if segments %}{{ top_segment.value }} accounted for "
        "{{ top_segment_pct }}% of the decline.{% endif %}"
    ),
    "plateau": (
        "{{ metric }} has stayed within {{ pct }}% of baseline for {{ window }} days "
        "after a previously variable period — worth confirming this is intentional."
    ),
    "volatility": (
        "{{ metric }} is swinging more than usual: recent variance is materially higher than "
        "the prior {{ baseline }}-day baseline."
    ),
}

_FOLLOWUPS = {
    "spike": "Review activity in the top contributing segment and check for upstream changes in the last 1–2 weeks.",
    "drop": "Investigate the largest contributing segment first; check for blockers, dependency changes, or process gaps.",
    "plateau": "Confirm whether the stabilization reflects a real fix or a measurement issue.",
    "volatility": "Look for intermittent events (deploys, batches, outages) lining up with the spikes.",
}


def _severity(pattern: str, significance: float, direction: str, delta: float) -> str:
    if pattern == "volatility":
        return "warn"
    if pattern == "plateau":
        return "info"
    going_wrong = (
        (direction == "higher_is_better" and delta < 0)
        or (direction == "lower_is_better" and delta > 0)
    )
    if significance >= 0.85 and going_wrong:
        return "critical"
    if significance >= 0.6:
        return "warn"
    return "info"


def build_insight(metric: dict, change: dict, segments: list[dict]) -> dict:
    pct = round(change["delta_pct"] * 100, 1)
    z = round(change["z_score"], 2)
    pattern = change["pattern"]
    top = segments[0] if segments else None
    ctx = {
        "metric": metric["name"],
        "pct": abs(pct),
        "window": change["window_days"],
        "baseline": 28,
        "z": z,
        "segments": segments,
        "top_segment": top,
        "top_segment_pct": round(abs(top["contribution"]) * 100, 1) if top else None,
    }
    headline = Template(_HEADLINES[pattern]).render(**ctx)
    summary = Template(_SUMMARIES[pattern]).render(**ctx)

    if settings.ollama_enabled:
        summary = _polish_with_ollama(summary) or summary

    evidence = {
        "pattern": pattern,
        "delta": change["delta"],
        "delta_pct": change["delta_pct"],
        "z_score": change["z_score"],
        "significance": change["significance"],
        "window_days": change["window_days"],
        "segments": segments,
    }

    return {
        "headline": headline,
        "summary": summary,
        "suggested_followup": _FOLLOWUPS[pattern],
        "evidence_json": evidence,
        "severity": _severity(pattern, change["significance"], metric.get("direction", "neutral"), change["delta"]),
    }


def _polish_with_ollama(text: str) -> str | None:
    prompt = (
        "Rewrite the following analytics insight in plain, concise business English. "
        "Do not change any numbers, percentages, or named entities. One or two sentences max.\n\n"
        f"INSIGHT:\n{text}"
    )
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(
                f"{settings.ollama_host}/api/generate",
                json={"model": settings.ollama_model, "prompt": prompt, "stream": False},
            )
            r.raise_for_status()
            return r.json().get("response", "").strip() or None
    except Exception:
        return None
