"""Tests for the agent loop — the part that turns model output into tool calls.

The model itself is stubbed. These tests are about the loop's contract: when it
stops, what it feeds back, how it handles a model that misbehaves, and that a
tool blowing up never takes the request down with it. No network is touched.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from app.agent import runner
from app.agent.runner import MAX_STEPS, _dispatch, _summarize, run_turn


def turn(db, message="why did cycle time go up?", history=None):
    """Drive one async turn from a sync test, so no async plugin is needed."""
    return asyncio.run(run_turn(db, history or [], message))


@pytest.fixture
def scripted(monkeypatch):
    """Stub the model with a fixed sequence of replies, recording what it saw.

    Returns the recorder so a test can assert on the conversation the loop
    built — that is where the interesting behaviour lives.
    """

    def _install(*responses):
        sent: list[list[dict]] = []
        remaining = list(responses)

        async def fake_chat(client, messages):
            # Copy: the loop mutates the same list between steps.
            sent.append([dict(m) for m in messages])
            if not remaining:
                raise AssertionError("the loop asked for more replies than scripted")
            return remaining.pop(0)

        monkeypatch.setattr(runner, "_ollama_chat", fake_chat)
        return sent

    return _install


def says(text):
    """A model reply with no tool calls — the terminal case."""
    return {"message": {"content": text}}


def calls(name, args, content=""):
    """A model reply requesting one tool call."""
    return {
        "message": {
            "content": content,
            "tool_calls": [{"function": {"name": name, "arguments": args}}],
        }
    }


class TestPlainAnswer:
    def test_returns_the_model_text_when_no_tools_are_called(self, db, scripted):
        scripted(says("Cycle time rose 25%."))
        result = turn(db)
        assert result["answer"] == "Cycle time rose 25%."
        assert result["trace"] == []

    def test_strips_surrounding_whitespace(self, db, scripted):
        scripted(says("  padded  "))
        assert turn(db)["answer"] == "padded"

    def test_empty_content_falls_back_rather_than_returning_blank(self, db, scripted):
        # A blank bubble in the UI is worse than an honest placeholder.
        scripted(says("   "))
        assert turn(db)["answer"] == "(no response)"

    def test_stops_after_one_call_when_the_model_answers_immediately(self, db, scripted):
        sent = scripted(says("done"))
        turn(db)
        assert len(sent) == 1


class TestConversationConstruction:
    def test_system_prompt_leads_and_user_message_trails(self, db, scripted):
        sent = scripted(says("ok"))
        turn(db, message="what changed?")
        conversation = sent[0]
        assert conversation[0]["role"] == "system"
        assert conversation[-1] == {"role": "user", "content": "what changed?"}

    def test_history_is_preserved_between_system_and_user(self, db, scripted):
        sent = scripted(says("ok"))
        history = [
            {"role": "user", "content": "earlier question"},
            {"role": "assistant", "content": "earlier answer"},
        ]
        turn(db, message="follow up", history=history)
        roles = [m["role"] for m in sent[0]]
        assert roles == ["system", "user", "assistant", "user"]


class TestToolLoop:
    def test_executes_a_tool_then_answers_from_its_result(self, db, make_metric, scripted):
        make_metric("Cycle Time")
        sent = scripted(calls("list_metrics", {}), says("There is one metric."))

        result = turn(db)

        assert result["answer"] == "There is one metric."
        assert [t["tool"] for t in result["trace"]] == ["list_metrics"]
        # Second round trip must carry the tool result back to the model.
        second = sent[1]
        assert second[-1]["role"] == "tool"
        assert second[-1]["name"] == "list_metrics"
        assert "Cycle Time" in second[-1]["content"]

    def test_the_assistant_tool_call_is_recorded_before_the_result(self, db, make_metric, scripted):
        # Without this the model sees a tool result with nothing that asked for it.
        make_metric("Cycle Time")
        sent = scripted(calls("list_metrics", {}), says("done"))
        turn(db)
        roles = [m["role"] for m in sent[1]]
        assert roles[-2:] == ["assistant", "tool"]

    def test_accepts_arguments_as_a_json_string(self, db, make_metric, scripted):
        # Ollama sometimes returns arguments already serialised.
        make_metric("Cycle Time")
        scripted(
            calls("get_metric_overview", json.dumps({"metric_name": "Cycle Time"})),
            says("done"),
        )
        result = turn(db)
        assert result["trace"][0]["args"] == {"metric_name": "Cycle Time"}

    def test_handles_several_tool_calls_in_one_step(self, db, make_metric, scripted):
        make_metric("Cycle Time")
        scripted(
            {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "list_metrics", "arguments": {}}},
                        {"function": {"name": "list_recent_insights", "arguments": {}}},
                    ],
                }
            },
            says("done"),
        )
        result = turn(db)
        assert [t["tool"] for t in result["trace"]] == ["list_metrics", "list_recent_insights"]

    def test_a_failing_tool_is_reported_to_the_model_rather_than_raising(self, db, scripted):
        # The model is told to recover by listing metrics, so the loop must
        # survive a bad call instead of failing the whole request.
        sent = scripted(
            calls("get_metric_overview", {"metric_name": "nonexistent"}),
            says("I could not find that metric."),
        )
        result = turn(db)
        assert "error" in result["trace"][0]["result_summary"]
        assert sent[1][-1]["role"] == "tool"

    def test_an_unknown_tool_name_is_an_error_not_a_crash(self, db, scripted):
        scripted(calls("no_such_tool", {}), says("recovered"))
        result = turn(db)
        assert result["answer"] == "recovered"
        assert "Unknown tool" in result["trace"][0]["result_summary"]

    def test_gives_up_after_the_step_cap(self, db, make_metric, scripted):
        # A model that only ever calls tools would otherwise loop forever.
        make_metric("Cycle Time")
        scripted(*[calls("list_metrics", {}) for _ in range(MAX_STEPS)])

        result = turn(db)

        assert result["answer"] == "I ran out of steps before producing a final answer."
        assert len(result["trace"]) == MAX_STEPS

    def test_tool_output_is_truncated_before_being_sent_back(self, db, make_metric, add_insight, scripted):
        # An unbounded tool result would blow the context window.
        metric = make_metric("Cycle Time")
        for index in range(60):
            add_insight(metric, headline=f"insight {index} " + "x" * 400)
        sent = scripted(calls("list_recent_insights", {"limit": 60}), says("done"))
        turn(db)
        assert len(sent[1][-1]["content"]) <= 8000


class TestDispatch:
    def test_runs_a_registered_tool(self, db, make_metric):
        make_metric("Cycle Time")
        assert _dispatch(db, "list_metrics", {})["metrics"][0]["name"] == "Cycle Time"

    def test_unknown_name_returns_an_error(self, db):
        assert "Unknown tool" in _dispatch(db, "nope", {})["error"]

    def test_a_missing_name_returns_an_error(self, db):
        assert "error" in _dispatch(db, None, {})

    def test_wrong_arguments_are_reported_as_bad_arguments(self, db):
        result = _dispatch(db, "get_metric_overview", {"not_a_parameter": 1})
        assert "Bad arguments" in result["error"]

    def test_an_exception_inside_a_tool_is_caught(self, db, monkeypatch):
        def explode(_db):
            raise RuntimeError("boom")

        monkeypatch.setitem(runner.TOOL_REGISTRY, "list_metrics", explode)
        result = _dispatch(db, "list_metrics", {})
        assert "boom" in result["error"]


class TestSummarize:
    def test_errors_are_surfaced_verbatim(self):
        assert _summarize({"error": "no such metric"}) == "error: no such metric"

    def test_counts_metrics(self):
        assert _summarize({"metrics": [1, 2, 3]}) == "3 metrics"

    def test_prefers_the_reported_count_for_insights(self):
        assert _summarize({"insights": [1], "count": 1}) == "1 insights"

    def test_falls_back_to_length_when_no_count_is_given(self):
        assert _summarize({"insights": [1, 2]}) == "2 insights"

    def test_counts_changes_and_segments(self):
        assert _summarize({"changes": [1, 2]}) == "2 changes"
        assert _summarize({"segments": [1]}) == "1 segments"

    def test_an_unrecognised_shape_is_ok_rather_than_a_crash(self):
        assert _summarize({"anything": True}) == "ok"

    def test_an_error_wins_over_other_keys(self):
        assert _summarize({"error": "bad", "metrics": [1]}).startswith("error")
