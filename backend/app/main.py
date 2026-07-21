from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api.tasks import router as tasks_router, _recover_active_tasks
from app.api.settings import router as settings_router
from app.api.system_logs import router as system_logs_router

_cleanup_timer: threading.Timer | None = None


def _run_log_cleanup() -> None:
    """执行一次日志清理，失败不影响业务。"""
    try:
        from app.db.session import get_session_local
        from app.services.log_retention import LogRetentionService
        db = get_session_local()()
        try:
            settings = get_settings()
            service = LogRetentionService(db, settings.get_storage_path("logs"))
            service.backfill_legacy_logs()
            service.run_full_cleanup()
        finally:
            db.close()
    except Exception as exc:
        import sys
        print(f"[startup] 日志清理异常: {exc}", file=sys.stderr)


def _schedule_daily_cleanup() -> None:
    """每 24 小时执行一次清理。"""
    global _cleanup_timer
    _run_log_cleanup()
    _cleanup_timer = threading.Timer(86400, _schedule_daily_cleanup)
    _cleanup_timer.daemon = True
    _cleanup_timer.start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    for subdir in ["uploads", "pages", "regions", "ai_outputs", "exports", "logs"]:
        settings.get_storage_path(subdir).mkdir(parents=True, exist_ok=True)
    _recover_active_tasks()
    # 启动时执行一次轻量清理，然后每 24 小时重复
    _schedule_daily_cleanup()
    yield
    # 关闭定时器
    global _cleanup_timer
    if _cleanup_timer is not None:
        _cleanup_timer.cancel()
        _cleanup_timer = None


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="PDFAI", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health_check() -> dict:
        return {"status": "ok"}

    app.include_router(tasks_router)
    app.include_router(settings_router)
    app.include_router(system_logs_router)

    return app


app = create_app()
