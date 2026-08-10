from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent.runner import run_turn
from app.db import get_db

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    history: list[ChatMessage] = Field(default_factory=list)
    message: str


class ChatTraceItem(BaseModel):
    tool: str
    args: dict[str, Any]
    result_summary: str


class ChatResponse(BaseModel):
    answer: str
    trace: list[ChatTraceItem]


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    if not req.message.strip():
        raise HTTPException(400, "Empty message.")
    history = [m.model_dump() for m in req.history]
    try:
        result = await run_turn(db, history, req.message)
    except Exception as e:
        raise HTTPException(502, f"Agent error: {e}")
    return result
