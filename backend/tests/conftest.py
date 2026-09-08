from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# 测试永远不碰真实 MySQL，也不读开发者本机 .env 里的真实 AI 端点。
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_pdfai_unit.db")
os.environ.setdefault("AI_BASE_URL", "https://example.com/v1")
os.environ.setdefault("AI_API_KEY", "replace-with-real-key")
os.environ.setdefault("AI_MODEL", "replace-with-vision-model")


@pytest.fixture()
def settings(tmp_path):
    """独立的 Settings：storage 指向 tmp，AI 相关项保持占位值（即"没有 .env 真实配置"）。"""
    from app.core.config import Settings

    return Settings(
        STORAGE_ROOT=str(tmp_path / "storage"),
        AI_BASE_URL="https://example.com/v1",
        AI_API_KEY="replace-with-real-key",
        AI_MODEL="replace-with-vision-model",
        AI_ENABLE_AUTO_FAILOVER=True,
        AI_FAILOVER_COOLDOWN_SECONDS=300,
        AI_FAILOVER_MAX_SWITCHES=0,
        AI_FAILOVER_ON_VISION_UNSUPPORTED=False,
    )


@pytest.fixture()
def settings_factory(tmp_path):
    """按用例覆盖任意 Settings 字段，其余保持与 settings fixture 相同的安全默认值。"""
    from app.core.config import Settings

    def build(**overrides):
        base = dict(
            STORAGE_ROOT=str(tmp_path / "storage"),
            AI_BASE_URL="https://example.com/v1",
            AI_API_KEY="replace-with-real-key",
            AI_MODEL="replace-with-vision-model",
            AI_ENABLE_AUTO_FAILOVER=True,
            AI_FAILOVER_COOLDOWN_SECONDS=300,
            AI_FAILOVER_MAX_SWITCHES=0,
            AI_FAILOVER_ON_VISION_UNSUPPORTED=False,
            AI_MAX_CONCURRENT_CALLS_PER_TASK=2,
        )
        base.update(overrides)
        return Settings(**base)

    return build


@pytest.fixture()
def db_session(tmp_path):
    """每个用例一套独立的 SQLite schema，由 ORM metadata 建表。"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.session import Base
    import app.models.models  # noqa: F401  确保所有表都已注册到 metadata

    engine = create_engine(f"sqlite:///{tmp_path / 'unit.db'}", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, future=True)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def profile_service(db_session, settings, tmp_path):
    from app.services.ai_profile_service import AiProfileService

    key_dir = tmp_path / "config"
    key_dir.mkdir(parents=True, exist_ok=True)
    return AiProfileService(db_session, settings=settings, key_path=key_dir / "ai-config.key")


def make_candidate(name, *, profile_id=None, model=None, behavior=None):
    """构造一个候选：behavior 是一个可调用对象，决定这套配置每次被调用时的行为。"""
    from app.ai.failover_provider import ProviderCandidate

    class _Stub:
        def __init__(self):
            self.calls = 0

        def _run(self, *args, **kwargs):
            self.calls += 1
            if behavior is None:
                return {"ok": name}
            return behavior(self.calls)

        detect_layout = _run
        extract_elements = _run
        compare_elements = _run

    stub = _Stub()
    candidate = ProviderCandidate(
        profile_id=profile_id,
        name=name,
        model=model or f"model-{name}",
        factory=lambda: stub,
    )
    return candidate, stub


def fail_with(message):
    def behavior(_call_no):
        raise Exception(message)

    return behavior


def succeed_with(payload):
    def behavior(_call_no):
        return payload

    return behavior
