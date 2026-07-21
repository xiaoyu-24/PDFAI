"""完整技术日志 JSONL 文件写入、压缩和读取服务。

每个任务运行批次独立一个 JSONL 文件，任务结束后压缩为 .gz。
写入失败不影响业务任务执行。
"""
from __future__ import annotations

import gzip
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.models import TaskLogFile
from app.services.task_log_service import sanitize_log_metadata, sanitize_log_text

DETAIL_LOG_RETENTION_DAYS = 7


def _validate_run_id(run_id: str) -> None:
    """防止路径穿越：run_id 只允许安全字符。"""
    if not run_id or any(c in run_id for c in ("/", "\\", "..", "\x00")):
        raise ValueError(f"非法的 run_id: {run_id!r}")


class TaskDetailLogWriter:
    """将全部技术事件追加写入任务 JSONL 文件。"""

    def __init__(self, logs_root: Path, db: Session):
        self._logs_root = logs_root.resolve()
        self._db = db
        self._handles: dict[tuple[int, str], tuple[Path, Any, int]] = {}

    def open(self, task_id: int, run_id: str) -> Path:
        _validate_run_id(run_id)
        date_dir = self._logs_root / datetime.now().strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)
        file_path = date_dir / f"task-{task_id}-{run_id}.jsonl"
        # 确保路径在 logs_root 内
        if not file_path.resolve().is_relative_to(self._logs_root):
            raise ValueError("路径穿越检测")
        handle = open(file_path, "a", encoding="utf-8")
        self._handles[(task_id, run_id)] = (file_path, handle, 0)
        # 创建或更新数据库清单
        self._upsert_manifest(task_id, run_id, file_path, status="writing")
        return file_path

    def write_event(
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
        error_detail: str | None = None,
        response_time_ms: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        key = (task_id, run_id)
        entry = self._handles.get(key)
        if entry is None:
            # 写入失败不阻塞业务
            print(f"[detail-log] 未打开的日志文件: task={task_id} run={run_id}", file=sys.stderr)
            return
        file_path, handle, line_count = entry
        record = {
            "timestamp": datetime.now().isoformat(),
            "task_id": task_id,
            "run_id": run_id,
            "stage": stage,
            "component": component,
            "event_type": event_type,
            "level": level,
            "status": status,
            "message": sanitize_log_text(message) or "",
            "error_category": error_category,
            "error_detail": sanitize_log_text(error_detail),
            "response_time_ms": response_time_ms,
        }
        if metadata:
            record["metadata"] = sanitize_log_metadata(metadata)
        try:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            self._handles[key] = (file_path, handle, line_count + 1)
        except Exception as exc:
            print(f"[detail-log] 写入失败: {exc}", file=sys.stderr)

    def close(self, task_id: int, run_id: str) -> Path:
        """关闭并压缩为 .gz，更新清单。"""
        key = (task_id, run_id)
        entry = self._handles.pop(key, None)
        if entry is None:
            # 尝试找到已有文件
            gz_path = self._find_gz(task_id, run_id)
            return gz_path or self._logs_root / "missing"
        file_path, handle, line_count = entry
        handle.close()
        # 压缩
        gz_path = file_path.with_suffix(".jsonl.gz")
        with open(file_path, "rb") as f_in:
            with gzip.open(gz_path, "wb") as f_out:
                f_out.writelines(f_in)
        file_path.unlink(missing_ok=True)
        # 更新清单
        self._upsert_manifest(
            task_id, run_id, gz_path,
            status="ready", line_count=line_count,
            size_bytes=gz_path.stat().st_size,
            finished=True,
        )
        return gz_path

    def _upsert_manifest(
        self, task_id: int, run_id: str, file_path: Path, *,
        status: str, line_count: int | None = None,
        size_bytes: int | None = None, finished: bool = False,
    ) -> None:
        try:
            relative = str(file_path.relative_to(self._logs_root))
            manifest = (
                self._db.query(TaskLogFile)
                .filter(TaskLogFile.task_id == task_id, TaskLogFile.run_id == run_id)
                .first()
            )
            now = datetime.now()
            if manifest is None:
                manifest = TaskLogFile(
                    task_id=task_id,
                    run_id=run_id,
                    relative_path=relative,
                    status=status,
                    line_count=line_count or 0,
                    size_bytes=size_bytes or 0,
                    started_at=now,
                    expires_at=now + timedelta(days=DETAIL_LOG_RETENTION_DAYS),
                )
                self._db.add(manifest)
            else:
                manifest.relative_path = relative
                manifest.status = status
                if line_count is not None:
                    manifest.line_count = line_count
                if size_bytes is not None:
                    manifest.size_bytes = size_bytes
                if finished:
                    manifest.finished_at = now
                    manifest.expires_at = now + timedelta(days=DETAIL_LOG_RETENTION_DAYS)
            self._db.commit()
        except Exception as exc:
            print(f"[detail-log] 清单更新失败: {exc}", file=sys.stderr)
            try:
                self._db.rollback()
            except Exception:
                pass

    def _find_gz(self, task_id: int, run_id: str) -> Path | None:
        manifest = (
            self._db.query(TaskLogFile)
            .filter(TaskLogFile.task_id == task_id, TaskLogFile.run_id == run_id)
            .first()
        )
        if manifest:
            p = self._logs_root / manifest.relative_path
            if p.exists():
                return p
        return None


def read_detail_logs(
    logs_root: Path,
    task_id: int,
    run_id: str,
    *,
    cursor: int = 0,
    limit: int = 200,
) -> tuple[list[dict], int] | list[dict]:
    """读取任务完整日志。

    返回 (entries, next_cursor) 用于游标分页。
    如果文件不存在返回空列表。
    """
    logs_root = logs_root.resolve()
    _validate_run_id(run_id)
    file_path = _find_log_file(logs_root, task_id, run_id)
    if file_path is None:
        return [], -1

    entries: list[dict] = []
    valid_index = 0
    has_more = False
    # 流式解析 JSON，跳过损坏行，避免把整个文件加载到内存。
    for line in _iter_file_lines(file_path):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if valid_index < cursor:
            valid_index += 1
            continue
        if len(entries) >= limit:
            has_more = True
            break
        entries.append(entry)
        valid_index += 1

    next_cursor = cursor + len(entries) if has_more else -1
    return entries, next_cursor


def _find_log_file(logs_root: Path, task_id: int, run_id: str) -> Path | None:
    """在日期目录中查找日志文件（.gz 优先）。"""
    pattern_gz = f"task-{task_id}-{run_id}.jsonl.gz"
    pattern_jsonl = f"task-{task_id}-{run_id}.jsonl"
    if not logs_root.exists():
        return None
    for date_dir in sorted(logs_root.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        gz = date_dir / pattern_gz
        if gz.exists():
            return gz
        jsonl = date_dir / pattern_jsonl
        if jsonl.exists():
            return jsonl
    return None


def _read_file_lines(file_path: Path) -> list[str]:
    """兼容旧调用方的整文件读取辅助函数。新读取路径使用 _iter_file_lines。"""
    if file_path.suffix == ".gz":
        with gzip.open(file_path, "rt", encoding="utf-8") as f:
            return f.readlines()
    return file_path.read_text(encoding="utf-8").split("\n")


def _iter_file_lines(file_path: Path):
    if file_path.suffix == ".gz":
        with gzip.open(file_path, "rt", encoding="utf-8") as file_handle:
            yield from file_handle
        return
    with file_path.open("r", encoding="utf-8") as file_handle:
        yield from file_handle
