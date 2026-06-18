from __future__ import annotations

import datetime
import json
from urllib.parse import quote

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, object_session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.task import (
    TaskResponse,
    TaskListResponse,
    TaskListItemResponse,
    ReportTableResponse,
    DiffSummaryResponse,
    DrawingElementResponse,
    CompareDiffResponse,
)
from app.services.task_service import TaskService
from app.services.task_runner import TaskRunner
from app.services.report_service import REPORT_COLUMNS, ReportService
from app.models.models import AiExtractionRun, DrawingElement, CompareDiff, CompareTask, PdfFile


def _run_full_pipeline(task_id: int) -> None:
    from app.db.session import get_session_local
    from app.services.task_service import TaskControlInterrupt
    db = get_session_local()()
    task = None
    try:
        service = TaskService(db)
        task = service.get_task(task_id)
        if not task:
            return

        steps = _steps_for_status(task.status, service)
        for step in steps:
            db.refresh(task)
            if task.status in {"failed", "paused", "deleted"}:
                break
            step(task)
    except TaskControlInterrupt:
        pass
    except Exception as exc:
        if task is not None:
            task.status = "failed"
            task.summary = f"任务执行失败: {exc}"
            db.commit()
    finally:
        db.close()


router = APIRouter(prefix="/api/tasks", tags=["tasks"])
task_runner = TaskRunner(_run_full_pipeline, max_workers=3)

ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


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


def _steps_for_status(status: str, service: TaskService):
    all_steps = [
        service.render_pages,
        service.detect_regions,
        service.crop_regions,
        service.extract_full_page_elements,
        service.extract_region_elements,
        service.merge_elements,
        service.compare_elements,
    ]
    start_by_status = {
        "queued": 0,
        "uploaded": 0,
        "rendering_pages": 0,
        "rendered": 1,
        "detecting_regions": 1,
        "regions_detected": 2,
        "cropping_regions": 2,
        "regions_cropped": 3,
        "extracting_full_page_elements": 3,
        "full_page_elements_skipped": 4,
        "extracting_region_elements": 4,
        "region_elements_skipped": 5,
        "merging_elements": 5,
        "saving_elements": 5,
        "comparing_elements": 6,
        "saving_diffs": 6,
    }
    start_index = start_by_status.get(status, 0)
    return all_steps[start_index:]


def _recover_active_tasks() -> None:
    from app.db.session import get_session_local
    db = get_session_local()()
    try:
        try:
            tasks = db.query(CompareTask).filter(CompareTask.status.in_(ACTIVE_TASK_STATUSES)).all()
        except OperationalError as exc:
            if _is_missing_column_error(exc):
                raise RuntimeError(
                    "数据库表结构未升级，请在 backend 目录执行 alembic upgrade head 后重新启动后端。"
                ) from exc
            raise
        for task in tasks:
            task_runner.submit(task.id)
    finally:
        db.close()


def _is_missing_column_error(exc: OperationalError) -> bool:
    text = str(exc).lower()
    return "unknown column" in text or "no such column" in text


STEP_INFO = {
    "queued": ("任务已排队", "系统会在并发名额可用时自动开始处理，最多同时运行 3 个任务。"),
    "paused": ("任务已暂停", "任务已停止在当前阶段边界，可点击继续处理。"),
    "uploaded": ("文件已上传", "任务已创建，正在等待进入处理队列。"),
    "rendering_pages": ("正在转换 PDF 页面", "系统正在把 PDF 页面转换为图像，页数较多时会更久。"),
    "rendered": ("PDF 页面已转换", "页面图像已准备好，即将识别图纸区域。"),
    "detecting_regions": ("正在识别图纸区域", "系统正在定位标题栏、明细表和主要图纸区域。"),
    "regions_detected": ("图纸区域已识别", "系统已完成区域定位，即将裁剪关键区域。"),
    "cropping_regions": ("正在裁剪关键区域", "系统正在生成局部小图，用于更细的 AI 识别。"),
    "regions_cropped": ("关键区域已裁剪", "局部图像已准备好，即将提取图纸元素。"),
    "extracting_full_page_elements": ("正在识别整页元素", "系统正在调用视觉模型识别整页图纸内容。"),
    "full_page_elements_skipped": ("已跳过整页识别", "当前策略关闭了整页识别。"),
    "extracting_region_elements": ("正在识别区域元素", "系统正在调用视觉模型识别局部区域内容。"),
    "region_elements_skipped": ("已跳过区域识别", "当前策略关闭了区域小图识别。"),
    "merging_elements": ("正在合并识别结果", "系统正在整理来自不同区域的图纸元素。"),
    "saving_elements": ("正在保存元素", "系统正在保存识别出的图纸元素。"),
    "comparing_elements": ("正在生成差异", "系统正在比较基准图纸和对比图纸的元素。"),
    "saving_diffs": ("正在保存差异", "系统正在保存差异报告。"),
    "completed": ("任务已完成", "可以查看差异报告、元素清单或导出结果。"),
    "failed": ("任务失败", "请查看失败原因和建议动作。"),
}


