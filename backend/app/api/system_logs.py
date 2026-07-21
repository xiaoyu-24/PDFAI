from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.models import CompareTask, TaskLog, TaskLogFile
from app.schemas.task_log import TaskLogListResponse, TaskLogResponse, TaskLogSummaryResponse, FullLogListResponse
from app.services.detail_log_writer import read_detail_logs


router = APIRouter(prefix="/api/system-logs", tags=["system-logs"])


def _filtered_query(
    db: Session,
    *,
    task_no: str | None = None,
    level: str | None = None,
    error_category: str | None = None,
    stage: str | None = None,
    event_type: str | None = None,
    degraded: bool | None = None,
    min_response_time_ms: int | None = None,
):
    query = db.query(TaskLog).join(CompareTask, CompareTask.id == TaskLog.task_id)
    if task_no:
        query = query.filter(CompareTask.task_no.ilike(f"%{task_no}%"))
    if level:
        query = query.filter(TaskLog.level == level)
    if error_category:
        query = query.filter(TaskLog.error_category == error_category)
    if stage:
        query = query.filter(TaskLog.stage == stage)
    if event_type:
        query = query.filter(TaskLog.event_type == event_type)
    if degraded is not None:
        query = query.filter(TaskLog.is_degraded.is_(degraded))
    if min_response_time_ms is not None:
        query = query.filter(TaskLog.response_time_ms >= min_response_time_ms)
    return query


def _to_response(log: TaskLog) -> TaskLogResponse:
    return TaskLogResponse(
        id=log.id,
        task_id=log.task_id,
        task_no=log.task.task_no if log.task else None,
        run_id=log.run_id,
        stage=log.stage,
        component=log.component,
        event_type=log.event_type,
        level=log.level,
        status=log.status,
        error_category=log.error_category,
        error_code=log.error_code,
        message=log.message,
        error_detail=log.error_detail,
        attempt_no=log.attempt_no,
        max_attempts=log.max_attempts,
        timeout_ms=log.timeout_ms,
        response_time_ms=log.response_time_ms,
        is_degraded=log.is_degraded,
        fallback_action=log.fallback_action,
        metadata_json=log.metadata_json,
        is_timeline=log.is_timeline,
        created_at=log.created_at,
    )


def _get_system_full_logs(
    db: Session,
    *,
    task_no: str | None,
    cursor: int,
    limit: int,
) -> FullLogListResponse:
    """按任务编号读取 7 天内的完整日志，避免无界扫描所有日志文件。"""
    normalized_task_no = (task_no or "").strip()
    if not normalized_task_no:
        return FullLogListResponse(
            items=[],
            total=0,
            cursor=cursor,
            status_message="请先输入任务编号，再查看完整日志（保存 7 天）。",
        )

    task = (
        db.query(CompareTask)
        .filter(
            CompareTask.status != "deleted",
            CompareTask.task_no.ilike(f"%{normalized_task_no}%"),
        )
        .order_by(CompareTask.id.desc())
        .first()
    )
    if task is None:
        return FullLogListResponse(
            items=[],
            total=0,
            cursor=cursor,
            status_message="未找到匹配的任务。",
        )

    manifest = (
        db.query(TaskLogFile)
        .filter(TaskLogFile.task_id == task.id)
        .order_by(TaskLogFile.id.desc())
        .first()
    )
    if manifest is None:
        return FullLogListResponse(
            items=[],
            total=0,
            cursor=cursor,
            status_message="当前任务无完整日志文件。",
        )
    if manifest.status == "expired":
        return FullLogListResponse(
            items=[],
            total=0,
            cursor=cursor,
            status_message="完整日志已过期（保存 7 天），请查看简洁时间线或异常记录。",
        )

    entries, next_cursor = read_detail_logs(
        get_settings().get_storage_path("logs"),
        task.id,
        manifest.run_id,
        cursor=cursor,
        limit=limit,
    )
    for entry in entries:
        entry.setdefault("task_no", task.task_no)
    status_message = None
    if not entries and manifest.status == "ready":
        status_message = "完整日志文件缺失或正在压缩中。"
    return FullLogListResponse(
        items=entries,
        total=manifest.line_count or len(entries),
        cursor=cursor,
        next_cursor=next_cursor if next_cursor != -1 else None,
        status_message=status_message,
    )


