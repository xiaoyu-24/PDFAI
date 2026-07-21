from __future__ import annotations

from pathlib import Path

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.models import AiProfile, CompareTask


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
    ) -> AiProfile:
        has_active = self.db.query(AiProfile).filter(AiProfile.is_active.is_(True)).first() is not None
        profile = AiProfile(
            name=name.strip(),
            base_url=base_url.strip(),
            api_key_encrypted=self._fernet().encrypt(api_key.encode("utf-8")).decode("ascii"),
            model=model.strip(),
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
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
        ).order_by(AiProfile.created_at, AiProfile.id).all()

    def update_profile(self, profile_id: int, **changes) -> AiProfile:
        profile = self._get_enabled(profile_id)
        for field in ["name", "base_url", "model", "timeout_seconds", "max_retries"]:
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