def _error_hint(summary: str | None) -> str | None:
    if not summary:
        return None
    text = summary.lower()
    if "pdf" in text or "文件" in summary or "鏂囦欢" in summary:
        return "请重新上传有效 PDF 文件。"
    if "api" in text or "key" in text or "model" in text or "ai" in text:
        return "请检查系统设置中的 AI 配置和模型能力。"
    if "timeout" in text or "超时" in summary or "限流" in summary:
        return "模型调用可能超时或被限流，请稍后重试。"
    return "请复制错误信息并检查任务输入或系统配置。"


def _recognition_strategy(settings) -> dict:
    return {
        "full_page_enabled": settings.AI_ENABLE_FULL_PAGE_EXTRACTION,
        "region_enabled": settings.AI_ENABLE_REGION_EXTRACTION,
        "pdf_dpi": settings.PDF_RENDER_DPI,
        "image_max_edge": settings.AI_IMAGE_MAX_EDGE,
        "jpeg_quality": settings.AI_IMAGE_JPEG_QUALITY,
    }


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    base_file: UploadFile = File(...),
    compare_file: UploadFile = File(...),
    base_file_format: str = Form("pdf"),
    compare_file_format: str = Form("pdf"),
    db: Session = Depends(get_db),
):
    _validate_upload_format(base_file, base_file_format, "基准文件")
    _validate_upload_format(compare_file, compare_file_format, "对比文件")

    base_bytes = await base_file.read()
    compare_bytes = await compare_file.read()

    service = TaskService(db)
    task = service.create_task(
        base_pdf_bytes=base_bytes,
        base_filename=base_file.filename,
        compare_pdf_bytes=compare_bytes,
        compare_filename=compare_file.filename,
        base_file_format=base_file_format,
        compare_file_format=compare_file_format,
    )

    task.status = "queued"
    db.commit()
    db.refresh(task)
    task_runner.submit(task.id)

    return _task_to_response(task)


def _validate_upload_format(file: UploadFile, file_format: str, label: str) -> None:
    normalized_format = file_format.lower()
    filename = file.filename or ""
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if normalized_format == "pdf":
        if not filename or suffix != ".pdf":
            raise HTTPException(status_code=422, detail=f"{label}必须是PDF格式")
        return
    if normalized_format == "image":
        if not filename or suffix not in ALLOWED_IMAGE_SUFFIXES:
            raise HTTPException(status_code=422, detail=f"{label}必须是PNG、JPG/JPEG或WebP图片")
        return
    raise HTTPException(status_code=422, detail="文件格式只能是pdf或image")