@router.get("")
def list_system_logs(
    view: str = Query("timeline", pattern="^(timeline|exceptions|full)$"),
    task_no: str | None = Query(None),
    level: str | None = Query(None),
    error_category: str | None = Query(None),
    stage: str | None = Query(None),
    event_type: str | None = Query(None),
    degraded: bool | None = Query(None),
    min_response_time_ms: int | None = Query(None, ge=0),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    cursor: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    if view == "full":
        return _get_system_full_logs(
            db,
            task_no=task_no,
            cursor=cursor,
            limit=limit,
        )

    query = _filtered_query(
        db,
        task_no=task_no,
        level=level,
        error_category=error_category,
        stage=stage,
        event_type=event_type,
        degraded=degraded,
        min_response_time_ms=min_response_time_ms,
    )
    if view == "timeline":
        query = query.filter(TaskLog.is_timeline.is_(True))
    elif view == "exceptions":
        query = query.filter(TaskLog.level.in_(["warning", "error"]))
    total = query.count()
    logs = query.order_by(TaskLog.created_at.desc(), TaskLog.id.desc()).offset(offset).limit(limit).all()
    return TaskLogListResponse(items=[_to_response(log) for log in logs], total=total, limit=limit, offset=offset)


@router.get("/summary", response_model=TaskLogSummaryResponse)
def get_system_log_summary(
    task_no: str | None = Query(None),
    level: str | None = Query(None),
    error_category: str | None = Query(None),
    stage: str | None = Query(None),
    event_type: str | None = Query(None),
    degraded: bool | None = Query(None),
    min_response_time_ms: int | None = Query(None, ge=0),
    db: Session = Depends(get_db),
):
    base_query = _filtered_query(
        db,
        task_no=task_no,
        level=level,
        error_category=error_category,
        stage=stage,
        event_type=event_type,
        degraded=degraded,
        min_response_time_ms=min_response_time_ms,
    )
    # SQL 聚合代替 .all() 内存统计
    row = base_query.with_entities(
        func.count(TaskLog.id).label("total"),
        func.sum(case((TaskLog.level == "error", 1), else_=0)).label("errors"),
        func.sum(case((TaskLog.event_type == "timeout", 1), else_=0)).label("timeouts"),
        func.sum(case((TaskLog.event_type == "retry", 1), else_=0)).label("retries"),
        func.sum(case((TaskLog.is_degraded.is_(True), 1), else_=0)).label("degraded"),
        func.avg(TaskLog.response_time_ms).label("avg_rt"),
    ).one()

    total = row.total or 0
    errors = int(row.errors or 0)
    timeouts = int(row.timeouts or 0)
    retries = int(row.retries or 0)
    degraded_count = int(row.degraded or 0)
    average = float(row.avg_rt) if row.avg_rt else 0.0

    # P95：有界查询计算
    p95_value = 0
    duration_count = base_query.filter(TaskLog.response_time_ms.isnot(None)).count()
    if duration_count > 0:
        p95_offset = max(0, math.ceil(duration_count * 0.95) - 1)
        p95_row = (
            base_query.filter(TaskLog.response_time_ms.isnot(None))
            .order_by(TaskLog.response_time_ms.asc())
            .offset(p95_offset)
            .limit(1)
            .with_entities(TaskLog.response_time_ms)
            .first()
        )
        if p95_row:
            p95_value = p95_row[0]

    # 错误分类统计
    cat_rows = (
        base_query.filter(TaskLog.error_category != "none")
        .with_entities(TaskLog.error_category, func.count(TaskLog.id))
        .group_by(TaskLog.error_category)
        .all()
    )
    categories = {cat: cnt for cat, cnt in cat_rows}

    return TaskLogSummaryResponse(
        total=total,
        errors=errors,
        timeouts=timeouts,
        retries=retries,
        degraded=degraded_count,
        average_response_time_ms=average,
        p95_response_time_ms=p95_value,
        category_counts=categories,
    )
