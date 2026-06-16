from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api.tasks import router as tasks_router, _recover_active_tasks
from app.api.settings import router as settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    for subdir in ["uploads", "pages", "regions", "ai_outputs", "exports"]:
        settings.get_storage_path(subdir).mkdir(parents=True, exist_ok=True)
    _recover_active_tasks()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="PDFAI", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health_check() -> dict:
        return {"status": "ok"}

    app.include_router(tasks_router)
    app.include_router(settings_router)

    return app


app = create_app()