@router.get("", response_model=TaskListResponse)
def list_tasks(
    status: str | None = Query(None),
    keyword: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(CompareTask)
    if status:
        query = query.filter(CompareTask.status == status)
    else:
        query = query.filter(CompareTask.status != "deleted")
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                CompareTask.task_no.ilike(pattern),
                CompareTask.base_file.has(PdfFile.original_name.ilike(pattern)),
                CompareTask.compare_file.has(PdfFile.original_name.ilike(pattern)),
            )
        )

    total = query.count()
    tasks = (
        query.order_by(CompareTask.created_at.desc(), CompareTask.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = [_task_to_list_item(task, db) for task in tasks]
    return TaskListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    service = TaskService(db)
    task = service.get_task(task_id)
    if not task or task.status == "deleted":
        raise HTTPException(status_code=404, detail="任务不存在")
    return _task_to_response(task)


@router.post("/{task_id}/pause", response_model=TaskResponse)
def pause_task(task_id: int, db: Session = Depends(get_db)):
    service = TaskService(db)
    task = service.get_task(task_id)
    if not task or task.status == "deleted":
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status in {"completed", "failed"}:
        raise HTTPException(status_code=409, detail="已结束的任务不能暂停")
    task.status = "paused"
    task.summary = "任务已暂停，可稍后继续处理。"
    db.commit()
    db.refresh(task)
    return _task_to_response(task)


@router.post("/{task_id}/resume", response_model=TaskResponse)
def resume_task(task_id: int, db: Session = Depends(get_db)):
    service = TaskService(db)
    task = service.get_task(task_id)
    if not task or task.status == "deleted":
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != "paused":
        raise HTTPException(status_code=409, detail="只有暂停中的任务可以继续")
    task.status = "queued"
    task.summary = None
    db.commit()
    db.refresh(task)
    task_runner.submit(task.id)
    return _task_to_response(task)


@router.post("/{task_id}/retry", response_model=TaskResponse)
def retry_task(task_id: int, db: Session = Depends(get_db)):
    service = TaskService(db)
    task = service.get_task(task_id)
    if not task or task.status == "deleted":
        raise HTTPException(status_code=404, detail="任务不存在")
    try:
        task = service.reset_failed_task_for_retry(task)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    task_runner.submit(task.id)
    return _task_to_response(task)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    service = TaskService(db)
    task = service.get_task(task_id)
    if not task or task.status == "deleted":
        raise HTTPException(status_code=404, detail="任务不存在")
    task.status = "deleted"
    task.summary = "任务已删除。"
    db.commit()
    return Response(status_code=204)


@router.get("/{task_id}/elements", response_model=list[DrawingElementResponse])
def get_task_elements(
    task_id: int,
    category: str | None = Query(None),
    file_role: str | None = Query(None),
    db: Session = Depends(get_db),
):
    service = TaskService(db)
    task = service.get_task(task_id)
    if not task or task.status == "deleted":
        raise HTTPException(status_code=404, detail="任务不存在")

    query = db.query(DrawingElement).filter(
        DrawingElement.file_id.in_([task.base_file_id, task.compare_file_id])
    )
    if category:
        query = query.filter(DrawingElement.category == category)
    if file_role == "base":
        query = query.filter(DrawingElement.file_id == task.base_file_id)
    elif file_role == "compare":
        query = query.filter(DrawingElement.file_id == task.compare_file_id)

    elements = query.all()
    return [_element_to_response(e) for e in elements]


@router.get("/{task_id}/diffs", response_model=list[CompareDiffResponse])
def get_task_diffs(task_id: int, db: Session = Depends(get_db)):
    service = TaskService(db)
    task = service.get_task(task_id)
    if not task or task.status == "deleted":
        raise HTTPException(status_code=404, detail="任务不存在")

    diffs = db.query(CompareDiff).filter(CompareDiff.compare_task_id == task.id).all()
    return [_diff_to_response(d) for d in diffs]


@router.get("/{task_id}/report-table", response_model=ReportTableResponse)
def get_task_report_table(task_id: int, db: Session = Depends(get_db)):
    service = TaskService(db)
    task = service.get_task(task_id)
    if not task or task.status == "deleted":
        raise HTTPException(status_code=404, detail="任务不存在")

    rows = ReportService(db).build_diff_report_rows(task.id)
    return ReportTableResponse(
        task_id=task.id,
        task_no=task.task_no,
        columns=REPORT_COLUMNS,
        rows=[row.as_dict() for row in rows],
    )


@router.get("/{task_id}/diff-summary", response_model=DiffSummaryResponse)
def get_task_diff_summary(task_id: int, db: Session = Depends(get_db)):
    service = TaskService(db)
    task = service.get_task(task_id)
    if not task or task.status == "deleted":
        raise HTTPException(status_code=404, detail="任务不存在")

    risk_counts = {"high": 0, "medium": 0, "low": 0, "manual_check": 0}
    review_counts = {
        "pending": 0,
        "confirmed": 0,
        "ignored": 0,
        "misjudged": 0,
        "modified": 0,
    }
    rows = ReportService(db).build_diff_report_rows(task.id)
    risk_label_to_key = {"高": "high", "中": "medium", "低": "low", "需人工确认": "manual_check"}
    for row in rows:
        risk_key = risk_label_to_key.get(row.risk_label)
        if risk_key:
            risk_counts[risk_key] = risk_counts.get(risk_key, 0) + 1
        review_counts[row.review_status] = review_counts.get(row.review_status, 0) + 1

    return DiffSummaryResponse(
        total_count=len(rows),
        risk_counts=risk_counts,
        review_counts=review_counts,
    )


class ReviewRequest(BaseModel):
    review_status: str
    reviewer_comment: str | None = None
    risk_level: str | None = None


@router.patch("/diffs/{diff_id}/review", response_model=CompareDiffResponse)
def review_diff(
    diff_id: int,
    body: ReviewRequest,
    db: Session = Depends(get_db),
):
    from app.models.models import ReviewLog
    diff = db.query(CompareDiff).filter(CompareDiff.id == diff_id).first()
    if not diff:
        raise HTTPException(status_code=404, detail="差异不存在")

    log = ReviewLog(
        compare_diff_id=diff.id,
        action="confirm" if body.review_status == "confirmed" else
              "ignore" if body.review_status == "ignored" else
              "mark_misjudged" if body.review_status == "misjudged" else
              "modify",
        old_value=json.dumps({"review_status": diff.review_status, "risk_level": diff.risk_level}),
        new_value=json.dumps({"review_status": body.review_status, "risk_level": body.risk_level or diff.risk_level}),
        comment=body.reviewer_comment,
    )
    db.add(log)

    diff.review_status = body.review_status
    if body.risk_level:
        diff.risk_level = body.risk_level
    if body.reviewer_comment is not None:
        diff.reviewer_comment = body.reviewer_comment

    db.commit()
    db.refresh(diff)
    return _diff_to_response(diff)


@router.get("/{task_id}/exports/diffs")
def export_diffs(task_id: int, db: Session = Depends(get_db)):
    service = TaskService(db)
    task = service.get_task(task_id)
    if not task or task.status == "deleted":
        raise HTTPException(status_code=404, detail="任务不存在")

    from app.exports.excel_exporter import ExcelExporter
    exporter = ExcelExporter()
    buf = exporter.export_diffs(db, task_id)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": _download_content_disposition(_timestamped_report_filename())},
    )


def _timestamped_report_filename() -> str:
    return f"报告{datetime.datetime.now().strftime('%Y%m%d-%H-%M-%S')}.xlsx"


def _download_content_disposition(filename: str) -> str:
    ascii_fallback = filename.replace("报告", "report")
    return f"attachment; filename={ascii_fallback}; filename*=UTF-8''{quote(filename)}"


@router.get("/{task_id}/exports/elements")
def export_elements(task_id: int, db: Session = Depends(get_db)):
    service = TaskService(db)
    task = service.get_task(task_id)
    if not task or task.status == "deleted":
        raise HTTPException(status_code=404, detail="任务不存在")

    from app.exports.excel_exporter import ExcelExporter
    exporter = ExcelExporter()
    buf = exporter.export_elements(db, task_id)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=elements_{task.task_no}.xlsx"},
    )


