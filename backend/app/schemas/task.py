from __future__ import annotations

from pydantic import BaseModel


class TaskResponse(BaseModel):
    id: int
    task_no: str
    base_file_id: int
    compare_file_id: int
    status: str
    progress: int
    summary: str | None = None
    created_at: str
    started_at: str | None = None
    updated_at: str | None = None
    completed_at: str | None = None
    failed_stage: str | None = None
    last_error: str | None = None
    ai_call_count: int = 0
    ai_total_duration_ms: int = 0
    last_ai_error: str | None = None
    base_file_name: str | None = None
    compare_file_name: str | None = None
    base_page_count: int | None = None
    compare_page_count: int | None = None
    current_step_label: str | None = None
    current_step_hint: str | None = None
    failed_stage: str | None = None
    error_hint: str | None = None
    recognition_strategy: dict | None = None

    model_config = {"from_attributes": True}


class TaskListItemResponse(TaskResponse):
    diff_count: int = 0
    high_risk_count: int = 0
    pending_review_count: int = 0


class TaskListResponse(BaseModel):
    items: list[TaskListItemResponse]
    total: int
    limit: int
    offset: int


class ReportTableRowResponse(BaseModel):
    section: str
    section_index: int
    category: str
    risk_label: str
    base_content: str
    compare_content: str
    conclusion: str
    impact: str
    suggestion: str
    evidence: str
    confidence: float | None = None
    manual_check_label: str
    diff_id: int
    review_status: str
    review_status_label: str


class ReportTableResponse(BaseModel):
    task_id: int
    task_no: str
    columns: list[str]
    rows: list[ReportTableRowResponse]


class DiffSummaryResponse(BaseModel):
    total_count: int
    risk_counts: dict[str, int]
    review_counts: dict[str, int]


class DrawingElementResponse(BaseModel):
    id: int
    file_id: int
    page_id: int | None = None
    region_id: int | None = None
    extraction_run_id: int | None = None
    category: str
    element_name: str
    raw_value: str | None = None
    normalized_value: str | None = None
    unit: str | None = None
    importance: str
    confidence: float | None = None
    need_manual_check: bool = False
    source_image_path: str | None = None
    region_desc: str | None = None
    extra_json: dict | None = None
    created_at: str

    model_config = {"from_attributes": True}


class CompareDiffResponse(BaseModel):
    id: int
    compare_task_id: int
    match_id: int | None = None
    base_element_id: int | None = None
    compare_element_id: int | None = None
    risk_level: str
    diff_category: str
    base_content: str | None = None
    compare_content: str | None = None
    diff_summary: str | None = None
    impact: str | None = None
    suggestion: str | None = None
    confidence: float | None = None
    need_manual_check: bool = False
    review_status: str
    reviewer_comment: str | None = None
    created_at: str

    model_config = {"from_attributes": True}
