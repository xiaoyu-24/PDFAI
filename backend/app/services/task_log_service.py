from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.models import TaskLog

EXCEPTION_RETENTION_DAYS = 90


_BEARER_PATTERN = re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s,;]+")
_API_KEY_PATTERN = re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)[^\s,;]+")
_WINDOWS_PATH_PATTERN = re.compile(r"(?i)\b[A-Z]:\\(?:[^\s\\]+\\)+[^\s,;]+")
_UNIX_STORAGE_PATH_PATTERN = re.compile(r"(?i)(?:/[^\s/]+)+/(?:storage|uploads|pages|regions)/[^\s,;]+")
_SENSITIVE_METADATA_KEYS = {"authorization", "api_key", "apikey", "token", "password", "secret"}


def classify_task_error(error: Exception | str | None) -> str:
    if error is None:
        return "none"
    text = str(error).lower()
    if any(marker in text for marker in ["database", "sql", "deadlock", "locked", "integrityerror", "operationalerror"]):
        return "database"
    if any(marker in text for marker in ["timeout", "timed out", "ssl", "dns", "connection", "network", "transport"]):
        return "network"
    if any(marker in text for marker in ["401", "403", "api key", "api_key", "model", "rate limit", "429"]):
        return "model_api"
    if any(marker in text for marker in ["file not found", "no such file", "missing file", "not found", "读取失败", "文件不存在"]):
        return "retrieval"
    return "code"


def sanitize_log_text(value: str | None) -> str | None:
    if value is None:
        return None
    sanitized = _BEARER_PATTERN.sub(r"\1[REDACTED]", value)
    sanitized = _API_KEY_PATTERN.sub(r"\1[REDACTED]", sanitized)
    sanitized = _WINDOWS_PATH_PATTERN.sub("[REDACTED_PATH]", sanitized)
    sanitized = _UNIX_STORAGE_PATH_PATTERN.sub("[REDACTED_PATH]", sanitized)
    return sanitized


def sanitize_log_metadata(value: Any, *, _key: str | None = None) -> Any:
    """递归脱敏日志元数据，避免密钥、令牌和路径进入数据库或文件。"""
    normalized_key = (_key or "").lower().replace("-", "_")
    if normalized_key in _SENSITIVE_METADATA_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(key): sanitize_log_metadata(item, _key=str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_log_metadata(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_log_metadata(item) for item in value]
    if isinstance(value, str):
        return sanitize_log_text(value)
    return value


class TaskLogService:
    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        *,
        task_id: int,
        run_id: str,
        stage: str,
        component: str,
        event_type: str,
        level: str,
        status: str,
        message: str,
        error_category: str | None = None,
        error_code: str | None = None,
        error_detail: str | None = None,
        attempt_no: int | None = None,
        max_attempts: int | None = None,
        timeout_ms: int | None = None,
        response_time_ms: int | None = None,
        is_degraded: bool = False,
        fallback_action: str | None = None,
        metadata_json: dict[str, Any] | None = None,
        is_timeline: bool = False,
        retention_until: datetime | None = None,
    ) -> TaskLog:
        safe_detail = sanitize_log_text(error_detail)
        # 异常事件自动设置 90 天保留期
        if retention_until is None and level in ("warning", "error"):
            retention_until = datetime.now() + timedelta(days=EXCEPTION_RETENTION_DAYS)
        log = TaskLog(
            task_id=task_id,
            run_id=run_id,
            stage=stage,
            component=component,
            event_type=event_type,
            level=level,
            status=status,
            error_category=error_category or classify_task_error(safe_detail),
            error_code=error_code,
            message=sanitize_log_text(message) or "",
            error_detail=safe_detail,
            attempt_no=attempt_no,
            max_attempts=max_attempts,
            timeout_ms=timeout_ms,
            response_time_ms=response_time_ms,
            is_degraded=is_degraded,
            fallback_action=sanitize_log_text(fallback_action),
            metadata_json=sanitize_log_metadata(metadata_json),
            is_timeline=is_timeline,
            retention_until=retention_until,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def safe_record(self, **kwargs) -> TaskLog | None:
        try:
            return self.record(**kwargs)
        except Exception:
            rollback = getattr(self.db, "rollback", None)
            if callable(rollback):
                try:
                    rollback()
                except Exception:
                    pass
            return None
