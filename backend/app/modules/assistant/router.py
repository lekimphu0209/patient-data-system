"""API trợ lý dữ liệu: ``POST /chat`` và ``GET /suggestions`` (cần đăng nhập)."""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_active_user

from . import agent
from .models import AssistantLog
from .snapshot import get_snapshot
from .tools import suggestions

logger = logging.getLogger(__name__)
router = APIRouter()

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: Annotated[str, StringConstraints(max_length=4000)]


class ChatRequest(BaseModel):
    message: Text
    history: list[Turn] = Field(default_factory=list, max_length=20)


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[int, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, user_id: int, limit: int, window: float = 60.0) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[user_id]
            while hits and now - hits[0] > window:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True


limiter = RateLimiter()


def llm_dependency() -> agent.AssistantLLM:
    try:
        return agent.get_assistant_llm()
    except agent.AssistantUnavailable as error:
        raise HTTPException(503, str(error)) from error


@router.get("/suggestions")
def get_suggestions(user=Depends(get_current_active_user)):
    return {"tools": suggestions()}


@router.post("/chat")
def chat(body: ChatRequest, user=Depends(get_current_active_user), db: Session = Depends(get_db),
         llm: agent.AssistantLLM = Depends(llm_dependency)):
    if not limiter.allow(user.id, settings.ASSISTANT_RATE_PER_MINUTE):
        raise HTTPException(429, "Bạn hỏi hơi nhanh, vui lòng chờ một lát rồi hỏi tiếp.")
    started = time.monotonic()
    log = AssistantLog(user_id=user.id, question=body.message, calls=[], usage={})
    try:
        snapshot = get_snapshot(db)
        answer = agent.run(llm, snapshot, body.message, [turn.model_dump() for turn in body.history])
    except Exception as error:  # noqa: BLE001 - ghi nhật ký rồi báo lỗi thân thiện
        logger.exception("Trợ lý dữ liệu lỗi")
        log.error = f"{type(error).__name__}: {error}"
        log.duration_ms = int((time.monotonic() - started) * 1000)
        _save(db, log)
        raise HTTPException(502, "Trợ lý chưa trả lời được lúc này. Vui lòng thử lại sau ít phút.") from error
    log.answer, log.calls, log.usage, log.model = answer.text, answer.calls, answer.usage, answer.model
    log.duration_ms = int((time.monotonic() - started) * 1000)
    _save(db, log)
    # Không trả SQL/tham số công cụ cho giao diện; chỉ câu trả lời, khối hiển thị, cách tính.
    return {"answer": answer.text, "blocks": answer.blocks, "methods": answer.methods, "tools": answer.tools}


def _save(db: Session, log: AssistantLog) -> None:
    try:
        db.add(log)
        db.commit()
    except Exception:  # noqa: BLE001 - nhật ký hỏng không chặn câu trả lời
        db.rollback()
        logger.exception("Không ghi được nhật ký trợ lý")
