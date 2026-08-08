from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

TaskStatus = Literal["queued", "running", "succeeded", "failed"]


class TaskCreate(BaseModel):
    command: str = Field(min_length=1, max_length=500)


class TaskView(BaseModel):
    id: str
    command: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    agent_id: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class AgentTask(BaseModel):
    id: str
    command: str


class AgentResult(BaseModel):
    ok: bool
    result: dict[str, Any] | None = None
    error: str | None = None
