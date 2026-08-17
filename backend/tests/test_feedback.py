"""Tests for the insight feedback loop."""
from __future__ import annotations


class TestSubmitFeedback:
    def test_records_a_positive_verdict(self, client, make_metric, add_insight):
        insight = add_insight(make_metric("Cycle Time"))
        body = client.post(f"/insights/{insight.id}/feedback", json={"helpful": True}).json()
        assert body["helpful"] is True
        assert body["feedback_at"] is not None

    def test_records_a_negative_verdict(self, client, make_metric, add_insight):
        insight = add_insight(make_metric("Cycle Time"))
        body = client.post(f"/insights/{insight.id}/feedback", json={"helpful": False}).json()
        assert body["helpful"] is False

    def test_keeps_a_note(self, client, make_metric, add_insight):
        insight = add_insight(make_metric("Cycle Time"))
        body = client.post(
            f"/insights/{insight.id}/feedback",
            json={"helpful": False, "note": "the segment attribution was wrong"},
        ).json()
        assert body["note"] == "the segment attribution was wrong"

    def test_drops_a_blank_note(self, client, make_metric, add_insight):
        insight = add_insight(make_metric("Cycle Time"))
        body = client.post(
            f"/insights/{insight.id}/feedback", json={"helpful": True, "note": "   "}
        ).json()
        assert body["note"] is None

    def test_re_rating_replaces_the_previous_verdict(self, client, make_metric, add_insight):
        insight = add_insight(make_metric("Cycle Time"))
        client.post(f"/insights/{insight.id}/feedback", json={"helpful": True})
        client.post(f"/insights/{insight.id}/feedback", json={"helpful": False})

        summary = client.get("/insights/feedback/summary").json()
        assert summary["rated"] == 1
        assert summary["helpful"] == 0
        assert summary["not_helpful"] == 1

    def test_helpful_is_required(self, client, make_metric, add_insight):
        insight = add_insight(make_metric("Cycle Time"))
        assert client.post(f"/insights/{insight.id}/feedback", json={}).status_code == 422

    def test_an_unknown_insight_is_a_404(self, client):
        assert client.post("/insights/9999/feedback", json={"helpful": True}).status_code == 404

    def test_feedback_shows_on_the_insight(self, client, make_metric, add_insight):
        insight = add_insight(make_metric("Cycle Time"))
        client.post(f"/insights/{insight.id}/feedback", json={"helpful": True})
        # The field is on the model, so a later read reflects it.
        assert client.get(f"/insights/{insight.id}").status_code == 200


class TestFeedbackSummary:
    def test_no_insights_at_all(self, client):
        summary = client.get("/insights/feedback/summary").json()
        assert summary == {
            "total": 0,
            "rated": 0,
            "helpful": 0,
            "not_helpful": 0,
            "helpful_rate": None,
        }

    def test_unrated_insights_count_toward_total_but_not_rated(
        self, client, make_metric, add_insight
    ):
        metric = make_metric("Cycle Time")
        add_insight(metric)
        add_insight(metric)
        summary = client.get("/insights/feedback/summary").json()
        assert summary["total"] == 2
        assert summary["rated"] == 0

    def test_rate_is_null_rather_than_zero_when_nothing_is_rated(
        self, client, make_metric, add_insight
    ):
        # "Nobody judged these" and "none were useful" are different signals and
        # must not collapse to the same number.
        add_insight(make_metric("Cycle Time"))
        assert client.get("/insights/feedback/summary").json()["helpful_rate"] is None

    def test_computes_the_helpful_rate_over_rated_only(self, client, make_metric, add_insight):
        metric = make_metric("Cycle Time")
        rated_up = add_insight(metric, headline="good")
        rated_down = add_insight(metric, headline="bad")
        add_insight(metric, headline="unjudged")

        client.post(f"/insights/{rated_up.id}/feedback", json={"helpful": True})
        client.post(f"/insights/{rated_down.id}/feedback", json={"helpful": False})

        summary = client.get("/insights/feedback/summary").json()
        assert summary["total"] == 3
        assert summary["rated"] == 2
        assert summary["helpful_rate"] == 0.5

    def test_all_helpful_reads_as_one(self, client, make_metric, add_insight):
        insight = add_insight(make_metric("Cycle Time"))
        client.post(f"/insights/{insight.id}/feedback", json={"helpful": True})
        assert client.get("/insights/feedback/summary").json()["helpful_rate"] == 1.0

    def test_the_summary_route_is_not_parsed_as_an_insight_id(self, client):
        # /insights/{id} would swallow "feedback" if declared first.
        assert client.get("/insights/feedback/summary").status_code == 200
