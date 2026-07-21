from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TaskLogResponse(BaseModel):
    id: int
    task_id: int
    task_no: str | None = None
    run_id: str
    stage: str
    component: str
    event_type: str
    level: str
    status: str
    error_category: str
    error_code: str | None = None
    message: str
    error_detail: str | None = None
    attempt_no: int | None = None
    max_attempts: int | None = None
    timeout_ms: int | None = None
    response_time_ms: int | None = None
    is_degraded: bool = False
    fallback_action: str | None = None
    metadata_json: dict | None = None
    is_timeline: bool = False
    created_at: datetime


class TaskLogListResponse(BaseModel):
    items: list[TaskLogResponse]
    total: int
    limit: int
    offset: int


class FullLogEntry(BaseModel):
    timestamp: str | None = None
    task_id: int | None = None
    run_id: str | None = None
    stage: str | None = None
    component: str | None = None
    event_type: str | None = None
    level: str | None = None
    status: str | None = None
    message: str | None = None
    error_category: str | None = None
    error_detail: str | None = None
    response_time_ms: int | None = None


class FullLogListResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    cursor: int
    next_cursor: int | None = None
    status_message: str | None = None


class TaskLogSummaryResponse(BaseModel):
    total: int
    errors: int
    timeouts: int
    retries: int
    degraded: int
    average_response_time_ms: float
    p95_response_time_ms: int
    category_counts: dict[str, int]
