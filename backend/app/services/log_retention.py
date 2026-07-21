"""日志保留策略清理服务。

职责：
1. 删除过期的完整日志文件（7 天）。
2. 批量删除过期异常数据库记录（90 天）。
3. 清除长期失败时间线的过期详情字段。

清理异常只记录告警，不影响业务服务启动和任务执行。
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.models import TaskLog, TaskLogFile


class LogRetentionService:
    def __init__(self, db: Session, logs_root: Path | None = None):
        self._db = db
        self._logs_root = logs_root.resolve() if logs_root is not None else None

    def cleanup_expired_files(self) -> int:
        """删除过期且不处于 writing 状态的完整日志文件。"""
        if self._logs_root is None:
            return 0
        now = datetime.now()
        expired_manifests = (
            self._db.query(TaskLogFile)
            .filter(
                TaskLogFile.status != "writing",
                TaskLogFile.expires_at.isnot(None),
                TaskLogFile.expires_at < now,
            )
            .all()
        )
        cleaned = 0
        for manifest in expired_manifests:
            try:
                file_path = (self._logs_root / manifest.relative_path).resolve()
                if not file_path.is_relative_to(self._logs_root):
                    raise ValueError("日志清单路径超出日志目录")
                if file_path.exists():
                    file_path.unlink()
                manifest.status = "expired"
                cleaned += 1
            except Exception as exc:
                print(f"[retention] 文件清理失败: {manifest.relative_path}: {exc}", file=sys.stderr)
        if cleaned:
            try:
                self._db.commit()
            except Exception:
                self._db.rollback()
        return cleaned

    def cleanup_expired_exceptions(self, batch_size: int = 500) -> int:
        """分批删除 90 天前、非时间线的异常数据库记录。"""
        now = datetime.now()
        deleted_total = 0
        while True:
            expired_ids = (
                self._db.query(TaskLog.id)
                .filter(
                    TaskLog.is_timeline.is_(False),
                    TaskLog.retention_until.isnot(None),
                    TaskLog.retention_until < now,
                )
                .limit(batch_size)
                .all()
            )
            if not expired_ids:
                break
            ids = [row[0] for row in expired_ids]
            deleted = (
                self._db.query(TaskLog)
                .filter(TaskLog.id.in_(ids))
                .delete(synchronize_session=False)
            )
            self._db.commit()
            deleted_total += deleted
            if len(ids) < batch_size:
                break
        return deleted_total

    def purge_old_timeline_details(self, days: int = 90) -> int:
        """对长期失败时间线清空已过期的错误堆栈和大段元数据，仅保留摘要。"""
        cutoff = datetime.now() - timedelta(days=days)
        old_timelines = (
            self._db.query(TaskLog)
            .filter(
                TaskLog.is_timeline.is_(True),
                TaskLog.created_at < cutoff,
                TaskLog.error_detail.isnot(None),
            )
            .all()
        )
        purged = 0
        for log in old_timelines:
            log.error_detail = None
            log.metadata_json = None
            purged += 1
        if purged:
            try:
                self._db.commit()
            except Exception:
                self._db.rollback()
        return purged

    def run_full_cleanup(self) -> dict[str, int]:
        """执行完整清理周期。"""
        results = {"files": 0, "exceptions": 0, "details": 0}
        try:
            results["files"] = self.cleanup_expired_files()
        except Exception as exc:
            print(f"[retention] 文件清理异常: {exc}", file=sys.stderr)
        try:
            results["exceptions"] = self.cleanup_expired_exceptions()
        except Exception as exc:
            print(f"[retention] 异常清理异常: {exc}", file=sys.stderr)
        try:
            results["details"] = self.purge_old_timeline_details()
        except Exception as exc:
            print(f"[retention] 详情清除异常: {exc}", file=sys.stderr)
        return results

    def backfill_legacy_logs(self) -> int:
        """回填旧日志的 is_timeline 和 retention_until 标记。

        规则：
        - 旧 succeeded/completed/failed/queued/paused/resumed/retry 主要阶段记录标记为时间线。
        - 旧 warning/error 标记异常保留期。
        - 旧 started/info 保持 is_timeline=false。
        """
        updated = 0
        # 标记时间线事件
        timeline_events = ["succeeded", "completed", "failed", "queued", "paused", "resumed", "retry", "degraded"]
        timeline_count = (
            self._db.query(TaskLog)
            .filter(
                TaskLog.is_timeline.is_(False),
                TaskLog.event_type.in_(timeline_events),
                TaskLog.level == "info",
            )
            .update({TaskLog.is_timeline: True}, synchronize_session=False)
        )
        updated += timeline_count
        # 标记异常保留期
        now = datetime.now()
        exception_count = (
            self._db.query(TaskLog)
            .filter(
                TaskLog.level.in_(["warning", "error"]),
                TaskLog.retention_until.is_(None),
                TaskLog.is_timeline.is_(False),
            )
            .update(
                {TaskLog.retention_until: now + timedelta(days=90)},
                synchronize_session=False,
            )
        )
        updated += exception_count
        if updated:
            try:
                self._db.commit()
            except Exception:
                self._db.rollback()
        return updated
