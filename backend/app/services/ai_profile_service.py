from __future__ import annotations

import datetime
from pathlib import Path

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.ai.failover_provider import ProviderCandidate
from app.core.config import Settings, get_settings
from app.models.models import AiProfile, CompareTask
from app.services.task_log_service import sanitize_log_text


# 健康错误会通过设置页展示给用户，必须先脱敏再截断。
HEALTH_ERROR_MAX_CHARS = 500


def summarize_health_error(error: str | None) -> str | None:
    """把一条 AI 调用错误压成可以安全展示的健康状态摘要。

    复用任务日志的脱敏规则去掉 Bearer/API Key/本地路径，再截断长度：
    上游报错常把整个响应体拼进消息里，原样入库既会撑爆字段也可能带出密钥。
    """
    if error is None:
        return None
    sanitized = sanitize_log_text(str(error)) or ""
    sanitized = " ".join(sanitized.split())
    if not sanitized:
        return None
    if len(sanitized) <= HEALTH_ERROR_MAX_CHARS:
        return sanitized
    return sanitized[: HEALTH_ERROR_MAX_CHARS - 3] + "..."


ACTIVE_TASK_STATUSES = {
    "queued",
    "uploaded",
    "rendering_pages",
    "rendered",
    "detecting_regions",
    "regions_detected",
    "cropping_regions",
    "regions_cropped",
    "extracting_full_page_elements",
    "full_page_elements_skipped",
    "extracting_region_elements",
    "region_elements_skipped",
    "merging_elements",
    "saving_elements",
    "comparing_elements",
    "saving_diffs",
}


