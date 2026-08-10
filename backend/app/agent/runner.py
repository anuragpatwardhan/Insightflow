"""Ollama-backed agent loop.

Talks to Ollama's /api/chat with OpenAI-style tools. Iterates: model emits
tool calls -> we execute against the DB -> we feed results back -> repeat
until the model produces a plain-text answer (or we hit the step cap).

No network calls outside localhost. No streaming yet — kept simple for MVP.
"""
from __future__ import annotations

import json
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.agent.tools import TOOL_REGISTRY, TOOL_SCHEMAS
from app.config import settings

SYSTEM_PROMPT = """You are InsightFlow, an analytics assistant that answers questions about KPI metrics and explains why they changed.

CRITICAL RULES:
1. To use a tool, emit a real tool_call. NEVER write JSON like {"name": "..."} in your text — that does nothing. If you need data, call the tool.
2. If a tool returns an error like "No metric matches" or "not found", IMMEDIATELY call `list_metrics` in your next step and retry with the closest real name. Do not give up after one failed call.
3. Available metrics include things like ticket_resolution_hours, daily_active_users, deployment_failures, nps_score. Map user phrases to these:
   - "ticket resolution time" / "resolution time" → ticket_resolution_hours
   - "DAU" / "active users" → daily_active_users
   - "deploys" / "deployment errors" → deployment_failures
   - "NPS" / "satisfaction" → nps_score
4. For "why did X change" questions → call `explain_change`.
5. For "what should I worry about" → call `list_recent_insights`.
6. Ground every number in tool output. Never invent values.
7. Keep answers tight: 2–4 sentences. Percentages with one decimal.
"""

MAX_STEPS = 6


async def run_turn(db: Session, history: list[dict[str, Any]], user_message: str) -> dict[str, Any]:
    """Run one user turn through the agent loop. Returns final assistant message + trace."""
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    trace: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=120.0) as client:
        for step in range(MAX_STEPS):
            resp = await _ollama_chat(client, messages)
            msg = resp.get("message", {})
            tool_calls = msg.get("tool_calls") or []

            if not tool_calls:
                content = msg.get("content", "").strip()
                return {"answer": content or "(no response)", "trace": trace}

            # append the assistant's tool-call message (Ollama format)
            messages.append({"role": "assistant", "content": msg.get("content", ""), "tool_calls": tool_calls})

            for call in tool_calls:
                fn = call.get("function", {})
                name = fn.get("name")
                raw_args = fn.get("arguments", {}) or {}
                args = raw_args if isinstance(raw_args, dict) else json.loads(raw_args)

                result = _dispatch(db, name, args)
                trace.append({"tool": name, "args": args, "result_summary": _summarize(result)})

                messages.append({
                    "role": "tool",
                    "content": json.dumps(result, default=str)[:8000],
                    "name": name,
                })

        return {"answer": "I ran out of steps before producing a final answer.", "trace": trace}


def _dispatch(db: Session, name: str | None, args: dict) -> dict:
    if not name or name not in TOOL_REGISTRY:
        return {"error": f"Unknown tool '{name}'."}
    try:
        return TOOL_REGISTRY[name](db, **args)
    except TypeError as e:
        return {"error": f"Bad arguments for {name}: {e}"}
    except Exception as e:
        return {"error": f"Tool {name} failed: {e}"}


def _summarize(result: dict) -> str:
    if "error" in result:
        return f"error: {result['error']}"
    if "metrics" in result:
        return f"{len(result['metrics'])} metrics"
    if "insights" in result:
        return f"{result.get('count', len(result['insights']))} insights"
    if "changes" in result:
        return f"{len(result['changes'])} changes"
    if "segments" in result:
        return f"{len(result['segments'])} segments"
    return "ok"


async def _ollama_chat(client: httpx.AsyncClient, messages: list[dict]) -> dict:
    r = await client.post(
        f"{settings.ollama_host}/api/chat",
        json={
            "model": settings.ollama_model,
            "messages": messages,
            "tools": TOOL_SCHEMAS,
            "stream": False,
            "options": {"temperature": 0.2},
        },
    )
    r.raise_for_status()
    return r.json()
