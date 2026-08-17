"""Tests for metric suppression — the unit logic and the HTTP surface."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.analysis.suppression import (
    MAX_SNOOZE_DAYS,
    active_metrics,
    is_suppressed,
    restore,
    suppress,
)

NOW = datetime(2026, 8, 17, 12, 0, 0)


class TestIsSuppressed:
    def test_a_fresh_metric_is_not_suppressed(self, make_metric):
        assert is_suppressed(make_metric("Cycle Time"), NOW) is False

    def test_indefinite_suppression_has_no_expiry(self, make_metric):
        metric = suppress(make_metric("Cycle Time"), days=None, now=NOW)
        assert metric.suppressed_until is None
        assert is_suppressed(metric, NOW) is True

    def test_indefinite_suppression_does_not_lapse(self, make_metric):
        metric = suppress(make_metric("Cycle Time"), days=None, now=NOW)
        assert is_suppressed(metric, NOW + timedelta(days=3650)) is True

    def test_a_snooze_holds_inside_its_window(self, make_metric):
        metric = suppress(make_metric("Cycle Time"), days=7, now=NOW)
        assert is_suppressed(metric, NOW + timedelta(days=6)) is True

    def test_a_snooze_lapses_on_its_own(self, make_metric):
        # No cleanup job runs — the metric returns simply by failing the check.
        metric = suppress(make_metric("Cycle Time"), days=7, now=NOW)
        assert is_suppressed(metric, NOW + timedelta(days=8)) is False

    def test_it_lapses_exactly_at_the_expiry(self, make_metric):
        metric = suppress(make_metric("Cycle Time"), days=1, now=NOW)
        assert is_suppressed(metric, NOW + timedelta(days=1)) is False


class TestSuppress:
    def test_records_an_absolute_expiry_not_a_duration(self, make_metric):
        # Absolute, so re-reading the row can never extend the snooze.
        metric = suppress(make_metric("Cycle Time"), days=7, now=NOW)
        assert metric.suppressed_until == NOW + timedelta(days=7)

    def test_stamps_when_it_was_suppressed(self, make_metric):
        assert suppress(make_metric("Cycle Time"), now=NOW).suppressed_at == NOW

    def test_keeps_a_reason(self, make_metric):
        metric = suppress(make_metric("Cycle Time"), reason="known seasonal spike", now=NOW)
        assert metric.suppression_reason == "known seasonal spike"

    def test_drops_a_blank_reason(self, make_metric):
        assert suppress(make_metric("Cycle Time"), reason="   ", now=NOW).suppression_reason is None

    @pytest.mark.parametrize("days", [0, -1])
    def test_rejects_a_non_positive_window(self, make_metric, days):
        with pytest.raises(ValueError):
            suppress(make_metric("Cycle Time"), days=days, now=NOW)

    def test_rejects_a_window_that_buries_the_problem(self, make_metric):
        with pytest.raises(ValueError):
            suppress(make_metric("Cycle Time"), days=MAX_SNOOZE_DAYS + 1, now=NOW)

    def test_accepts_the_maximum_window(self, make_metric):
        assert suppress(make_metric("Cycle Time"), days=MAX_SNOOZE_DAYS, now=NOW) is not None

    def test_re_suppressing_replaces_rather_than_stacks(self, make_metric):
        metric = make_metric("Cycle Time")
        suppress(metric, days=7, now=NOW)
        suppress(metric, days=2, now=NOW)
        assert metric.suppressed_until == NOW + timedelta(days=2)


class TestRestore:
    def test_clears_every_suppression_field(self, make_metric):
        metric = suppress(make_metric("Cycle Time"), days=7, reason="noisy", now=NOW)
        restore(metric)
        assert metric.suppressed_at is None
        assert metric.suppressed_until is None
        assert metric.suppression_reason is None
        assert is_suppressed(metric, NOW) is False


class TestActiveMetrics:
    def test_filters_out_the_muted_ones(self, make_metric):
        loud = make_metric("Loud")
        quiet = suppress(make_metric("Quiet"), days=7, now=NOW)
        assert [m.name for m in active_metrics([loud, quiet], NOW)] == ["Loud"]

    def test_a_lapsed_metric_comes_back(self, make_metric):
        quiet = suppress(make_metric("Quiet"), days=1, now=NOW)
        assert len(active_metrics([quiet], NOW + timedelta(days=2))) == 1


class TestSuppressionEndpoints:
    def test_suppressing_indefinitely_needs_no_body(self, client, make_metric):
        metric = make_metric("Cycle Time")
        response = client.post(f"/metrics/{metric.id}/suppress")
        assert response.status_code == 200
        body = response.json()
        assert body["suppressed"] is True
        assert body["suppressed_until"] is None

    def test_suppressing_for_a_window_returns_the_expiry(self, client, make_metric):
        metric = make_metric("Cycle Time")
        body = client.post(f"/metrics/{metric.id}/suppress", json={"days": 7}).json()
        assert body["suppressed"] is True
        assert body["suppressed_until"] is not None

    def test_a_reason_is_stored(self, client, make_metric):
        metric = make_metric("Cycle Time")
        body = client.post(
            f"/metrics/{metric.id}/suppress", json={"days": 3, "reason": "seasonal"}
        ).json()
        assert body["suppression_reason"] == "seasonal"

    @pytest.mark.parametrize("days", [0, -5, MAX_SNOOZE_DAYS + 1])
    def test_an_invalid_window_is_a_400_not_a_500(self, client, make_metric, days):
        metric = make_metric("Cycle Time")
        assert client.post(f"/metrics/{metric.id}/suppress", json={"days": days}).status_code == 400

    def test_a_rejected_request_does_not_suppress_anything(self, client, db, make_metric):
        metric = make_metric("Cycle Time")
        client.post(f"/metrics/{metric.id}/suppress", json={"days": -1})
        db.refresh(metric)
        assert metric.suppressed_at is None

    def test_suppressing_an_unknown_metric_is_a_404(self, client):
        assert client.post("/metrics/9999/suppress").status_code == 404

    def test_restoring_brings_it_back(self, client, make_metric):
        metric = make_metric("Cycle Time")
        client.post(f"/metrics/{metric.id}/suppress")
        body = client.delete(f"/metrics/{metric.id}/suppress").json()
        assert body["suppressed"] is False

    def test_restoring_something_never_suppressed_is_a_404(self, client, make_metric):
        metric = make_metric("Cycle Time")
        assert client.delete(f"/metrics/{metric.id}/suppress").status_code == 404

    def test_metrics_are_listed_even_when_suppressed(self, client, make_metric):
        # They stay visible by default, or you could never un-suppress one.
        metric = make_metric("Cycle Time")
        client.post(f"/metrics/{metric.id}/suppress")
        assert len(client.get("/metrics").json()) == 1

    def test_they_can_be_excluded_on_request(self, client, make_metric):
        metric = make_metric("Cycle Time")
        client.post(f"/metrics/{metric.id}/suppress")
        body = client.get("/metrics", params={"include_suppressed": False}).json()
        assert body == []


class TestSuppressionHidesInsights:
    def test_insights_from_a_suppressed_metric_drop_out_of_the_feed(
        self, client, make_metric, add_insight
    ):
        loud = make_metric("Loud")
        quiet = make_metric("Quiet")
        add_insight(loud, headline="from loud")
        add_insight(quiet, headline="from quiet")

        client.post(f"/metrics/{quiet.id}/suppress")

        headlines = [i["headline"] for i in client.get("/insights").json()]
        assert headlines == ["from loud"]

    def test_they_can_be_included_on_request(self, client, make_metric, add_insight):
        quiet = make_metric("Quiet")
        add_insight(quiet, headline="from quiet")
        client.post(f"/metrics/{quiet.id}/suppress")

        body = client.get("/insights", params={"include_suppressed": True}).json()
        assert [i["headline"] for i in body] == ["from quiet"]

    def test_restoring_returns_the_insights_too(self, client, make_metric, add_insight):
        quiet = make_metric("Quiet")
        add_insight(quiet, headline="from quiet")
        client.post(f"/metrics/{quiet.id}/suppress")
        client.delete(f"/metrics/{quiet.id}/suppress")
        assert len(client.get("/insights").json()) == 1
