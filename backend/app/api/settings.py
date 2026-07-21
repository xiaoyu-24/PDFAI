from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.services.ai_profile_service import AiProfileService


router = APIRouter(prefix="/api/settings", tags=["settings"])


class RecognitionStrategyResponse(BaseModel):
    full_page_enabled: bool
    region_enabled: bool
    pdf_dpi: int
    image_max_edge: int
    jpeg_quality: int


class SettingsResponse(BaseModel):
    app_env: str
    task_max_workers: int
    ai_base_url: str
    ai_model: str
    has_ai_api_key: bool
    ai_timeout_seconds: int
    ai_max_retries: int
    storage_root: str
    recognition_strategy: RecognitionStrategyResponse


class UpdateSettingsRequest(BaseModel):
    ai_base_url: Optional[str] = None
    ai_model: Optional[str] = None
    ai_api_key: Optional[str] = None
    ai_timeout_seconds: Optional[int] = Field(default=None, ge=10)
    ai_max_retries: Optional[int] = Field(default=None, ge=0, le=10)
    pdf_render_dpi: Optional[int] = Field(default=None, ge=72, le=1200)
    ai_enable_full_page_extraction: Optional[bool] = None
    ai_enable_region_extraction: Optional[bool] = None
    ai_image_max_edge: Optional[int] = Field(default=None, ge=512, le=8000)
    ai_image_jpeg_quality: Optional[int] = Field(default=None, ge=40, le=95)


class AiProfileCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    base_url: str = Field(min_length=1, max_length=1024)
    api_key: str = Field(min_length=1)
    model: str = Field(min_length=1, max_length=256)
    timeout_seconds: int = Field(default=120, ge=10)
    max_retries: int = Field(default=2, ge=0, le=10)


class AiProfileUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    base_url: Optional[str] = Field(default=None, min_length=1, max_length=1024)
    api_key: Optional[str] = None
    model: Optional[str] = Field(default=None, min_length=1, max_length=256)
    timeout_seconds: Optional[int] = Field(default=None, ge=10)
    max_retries: Optional[int] = Field(default=None, ge=0, le=10)


class AiProfileResponse(BaseModel):
    id: int
    name: str
    base_url: str
    model: str
    timeout_seconds: int
    max_retries: int
    has_api_key: bool
    is_active: bool
    is_pending: bool
    is_enabled: bool


class AiProfileListResponse(BaseModel):
    items: list[AiProfileResponse]
    active_profile_id: Optional[int]
    pending_profile_id: Optional[int]


class AiProfileActivationResponse(BaseModel):
    activation_status: str
    profile: AiProfileResponse


def _update_env_file(updates: dict[str, str]) -> None:
    env_path = Path(__file__).parent.parent.parent / ".env"
    if not env_path.exists():
        raise HTTPException(status_code=500, detail=".env 文件不存在")

    lines = env_path.read_text(encoding="utf-8").splitlines()
    updated_keys = set()
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue

        if "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                updated_keys.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    for key, value in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


@router.get("", response_model=SettingsResponse)
def get_public_settings() -> SettingsResponse:
    settings = get_settings()
    return SettingsResponse(
        app_env=settings.APP_ENV,
        task_max_workers=settings.TASK_MAX_WORKERS,
        ai_base_url=settings.AI_BASE_URL,
        ai_model=settings.AI_MODEL,
        has_ai_api_key=bool(settings.AI_API_KEY.strip()),
        ai_timeout_seconds=settings.AI_TIMEOUT_SECONDS,
        ai_max_retries=settings.AI_MAX_RETRIES,
        storage_root=str(settings.storage_root_path),
        recognition_strategy=RecognitionStrategyResponse(
            full_page_enabled=settings.AI_ENABLE_FULL_PAGE_EXTRACTION,
            region_enabled=settings.AI_ENABLE_REGION_EXTRACTION,
            pdf_dpi=settings.PDF_RENDER_DPI,
            image_max_edge=settings.AI_IMAGE_MAX_EDGE,
            jpeg_quality=settings.AI_IMAGE_JPEG_QUALITY,
        ),
    )


