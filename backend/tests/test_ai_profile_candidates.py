"""候选链构建、冷却语义、Mock 安全性与健康状态落库。"""
from __future__ import annotations

import datetime

import pytest

from app.models.models import AiProfile, CompareTask, PdfFile


def _make_profile(service, name, *, priority=100, model="gpt-4o", base_url=None, api_key=None):
    return service.create_profile(
        name,
        base_url or f"https://api.{name}.com/v1",
        api_key or f"sk-{name}-key",
        model,
        120,
        2,
        priority=priority,
    )


def _make_task(db, profile_id):
    base = PdfFile(
        original_name="a.pdf", stored_path="/tmp/a.pdf", file_hash="h1",
        page_count=1, file_role="base", file_type="pdf", status="uploaded",
    )
    compare = PdfFile(
        original_name="b.pdf", stored_path="/tmp/b.pdf", file_hash="h2",
        page_count=1, file_role="compare", file_type="pdf", status="uploaded",
    )
    db.add_all([base, compare])
    db.commit()
    task = CompareTask(
        task_no="TASK-TEST-0001", base_file_id=base.id, compare_file_id=compare.id,
        ai_profile_id=profile_id, status="uploaded", progress=0,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


# ─── 10. 真实配置失败绝不使用 Mock ───
def test_real_configs_never_fall_back_to_mock(profile_service, db_session):
    primary = _make_profile(profile_service, "primary", priority=1)
    backup = _make_profile(profile_service, "backup", priority=2)
    task = _make_task(db_session, primary.id)

    candidates = profile_service.build_provider_candidates(task)

    names = [c.name for c in candidates]
    assert names == ["primary", "backup"]
    assert all("Mock" not in name for name in names)
    assert all(c.profile_id is not None for c in candidates)


def test_mock_only_when_no_real_config_at_all(profile_service, db_session):
    # 只有占位配置：等同于"系统没有真实 AI 配置"。
    placeholder = profile_service.create_profile(
        "占位配置", "https://example.com/v1", "replace-with-real-key",
        "replace-with-vision-model", 120, 2,
    )
    task = _make_task(db_session, placeholder.id)

    candidates = profile_service.build_provider_candidates(task)

    assert len(candidates) == 1
    assert candidates[0].name == "Mock 模拟配置"
    assert candidates[0].profile_id is None


# ─── 9. cooldown 语义 ───
def test_cooling_down_profile_sorts_last(profile_service, db_session):
    primary = _make_profile(profile_service, "primary", priority=1)
    backup = _make_profile(profile_service, "backup", priority=50)
    task = _make_task(db_session, primary.id)

    # 主配置刚失败并进入冷却。
    profile_service.mark_profile_unhealthy(primary.id, "503 service unavailable")

    candidates = profile_service.build_provider_candidates(task)

    # 健康的备用配置排到前面，冷却中的主配置只作为最后兜底。
    assert [c.name for c in candidates] == ["backup", "primary"]


def test_expired_cooldown_returns_to_normal_order(profile_service, db_session):
    primary = _make_profile(profile_service, "primary", priority=1)
    _make_profile(profile_service, "backup", priority=50)
    task = _make_task(db_session, primary.id)

    # 冷却已过期：允许半开探测，主配置回到最前面。
    db_session.query(AiProfile).filter(AiProfile.id == primary.id).update({
        AiProfile.health_status: "unhealthy",
        AiProfile.cooldown_until: datetime.datetime.now() - datetime.timedelta(seconds=1),
    })
    db_session.commit()

    candidates = profile_service.build_provider_candidates(task)

    assert [c.name for c in candidates] == ["primary", "backup"]


def test_priority_orders_non_bound_candidates(profile_service, db_session):
    bound = _make_profile(profile_service, "bound", priority=500)
    _make_profile(profile_service, "low-number", priority=1)
    _make_profile(profile_service, "mid", priority=10)
    task = _make_task(db_session, bound.id)

    candidates = profile_service.build_provider_candidates(task)

    # 绑定配置永远第一；其余按 priority 升序。
    assert [c.name for c in candidates] == ["bound", "low-number", "mid"]


def test_preferred_profile_sorts_before_bound(profile_service, db_session):
    """后续阶段沿用已经成功的后备配置，而不是重新打故障主配置。"""
    bound = _make_profile(profile_service, "bound", priority=1)
    backup = _make_profile(profile_service, "backup", priority=90)
    task = _make_task(db_session, bound.id)

    candidates = profile_service.build_provider_candidates(
        task, preferred_profile_id=backup.id
    )

    assert [c.name for c in candidates] == ["backup", "bound"]


# ─── 7. .env 去重 ───
def test_env_config_appended_when_distinct(profile_service, db_session, settings):
    settings.AI_BASE_URL = "https://env.example.org/v1"
    settings.AI_API_KEY = "sk-env-key"
    settings.AI_MODEL = "env-model"
    profile = _make_profile(profile_service, "db-profile")
    task = _make_task(db_session, profile.id)

    candidates = profile_service.build_provider_candidates(task)

    assert [c.name for c in candidates] == ["db-profile", ".env 全局配置"]


def test_env_config_deduplicated_against_identical_profile(profile_service, db_session, settings):
    settings.AI_BASE_URL = "https://same.example.org/v1"
    settings.AI_API_KEY = "sk-same-key"
    settings.AI_MODEL = "same-model"
    profile = _make_profile(
        profile_service, "same", base_url="https://same.example.org/v1",
        api_key="sk-same-key", model="same-model",
    )
    task = _make_task(db_session, profile.id)

    candidates = profile_service.build_provider_candidates(task)

    # 同一个端点/模型/Key 不重复尝试。
    assert [c.name for c in candidates] == ["same"]


def test_env_dedup_ignores_trailing_slash_and_suffix(profile_service, db_session, settings):
    settings.AI_BASE_URL = "https://same.example.org/v1/chat/completions"
    settings.AI_API_KEY = "sk-same-key"
    settings.AI_MODEL = "same-model"
    profile = _make_profile(
        profile_service, "same", base_url="https://same.example.org/v1/",
        api_key="sk-same-key", model="same-model",
    )
    task = _make_task(db_session, profile.id)

    candidates = profile_service.build_provider_candidates(task)

    assert [c.name for c in candidates] == ["same"]


# ─── 8. 解密失败要留下痕迹 ───
def test_undecryptable_profile_is_recorded_not_silently_skipped(profile_service, db_session):
    good = _make_profile(profile_service, "good", priority=1)
    broken = _make_profile(profile_service, "broken", priority=2)
    # 破坏密文，模拟密钥轮换后无法解密。
    db_session.query(AiProfile).filter(AiProfile.id == broken.id).update(
        {AiProfile.api_key_encrypted: "not-a-valid-fernet-token"}
    )
    db_session.commit()
    task = _make_task(db_session, good.id)

    candidates = profile_service.build_provider_candidates(task)

    # 坏配置不进候选链……
    assert [c.name for c in candidates] == ["good"]
    # ……但健康状态里留下了痕迹。
    db_session.refresh(broken)
    assert broken.health_status == "unhealthy"
    assert broken.last_health_error is not None
    assert "解密失败" in broken.last_health_error
    assert broken.last_health_checked_at is not None


# ─── 健康状态落库 ───
def test_apply_failover_outcome_persists_health(profile_service, db_session):
    from app.ai.failover_provider import FailoverOutcome

    failed = _make_profile(profile_service, "failed-one")
    succeeded = _make_profile(profile_service, "good-one")

    profile_service.apply_failover_outcome(
        FailoverOutcome(
            failed_profiles={failed.id: "503 service unavailable"},
            succeeded_profile_ids=[succeeded.id],
        )
    )

    db_session.refresh(failed)
    db_session.refresh(succeeded)
    assert failed.health_status == "unhealthy"
    assert failed.cooldown_until is not None
    assert succeeded.health_status == "healthy"
    assert succeeded.cooldown_until is None


def test_profile_failing_and_succeeding_keeps_cooldown(profile_service, db_session):
    """同一阶段里既失败又成功：以失败为准，不能立刻清掉刚设的 cooldown。"""
    from app.ai.failover_provider import FailoverOutcome

    profile = _make_profile(profile_service, "flaky")

    profile_service.apply_failover_outcome(
        FailoverOutcome(
            failed_profiles={profile.id: "429 rate limit"},
            succeeded_profile_ids=[profile.id],
        )
    )

    db_session.refresh(profile)
    assert profile.health_status == "unhealthy"
    assert profile.cooldown_until is not None


def test_health_error_is_sanitized_and_truncated(profile_service, db_session):
    profile = _make_profile(profile_service, "leaky")

    profile_service.mark_profile_unhealthy(
        profile.id, "Authorization: Bearer sk-super-secret-value 401 unauthorized " + "x" * 900
    )

    db_session.refresh(profile)
    assert "sk-super-secret-value" not in profile.last_health_error
    assert "[REDACTED]" in profile.last_health_error
    assert len(profile.last_health_error) <= 500


def test_public_dict_never_exposes_encrypted_key(profile_service):
    profile = _make_profile(profile_service, "p1")

    public = profile_service.to_public_dict(profile)

    assert "api_key_encrypted" not in public
    assert "api_key" not in public
    assert public["has_api_key"] is True
    assert public["health_status"] == "unknown"
    assert public["priority"] == 100


def test_effective_health_status_derives_cooling_down(profile_service, db_session):
    profile = _make_profile(profile_service, "p1")
    profile_service.mark_profile_unhealthy(profile.id, "503 unavailable")
    db_session.refresh(profile)

    assert profile.health_status == "unhealthy"
    # 冷却期内对外显示为 cooling_down。
    assert profile_service.to_public_dict(profile)["health_status"] == "cooling_down"


# ─── 自动切换关闭时的行为 ───
def test_failover_disabled_returns_single_candidate(profile_service, db_session, settings):
    settings.AI_ENABLE_AUTO_FAILOVER = False
    bound = _make_profile(profile_service, "bound", priority=1)
    _make_profile(profile_service, "other", priority=2)
    task = _make_task(db_session, bound.id)

    candidates = profile_service.build_provider_candidates(task)

    assert [c.name for c in candidates] == ["bound"]


def test_disabled_bound_profile_is_still_attempted(profile_service, db_session):
    """任务绑定的配置即使已停用也要尝试，保持与旧行为一致。"""
    bound = _make_profile(profile_service, "bound", priority=1)
    other = _make_profile(profile_service, "other", priority=2)
    task = _make_task(db_session, bound.id)
    # 直接改库绕过"当前生效配置不能停用"的业务校验。
    db_session.query(AiProfile).filter(AiProfile.id == bound.id).update(
        {AiProfile.is_enabled: False, AiProfile.is_active: False}
    )
    db_session.commit()

    candidates = profile_service.build_provider_candidates(task)

    assert [c.name for c in candidates] == ["bound", "other"]
