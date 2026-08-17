"""Tests for the HTTP surface — the layer the frontend and any API consumer sees."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models import MetricValue


class TestHealth:
    def test_healthz_reports_ok(self, client):
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestListMetrics:
    def test_empty_database_returns_an_empty_list(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_metrics_sorted_by_name(self, client, make_metric):
        make_metric("Zeta")
        make_metric("Alpha")
        assert [m["name"] for m in client.get("/metrics").json()] == ["Alpha", "Zeta"]

    def test_serialises_the_documented_fields(self, client, make_metric):
        make_metric("Cycle Time", owner="platform", unit="hours", direction="lower_is_better")
        body = client.get("/metrics").json()[0]
        assert body["name"] == "Cycle Time"
        assert body["owner"] == "platform"
        assert body["unit"] == "hours"
        assert body["direction"] == "lower_is_better"
        assert "id" in body


class TestGetMetric:
    def test_returns_a_single_metric(self, client, make_metric):
        metric = make_metric("Cycle Time")
        response = client.get(f"/metrics/{metric.id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Cycle Time"

    def test_unknown_id_is_a_404(self, client):
        response = client.get("/metrics/9999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Metric not found"

    def test_a_non_numeric_id_is_rejected(self, client):
        # The path is typed as int, so FastAPI rejects before the handler runs.
        assert client.get("/metrics/not-a-number").status_code == 422


class TestGetSeries:
    def test_returns_points_in_chronological_order(self, client, db, make_metric):
        metric = make_metric("Cycle Time")
        now = datetime.utcnow()
        # Inserted newest-first on purpose; the endpoint must still sort.
        for offset in (1, 5, 3):
            db.add(MetricValue(metric_id=metric.id, ts=now - timedelta(days=offset), value=float(offset)))
        db.commit()

        points = client.get(f"/metrics/{metric.id}/series").json()

        assert [p["value"] for p in points] == [5.0, 3.0, 1.0]

    def test_unknown_metric_is_a_404(self, client):
        assert client.get("/metrics/9999/series").status_code == 404

    def test_a_metric_with_no_values_returns_an_empty_list(self, client, make_metric):
        metric = make_metric("Cycle Time")
        response = client.get(f"/metrics/{metric.id}/series")
        assert response.status_code == 200
        assert response.json() == []

    def test_days_window_excludes_older_points(self, client, db, make_metric):
        metric = make_metric("Cycle Time")
        now = datetime.utcnow()
        db.add(MetricValue(metric_id=metric.id, ts=now - timedelta(days=2), value=1.0))
        db.add(MetricValue(metric_id=metric.id, ts=now - timedelta(days=90), value=2.0))
        db.commit()

        points = client.get(f"/metrics/{metric.id}/series", params={"days": 7}).json()

        assert [p["value"] for p in points] == [1.0]

    @pytest.mark.parametrize("days", [0, -1, 366])
    def test_days_outside_the_allowed_range_is_rejected(self, client, make_metric, days):
        metric = make_metric("Cycle Time")
        response = client.get(f"/metrics/{metric.id}/series", params={"days": days})
        assert response.status_code == 422

    @pytest.mark.parametrize("days", [1, 365])
    def test_the_range_boundaries_are_accepted(self, client, make_metric, days):
        metric = make_metric("Cycle Time")
        assert client.get(f"/metrics/{metric.id}/series", params={"days": days}).status_code == 200

    def test_points_from_another_metric_are_not_included(self, client, db, make_metric):
        wanted = make_metric("Wanted")
        other = make_metric("Other")
        now = datetime.utcnow()
        db.add(MetricValue(metric_id=wanted.id, ts=now, value=1.0))
        db.add(MetricValue(metric_id=other.id, ts=now, value=2.0))
        db.commit()

        points = client.get(f"/metrics/{wanted.id}/series").json()
        assert [p["value"] for p in points] == [1.0]


class TestListInsights:
    def test_empty_database_returns_an_empty_list(self, client):
        assert client.get("/insights").json() == []

    def test_joins_the_metric_name_onto_each_insight(self, client, make_metric, add_insight):
        metric = make_metric("Cycle Time")
        add_insight(metric, headline="Cycle time jumped")
        body = client.get("/insights").json()[0]
        assert body["metric_name"] == "Cycle Time"
        assert body["headline"] == "Cycle time jumped"

    def test_newest_first(self, client, make_metric, add_insight):
        metric = make_metric("Cycle Time")
        now = datetime.utcnow()
        add_insight(metric, headline="older", created_at=now - timedelta(days=2))
        add_insight(metric, headline="newer", created_at=now)
        assert [i["headline"] for i in client.get("/insights").json()] == ["newer", "older"]

    def test_filters_by_severity(self, client, make_metric, add_insight):
        metric = make_metric("Cycle Time")
        add_insight(metric, headline="quiet", severity="info")
        add_insight(metric, headline="loud", severity="critical")
        body = client.get("/insights", params={"severity": "critical"}).json()
        assert [i["headline"] for i in body] == ["loud"]

    def test_an_unrecognised_severity_is_rejected_rather_than_ignored(self, client):
        # The route constrains severity with a pattern, so a typo is a 422 rather
        # than silently returning everything.
        assert client.get("/insights", params={"severity": "urgent"}).status_code == 422

    def test_filters_by_metric(self, client, make_metric, add_insight):
        first = make_metric("First")
        second = make_metric("Second")
        add_insight(first, headline="from first")
        add_insight(second, headline="from second")
        body = client.get("/insights", params={"metric_id": second.id}).json()
        assert [i["headline"] for i in body] == ["from second"]

    def test_respects_the_limit(self, client, make_metric, add_insight):
        metric = make_metric("Cycle Time")
        for index in range(5):
            add_insight(metric, headline=f"insight {index}")
        assert len(client.get("/insights", params={"limit": 2}).json()) == 2

    @pytest.mark.parametrize("limit", [0, 201])
    def test_limit_outside_the_allowed_range_is_rejected(self, client, limit):
        assert client.get("/insights", params={"limit": limit}).status_code == 422

    def test_missing_evidence_serialises_as_an_empty_object(self, client, make_metric, add_insight):
        metric = make_metric("Cycle Time")
        add_insight(metric, evidence_json={})
        assert client.get("/insights").json()[0]["evidence_json"] == {}


class TestGetInsight:
    def test_returns_a_single_insight_with_its_metric_name(self, client, make_metric, add_insight):
        metric = make_metric("Cycle Time")
        insight = add_insight(metric, headline="Something moved")
        body = client.get(f"/insights/{insight.id}").json()
        assert body["headline"] == "Something moved"
        assert body["metric_name"] == "Cycle Time"

    def test_unknown_id_is_a_404(self, client):
        response = client.get("/insights/9999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Insight not found"


class TestChat:
    """The chat route delegates to the agent, so the agent itself is stubbed.

    These tests are about the HTTP contract: validation, error mapping and the
    response shape. Agent behaviour is covered in test_agent_tools.
    """

    @pytest.fixture
    def stub_agent(self, monkeypatch):
        def _stub(result=None, raises=None):
            async def fake_run_turn(db, history, message):
                if raises is not None:
                    raise raises
                return result

            # Patched where it is used, not where it is defined — the router
            # imported the name at module load.
            monkeypatch.setattr("app.routers.chat.run_turn", fake_run_turn)

        return _stub

    def test_returns_the_agent_answer_and_trace(self, client, stub_agent):
        stub_agent(
            result={
                "answer": "Cycle time rose 25%.",
                "trace": [
                    {"tool": "explain_change", "args": {"metric_name": "Cycle Time"}, "result_summary": "spike"}
                ],
            }
        )
        response = client.post("/chat", json={"message": "why did cycle time go up?"})
        assert response.status_code == 200
        body = response.json()
        assert body["answer"] == "Cycle time rose 25%."
        assert body["trace"][0]["tool"] == "explain_change"

    def test_an_empty_message_is_rejected(self, client, stub_agent):
        stub_agent(result={"answer": "unused", "trace": []})
        response = client.post("/chat", json={"message": ""})
        assert response.status_code == 400
        assert response.json()["detail"] == "Empty message."

    def test_a_whitespace_only_message_is_rejected(self, client, stub_agent):
        stub_agent(result={"answer": "unused", "trace": []})
        assert client.post("/chat", json={"message": "   "}).status_code == 400

    def test_a_missing_message_field_is_rejected(self, client):
        assert client.post("/chat", json={}).status_code == 422

    def test_history_is_optional(self, client, stub_agent):
        stub_agent(result={"answer": "fine", "trace": []})
        assert client.post("/chat", json={"message": "hello"}).status_code == 200

    def test_an_invalid_history_role_is_rejected(self, client):
        response = client.post(
            "/chat",
            json={"message": "hello", "history": [{"role": "system", "content": "hi"}]},
        )
        assert response.status_code == 422

    def test_an_agent_failure_becomes_a_502_not_a_500(self, client, stub_agent):
        # The model server being down is an upstream failure, and the client
        # should be able to tell that apart from a bug in this service.
        stub_agent(raises=RuntimeError("ollama unreachable"))
        response = client.post("/chat", json={"message": "why?"})
        assert response.status_code == 502
        assert "ollama unreachable" in response.json()["detail"]