@router.put("", response_model=SettingsResponse)
def update_settings(request: UpdateSettingsRequest) -> SettingsResponse:
    updates = {}

    if request.ai_base_url is not None:
        updates["AI_BASE_URL"] = request.ai_base_url
    if request.ai_model is not None:
        updates["AI_MODEL"] = request.ai_model
    if request.ai_api_key is not None:
        updates["AI_API_KEY"] = request.ai_api_key
    if request.ai_timeout_seconds is not None:
        updates["AI_TIMEOUT_SECONDS"] = str(request.ai_timeout_seconds)
    if request.ai_max_retries is not None:
        updates["AI_MAX_RETRIES"] = str(request.ai_max_retries)
    if request.pdf_render_dpi is not None:
        updates["PDF_RENDER_DPI"] = str(request.pdf_render_dpi)
    if request.ai_enable_full_page_extraction is not None:
        updates["AI_ENABLE_FULL_PAGE_EXTRACTION"] = str(request.ai_enable_full_page_extraction).lower()
    if request.ai_enable_region_extraction is not None:
        updates["AI_ENABLE_REGION_EXTRACTION"] = str(request.ai_enable_region_extraction).lower()
    if request.ai_image_max_edge is not None:
        updates["AI_IMAGE_MAX_EDGE"] = str(request.ai_image_max_edge)
    if request.ai_image_jpeg_quality is not None:
        updates["AI_IMAGE_JPEG_QUALITY"] = str(request.ai_image_jpeg_quality)

    if not updates:
        raise HTTPException(status_code=400, detail="没有提供要更新的设置")

    _update_env_file(updates)

    get_settings.cache_clear()
    settings = get_settings()

    return SettingsResponse(
        app_env=settings.APP_ENV,
        task_max_workers=settings.TASK_MAX_WORKERS,
        ai_base_url=settings.AI_BASE_URL,
        ai_model=settings.AI_MODEL,
        has_ai_api_key=bool(settings.AI_API_KEY.strip()),
        ai_timeout_seconds=settings.AI_TIMEOUT_SECONDS,
        ai_max_retries=settings.AI_MAX_RETRIES,
        storage_root=str(settings.storage_root_path),
        recognition_strategy=RecognitionStrategyResponse(
            full_page_enabled=settings.AI_ENABLE_FULL_PAGE_EXTRACTION,
            region_enabled=settings.AI_ENABLE_REGION_EXTRACTION,
            pdf_dpi=settings.PDF_RENDER_DPI,
            image_max_edge=settings.AI_IMAGE_MAX_EDGE,
            jpeg_quality=settings.AI_IMAGE_JPEG_QUALITY,
        ),
    )


@router.get("/ai-profiles", response_model=AiProfileListResponse)
def list_ai_profiles(db: Session = Depends(get_db)) -> AiProfileListResponse:
    service = AiProfileService(db)
    service.ensure_default_profile()
    items = [AiProfileResponse(**service.to_public_dict(profile)) for profile in service.list_profiles()]
    active = next((item.id for item in items if item.is_active), None)
    pending = next((item.id for item in items if item.is_pending), None)
    return AiProfileListResponse(items=items, active_profile_id=active, pending_profile_id=pending)


@router.post("/ai-profiles", response_model=AiProfileResponse, status_code=201)
def create_ai_profile(request: AiProfileCreateRequest, db: Session = Depends(get_db)) -> AiProfileResponse:
    service = AiProfileService(db)
    try:
        profile = service.create_profile(**request.model_dump())
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="AI 配置名称已存在") from exc
    return AiProfileResponse(**service.to_public_dict(profile))


@router.put("/ai-profiles/{profile_id}", response_model=AiProfileResponse)
def update_ai_profile(
    profile_id: int,
    request: AiProfileUpdateRequest,
    db: Session = Depends(get_db),
) -> AiProfileResponse:
    service = AiProfileService(db)
    try:
        profile = service.update_profile(profile_id, **request.model_dump(exclude_unset=True))
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="AI 配置名称已存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AiProfileResponse(**service.to_public_dict(profile))


@router.post("/ai-profiles/{profile_id}/activate", response_model=AiProfileActivationResponse)
def activate_ai_profile(profile_id: int, db: Session = Depends(get_db)) -> AiProfileActivationResponse:
    service = AiProfileService(db)
    try:
        activation_status = service.request_activation(profile_id)
        profile = service._get_enabled(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AiProfileActivationResponse(
        activation_status=activation_status,
        profile=AiProfileResponse(**service.to_public_dict(profile)),
    )


@router.delete("/ai-profiles/{profile_id}", status_code=204, response_class=Response)
def delete_ai_profile(profile_id: int, db: Session = Depends(get_db)) -> Response:
    try:
        AiProfileService(db).disable_profile(profile_id)
    except ValueError as exc:
        detail = str(exc)
        status_code = 409 if "不能停用" in detail else 404
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return Response(status_code=204)
