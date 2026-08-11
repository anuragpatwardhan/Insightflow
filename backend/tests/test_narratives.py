"""Tests for rule-based insight narrative generation."""
from __future__ import annotations

import pytest

from app.analysis import narratives
from app.analysis.narratives import build_insight


@pytest.fixture(autouse=True)
def disable_ollama(monkeypatch):
    """Keep narratives deterministic and offline.

    The local .env enables Ollama, so without this every call would attempt an
    HTTP request to a model server and rewrite the summary under test.
    """
    monkeypatch.setattr(narratives.settings, "ollama_enabled", False)


def change(**overrides) -> dict:
    base = {
        "window_days": 7,
        "delta": 5.0,
        "delta_pct": 0.25,
        "z_score": 2.4,
        "significance": 0.65,
        "pattern": "spike",
    }
    return {**base, **overrides}


def metric(**overrides) -> dict:
    return {"name": "Cycle time", "direction": "neutral", **overrides}


SEGMENTS = [{"dimension": "team", "value": "Platform", "contribution": 0.42}]


def test_spike_headline_states_the_metric_direction_and_window():
    insight = build_insight(metric(), change(), SEGMENTS)
    assert insight["headline"] == "Cycle time jumped 25.0% over the last 7 days"


def test_drop_headline_reads_as_a_fall():
    insight = build_insight(metric(), change(pattern="drop", delta=-5.0, delta_pct=-0.25), SEGMENTS)
    assert insight["headline"] == "Cycle time fell 25.0% over the last 7 days"


def test_headline_percentages_are_absolute():
    insight = build_insight(metric(), change(pattern="drop", delta=-5.0, delta_pct=-0.25), SEGMENTS)
    assert "-25" not in insight["headline"]


@pytest.mark.parametrize("pattern", ["spike", "drop", "plateau", "volatility"])
def test_every_pattern_produces_a_complete_insight(pattern):
    insight = build_insight(metric(), change(pattern=pattern), SEGMENTS)
    assert set(insight) == {
        "headline",
        "summary",
        "suggested_followup",
        "evidence_json",
        "severity",
    }
    assert all(insight[key] for key in ("headline", "summary", "suggested_followup"))


def test_the_top_segment_is_named_in_the_summary():
    insight = build_insight(metric(), change(), SEGMENTS)
    assert "Platform" in insight["summary"]
    assert "42.0" in insight["summary"]


def test_the_summary_omits_attribution_when_no_segments_are_known():
    insight = build_insight(metric(), change(), [])
    assert "Platform" not in insight["summary"]
    assert insight["summary"].strip().endswith(".")


def test_evidence_carries_the_raw_change_and_segments():
    ch = change()
    insight = build_insight(metric(), ch, SEGMENTS)
    evidence = insight["evidence_json"]
    assert evidence["z_score"] == ch["z_score"]
    assert evidence["delta"] == ch["delta"]
    assert evidence["segments"] == SEGMENTS


class TestSeverity:
    def test_volatility_always_warns(self):
        insight = build_insight(metric(), change(pattern="volatility", significance=0.05), [])
        assert insight["severity"] == "warn"

    def test_plateau_is_informational(self):
        insight = build_insight(metric(), change(pattern="plateau", significance=0.99), [])
        assert insight["severity"] == "info"

    def test_a_strong_move_in_the_wrong_direction_is_critical(self):
        # lower_is_better metric rising sharply is the bad case.
        insight = build_insight(
            metric(direction="lower_is_better"),
            change(significance=0.9, delta=5.0),
            SEGMENTS,
        )
        assert insight["severity"] == "critical"

    def test_a_strong_move_in_the_right_direction_is_only_a_warning(self):
        insight = build_insight(
            metric(direction="lower_is_better"),
            change(significance=0.9, delta=-5.0, delta_pct=-0.25, pattern="drop"),
            SEGMENTS,
        )
        assert insight["severity"] == "warn"

    def test_a_neutral_metric_is_never_critical(self):
        insight = build_insight(metric(direction="neutral"), change(significance=0.99), SEGMENTS)
        assert insight["severity"] == "warn"

    def test_a_weak_signal_is_informational(self):
        insight = build_insight(
            metric(direction="lower_is_better"),
            change(significance=0.2, delta=5.0),
            SEGMENTS,
        )
        assert insight["severity"] == "info"


def test_a_missing_direction_defaults_to_neutral():
    insight = build_insight({"name": "Cycle time"}, change(significance=0.99), SEGMENTS)
    assert insight["severity"] == "warn"


def test_ollama_failure_leaves_the_template_summary_intact(monkeypatch):
    monkeypatch.setattr(narratives.settings, "ollama_enabled", True)
    monkeypatch.setattr(narratives, "_polish_with_ollama", lambda _text: None)
    insight = build_insight(metric(), change(), SEGMENTS)
    assert "Platform" in insight["summary"]
