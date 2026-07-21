from __future__ import annotations

from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, ForeignKey, JSON, Enum, Boolean, Index, UniqueConstraint, func,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


class PdfFile(Base):
    __tablename__ = "pdf_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    original_name = Column(String(512), nullable=False)
    stored_path = Column(String(1024), nullable=False)
    file_hash = Column(String(128), nullable=False)
    page_count = Column(Integer, nullable=False, default=0)
    file_role = Column(Enum("base", "compare", name="file_role_enum"), nullable=False)
    file_type = Column(String(16), nullable=False, default="pdf", server_default="pdf")
    status = Column(String(64), nullable=False, default="uploaded")
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    pages = relationship("PdfPage", back_populates="file", cascade="all, delete-orphan")
    regions = relationship("PageRegion", back_populates="file", cascade="all, delete-orphan")
    extraction_runs = relationship("AiExtractionRun", back_populates="file", cascade="all, delete-orphan")
    elements = relationship("DrawingElement", back_populates="file", cascade="all, delete-orphan")


class PdfPage(Base):
    __tablename__ = "pdf_pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey("pdf_files.id", ondelete="CASCADE"), nullable=False)
    page_no = Column(Integer, nullable=False)
    image_path = Column(String(1024), nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    dpi = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    file = relationship("PdfFile", back_populates="pages")
    regions = relationship("PageRegion", back_populates="page", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_pdf_pages_file_id", "file_id"),
    )


class PageRegion(Base):
    __tablename__ = "page_regions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey("pdf_files.id", ondelete="CASCADE"), nullable=False)
    page_id = Column(Integer, ForeignKey("pdf_pages.id", ondelete="CASCADE"), nullable=False)
    page_no = Column(Integer, nullable=False)
    region_type = Column(String(128), nullable=False)
    region_name = Column(String(512), nullable=False)
    crop_image_path = Column(String(1024), nullable=True)
    bbox_json = Column(JSON, nullable=False)
    ai_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    file = relationship("PdfFile", back_populates="regions")
    page = relationship("PdfPage", back_populates="regions")
    extraction_runs = relationship("AiExtractionRun", back_populates="region", cascade="all, delete-orphan")
    elements = relationship("DrawingElement", back_populates="region")

    __table_args__ = (
        Index("idx_page_regions_file_id", "file_id"),
        Index("idx_page_regions_page_id", "page_id"),
    )


class AiExtractionRun(Base):
    __tablename__ = "ai_extraction_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey("pdf_files.id", ondelete="CASCADE"), nullable=False)
    page_id = Column(Integer, ForeignKey("pdf_pages.id", ondelete="SET NULL"), nullable=True)
    region_id = Column(Integer, ForeignKey("page_regions.id", ondelete="SET NULL"), nullable=True)
    model_name = Column(String(256), nullable=False)
    prompt_version = Column(String(64), nullable=False, default="v1")
    input_type = Column(Enum("full_page", "region", "merge", name="input_type_enum"), nullable=False)
    raw_output_path = Column(String(1024), nullable=True)
    status = Column(String(64), nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    attempt_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    file = relationship("PdfFile", back_populates="extraction_runs")
    page = relationship("PdfPage")
    region = relationship("PageRegion", back_populates="extraction_runs")
    elements = relationship("DrawingElement", back_populates="extraction_run")

    __table_args__ = (
        Index("idx_ai_extraction_runs_file_id", "file_id"),
    )


class DrawingElement(Base):
    __tablename__ = "drawing_elements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey("pdf_files.id", ondelete="CASCADE"), nullable=False)
    page_id = Column(Integer, ForeignKey("pdf_pages.id", ondelete="SET NULL"), nullable=True)
    region_id = Column(Integer, ForeignKey("page_regions.id", ondelete="SET NULL"), nullable=True)
    extraction_run_id = Column(Integer, ForeignKey("ai_extraction_runs.id", ondelete="SET NULL"), nullable=True)
    category = Column(String(128), nullable=False)
    element_name = Column(String(512), nullable=False)
    raw_value = Column(Text, nullable=True)
    normalized_value = Column(String(1024), nullable=True)
    unit = Column(String(64), nullable=True)
    importance = Column(Enum("high", "medium", "low", name="importance_enum"), nullable=False, default="medium")
    confidence = Column(Float, nullable=True)
    need_manual_check = Column(Boolean, nullable=False, default=False)
    source_image_path = Column(String(1024), nullable=True)
    region_desc = Column(Text, nullable=True)
    extra_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    file = relationship("PdfFile", back_populates="elements")
    page = relationship("PdfPage")
    region = relationship("PageRegion", back_populates="elements")
    extraction_run = relationship("AiExtractionRun", back_populates="elements")
    base_matches = relationship(
        "ElementMatch", foreign_keys="ElementMatch.base_element_id", back_populates="base_element"
    )
    compare_matches = relationship(
        "ElementMatch", foreign_keys="ElementMatch.compare_element_id", back_populates="compare_element"
    )

    __table_args__ = (
        Index("idx_drawing_elements_file_id", "file_id"),
        Index("idx_drawing_elements_file_category", "file_id", "category"),
    )


class CompareTask(Base):
    __tablename__ = "compare_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_no = Column(String(64), nullable=False, unique=True)
    base_file_id = Column(Integer, ForeignKey("pdf_files.id", ondelete="CASCADE"), nullable=False)
    compare_file_id = Column(Integer, ForeignKey("pdf_files.id", ondelete="CASCADE"), nullable=False)
    ai_profile_id = Column(Integer, ForeignKey("ai_profiles.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(64), nullable=False, default="uploaded")
    progress = Column(Integer, nullable=False, default=0)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    started_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True, server_default=func.now(), onupdate=func.now())
    failed_stage = Column(String(64), nullable=True)
    last_error = Column(Text, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    base_file = relationship("PdfFile", foreign_keys=[base_file_id])
    compare_file = relationship("PdfFile", foreign_keys=[compare_file_id])
    ai_profile = relationship("AiProfile", back_populates="tasks")
    matches = relationship("ElementMatch", back_populates="compare_task", cascade="all, delete-orphan")
    diffs = relationship("CompareDiff", back_populates="compare_task", cascade="all, delete-orphan")
    logs = relationship("TaskLog", back_populates="task", cascade="all, delete-orphan")


class AiProfile(Base):
    __tablename__ = "ai_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, unique=True)
    base_url = Column(String(1024), nullable=False)
    api_key_encrypted = Column(Text, nullable=False)
    model = Column(String(256), nullable=False)
    timeout_seconds = Column(Integer, nullable=False, default=120)
    max_retries = Column(Integer, nullable=False, default=2)
    is_active = Column(Boolean, nullable=False, default=False)
    is_pending = Column(Boolean, nullable=False, default=False)
    is_enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    tasks = relationship("CompareTask", back_populates="ai_profile")


class ElementMatch(Base):
    __tablename__ = "element_matches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    compare_task_id = Column(Integer, ForeignKey("compare_tasks.id", ondelete="CASCADE"), nullable=False)
    base_element_id = Column(Integer, ForeignKey("drawing_elements.id", ondelete="SET NULL"), nullable=True)
    compare_element_id = Column(Integer, ForeignKey("drawing_elements.id", ondelete="SET NULL"), nullable=True)
    match_type = Column(
        Enum("exact", "semantic", "suspicious", "base_missing", "compare_missing", name="match_type_enum"),
        nullable=False,
    )
    match_reason = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    compare_task = relationship("CompareTask", back_populates="matches")
    base_element = relationship("DrawingElement", foreign_keys=[base_element_id], back_populates="base_matches")
    compare_element = relationship("DrawingElement", foreign_keys=[compare_element_id], back_populates="compare_matches")
    diffs = relationship("CompareDiff", back_populates="match", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_element_matches_task_id", "compare_task_id"),
    )


class CompareDiff(Base):
    __tablename__ = "compare_diffs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    compare_task_id = Column(Integer, ForeignKey("compare_tasks.id", ondelete="CASCADE"), nullable=False)
    match_id = Column(Integer, ForeignKey("element_matches.id", ondelete="SET NULL"), nullable=True)
    base_element_id = Column(Integer, ForeignKey("drawing_elements.id", ondelete="SET NULL"), nullable=True)
    compare_element_id = Column(Integer, ForeignKey("drawing_elements.id", ondelete="SET NULL"), nullable=True)
    risk_level = Column(
        Enum("high", "medium", "low", "manual_check", name="risk_level_enum"), nullable=False, default="manual_check"
    )
    diff_category = Column(String(128), nullable=False)
    base_content = Column(Text, nullable=True)
    compare_content = Column(Text, nullable=True)
    diff_summary = Column(Text, nullable=True)
    impact = Column(Text, nullable=True)
    suggestion = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    need_manual_check = Column(Boolean, nullable=False, default=False)
    review_status = Column(
        Enum("pending", "confirmed", "ignored", "misjudged", "modified", name="review_status_enum"),
        nullable=False,
        default="pending",
    )
    reviewer_comment = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    compare_task = relationship("CompareTask", back_populates="diffs")
    match = relationship("ElementMatch", back_populates="diffs")
    base_element = relationship("DrawingElement", foreign_keys=[base_element_id])
    compare_element = relationship("DrawingElement", foreign_keys=[compare_element_id])
    review_logs = relationship("ReviewLog", back_populates="compare_diff", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_compare_diffs_task_id", "compare_task_id"),
        Index("idx_compare_diffs_task_risk", "compare_task_id", "risk_level"),
    )


class ReviewLog(Base):
    __tablename__ = "review_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    compare_diff_id = Column(Integer, ForeignKey("compare_diffs.id", ondelete="CASCADE"), nullable=False)
    action = Column(
        Enum("confirm", "ignore", "modify", "mark_misjudged", name="review_action_enum"), nullable=False
    )
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    comment = Column(Text, nullable=True)
    reviewer = Column(String(256), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    compare_diff = relationship("CompareDiff", back_populates="review_logs")

    __table_args__ = (
        Index("idx_review_logs_diff_id", "compare_diff_id"),
    )


class TaskLog(Base):
    __tablename__ = "task_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("compare_tasks.id", ondelete="CASCADE"), nullable=False)
    run_id = Column(String(64), nullable=False)
    stage = Column(String(64), nullable=False)
    component = Column(String(64), nullable=False, default="task")
    event_type = Column(String(32), nullable=False)
    level = Column(String(16), nullable=False, default="info")
    status = Column(String(32), nullable=False)
    error_category = Column(String(32), nullable=False, default="none")
    error_code = Column(String(64), nullable=True)
    message = Column(Text, nullable=False)
    error_detail = Column(Text, nullable=True)
    attempt_no = Column(Integer, nullable=True)
    max_attempts = Column(Integer, nullable=True)
    timeout_ms = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    is_degraded = Column(Boolean, nullable=False, default=False)
    fallback_action = Column(String(128), nullable=True)
    metadata_json = Column(JSON, nullable=True)
    is_timeline = Column(Boolean, nullable=False, default=False, server_default="0")
    retention_until = Column(DateTime, nullable=True)
    detail_available_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    task = relationship("CompareTask", back_populates="logs")

    __table_args__ = (
        Index("idx_task_logs_task_created", "task_id", "created_at"),
        Index("idx_task_logs_level_created", "level", "created_at"),
        Index("idx_task_logs_category_created", "error_category", "created_at"),
        Index("idx_task_logs_stage_status", "stage", "status"),
        Index("idx_task_logs_run_created", "run_id", "created_at"),
        Index("idx_task_logs_timeline", "task_id", "is_timeline", "created_at"),
        Index("idx_task_logs_retention", "level", "retention_until", "created_at"),
    )


class TaskLogFile(Base):
    __tablename__ = "task_log_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("compare_tasks.id", ondelete="CASCADE"), nullable=False)
    run_id = Column(String(64), nullable=False)
    relative_path = Column(String(512), nullable=False)
    status = Column(String(32), nullable=False, default="writing")
    line_count = Column(Integer, nullable=False, default=0)
    size_bytes = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    task = relationship("CompareTask")

    __table_args__ = (
        Index("idx_task_log_files_task_id", "task_id"),
        Index("idx_task_log_files_expires", "expires_at", "status"),
        UniqueConstraint("task_id", "run_id", name="uq_task_log_files_task_run"),
    )
