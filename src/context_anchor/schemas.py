from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

TaskStatus = Literal["queued", "running", "succeeded", "failed"]
ActionJournalState = Literal["prepared", "in_flight", "executed", "acknowledged"]


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
    lease_expires_at: datetime | None = None
    attempts: int = 0


class AgentTask(BaseModel):
    id: str
    command: str
    lease_token: str = Field(min_length=20)
    lease_expires_at: datetime
    lease_seconds: int = Field(ge=1, le=3600)


class AgentLeaseRenewal(BaseModel):
    lease_token: str = Field(min_length=20)


class AgentLeaseView(BaseModel):
    id: str
    lease_expires_at: datetime


class AgentActionPrepare(BaseModel):
    lease_token: str = Field(min_length=20)
    action_key: str = Field(min_length=1, max_length=160)
    action_name: str = Field(min_length=1, max_length=80)
    repeat_safe: bool = False


class AgentActionTransition(BaseModel):
    lease_token: str = Field(min_length=20)
    action_key: str = Field(min_length=1, max_length=160)
    state: Literal["prepared", "in_flight", "executed"]
    receipt: dict[str, Any] | None = None


class AgentActionJournalView(BaseModel):
    task_id: str
    action_key: str
    action_name: str
    repeat_safe: bool
    state: ActionJournalState
    receipt: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    acknowledged_at: datetime | None = None


class AgentResult(BaseModel):
    lease_token: str = Field(min_length=20)
    ok: bool
    result: dict[str, Any] | None = None
    error: str | None = None
