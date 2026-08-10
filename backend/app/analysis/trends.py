"""Trend detection: rolling stats + z-score classification.

Returns a list of MetricChange-shaped dicts. The pipeline persists them.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class DetectionConfig:
    window_days: int = 7
    baseline_days: int = 28
    min_z: float = 1.5            # ignore changes within +/- this many SDs
    min_pct: float = 0.05         # minimum relative effect to surface
    plateau_z_max: float = 0.5    # below this, the metric is "flat"
    volatility_ratio: float = 1.75  # recent std / baseline std to flag volatility


def _resample_daily(df: pd.DataFrame) -> pd.Series:
    s = df.set_index("ts")["value"].sort_index()
    return s.resample("D").mean().interpolate(limit_direction="both")


def detect(df: pd.DataFrame, cfg: DetectionConfig | None = None) -> list[dict]:
    """`df` columns: ts (datetime64), value (float). Returns 0+ change rows."""
    cfg = cfg or DetectionConfig()
    if df.empty:
        return []

    series = _resample_daily(df)
    if len(series) < cfg.baseline_days + cfg.window_days:
        return []

    recent = series.iloc[-cfg.window_days:]
    baseline = series.iloc[-(cfg.baseline_days + cfg.window_days):-cfg.window_days]

    recent_mean = float(recent.mean())
    baseline_mean = float(baseline.mean())
    baseline_std = float(baseline.std(ddof=0)) or 1e-9

    delta = recent_mean - baseline_mean
    delta_pct = delta / (abs(baseline_mean) or 1e-9)
    z = delta / baseline_std

    recent_std = float(recent.std(ddof=0))
    vol_ratio = recent_std / (baseline_std or 1e-9)

    changes: list[dict] = []

    if abs(z) >= cfg.min_z and abs(delta_pct) >= cfg.min_pct:
        pattern = "spike" if delta > 0 else "drop"
        changes.append(_pack(cfg, delta, delta_pct, z, pattern))
    elif abs(z) <= cfg.plateau_z_max and abs(delta_pct) < cfg.min_pct:
        # flat for the window — only interesting if baseline was volatile
        if vol_ratio < 0.6:
            changes.append(_pack(cfg, delta, delta_pct, z, "plateau"))

    if vol_ratio >= cfg.volatility_ratio:
        changes.append(_pack(cfg, delta, delta_pct, z, "volatility"))

    return changes


def _pack(cfg: DetectionConfig, delta: float, delta_pct: float, z: float, pattern: str) -> dict:
    # significance: squashed |z| with cap at 1.0
    sig = float(np.tanh(abs(z) / 3.0))
    return {
        "window_days": cfg.window_days,
        "delta": delta,
        "delta_pct": delta_pct,
        "z_score": z,
        "significance": sig,
        "pattern": pattern,
    }
