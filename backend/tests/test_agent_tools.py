"""Tests for the read-only tools the chat agent may call."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.agent.tools import (
    TOOL_SCHEMAS,
    _expand,
    _find_metric,
    _tokens,
    explain_change,
    get_metric_overview,
    list_metrics,
    list_recent_insights,
)


class TestTokenising:
    def test_splits_on_punctuation_and_lowercases(self):
        assert _tokens("Cycle-Time (hours)") == {"cycle", "time", "hours"}

    def test_drops_empty_fragments(self):
        assert _tokens("  ---  ") == set()

    def test_keeps_digits(self):
        assert _tokens("p95 latency") == {"p95", "latency"}


class TestSynonymExpansion:
    def test_keeps_the_original_tokens(self):
        assert {"time"} <= _expand({"time"})

    def test_adds_known_synonyms(self):
        assert "duration" in _expand({"time"})

    def test_leaves_unknown_tokens_alone(self):
        assert _expand({"widgets"}) == {"widgets"}

    def test_expands_every_token_in_the_set(self):
        expanded = _expand({"users", "failures"})
        assert "dau" in expanded
        assert "errors" in expanded


class TestFindMetric:
    def test_returns_none_when_no_metrics_exist(self, db):
        assert _find_metric(db, "anything") is None

    def test_exact_match_ignoring_case_and_padding(self, db, make_metric):
        make_metric("Cycle Time")
        assert _find_metric(db, "  cycle time  ").name == "Cycle Time"

    def test_exact_match_wins_over_a_substring_match(self, db, make_metric):
        make_metric("Cycle Time P95")
        make_metric("Cycle Time")
        assert _find_metric(db, "Cycle Time").name == "Cycle Time"

    def test_user_query_contained_in_the_metric_name(self, db, make_metric):
        make_metric("Deployment Frequency")
        assert _find_metric(db, "deployment").name == "Deployment Frequency"

    def test_metric_name_contained_in_the_user_query(self, db, make_metric):
        make_metric("Latency")
        assert _find_metric(db, "what about latency this week").name == "Latency"

    def test_falls_back_to_synonym_overlap(self, db, make_metric):
        # "hours" never appears in the name; the synonym table bridges it to "time".
        make_metric("Cycle Time")
        assert _find_metric(db, "hours").name == "Cycle Time"

    def test_returns_none_when_nothing_overlaps(self, db, make_metric):
        make_metric("Cycle Time")
        assert _find_metric(db, "revenue") is None

    def test_returns_none_for_an_empty_query(self, db, make_metric):
        make_metric("Cycle Time")
        assert _find_metric(db, "!!!") is None

    def test_picks_the_strongest_token_overlap(self, db, make_metric):
        make_metric("Deploy Failure Rate")
        make_metric("Build Duration")
        assert _find_metric(db, "deploy failure").name == "Deploy Failure Rate"


class TestListMetrics:
    def test_returns_an_empty_list_when_there_are_none(self, db):
        assert list_metrics(db) == {"metrics": []}

    def test_returns_metrics_sorted_by_name(self, db, make_metric):
        make_metric("Zeta")
        make_metric("Alpha")
        assert [m["name"] for m in list_metrics(db)["metrics"]] == ["Alpha", "Zeta"]

    def test_includes_the_fields_the_model_needs(self, db, make_metric):
        make_metric("Cycle Time", owner="platform", unit="hours", direction="lower_is_better")
        entry = list_metrics(db)["metrics"][0]
        assert entry == {
            "name": "Cycle Time",
            "owner": "platform",
            "unit": "hours",
            "direction": "lower_is_better",
            "description": None,
        }


class TestGetMetricOverview:
    def test_reports_an_error_for_an_unknown_metric(self, db, make_metric):
        make_metric("Cycle Time")
        result = get_metric_overview(db, "revenue")
        assert "error" in result
        assert "list_metrics" in result["error"]

    def test_reports_an_error_when_the_metric_has_no_data(self, db, make_metric):
        make_metric("Cycle Time")
        assert "error" in get_metric_overview(db, "Cycle Time")

    def test_summarises_a_steady_series(self, db, make_metric, add_values):
        metric = make_metric("Cycle Time")
        add_values(metric, [10.0] * 40)

        result = get_metric_overview(db, "Cycle Time")

        assert result["name"] == "Cycle Time"
        assert result["unit"] == "hours"
        assert result["current_7d_avg"] == 10.0
        assert result["min"] == 10.0
        assert result["max"] == 10.0
        assert result["delta_pct_vs_prior_28d"] == 0.0

    def test_detects_a_rise_against_the_prior_baseline(self, db, make_metric, add_values):
        metric = make_metric("Cycle Time")
        add_values(metric, [10.0] * 33 + [20.0] * 7)

        result = get_metric_overview(db, "Cycle Time")

        assert result["current_7d_avg"] == 20.0
        assert result["prior_28d_avg"] == 10.0
        assert result["delta_pct_vs_prior_28d"] > 0

    def test_counts_the_days_it_summarised(self, db, make_metric, add_values):
        metric = make_metric("Cycle Time")
        add_values(metric, [10.0] * 40)
        assert get_metric_overview(db, "Cycle Time")["n_days"] == 40

    def test_matches_a_metric_by_partial_name(self, db, make_metric, add_values):
        metric = make_metric("Deployment Frequency")
        add_values(metric, [5.0] * 40)
        assert get_metric_overview(db, "deployment")["name"] == "Deployment Frequency"


class TestExplainChange:
    def test_reports_an_error_for_an_unknown_metric(self, db, make_metric):
        make_metric("Cycle Time")
        assert "error" in explain_change(db, "revenue")

    def test_reports_an_error_when_the_metric_has_no_data(self, db, make_metric):
        make_metric("Cycle Time")
        assert "error" in explain_change(db, "Cycle Time")

    def test_says_so_when_nothing_moved(self, db, make_metric, add_values):
        metric = make_metric("Cycle Time")
        # A steady series with a varied baseline: no spike, and not flat enough
        # after a volatile stretch to register as a plateau either.
        add_values(metric, [10.0, 11.0] * 20)

        result = explain_change(db, "Cycle Time")

        assert result["verdict"] == "no_significant_change"
        assert "Cycle Time" in result["message"]

    def test_surfaces_a_detected_spike(self, db, make_metric, add_values):
        metric = make_metric("Cycle Time")
        add_values(metric, [10.0, 11.0] * 16 + [40.0] * 7)

        result = explain_change(db, "Cycle Time")

        assert result["metric"] == "Cycle Time"
        assert result["direction"] == "lower_is_better"
        patterns = {change["pattern"] for change in result["changes"]}
        assert "spike" in patterns

    def test_attaches_segments_when_the_data_carries_dimensions(self, db, make_metric, add_values):
        metric = make_metric("Cycle Time")
        values = [10.0, 11.0] * 16 + [40.0] * 7
        dimensions = [{"team": "alpha"} for _ in values]
        add_values(metric, values, dimensions)

        result = explain_change(db, "Cycle Time")

        spike = next(c for c in result["changes"] if c["pattern"] == "spike")
        assert spike["top_segments"]
        assert spike["top_segments"][0]["dimension"] == "team"

    def test_returns_no_segments_when_there_are_no_dimensions(self, db, make_metric, add_values):
        metric = make_metric("Cycle Time")
        add_values(metric, [10.0, 11.0] * 16 + [40.0] * 7)
        spike = next(c for c in explain_change(db, "Cycle Time")["changes"] if c["pattern"] == "spike")
        assert spike["top_segments"] == []


class TestListRecentInsights:
    def test_returns_nothing_when_there_are_none(self, db):
        assert list_recent_insights(db) == {"insights": [], "count": 0}

    def test_returns_the_metric_name_alongside_the_insight(self, db, make_metric, add_insight):
        metric = make_metric("Cycle Time")
        add_insight(metric, headline="Cycle time jumped 25%")
        entry = list_recent_insights(db)["insights"][0]
        assert entry["metric"] == "Cycle Time"
        assert entry["headline"] == "Cycle time jumped 25%"

    def test_pulls_pattern_and_delta_out_of_the_evidence(self, db, make_metric, add_insight):
        metric = make_metric("Cycle Time")
        add_insight(metric, evidence_json={"pattern": "drop", "delta_pct": -0.4})
        entry = list_recent_insights(db)["insights"][0]
        assert entry["pattern"] == "drop"
        assert entry["delta_pct"] == -0.4

    def test_tolerates_empty_evidence(self, db, make_metric, add_insight):
        metric = make_metric("Cycle Time")
        add_insight(metric, evidence_json={})
        entry = list_recent_insights(db)["insights"][0]
        assert entry["pattern"] is None
        assert entry["delta_pct"] is None

    def test_newest_insight_comes_first(self, db, make_metric, add_insight):
        metric = make_metric("Cycle Time")
        now = datetime.utcnow()
        add_insight(metric, headline="older", created_at=now - timedelta(days=2))
        add_insight(metric, headline="newer", created_at=now)
        assert [i["headline"] for i in list_recent_insights(db)["insights"]] == ["newer", "older"]

    def test_filters_by_severity(self, db, make_metric, add_insight):
        metric = make_metric("Cycle Time")
        add_insight(metric, headline="quiet", severity="info")
        add_insight(metric, headline="loud", severity="critical")
        result = list_recent_insights(db, severity="critical")
        assert [i["headline"] for i in result["insights"]] == ["loud"]

    def test_an_unrecognised_severity_is_ignored_rather_than_returning_nothing(
        self, db, make_metric, add_insight
    ):
        metric = make_metric("Cycle Time")
        add_insight(metric, severity="info")
        assert list_recent_insights(db, severity="urgent")["count"] == 1

    def test_respects_the_limit(self, db, make_metric, add_insight):
        metric = make_metric("Cycle Time")
        for index in range(5):
            add_insight(metric, headline=f"insight {index}")
        assert list_recent_insights(db, limit=2)["count"] == 2


class TestToolSchemas:
    def test_every_registered_tool_has_a_schema(self):
        from app.agent.tools import TOOL_REGISTRY

        schema_names = {schema["function"]["name"] for schema in TOOL_SCHEMAS}
        assert schema_names == set(TOOL_REGISTRY)

    def test_each_schema_is_shaped_for_tool_calling(self):
        for schema in TOOL_SCHEMAS:
            assert schema["type"] == "function"
            function = schema["function"]
            assert function["description"]
            assert function["parameters"]["type"] == "object"
            for required in function["parameters"]["required"]:
                assert required in function["parameters"]["properties"]
