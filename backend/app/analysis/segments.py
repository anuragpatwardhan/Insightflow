"""Contribution analysis: which dimension values drove the metric change?

For each dimension (team, project, ...), we compute the per-segment delta
between the recent window and the baseline, then express each as a share
of the total absolute delta. Top contributors are returned.
"""
from __future__ import annotations

import pandas as pd


def rank_segments(
    df: pd.DataFrame,
    dimension: str,
    window_days: int = 7,
    baseline_days: int = 28,
    top_k: int = 5,
) -> list[dict]:
    """`df` columns: ts, value, and the `dimension` column.

    Returns up to top_k segments, each with absolute and signed contribution.
    """
    if df.empty or dimension not in df.columns:
        return []

    df = df.copy()
    df["ts"] = pd.to_datetime(df["ts"])
    max_ts = df["ts"].max()
    recent_start = max_ts - pd.Timedelta(days=window_days)
    baseline_start = recent_start - pd.Timedelta(days=baseline_days)

    recent = df[df["ts"] > recent_start]
    baseline = df[(df["ts"] > baseline_start) & (df["ts"] <= recent_start)]

    recent_means = recent.groupby(dimension)["value"].mean()
    baseline_means = baseline.groupby(dimension)["value"].mean()

    joined = pd.concat([baseline_means.rename("baseline"), recent_means.rename("recent")], axis=1).fillna(0)
    joined["delta"] = joined["recent"] - joined["baseline"]

    total_abs = joined["delta"].abs().sum() or 1e-9
    joined["contribution"] = joined["delta"] / total_abs

    ranked = joined.reindex(joined["delta"].abs().sort_values(ascending=False).index).head(top_k)

    return [
        {"dimension": dimension, "value": str(idx), "contribution": float(row["contribution"])}
        for idx, row in ranked.iterrows()
    ]
