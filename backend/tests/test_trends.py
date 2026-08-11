"""Tests for the rolling z-score trend detector."""
from __future__ import annotations

import pandas as pd
import pytest

from app.analysis.trends import DetectionConfig, detect

CFG = DetectionConfig()
TOTAL_DAYS = CFG.baseline_days + CFG.window_days


def series(values: list[float]) -> pd.DataFrame:
    """Build a daily ts/value frame ending today, oldest value first."""
    end = pd.Timestamp("2026-01-31")
    ts = pd.date_range(end=end, periods=len(values), freq="D")
    return pd.DataFrame({"ts": ts, "value": values})


def flat(level: float, days: int = TOTAL_DAYS) -> list[float]:
    return [level] * days


def patterns(changes: list[dict]) -> set[str]:
    return {c["pattern"] for c in changes}


def test_empty_frame_yields_nothing():
    assert detect(pd.DataFrame({"ts": [], "value": []})) == []


def test_too_short_a_history_yields_nothing():
    # One day short of baseline + window: there is no baseline to compare against.
    assert detect(series(flat(10.0, TOTAL_DAYS - 1))) == []


def test_exactly_enough_history_is_evaluated():
    assert detect(series(flat(10.0, TOTAL_DAYS))) is not None


def test_a_large_jump_is_reported_as_a_spike():
    values = flat(10.0, CFG.baseline_days) + [20.0] * CFG.window_days
    assert "spike" in patterns(detect(series(values)))


def test_a_large_fall_is_reported_as_a_drop():
    values = flat(20.0, CFG.baseline_days) + [8.0] * CFG.window_days
    assert "drop" in patterns(detect(series(values)))


def test_spike_records_a_positive_delta_and_drop_a_negative_one():
    up = [c for c in detect(series(flat(10.0, CFG.baseline_days) + [20.0] * CFG.window_days))
          if c["pattern"] == "spike"][0]
    down = [c for c in detect(series(flat(20.0, CFG.baseline_days) + [8.0] * CFG.window_days))
            if c["pattern"] == "drop"][0]
    assert up["delta"] > 0
    assert down["delta"] < 0


def test_a_change_smaller_than_the_percentage_floor_is_ignored():
    # 2% shift: it may clear the z threshold on a quiet baseline but is below min_pct.
    baseline = [10.0, 10.1] * (CFG.baseline_days // 2)
    values = baseline + [10.2] * CFG.window_days
    assert "spike" not in patterns(detect(series(values)))


def test_volatility_is_flagged_when_recent_swings_widen():
    baseline = [10.0, 10.1] * (CFG.baseline_days // 2)
    recent = [5.0, 15.0, 4.0, 16.0, 6.0, 14.0, 5.0][: CFG.window_days]
    assert "volatility" in patterns(detect(series(baseline + recent)))


def test_a_steady_series_is_not_flagged_as_volatile():
    assert "volatility" not in patterns(detect(series(flat(10.0))))


def test_significance_rises_with_the_size_of_the_change():
    # The baseline needs real variance for this to be observable: significance is
    # tanh(|z|/3), and z divides by the baseline standard deviation.
    noisy = [8.0, 12.0] * (CFG.baseline_days // 2)
    small = detect(series(noisy + [13.0] * CFG.window_days))
    large = detect(series(noisy + [20.0] * CFG.window_days))
    assert small and large
    assert large[0]["significance"] > small[0]["significance"]


def test_a_perfectly_flat_baseline_saturates_significance():
    # With zero baseline deviation the detector substitutes 1e-9, so z explodes and
    # tanh pins to 1.0. Any change against a perfectly steady metric reads as
    # maximally significant — worth knowing when reading scores.
    values = flat(10.0, CFG.baseline_days) + [10.5] * CFG.window_days
    assert [c["significance"] for c in detect(series(values))] == [1.0]


def test_significance_never_exceeds_one():
    values = flat(10.0, CFG.baseline_days) + [10_000.0] * CFG.window_days
    for change in detect(series(values)):
        assert 0.0 <= change["significance"] <= 1.0


def test_every_change_carries_the_full_shape():
    values = flat(10.0, CFG.baseline_days) + [20.0] * CFG.window_days
    for change in detect(series(values)):
        assert set(change) == {
            "window_days",
            "delta",
            "delta_pct",
            "z_score",
            "significance",
            "pattern",
        }
        assert change["window_days"] == CFG.window_days


def test_a_zero_baseline_does_not_divide_by_zero():
    values = flat(0.0, CFG.baseline_days) + [5.0] * CFG.window_days
    for change in detect(series(values)):
        assert change["delta_pct"] == pytest.approx(5.0 / 1e-9, rel=1e-6)


def test_config_overrides_are_honoured():
    values = flat(10.0, CFG.baseline_days) + [11.0] * CFG.window_days
    strict = DetectionConfig(min_pct=0.5)
    assert "spike" not in patterns(detect(series(values), strict))


def test_unsorted_input_is_ordered_before_analysis():
    values = flat(10.0, CFG.baseline_days) + [20.0] * CFG.window_days
    ordered = series(values)
    shuffled = ordered.sample(frac=1.0, random_state=0).reset_index(drop=True)
    assert detect(shuffled) == detect(ordered)
