from __future__ import annotations

from pathlib import Path
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "development"
    DATABASE_URL: str = "mysql+pymysql://pdfai:password@localhost:3306/pdfai"
    TEST_DATABASE_URL: str = "sqlite:///./test_pdfai.db"
    STORAGE_ROOT: str = "../storage"

    PDF_RENDER_DPI: int = Field(default=300, ge=72, le=1200)
    PDF_RENDER_FORMAT: str = "png"
    CROP_PADDING_RATIO: float = Field(default=0.06, ge=0.0, le=0.5)

    AI_BASE_URL: str = "https://example.com/v1"
    AI_API_KEY: str = "replace-with-real-key"
    AI_MODEL: str = "replace-with-vision-model"
    AI_TIMEOUT_SECONDS: int = Field(default=120, ge=10)
    AI_MAX_RETRIES: int = Field(default=2, ge=0, le=10)
    AI_MAX_CONCURRENT_CALLS_PER_TASK: int = Field(default=2, ge=1, le=8)
    AI_ENABLE_FULL_PAGE_EXTRACTION: bool = True
    AI_ENABLE_REGION_EXTRACTION: bool = False
    AI_IMAGE_MAX_EDGE: int = Field(default=1600, ge=512, le=8000)
    AI_IMAGE_JPEG_QUALITY: int = Field(default=75, ge=40, le=95)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def has_real_ai_config(self) -> bool:
        return all(
            [
                self.AI_BASE_URL.strip()
                and self.AI_BASE_URL.strip() != "https://example.com/v1",
                self.AI_API_KEY.strip()
                and self.AI_API_KEY.strip() != "replace-with-real-key",
                self.AI_MODEL.strip()
                and self.AI_MODEL.strip() != "replace-with-vision-model",
            ]
        )

    @property
    def storage_root_path(self) -> Path:
        base = Path(self.STORAGE_ROOT)
        if not base.is_absolute():
            base = Path(__file__).parent.parent.parent / base
        return base.resolve()

    def get_storage_path(self, subdir: str) -> Path:
        return self.storage_root_path / subdir


@lru_cache()
def get_settings() -> Settings:
    return Settings()
