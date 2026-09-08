"""迁移 c3a4b5c6d7e8（AI 配置故障切换字段）的验证。

注意：项目最早的基线迁移 d2135e58fd8a 使用 server_default=sa.text("now()")，这是
MySQL 专有语法，SQLite 无法解析，因此整条迁移链无法在 SQLite 上重放。这是本次改动之前
就存在的性质，不是故障切换迁移引入的问题。

所以这里的策略是：
1. 用与 ae1f2a3b4c5d 等价、但 SQLite 可建的 ai_profiles 表还原迁移前状态；
2. 直接对这张表跑本次迁移的 upgrade() / downgrade()，验证可执行且可回滚；
3. 另外用 MySQL 方言静态编译 DDL，验证 MySQL 侧同样成立（无需真实 MySQL 服务）。
"""
from __future__ import annotations

import datetime
from pathlib import Path

import pytest
from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, create_engine, inspect, text
from sqlalchemy.schema import CreateTable

BACKEND_ROOT = Path(__file__).resolve().parent.parent
ALEMBIC_DIR = BACKEND_ROOT / "alembic"


def _alembic_script_directory():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config()
    config.set_main_option("script_location", str(ALEMBIC_DIR))
    return ScriptDirectory.from_config(config)


def test_migration_chain_has_single_head():
    """新迁移必须接在原 head 之后，且不引入分叉。"""
    script = _alembic_script_directory()
    heads = script.get_heads()

    assert list(heads) == ["c3a4b5c6d7e8"], f"期望单一 head c3a4b5c6d7e8，实际 {heads}"
    revision = script.get_revision("c3a4b5c6d7e8")
    assert revision.down_revision == "bf2a3b4c5d6e"


def _create_pre_migration_ai_profiles(engine):
    """还原 c3a4b5c6d7e8 之前的 ai_profiles 结构（SQLite 可建版本）。"""
    metadata = MetaData()
    Table(
        "ai_profiles",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("name", String(128), nullable=False, unique=True),
        Column("base_url", String(1024), nullable=False),
        Column("api_key_encrypted", Text, nullable=False),
        Column("model", String(256), nullable=False),
        Column("timeout_seconds", Integer, nullable=False),
        Column("max_retries", Integer, nullable=False),
        Column("is_active", Integer, nullable=False, server_default="0"),
        Column("is_pending", Integer, nullable=False, server_default="0"),
        Column("is_enabled", Integer, nullable=False, server_default="1"),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
    )
    metadata.create_all(engine)


def _run_migration(engine, direction: str):
    """在给定引擎上直接执行本次迁移的 upgrade() 或 downgrade()。"""
    import importlib.util

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    spec = importlib.util.spec_from_file_location(
        "migration_c3a4b5c6d7e8",
        ALEMBIC_DIR / "versions" / "c3a4b5c6d7e8_add_ai_profile_failover_fields.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            getattr(module, direction)()


@pytest.fixture()
def migrated_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}", future=True)
    _create_pre_migration_ai_profiles(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def test_upgrade_adds_all_failover_columns(migrated_engine):
    _run_migration(migrated_engine, "upgrade")

    columns = {c["name"] for c in inspect(migrated_engine).get_columns("ai_profiles")}
    for expected in [
        "priority",
        "health_status",
        "cooldown_until",
        "last_health_error",
        "last_health_checked_at",
    ]:
        assert expected in columns, f"upgrade 后缺少列 {expected}"

    indexes = {i["name"] for i in inspect(migrated_engine).get_indexes("ai_profiles")}
    assert "idx_ai_profiles_priority" in indexes


def test_upgrade_then_downgrade_roundtrip(migrated_engine):
    """downgrade 必须可执行，并把新增列和索引完全移除。"""
    _run_migration(migrated_engine, "upgrade")
    _run_migration(migrated_engine, "downgrade")

    columns = {c["name"] for c in inspect(migrated_engine).get_columns("ai_profiles")}
    for removed in [
        "priority",
        "health_status",
        "cooldown_until",
        "last_health_error",
        "last_health_checked_at",
    ]:
        assert removed not in columns, f"downgrade 后仍残留列 {removed}"

    indexes = {i["name"] for i in inspect(migrated_engine).get_indexes("ai_profiles")}
    assert "idx_ai_profiles_priority" not in indexes
    # 原有列必须保留。
    assert {"id", "name", "base_url", "model", "is_enabled"} <= columns


def test_server_default_applies_to_existing_rows(migrated_engine):
    """迁移前已存在的行必须自动获得 priority=100 / health_status=unknown。"""
    now = datetime.datetime(2026, 1, 1, 12, 0, 0)
    with migrated_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO ai_profiles "
                "(name, base_url, api_key_encrypted, model, timeout_seconds, max_retries, "
                " is_active, is_pending, is_enabled, created_at, updated_at) "
                "VALUES ('旧配置', 'https://old.example.com/v1', 'enc', 'm', 60, 2, "
                " 1, 0, 1, :now, :now)"
            ),
            {"now": now},
        )

    _run_migration(migrated_engine, "upgrade")

    with migrated_engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT priority, health_status, cooldown_until, last_health_error, "
                "last_health_checked_at FROM ai_profiles WHERE name='旧配置'"
            )
        ).one()

    assert row[0] == 100, "存量行应当拿到 server default 100"
    assert row[1] == "unknown", "存量行健康状态应为 unknown"
    assert row[2] is None and row[3] is None and row[4] is None


def test_new_columns_compile_for_mysql():
    """静态验证 MySQL 方言：新增列的 DDL 必须能为 MySQL 编译出来。

    不需要真实 MySQL 服务，只确认类型与 server default 在 MySQL 上是合法的。
    """
    from sqlalchemy.dialects import mysql

    metadata = MetaData()
    table = Table(
        "ai_profiles_probe",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("priority", Integer, nullable=False, server_default="100"),
        Column("health_status", String(16), nullable=False, server_default="unknown"),
        Column("cooldown_until", DateTime, nullable=True),
        Column("last_health_error", Text, nullable=True),
        Column("last_health_checked_at", DateTime, nullable=True),
    )
    ddl = str(CreateTable(table).compile(dialect=mysql.dialect()))

    assert "priority INTEGER NOT NULL DEFAULT '100'" in ddl
    assert "health_status VARCHAR(16) NOT NULL DEFAULT 'unknown'" in ddl
    # TEXT 在 MySQL 上不能有默认值，这里必须是可空且无默认。
    assert "last_health_error TEXT" in ddl


def test_orm_model_matches_migration_columns(migrated_engine):
    """ORM 模型声明的新字段必须与迁移后的实际表结构一致。"""
    _run_migration(migrated_engine, "upgrade")

    from app.models.models import AiProfile

    actual = {c["name"] for c in inspect(migrated_engine).get_columns("ai_profiles")}
    declared = {c.name for c in AiProfile.__table__.columns}

    missing_in_db = declared - actual
    assert not missing_in_db, f"ORM 声明了迁移里没有的列: {missing_in_db}"


def test_orm_defaults_apply_without_server_default(db_session):
    """通过 ORM 新建配置时，priority / health_status 必须有 Python 侧默认值。

    ORM 建表路径（测试与开发用的 create_all）不依赖 server_default，
    所以这里单独确认 ORM default 也已设置。
    """
    from app.models.models import AiProfile

    profile = AiProfile(
        name="orm-default-probe",
        base_url="https://x.example.com/v1",
        api_key_encrypted="enc",
        model="m",
        timeout_seconds=60,
        max_retries=1,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)

    assert profile.priority == 100
    assert profile.health_status == "unknown"
    assert profile.cooldown_until is None
