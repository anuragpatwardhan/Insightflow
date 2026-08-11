"""Tests for contribution ranking across a dimension."""
from __future__ import annotations

import pandas as pd

from app.analysis.segments import rank_segments

END = pd.Timestamp("2026-01-31")


def frame(rows: list[tuple[int, str, float]]) -> pd.DataFrame:
    """Rows of (days_before_end, team, value)."""
    return pd.DataFrame(
        [{"ts": END - pd.Timedelta(days=d), "team": team, "value": v} for d, team, v in rows]
    )


def steady(team: str, level: float, start: int, stop: int) -> list[tuple[int, str, float]]:
    return [(d, team, level) for d in range(start, stop)]


def test_empty_frame_returns_nothing():
    assert rank_segments(pd.DataFrame({"ts": [], "value": []}), "team") == []


def test_unknown_dimension_returns_nothing():
    assert rank_segments(frame(steady("alpha", 10.0, 0, 30)), "region") == []


def test_the_largest_mover_ranks_first():
    rows = (
        steady("alpha", 10.0, 8, 30) + steady("alpha", 30.0, 0, 7)
        + steady("beta", 10.0, 8, 30) + steady("beta", 12.0, 0, 7)
    )
    ranked = rank_segments(frame(rows), "team")
    assert ranked[0]["value"] == "alpha"


def test_ranking_is_by_magnitude_not_sign():
    # beta falls further than alpha rises, so beta should lead.
    rows = (
        steady("alpha", 10.0, 8, 30) + steady("alpha", 15.0, 0, 7)
        + steady("beta", 30.0, 8, 30) + steady("beta", 10.0, 0, 7)
    )
    ranked = rank_segments(frame(rows), "team")
    assert ranked[0]["value"] == "beta"
    assert ranked[0]["contribution"] < 0


def test_a_rising_segment_contributes_positively():
    rows = steady("alpha", 10.0, 8, 30) + steady("alpha", 20.0, 0, 7)
    assert rank_segments(frame(rows), "team")[0]["contribution"] > 0


def test_contributions_are_shares_of_the_total_absolute_movement():
    rows = (
        steady("alpha", 10.0, 8, 30) + steady("alpha", 20.0, 0, 7)
        + steady("beta", 10.0, 8, 30) + steady("beta", 20.0, 0, 7)
    )
    ranked = rank_segments(frame(rows), "team")
    assert sum(r["contribution"] for r in ranked) == 1.0
    assert all(round(r["contribution"], 6) == 0.5 for r in ranked)


def test_top_k_caps_the_result():
    rows: list[tuple[int, str, float]] = []
    for i in range(9):
        team = f"team{i}"
        rows += steady(team, 10.0, 8, 30) + steady(team, 10.0 + i, 0, 7)
    assert len(rank_segments(frame(rows), "team", top_k=3)) == 3


def test_a_segment_absent_from_the_baseline_counts_as_zero():
    # A team that only appears in the recent window should show its full value as
    # growth rather than being dropped by the join.
    rows = steady("alpha", 10.0, 8, 30) + steady("alpha", 10.0, 0, 7) + steady("newbie", 25.0, 0, 7)
    ranked = rank_segments(frame(rows), "team")
    assert ranked[0]["value"] == "newbie"
    assert ranked[0]["contribution"] > 0


def test_every_row_reports_the_dimension_it_came_from():
    rows = steady("alpha", 10.0, 8, 30) + steady("alpha", 20.0, 0, 7)
    assert all(r["dimension"] == "team" for r in rank_segments(frame(rows), "team"))


def test_no_movement_yields_zero_contributions():
    rows = steady("alpha", 10.0, 0, 30) + steady("beta", 4.0, 0, 30)
    assert all(r["contribution"] == 0.0 for r in rank_segments(frame(rows), "team"))


def test_string_timestamps_are_parsed():
    rows = steady("alpha", 10.0, 8, 30) + steady("alpha", 20.0, 0, 7)
    df = frame(rows)
    df["ts"] = df["ts"].astype(str)
    assert rank_segments(df, "team")[0]["value"] == "alpha"


def test_the_caller_s_frame_is_not_modified():
    df = frame(steady("alpha", 10.0, 8, 30) + steady("alpha", 20.0, 0, 7))
    before = df.copy(deep=True)
    rank_segments(df, "team")
    pd.testing.assert_frame_equal(df, before)