@router.get("/{task_id}/exports/final")
def export_final(task_id: int, db: Session = Depends(get_db)):
    service = TaskService(db)
    task = service.get_task(task_id)
    if not task or task.status == "deleted":
        raise HTTPException(status_code=404, detail="任务不存在")

    from app.exports.excel_exporter import ExcelExporter
    exporter = ExcelExporter()
    buf = exporter.export_final_report(db, task_id)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=final_report_{task.task_no}.xlsx"},
    )


def _task_to_response(task) -> TaskResponse:
    label, hint = STEP_INFO.get(task.status, (task.status, None))
    observability = _task_observability(task)
    failed_stage = task.failed_stage if task.status == "failed" else None
    settings = get_settings()
    return TaskResponse(
        id=task.id, task_no=task.task_no,
        base_file_id=task.base_file_id, compare_file_id=task.compare_file_id,
        status=task.status, progress=task.progress, summary=task.summary,
        created_at=task.created_at.isoformat() if task.created_at else "",
        started_at=task.started_at.isoformat() if task.started_at else None,
        updated_at=task.updated_at.isoformat() if task.updated_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        failed_stage=failed_stage,
        last_error=task.last_error,
        ai_call_count=observability["ai_call_count"],
        ai_total_duration_ms=observability["ai_total_duration_ms"],
        last_ai_error=observability["last_ai_error"],
        base_file_name=task.base_file.original_name if task.base_file else None,
        compare_file_name=task.compare_file.original_name if task.compare_file else None,
        base_page_count=task.base_file.page_count if task.base_file else None,
        compare_page_count=task.compare_file.page_count if task.compare_file else None,
        current_step_label=label,
        current_step_hint=hint,
        error_hint=_error_hint(task.summary) if task.status == "failed" else None,
        recognition_strategy=_recognition_strategy(settings),
    )


