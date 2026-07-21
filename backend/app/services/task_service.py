from __future__ import annotations

import uuid
import datetime
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import get_settings, Settings
from app.models.models import (
    PdfFile, PdfPage, PageRegion, AiExtractionRun,
    DrawingElement, CompareTask, ElementMatch, CompareDiff, AiProfile,
)
from app.services.pdf_service import PdfRenderService, compute_hash
from app.services.crop_service import CropService
from app.ai.base import VisionModelProvider
from app.services.ai_profile_service import AiProfileService


class TaskControlInterrupt(RuntimeError):
    pass


def generate_task_no() -> str:
    return f"TASK-{datetime.datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def classify_ai_error(error: Exception | str) -> str:
    message = str(error)
    text = message.lower()

    if any(marker in text for marker in ["401", "unauthorized", "invalid api key", "incorrect api key"]):
        return f"认证错误: {message}。建议：检查 AI API Key 是否正确，或确认当前服务商账号权限。"
    if any(marker in text for marker in ["does not support image", "image_url", "vision", "unsupported image"]):
        return f"模型不支持图片: {message}。建议：检查当前模型是否支持视觉输入。"
    if any(marker in text for marker in ["json解析失败", "jsondecodeerror", "expecting value", "invalid json"]):
        return f"JSON解析失败: {message}。建议：模型返回格式不符合要求，请重试或调整模型配置。"
    if any(marker in text for marker in ["未识别到任何元素", "缺少 elements", "空结果", "empty result"]):
        return f"空结果: {message}。建议：检查图纸清晰度、识别策略或开启区域小图识别。"
    if any(marker in text for marker in ["timeout", "timed out", "超时", "429", "rate limit", "限流"]):
        return f"限流或超时: {message}。建议：稍后重试，或调大 AI 超时时间和降低并发压力。"
    if any(
        marker in text
        for marker in [
            "ai网络连接中断",
            "transport",
            "server disconnected",
            "connection reset",
            "unexpected_eof",
            "remote protocol",
            "ssl",
            "connecterror",
        ]
    ):
        return f"网络错误: {message}。建议：检查 AI Base URL、网络代理/防火墙和服务商可用性。"
    return f"未知错误: {message}。建议：复制错误信息，检查 AI 配置、输入图纸和后端日志。"