class AiProfileService:
    def __init__(
        self,
        db: Session,
        settings: Settings | None = None,
        key_path: Path | None = None,
    ):
        self.db = db
        self.settings = settings or get_settings()
        self.key_path = key_path or self.settings.get_storage_path("config") / "ai-config.key"

    def create_profile(
        self,
        name: str,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int,
        max_retries: int,
        priority: int = 100,
    ) -> AiProfile:
        has_active = self.db.query(AiProfile).filter(AiProfile.is_active.is_(True)).first() is not None
        profile = AiProfile(
            name=name.strip(),
            base_url=base_url.strip(),
            api_key_encrypted=self._fernet().encrypt(api_key.encode("utf-8")).decode("ascii"),
            model=model.strip(),
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            priority=priority,
            is_active=not has_active,
        )
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def ensure_default_profile(self) -> AiProfile:
        active = self.get_active_profile()
        if active:
            return active
        existing = self.db.query(AiProfile).filter(AiProfile.is_enabled.is_(True)).order_by(AiProfile.id).first()
        if existing:
            existing.is_active = True
            self.db.commit()
            self.db.refresh(existing)
            return existing
        return self.create_profile(
            "默认配置",
            self.settings.AI_BASE_URL,
            self.settings.AI_API_KEY,
            self.settings.AI_MODEL,
            self.settings.AI_TIMEOUT_SECONDS,
            self.settings.AI_MAX_RETRIES,
        )

    def get_active_profile(self) -> AiProfile | None:
        return self.db.query(AiProfile).filter(
            AiProfile.is_active.is_(True), AiProfile.is_enabled.is_(True)
        ).first()

    def list_profiles(self) -> list[AiProfile]:
        return self.db.query(AiProfile).filter(
            AiProfile.is_enabled.is_(True)
        ).order_by(AiProfile.priority, AiProfile.created_at, AiProfile.id).all()

    def update_profile(self, profile_id: int, **changes) -> AiProfile:
        profile = self._get_enabled(profile_id)
        for field in ["name", "base_url", "model", "timeout_seconds", "max_retries", "priority"]:
            value = changes.get(field)
            if value is not None:
                setattr(profile, field, value.strip() if isinstance(value, str) else value)
        api_key = changes.get("api_key")
        if api_key:
            profile.api_key_encrypted = self._fernet().encrypt(api_key.encode("utf-8")).decode("ascii")
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def disable_profile(self, profile_id: int) -> None:
        profile = self._get_enabled(profile_id)
        if profile.is_active:
            raise ValueError("当前生效的 AI 配置不能停用")
        if profile.is_pending:
            raise ValueError("待生效的 AI 配置不能停用")
        profile.is_enabled = False
        self.db.commit()

    def decrypt_api_key(self, profile: AiProfile) -> str:
        return self._fernet().decrypt(profile.api_key_encrypted.encode("ascii")).decode("utf-8")

    def to_public_dict(self, profile: AiProfile) -> dict:
        return {
            "id": profile.id,
            "name": profile.name,
            "base_url": profile.base_url,
            "model": profile.model,
            "timeout_seconds": profile.timeout_seconds,
            "max_retries": profile.max_retries,
            "has_api_key": bool(profile.api_key_encrypted),
            "is_active": profile.is_active,
            "is_pending": profile.is_pending,
            "is_enabled": profile.is_enabled,
            "priority": profile.priority if profile.priority is not None else 100,
            "health_status": self._effective_health_status(profile),
            "cooldown_until": profile.cooldown_until.isoformat() if profile.cooldown_until else None,
            # 写入时已脱敏；读取时再脱敏一次，防止历史行把密钥带到前端。
            "last_health_error": summarize_health_error(profile.last_health_error),
            "last_health_checked_at": (
                profile.last_health_checked_at.isoformat() if profile.last_health_checked_at else None
            ),
        }

    def request_activation(self, profile_id: int) -> str:
        profile = self._get_enabled(profile_id)
        if self._has_active_tasks():
            self.db.query(AiProfile).update({AiProfile.is_pending: False})
            profile.is_pending = True
            self.db.commit()
            return "pending"
        self._activate(profile)
        return "active"

    def apply_pending_if_idle(self) -> bool:
        if self._has_active_tasks():
            return False
        pending = self.db.query(AiProfile).filter(
            AiProfile.is_pending.is_(True), AiProfile.is_enabled.is_(True)
        ).first()
        if not pending:
            return False
        self._activate(pending)
        return True

    # ─── 自动故障切换 ───
    def has_real_config(self, profile: AiProfile) -> bool:
        """配置是否指向真实可用的服务端点（而不是占位样例值）。

        密钥解密失败视为"配置错误"而不是"没有配置"：调用方应通过
        build_provider_candidates() 让这类配置在健康状态里留下痕迹，不要静默跳过。
        """
        try:
            api_key = self.decrypt_api_key(profile)
        except Exception:
            return False
        return self._is_real_endpoint(profile.base_url, api_key, profile.model)

    @staticmethod
    def _is_real_endpoint(base_url: str | None, api_key: str | None, model: str | None) -> bool:
        return all([
            base_url and base_url.strip() and base_url.strip() != "https://example.com/v1",
            api_key and api_key.strip() and api_key.strip() != "replace-with-real-key",
            model and model.strip() and model.strip() != "replace-with-vision-model",
        ])

    def build_provider_candidates(
        self, task: CompareTask | None, *, preferred_profile_id: int | None = None
    ) -> list[ProviderCandidate]:
        """构建按优先级排序的候选链。

        排序键：先健康后冷却 → 本次运行已成功过的配置 → 任务绑定的配置 → priority 小的优先
        → created_at → id。
        冷却中的配置只作为最后兜底，因此后续阶段不会反复先打刚刚失败的那套配置；
        cooldown 到期后它自动回到正常序列，形成半开探测。
        preferred_profile_id 让同一次运行的后续阶段继续用已经切换成功的后备配置。

        Mock 只在系统完全没有任何真实配置时出现，且此时候选链里不会有真实配置——
        真实配置调用失败绝不会退化到 Mock，避免产出假的生产结果。

        API Key 在这里（主线程）解密并捕获进闭包，工作线程内的 factory 不再触碰数据库会话。
        """
        now = datetime.datetime.now()
        bound_id = task.ai_profile_id if task is not None else None

        if self.settings.AI_ENABLE_AUTO_FAILOVER:
            profiles = self.db.query(AiProfile).filter(AiProfile.is_enabled.is_(True)).all()
            # 任务绑定的配置即使被停用也要尝试，保持与旧行为一致。
            if bound_id is not None and not any(p.id == bound_id for p in profiles):
                bound = self.db.query(AiProfile).filter(AiProfile.id == bound_id).first()
                if bound is not None:
                    profiles.append(bound)
        elif bound_id is not None:
            profiles = self.db.query(AiProfile).filter(AiProfile.id == bound_id).all()
        else:
            profiles = []
            active = self.get_active_profile()
            if active is not None:
                profiles = [active]

        usable: list[AiProfile] = []
        broken: dict[int, str] = {}
        for profile in profiles:
            try:
                api_key = self.decrypt_api_key(profile)
            except Exception as exc:
                # 不静默跳过：记下来，让健康状态和设置页能显示"配置错误"。
                broken[profile.id] = f"API Key 解密失败: {type(exc).__name__}"
                continue
            if self._is_real_endpoint(profile.base_url, api_key, profile.model):
                usable.append(profile)
        if broken:
            self._mark_profiles_broken(broken)

        usable.sort(
            key=lambda p: (
                1 if (p.cooldown_until and p.cooldown_until > now) else 0,
                0 if (preferred_profile_id is not None and p.id == preferred_profile_id) else 1,
                0 if p.id == bound_id else 1,
                p.priority if p.priority is not None else 100,
                p.created_at or now,
                p.id,
            )
        )
        candidates = [self._candidate_from_profile(p) for p in usable]

        # .env 全局配置作为最后一个真实候选；与数据库里等价的端点重复时不再重试同一个目标。
        if self.settings.has_real_ai_config:
            env_key = self._endpoint_key(
                self.settings.AI_BASE_URL, self.settings.AI_API_KEY, self.settings.AI_MODEL
            )
            db_keys = {
                self._endpoint_key(p.base_url, self._safe_api_key(p), p.model) for p in usable
            }
            if env_key not in db_keys:
                candidates.append(
                    ProviderCandidate(
                        profile_id=None,
                        name=".env 全局配置",
                        model=self.settings.AI_MODEL,
                        factory=self._env_provider_factory(),
                    )
                )

        if not candidates:
            # 系统完全没有真实 AI 配置：保留原有开发期降级行为。
            candidates.append(
                ProviderCandidate(
                    profile_id=None,
                    name="Mock 模拟配置",
                    model="mock",
                    factory=self._mock_provider_factory(),
                )
            )
        return candidates

    def _endpoint_key(self, base_url: str | None, api_key: str | None, model: str | None) -> tuple:
        return (
            self._normalized_endpoint(base_url),
            (api_key or "").strip(),
            (model or "").strip(),
        )

    @staticmethod
    def _normalized_endpoint(base_url: str | None) -> str:
        url = (base_url or "").strip().rstrip("/")
        if url.endswith("/chat/completions"):
            url = url[: -len("/chat/completions")]
        return url

    def _safe_api_key(self, profile: AiProfile) -> str:
        try:
            return self.decrypt_api_key(profile)
        except Exception:
            return ""

    def mark_profile_unhealthy(self, profile_id: int, error: str) -> None:
        cooldown_seconds = self.settings.AI_FAILOVER_COOLDOWN_SECONDS
        now = datetime.datetime.now()
        self._update_health(
            profile_id,
            {
                AiProfile.health_status: "unhealthy",
                AiProfile.cooldown_until: now + datetime.timedelta(seconds=cooldown_seconds),
                AiProfile.last_health_error: summarize_health_error(error),
                AiProfile.last_health_checked_at: now,
            },
        )

    def mark_profile_healthy(self, profile_id: int) -> None:
        self._update_health(
            profile_id,
            {
                AiProfile.health_status: "healthy",
                AiProfile.cooldown_until: None,
                AiProfile.last_health_error: None,
                AiProfile.last_health_checked_at: datetime.datetime.now(),
            },
        )

    def apply_failover_outcome(self, outcome) -> None:
        """把一个阶段累积的健康状态变更一次性落库（主线程调用）。

        成功配置只在这里更新一次，不会为每一次并发 AI 请求都 commit。
        """
        failed_profiles = getattr(outcome, "failed_profiles", None) or {}
        succeeded = getattr(outcome, "succeeded_profile_ids", None) or []
        for profile_id, error in failed_profiles.items():
            if profile_id is None:
                continue
            self.mark_profile_unhealthy(profile_id, error)
        for profile_id in succeeded:
            if profile_id is None or profile_id in failed_profiles:
                # 同一阶段里既成功又失败：以失败与冷却为准，避免立刻清掉刚设的 cooldown。
                continue
            self.mark_profile_healthy(profile_id)

    def _mark_profiles_broken(self, errors: dict[int, str]) -> None:
        now = datetime.datetime.now()
        for profile_id, error in errors.items():
            self._update_health(
                profile_id,
                {
                    AiProfile.health_status: "unhealthy",
                    AiProfile.last_health_error: summarize_health_error(error),
                    AiProfile.last_health_checked_at: now,
                },
            )

    def _update_health(self, profile_id: int, values: dict) -> None:
        try:
            self.db.query(AiProfile).filter(AiProfile.id == profile_id).update(values)
            self.db.commit()
        except Exception:
            self._safe_rollback()

    def _candidate_from_profile(self, profile: AiProfile) -> ProviderCandidate:
        base_url = profile.base_url
        api_key = self.decrypt_api_key(profile)
        model = profile.model
        timeout_seconds = profile.timeout_seconds
        max_retries = profile.max_retries

        def factory():
            from app.ai.openai_provider import OpenAICompatibleProvider
            return OpenAICompatibleProvider(
                base_url=base_url,
                api_key=api_key,
                model=model,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
            )

        return ProviderCandidate(
            profile_id=profile.id, name=profile.name, model=model, factory=factory
        )

    @staticmethod
    def _env_provider_factory():
        def factory():
            from app.ai.openai_provider import OpenAICompatibleProvider
            return OpenAICompatibleProvider()
        return factory

    @staticmethod
    def _mock_provider_factory():
        def factory():
            from app.ai.mock_provider import MockVisionProvider
            return MockVisionProvider()
        return factory

    def _effective_health_status(self, profile: AiProfile) -> str:
        if profile.cooldown_until and profile.cooldown_until > datetime.datetime.now():
            return "cooling_down"
        return profile.health_status or "unknown"

    def _safe_rollback(self) -> None:
        rollback = getattr(self.db, "rollback", None)
        if callable(rollback):
            try:
                rollback()
            except Exception:
                pass

    def _activate(self, profile: AiProfile) -> None:
        self.db.query(AiProfile).update({AiProfile.is_active: False, AiProfile.is_pending: False})
        profile.is_active = True
        profile.is_pending = False
        self.db.commit()

    def _get_enabled(self, profile_id: int) -> AiProfile:
        profile = self.db.query(AiProfile).filter(
            AiProfile.id == profile_id, AiProfile.is_enabled.is_(True)
        ).first()
        if not profile:
            raise ValueError("AI 配置不存在或已停用")
        return profile

    def _has_active_tasks(self) -> bool:
        return self.db.query(CompareTask).filter(CompareTask.status.in_(ACTIVE_TASK_STATUSES)).first() is not None

    def _fernet(self) -> Fernet:
        if not self.key_path.exists():
            self.key_path.parent.mkdir(parents=True, exist_ok=True)
            self.key_path.write_bytes(Fernet.generate_key())
        return Fernet(self.key_path.read_bytes().strip())