def _task_observability(task) -> dict:
    db = object_session(task)
    if db is None:
        return {"ai_call_count": 0, "ai_total_duration_ms": 0, "last_ai_error": None}
    file_ids = [task.base_file_id, task.compare_file_id]
    query = db.query(AiExtractionRun).filter(AiExtractionRun.file_id.in_(file_ids))
    ai_call_count = query.count()
    ai_total_duration_ms = (
        db.query(func.coalesce(func.sum(AiExtractionRun.duration_ms), 0))
        .filter(AiExtractionRun.file_id.in_(file_ids))
        .scalar()
        or 0
    )
    last_failed_run = (
        query.filter(AiExtractionRun.status == "failed", AiExtractionRun.error_message.isnot(None))
        .order_by(
            AiExtractionRun.finished_at.is_(None).asc(),
            AiExtractionRun.finished_at.desc(),
            AiExtractionRun.id.desc(),
        )
        .first()
    )
    return {
        "ai_call_count": ai_call_count,
        "ai_total_duration_ms": int(ai_total_duration_ms),
        "last_ai_error": last_failed_run.error_message if last_failed_run else None,
    }


def _task_to_list_item(task, db: Session) -> TaskListItemResponse:
    response = _task_to_response(task)
    report_rows = ReportService(db).build_diff_report_rows(task.id)
    counts = {
        "diff_count": len(report_rows),
        "high_risk_count": sum(1 for row in report_rows if row.risk_label == "高"),
        "pending_review_count": sum(1 for row in report_rows if row.review_status == "pending"),
    }
    return TaskListItemResponse(**response.model_dump(), **counts)


def _element_to_response(e: DrawingElement) -> DrawingElementResponse:
    return DrawingElementResponse(
        id=e.id, file_id=e.file_id, page_id=e.page_id, region_id=e.region_id,
        extraction_run_id=e.extraction_run_id, category=e.category,
        element_name=e.element_name, raw_value=e.raw_value,
        normalized_value=e.normalized_value, unit=e.unit,
        importance=e.importance, confidence=e.confidence,
        need_manual_check=e.need_manual_check,
        source_image_path=e.source_image_path, region_desc=e.region_desc,
        extra_json=e.extra_json, created_at=e.created_at.isoformat() if e.created_at else "",
    )


def _diff_to_response(d: CompareDiff) -> CompareDiffResponse:
    return CompareDiffResponse(
        id=d.id, compare_task_id=d.compare_task_id, match_id=d.match_id,
        base_element_id=d.base_element_id, compare_element_id=d.compare_element_id,
        risk_level=d.risk_level, diff_category=d.diff_category,
        base_content=d.base_content, compare_content=d.compare_content,
        diff_summary=d.diff_summary, impact=d.impact, suggestion=d.suggestion,
        confidence=d.confidence, need_manual_check=d.need_manual_check,
        review_status=d.review_status, reviewer_comment=d.reviewer_comment,
        created_at=d.created_at.isoformat() if d.created_at else "",
    )