class TaskService:
    def __init__(self, db: Session, settings: Settings | None = None):
        self.db = db
        self.settings = settings or get_settings()
        self._provider_task: CompareTask | None = None

    def create_task(
        self,
        base_pdf_bytes: bytes,
        base_filename: str,
        compare_pdf_bytes: bytes,
        compare_filename: str,
        base_file_format: str = "pdf",
        compare_file_format: str = "pdf",
    ) -> CompareTask:
        base_file = self._save_input_file(base_pdf_bytes, base_filename, "base", base_file_format)
        compare_file = self._save_input_file(compare_pdf_bytes, compare_filename, "compare", compare_file_format)
        profile = AiProfileService(self.db, settings=self.settings).ensure_default_profile()
        task = CompareTask(
            task_no=generate_task_no(),
            base_file_id=base_file.id,
            compare_file_id=compare_file.id,
            ai_profile_id=profile.id,
            status="uploaded",
            progress=0,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def _save_input_file(self, file_bytes: bytes, filename: str, file_role: str, file_format: str) -> PdfFile:
        normalized_format = file_format.lower()
        if normalized_format not in {"pdf", "image"}:
            raise ValueError("文件格式只能是 pdf 或 image")

        file_hash = compute_hash(file_bytes)
        uploads_dir = self.settings.get_storage_path("uploads")
        uploads_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}_{filename}"
        stored_path = uploads_dir / stored_name
        stored_path.write_bytes(file_bytes)

        if normalized_format == "pdf":
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page_count = doc.page_count
            doc.close()
        else:
            with Image.open(stored_path) as image:
                image.verify()
            page_count = 1

        pdf_file = PdfFile(
            original_name=filename, stored_path=str(stored_path),
            file_hash=file_hash, page_count=page_count, file_role=file_role,
            file_type=normalized_format, status="uploaded",
        )
        self.db.add(pdf_file)
        self.db.commit()
        self.db.refresh(pdf_file)
        return pdf_file

    def _save_pdf_file(self, pdf_bytes: bytes, filename: str, file_role: str) -> PdfFile:
        return self._save_input_file(pdf_bytes, filename, file_role, "pdf")

    def _get_provider_for_task(self, task: CompareTask) -> VisionModelProvider:
        self._provider_task = task
        return self._get_provider()

    def _get_provider(self) -> VisionModelProvider:
        task = self._provider_task
        if task is not None and task.ai_profile_id is not None:
            profile_service = AiProfileService(self.db, settings=self.settings)
            profile = self.db.query(AiProfile).filter(AiProfile.id == task.ai_profile_id).first()
            if profile and self._has_real_profile_config(profile, profile_service):
                from app.ai.openai_provider import OpenAICompatibleProvider
                return OpenAICompatibleProvider(
                    base_url=profile.base_url,
                    api_key=profile_service.decrypt_api_key(profile),
                    model=profile.model,
                    timeout_seconds=profile.timeout_seconds,
                    max_retries=profile.max_retries,
                )
        if self.settings.has_real_ai_config:
            from app.ai.openai_provider import OpenAICompatibleProvider
            return OpenAICompatibleProvider()

        from app.ai.mock_provider import MockVisionProvider
        return MockVisionProvider()

    @staticmethod
    def _has_real_profile_config(profile, profile_service: AiProfileService) -> bool:
        api_key = profile_service.decrypt_api_key(profile)
        return all([
            profile.base_url and profile.base_url != "https://example.com/v1",
            api_key and api_key != "replace-with-real-key",
            profile.model and profile.model != "replace-with-vision-model",
        ])

    # ─── Step 1: Render Pages ───
    def render_pages(self, task: CompareTask) -> None:
        self._set_status(task, "rendering_pages", 10)
        base_file, compare_file = self._get_both_files(task)
        if not base_file or not compare_file:
            return self._fail(task, "找不到PDF文件记录")

        renderer = PdfRenderService(dpi=self.settings.PDF_RENDER_DPI)
        pages_dir = self.settings.get_storage_path("pages")
        pages_dir.mkdir(parents=True, exist_ok=True)

        for file_obj in (base_file, compare_file):
            try:
                if file_obj.file_type == "image":
                    results = [self._image_file_as_page(file_obj)]
                else:
                    pdf_bytes = Path(file_obj.stored_path).read_bytes()
                    results = renderer.render_to_images(pdf_bytes, file_obj.id, pages_dir)
                for r in results:
                    self.db.add(PdfPage(file_id=file_obj.id, page_no=r["page_no"],
                                         image_path=r["image_path"], width=r["width"],
                                         height=r["height"], dpi=r["dpi"]))
                file_obj.status = "rendered"
            except Exception as e:
                return self._fail(task, f"{file_obj.file_role} PDF渲染失败: {e}")

        self._set_status(task, "rendered", 25)

    def _image_file_as_page(self, file_obj: PdfFile) -> dict[str, Any]:
        with Image.open(file_obj.stored_path) as image:
            width, height = image.size
        return {
            "page_no": 1,
            "image_path": file_obj.stored_path,
            "width": width,
            "height": height,
            "dpi": self.settings.PDF_RENDER_DPI,
        }

    # ─── Step 2: Detect Regions ───
    def detect_regions(self, task: CompareTask) -> None:
        self._set_status(task, "detecting_regions", 30)
        return self._detect_regions_concurrent(task)

    # Detect region AI calls run concurrently; DB writes stay on the main thread.
    def _detect_regions_concurrent(self, task: CompareTask) -> None:
        provider = self._get_provider_for_task(task)
        pages = self.db.query(PdfPage).filter(
            PdfPage.file_id.in_([task.base_file_id, task.compare_file_id])
        ).all()
        page_sources = [
            {
                "id": page.id,
                "file_id": page.file_id,
                "page_no": page.page_no,
                "width": page.width,
                "height": page.height,
                "image_path": page.image_path,
            }
            for page in pages
        ]
        self.db.commit()

        for job in self._run_detect_layout_jobs(provider, page_sources):
            page = job["page"]
            started_at = job["started_at"]
            finished_at = job["finished_at"]
            try:
                if job["error"] is not None:
                    raise job["error"]
                layout = job["result"]
                run = self._build_ai_run(
                    provider=provider,
                    file_id=page["file_id"],
                    page_id=page["id"],
                    region_id=None,
                    input_type="full_page",
                    status="success",
                    started_at=started_at,
                    finished_at=finished_at,
                )
                self.db.add(run)
                self.db.flush()

                for reg in layout["regions"]:
                    self.db.add(PageRegion(
                        file_id=page["file_id"],
                        page_id=page["id"],
                        page_no=page["page_no"],
                        region_type=reg["region_type"],
                        region_name=reg["region_name"],
                        bbox_json=reg["bbox"],
                        ai_reason=reg["reason"],
                    ))
            except Exception as exc:
                formatted_error = classify_ai_error(exc)
                self.db.rollback()
                self.db.add(self._build_ai_run(
                    provider=provider,
                    file_id=page["file_id"],
                    page_id=page["id"],
                    region_id=None,
                    input_type="full_page",
                    status="failed",
                    started_at=started_at,
                    finished_at=finished_at,
                    error_message=formatted_error,
                ))
                self.db.commit()
                return self._fail(task, f"layout detection failed: {formatted_error}")

        self.db.commit()
        self._set_status(task, "regions_detected", 40)

    def _run_detect_layout_jobs(
        self, provider: VisionModelProvider, pages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not pages:
            return []
        max_workers = min(self._ai_max_concurrent_calls_per_task(), len(pages))
        if max_workers <= 1:
            return [self._call_detect_layout(provider, page, index) for index, page in enumerate(pages)]

        jobs: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self._call_detect_layout, provider, page, index)
                for index, page in enumerate(pages)
            ]
            for future in as_completed(futures):
                jobs.append(future.result())
        jobs.sort(key=lambda job: job["index"])
        return jobs

    def _call_detect_layout(
        self, provider: VisionModelProvider, page: dict[str, Any], index: int
    ) -> dict[str, Any]:
        started_at = datetime.datetime.now()
        try:
            result = provider.detect_layout(page["page_no"], page["width"], page["height"], page["image_path"])
            return {
                "index": index,
                "page": page,
                "result": result,
                "error": None,
                "started_at": started_at,
                "finished_at": datetime.datetime.now(),
            }
        except Exception as exc:
            return {
                "index": index,
                "page": page,
                "result": None,
                "error": exc,
                "started_at": started_at,
                "finished_at": datetime.datetime.now(),
            }

    # Step 3: Crop Regions
    def crop_regions(self, task: CompareTask) -> None:
        self._set_status(task, "cropping_regions", 45)
        cropper = CropService(padding_ratio=self.settings.CROP_PADDING_RATIO)
        regions_dir = self.settings.get_storage_path("regions")
        regions_dir.mkdir(parents=True, exist_ok=True)

        base_file, compare_file = self._get_both_files(task)
        for file_obj in (base_file, compare_file):
            regions = self.db.query(PageRegion).filter(PageRegion.file_id == file_obj.id).all()
            for region in regions:
                try:
                    page = self.db.query(PdfPage).filter(PdfPage.id == region.page_id).first()
                    if not page:
                        continue
                    result = cropper.crop_region(
                        image_path=page.image_path, bbox=region.bbox_json,
                        region_name=region.region_name, file_id=file_obj.id,
                        page_id=page.id, page_no=page.page_no, output_dir=regions_dir,
                    )
                    region.crop_image_path = result["crop_image_path"]
                except Exception as e:
                    continue
        self.db.commit()
        self._set_status(task, "regions_cropped", 55)

    # ─── Step 4: Extract Full Page Elements ───
    def extract_full_page_elements(self, task: CompareTask) -> None:
        self._set_status(task, "extracting_full_page_elements", 60)
        if not self.settings.AI_ENABLE_FULL_PAGE_EXTRACTION:
            self._set_status(task, "full_page_elements_skipped", 70)
            return
        self._extract_elements_for_task_concurrent(task, context="full_page", use_pages=True)

    # ─── Step 5: Extract Region Elements ───
    def extract_region_elements(self, task: CompareTask) -> None:
        self._set_status(task, "extracting_region_elements", 75)
        if not self.settings.AI_ENABLE_REGION_EXTRACTION:
            self._set_status(task, "region_elements_skipped", 80)
            return
        self._extract_elements_for_task_concurrent(task, context="region", use_regions=True)

    def _extract_elements_for_task_concurrent(
        self, task: CompareTask, context: str, use_pages: bool = False, use_regions: bool = False
    ) -> None:
        provider = self._get_provider_for_task(task)
        base_file, compare_file = self._get_both_files(task)
        file_infos = [
            {"id": base_file.id, "original_name": base_file.original_name},
            {"id": compare_file.id, "original_name": compare_file.original_name},
        ]
        errors: list[str] = []
        file_element_counts = {file_info["id"]: 0 for file_info in file_infos}
        sources: list[dict[str, Any]] = []

        for file_info in file_infos:
            if use_pages:
                pages = self.db.query(PdfPage).filter(PdfPage.file_id == file_info["id"]).all()
                for page in pages:
                    sources.append({
                        "file_id": file_info["id"],
                        "original_name": file_info["original_name"],
                        "region_type": "full_page",
                        "region_name": None,
                        "image_path": page.image_path,
                        "page_id": page.id,
                        "region_id": None,
                    })
            if use_regions:
                regions = self.db.query(PageRegion).filter(
                    PageRegion.file_id == file_info["id"], PageRegion.crop_image_path.isnot(None)
                ).all()
                for region in regions:
                    sources.append({
                        "file_id": file_info["id"],
                        "original_name": file_info["original_name"],
                        "region_type": region.region_type,
                        "region_name": region.region_name,
                        "image_path": region.crop_image_path,
                        "page_id": region.page_id,
                        "region_id": region.id,
                    })
        self.db.commit()

        if not sources:
            self._fail(task, f"{context}\u5143\u7d20\u8bc6\u522b\u5931\u8d25: \u6ca1\u6709\u53ef\u8bc6\u522b\u7684\u56fe\u50cf\u6e90")
            return

        for job in self._run_extract_element_jobs(provider, context, sources):
            source = job["source"]
            img_path = source["image_path"]
            started_at = job["started_at"]
            finished_at = job["finished_at"]
            duration_ms = int((finished_at - started_at).total_seconds() * 1000)
            try:
                if job["error"] is not None:
                    raise job["error"]
                result = job["result"]
                elements = result.get("elements") if isinstance(result, dict) else None
                if not isinstance(elements, list):
                    raise ValueError("AI\u8fd4\u56de\u7f3a\u5c11 elements \u6570\u7ec4")
                if not elements:
                    raise ValueError("AI鏈瘑鍒埌浠讳綍鍏冪礌")

                run = AiExtractionRun(
                    file_id=source["file_id"],
                    page_id=source["page_id"],
                    region_id=source["region_id"],
                    model_name=getattr(provider, "_model", "mock_extract"),
                    prompt_version="v1",
                    input_type=context,
                    status="success",
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_ms=duration_ms,
                    attempt_count=1,
                )
                self.db.add(run)
                self.db.flush()

                added_count = 0
                for elem_data in elements:
                    if not isinstance(elem_data, dict):
                        raise ValueError("AI\u8fd4\u56de\u7684\u5143\u7d20\u4e0d\u662f\u5bf9\u8c61")
                    category = elem_data.get("category")
                    element_name = elem_data.get("element_name")
                    if not category or not element_name:
                        raise ValueError("AI杩斿洖鐨勫厓绱犵己灏?category 鎴?element_name")
                    importance = elem_data.get("importance", "medium")
                    if importance not in {"high", "medium", "low"}:
                        importance = "medium"
                    self.db.add(DrawingElement(
                        file_id=source["file_id"],
                        page_id=source["page_id"],
                        region_id=source["region_id"],
                        extraction_run_id=run.id,
                        category=category,
                        element_name=element_name,
                        raw_value=elem_data.get("raw_value", ""),
                        normalized_value=elem_data.get("normalized_value", ""),
                        unit=elem_data.get("unit", ""),
                        importance=importance,
                        confidence=elem_data.get("confidence"),
                        need_manual_check=elem_data.get("need_manual_check", False),
                        source_image_path=img_path,
                        region_desc=f"{source['region_name'] or ''}" if source["region_name"] else "",
                    ))
                    added_count += 1
                self.db.commit()
                file_element_counts[source["file_id"]] += added_count
            except Exception as exc:
                formatted_error = classify_ai_error(exc)
                self.db.rollback()
                self.db.add(AiExtractionRun(
                    file_id=source["file_id"],
                    page_id=source["page_id"],
                    region_id=source["region_id"],
                    model_name=getattr(provider, "_model", "mock_extract"),
                    prompt_version="v1",
                    input_type=context,
                    status="failed",
                    error_message=formatted_error,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_ms=duration_ms,
                    attempt_count=1,
                ))
                self.db.commit()
                source_name = Path(img_path).name if img_path else "unknown"
                errors.append(f"{source['original_name']}/{source_name}: {formatted_error}")

        if errors:
            self._fail(task, f"{context}\u5143\u7d20\u8bc6\u522b\u5931\u8d25: {'; '.join(errors[:3])}")
            return
        missing_files = [
            file_info["original_name"] for file_info in file_infos
            if file_element_counts.get(file_info["id"], 0) == 0
        ]
        if missing_files:
            self._fail(task, f"{context}\u5143\u7d20\u8bc6\u522b\u5931\u8d25: {', '.join(missing_files)} \u672a\u63d0\u53d6\u5230\u5143\u7d20")

    def _run_extract_element_jobs(
        self, provider: VisionModelProvider, context: str, sources: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not sources:
            return []
        max_workers = min(self._ai_max_concurrent_calls_per_task(), len(sources))
        if max_workers <= 1:
            return [self._call_extract_elements(provider, context, source, index) for index, source in enumerate(sources)]

        jobs: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self._call_extract_elements, provider, context, source, index)
                for index, source in enumerate(sources)
            ]
            for future in as_completed(futures):
                jobs.append(future.result())
        jobs.sort(key=lambda job: job["index"])
        return jobs

    def _call_extract_elements(
        self, provider: VisionModelProvider, context: str, source: dict[str, Any], index: int
    ) -> dict[str, Any]:
        started_at = datetime.datetime.now()
        try:
            result = provider.extract_elements(source["image_path"], context, source["region_type"])
            return {
                "index": index,
                "source": source,
                "result": result,
                "error": None,
                "started_at": started_at,
                "finished_at": datetime.datetime.now(),
            }
        except Exception as exc:
            return {
                "index": index,
                "source": source,
                "result": None,
                "error": exc,
                "started_at": started_at,
                "finished_at": datetime.datetime.now(),
            }

    def _ai_max_concurrent_calls_per_task(self) -> int:
        value = getattr(self.settings, "AI_MAX_CONCURRENT_CALLS_PER_TASK", 1)
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return 1

    # ─── Step 6: Merge & Save Elements ───
    def merge_elements(self, task: CompareTask) -> None:
        self._set_status(task, "saving_elements", 85)

    # ─── Step 7: Compare Elements ───
    def compare_elements(self, task: CompareTask) -> None:
        self._set_status(task, "comparing_elements", 90)
        provider = self._get_provider_for_task(task)

        base_elements = self.db.query(DrawingElement).filter(
            DrawingElement.file_id == task.base_file_id
        ).all()
        compare_elements = self.db.query(DrawingElement).filter(
            DrawingElement.file_id == task.compare_file_id
        ).all()

        base_list = [{"id": f"base:{e.id}", "element_name": e.element_name,
                       "raw_value": e.raw_value, "normalized_value": e.normalized_value,
                       "category": e.category, "importance": e.importance,
                       "confidence": e.confidence} for e in base_elements]
        compare_list = [{"id": f"compare:{e.id}", "element_name": e.element_name,
                          "raw_value": e.raw_value, "normalized_value": e.normalized_value,
                          "category": e.category, "importance": e.importance,
                          "confidence": e.confidence} for e in compare_elements]
        task_id = task.id
        started_at = datetime.datetime.now()
        self.db.commit()

        try:
            result = provider.compare_elements(base_list, compare_list)
            finished_at = datetime.datetime.now()
            self.db.add(self._build_ai_run(
                provider=provider,
                file_id=task.compare_file_id,
                page_id=None,
                region_id=None,
                input_type="merge",
                status="success",
                started_at=started_at,
                finished_at=finished_at,
            ))
            self.db.flush()
            base_by_ref = {item["id"]: int(item["id"].split(":", 1)[1]) for item in base_list}
            compare_by_ref = {item["id"]: int(item["id"].split(":", 1)[1]) for item in compare_list}
            matches_by_refs: dict[tuple[int | None, int | None], ElementMatch] = {}

            for match_data in result.get("matches", []):
                base_element_id = base_by_ref.get(match_data.get("base_element_ref"))
                compare_element_id = compare_by_ref.get(match_data.get("compare_element_ref"))
                match = ElementMatch(
                    compare_task_id=task_id,
                    base_element_id=base_element_id,
                    compare_element_id=compare_element_id,
                    match_type=match_data.get("match_type", "semantic"),
                    match_reason=match_data.get("match_reason"),
                    confidence=match_data.get("confidence"),
                )
                self.db.add(match)
                self.db.flush()
                matches_by_refs[(base_element_id, compare_element_id)] = match

            for diff_data in result.get("diffs", []):
                base_element_id = base_by_ref.get(diff_data.get("base_element_ref"))
                compare_element_id = compare_by_ref.get(diff_data.get("compare_element_ref"))
                match = matches_by_refs.get((base_element_id, compare_element_id))
                self.db.add(CompareDiff(
                    compare_task_id=task_id,
                    match_id=match.id if match else None,
                    base_element_id=base_element_id,
                    compare_element_id=compare_element_id,
                    risk_level=diff_data.get("risk_level", "manual_check"),
                    diff_category=diff_data.get("diff_category", ""),
                    base_content=diff_data.get("base_content", ""),
                    compare_content=diff_data.get("compare_content", ""),
                    diff_summary=diff_data.get("diff_summary", ""),
                    impact=diff_data.get("impact", ""),
                    suggestion=diff_data.get("suggestion", ""),
                    confidence=diff_data.get("confidence"),
                    need_manual_check=diff_data.get("need_manual_check", False),
                ))
            self.db.commit()
        except Exception as e:
            finished_at = datetime.datetime.now()
            formatted_error = classify_ai_error(e)
            self.db.rollback()
            self.db.add(self._build_ai_run(
                provider=provider,
                file_id=task.compare_file_id,
                page_id=None,
                region_id=None,
                input_type="merge",
                status="failed",
                started_at=started_at,
                finished_at=finished_at,
                error_message=formatted_error,
            ))
            self.db.commit()
            return self._fail(task, f"元素对比失败: {formatted_error}")

        self._set_status(task, "completed", 100)
        task.completed_at = datetime.datetime.now()
        self.db.commit()

    # ─── Helpers ───
    def _set_status(self, task: CompareTask, status: str, progress: int) -> None:
        self.db.refresh(task)
        if task.status in {"paused", "deleted"}:
            raise TaskControlInterrupt(task.status)
        now = datetime.datetime.now()
        if task.started_at is None and status not in {"queued", "uploaded"}:
            task.started_at = now
        task.status = status
        task.progress = progress
        task.updated_at = now
        self.db.commit()

    def _fail(self, task: CompareTask, message: str) -> None:
        failed_stage = task.status
        task.status = "failed"
        task.summary = message
        task.failed_stage = failed_stage
        task.last_error = message
        task.updated_at = datetime.datetime.now()
        self.db.commit()

    def _build_ai_run(
        self,
        provider: VisionModelProvider,
        file_id: int,
        page_id: int | None,
        region_id: int | None,
        input_type: str,
        status: str,
        started_at: datetime.datetime,
        finished_at: datetime.datetime,
        error_message: str | None = None,
    ) -> AiExtractionRun:
        return AiExtractionRun(
            file_id=file_id,
            page_id=page_id,
            region_id=region_id,
            model_name=getattr(provider, "_model", "mock_ai"),
            prompt_version="v1",
            input_type=input_type,
            status=status,
            error_message=error_message,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=int((finished_at - started_at).total_seconds() * 1000),
            attempt_count=1,
        )

    def _get_both_files(self, task: CompareTask):
        base = self.db.query(PdfFile).filter(PdfFile.id == task.base_file_id).first()
        compare = self.db.query(PdfFile).filter(PdfFile.id == task.compare_file_id).first()
        return base, compare

    def get_task(self, task_id: int) -> CompareTask | None:
        return self.db.query(CompareTask).filter(CompareTask.id == task_id).first()

    def reset_failed_task_for_retry(self, task: CompareTask) -> CompareTask:
        if task.status != "failed":
            raise ValueError("只有失败任务可以重试")
        base_file, compare_file = self._get_both_files(task)
        if not base_file or not compare_file:
            raise ValueError("原始文件缺失，请重新创建任务")

        file_ids = [task.base_file_id, task.compare_file_id]
        retry_status = self._clear_retry_data_for_stage(task, file_ids, task.failed_stage)

        task.status = retry_status
        task.progress = self._retry_progress_for_status(retry_status)
        task.summary = None
        task.completed_at = None
        task.failed_stage = None
        task.last_error = None
        task.started_at = None
        task.updated_at = datetime.datetime.now()
        self.db.commit()
        self.db.refresh(task)
        return task

    def _clear_retry_data_for_stage(self, task: CompareTask, file_ids: list[int], failed_stage: str | None) -> str:
        if failed_stage == "detecting_regions":
            self._clear_from_regions(file_ids, task.id)
            return "rendered"
        if failed_stage == "cropping_regions":
            self._clear_from_crops(file_ids, task.id)
            return "regions_detected"
        if failed_stage == "extracting_full_page_elements":
            self._clear_from_full_page_elements(file_ids, task.id)
            return "regions_cropped"
        if failed_stage == "extracting_region_elements":
            self._clear_from_region_elements(file_ids, task.id)
            return "extracting_region_elements"
        if failed_stage in {"comparing_elements", "saving_diffs"}:
            self._clear_from_compare(task.id, file_ids)
            return "comparing_elements"

        self._clear_all_generated_data(task.id, file_ids)
        return "queued"

    def _clear_all_generated_data(self, task_id: int, file_ids: list[int]) -> None:
        self.db.query(CompareDiff).filter(CompareDiff.compare_task_id == task_id).delete(synchronize_session=False)
        self.db.query(ElementMatch).filter(ElementMatch.compare_task_id == task_id).delete(synchronize_session=False)
        self.db.query(DrawingElement).filter(DrawingElement.file_id.in_(file_ids)).delete(synchronize_session=False)
        self.db.query(AiExtractionRun).filter(AiExtractionRun.file_id.in_(file_ids)).delete(synchronize_session=False)
        self.db.query(PageRegion).filter(PageRegion.file_id.in_(file_ids)).delete(synchronize_session=False)
        self.db.query(PdfPage).filter(PdfPage.file_id.in_(file_ids)).delete(synchronize_session=False)

    def _clear_from_regions(self, file_ids: list[int], task_id: int) -> None:
        self.db.query(CompareDiff).filter(CompareDiff.compare_task_id == task_id).delete(synchronize_session=False)
        self.db.query(ElementMatch).filter(ElementMatch.compare_task_id == task_id).delete(synchronize_session=False)
        self.db.query(DrawingElement).filter(DrawingElement.file_id.in_(file_ids)).delete(synchronize_session=False)
        self.db.query(AiExtractionRun).filter(AiExtractionRun.file_id.in_(file_ids)).delete(synchronize_session=False)
        self.db.query(PageRegion).filter(PageRegion.file_id.in_(file_ids)).delete(synchronize_session=False)

    def _clear_from_crops(self, file_ids: list[int], task_id: int) -> None:
        self.db.query(CompareDiff).filter(CompareDiff.compare_task_id == task_id).delete(synchronize_session=False)
        self.db.query(ElementMatch).filter(ElementMatch.compare_task_id == task_id).delete(synchronize_session=False)
        self.db.query(DrawingElement).filter(DrawingElement.file_id.in_(file_ids)).delete(synchronize_session=False)
        self.db.query(AiExtractionRun).filter(AiExtractionRun.file_id.in_(file_ids)).delete(synchronize_session=False)
        self.db.query(PageRegion).filter(PageRegion.file_id.in_(file_ids)).update(
            {"crop_image_path": None},
            synchronize_session=False,
        )

    def _clear_from_full_page_elements(self, file_ids: list[int], task_id: int) -> None:
        self._clear_from_compare(task_id, file_ids)
        run_ids = self._ai_run_ids_for_input(file_ids, "full_page")
        target_run_ids = sorted(
            set(self._referenced_element_run_ids(file_ids, run_ids))
            | set(self._failed_ai_run_ids(file_ids, "full_page"))
        )
        self._delete_elements_and_runs(target_run_ids)

    def _clear_from_region_elements(self, file_ids: list[int], task_id: int) -> None:
        self._clear_from_compare(task_id, file_ids)
        self._delete_elements_and_runs(self._ai_run_ids_for_input(file_ids, "region"))

    def _clear_from_compare(self, task_id: int, file_ids: list[int]) -> None:
        self.db.query(CompareDiff).filter(CompareDiff.compare_task_id == task_id).delete(synchronize_session=False)
        self.db.query(ElementMatch).filter(ElementMatch.compare_task_id == task_id).delete(synchronize_session=False)
        self.db.query(AiExtractionRun).filter(
            AiExtractionRun.file_id.in_(file_ids),
            AiExtractionRun.input_type == "merge",
        ).delete(synchronize_session=False)

    def _ai_run_ids_for_input(self, file_ids: list[int], input_type: str) -> list[int]:
        return [
            run_id for (run_id,) in self.db.query(AiExtractionRun.id)
            .filter(AiExtractionRun.file_id.in_(file_ids), AiExtractionRun.input_type == input_type)
            .all()
        ]

    def _failed_ai_run_ids(self, file_ids: list[int], input_type: str) -> list[int]:
        return [
            run_id for (run_id,) in self.db.query(AiExtractionRun.id)
            .filter(
                AiExtractionRun.file_id.in_(file_ids),
                AiExtractionRun.input_type == input_type,
                AiExtractionRun.status == "failed",
            )
            .all()
        ]

    def _referenced_element_run_ids(self, file_ids: list[int], run_ids: list[int]) -> list[int]:
        if not run_ids:
            return []
        return [
            run_id for (run_id,) in self.db.query(DrawingElement.extraction_run_id)
            .filter(
                DrawingElement.file_id.in_(file_ids),
                DrawingElement.extraction_run_id.in_(run_ids),
            )
            .distinct()
            .all()
            if run_id is not None
        ]

    def _delete_elements_and_runs(self, run_ids: list[int]) -> None:
        if not run_ids:
            return
        self.db.query(DrawingElement).filter(
            DrawingElement.extraction_run_id.in_(run_ids)
        ).delete(synchronize_session=False)
        self.db.query(AiExtractionRun).filter(
            AiExtractionRun.id.in_(run_ids)
        ).delete(synchronize_session=False)

    def _retry_progress_for_status(self, status: str) -> int:
        return {
            "queued": 0,
            "rendered": 25,
            "regions_detected": 40,
            "regions_cropped": 55,
            "extracting_region_elements": 75,
            "comparing_elements": 90,
        }.get(status, 0)
