from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings


router = APIRouter(prefix="/api/settings", tags=["settings"])


class RecognitionStrategyResponse(BaseModel):
    full_page_enabled: bool
    region_enabled: bool
    pdf_dpi: int
    image_max_edge: int
    jpeg_quality: int


class SettingsResponse(BaseModel):
    app_env: str
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
