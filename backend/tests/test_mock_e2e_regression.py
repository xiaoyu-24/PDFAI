"""Mock 端到端回归：没有真实 AI 配置时，整条流水线仍要跑通。

这条链路是本次改动最容易被破坏的地方——_get_provider() 被重写过，如果候选链构建有误，
开发期的 Mock 流程会直接崩掉，或者更糟：真实配置失败时悄悄用 Mock 产出假结果。
"""
from __future__ import annotations

import pytest

from app.ai.mock_provider import MockVisionProvider
from app.models.models import (
    CompareDiff,
    CompareTask,
    DrawingElement,
    PageRegion,
    PdfFile,
    PdfPage,
)
from app.services.ai_profile_service import AiProfileService
from app.services.task_service import TaskService


@pytest.fixture()
def mock_task(db_session, settings_factory, tmp_path):
    """没有任何真实 AI 配置的环境 + 一个可跑的两文件任务。"""
    settings = settings_factory(
        AI_ENABLE_FULL_PAGE_EXTRACTION=True,
        AI_ENABLE_REGION_EXTRACTION=False,
        AI_MAX_CONCURRENT_CALLS_PER_TASK=2,
    )
    from PIL import Image

    image = tmp_path / "page.png"
    Image.new("RGB", (40, 40), "white").save(image)

    files = []
    for role in ("base", "compare"):
        pdf = PdfFile(
            original_name=f"{role}.pdf",
            stored_path=str(tmp_path / f"{role}.pdf"),
            file_hash=f"hash-{role}",
            page_count=1,
            file_role=role,
            file_type="pdf",
            status="uploaded",
        )
        db_session.add(pdf)
        db_session.flush()
        db_session.add(
            PdfPage(
                file_id=pdf.id,
                page_no=1,
                width=40,
                height=40,
                dpi=300,
                image_path=str(image),
            )
        )
        files.append(pdf)

    task = CompareTask(
        task_no="TASK-MOCK-E2E",
        base_file_id=files[0].id,
        compare_file_id=files[1].id,
        status="uploaded",
        progress=0,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    service = TaskService(db_session, settings=settings)
    service.bind_run_context(run_id="mock-run")
    return {"service": service, "task": task, "settings": settings}


def test_provider_is_mock_when_no_real_config(mock_task):
    """占位配置（.env 与默认配置都是样例值）时必须落到 Mock。"""
    service, task = mock_task["service"], mock_task["task"]

    provider = service._get_provider_for_task(task)

    assert isinstance(provider, MockVisionProvider)


def test_mock_pipeline_completes_end_to_end(mock_task, db_session):
    """识别 → 裁剪 → 元素提取 → 对比：Mock 全流程走通并产出差异。"""
    service, task = mock_task["service"], mock_task["task"]

    service.detect_regions(task)
    db_session.refresh(task)
    assert task.status == "regions_detected", task.summary
    assert db_session.query(PageRegion).count() > 0

    service.crop_regions(task)
    db_session.refresh(task)
    assert task.status == "regions_cropped", task.summary

    service.extract_full_page_elements(task)
    db_session.refresh(task)
    assert task.status != "failed", task.summary
    assert db_session.query(DrawingElement).count() > 0

    service.merge_elements(task)
    service.compare_elements(task)
    db_session.refresh(task)

    assert task.status == "completed", task.summary
    assert task.progress == 100
    assert db_session.query(CompareDiff).filter(
        CompareDiff.compare_task_id == task.id
    ).count() > 0


def test_mock_run_records_no_failover_log(mock_task, db_session):
    """Mock 单候选链不应产生任何故障切换日志。"""
    from app.models.models import TaskLog

    service, task = mock_task["service"], mock_task["task"]

    service.detect_regions(task)

    failover_logs = db_session.query(TaskLog).filter(TaskLog.event_type == "failover").count()
    assert failover_logs == 0


def test_mock_model_name_recorded_on_ai_runs(mock_task, db_session):
    """AiExtractionRun 的 model_name 仍要记录 Mock 的模型名，不能变成包装器的名字。"""
    from app.models.models import AiExtractionRun

    service, task = mock_task["service"], mock_task["task"]

    service.detect_regions(task)

    runs = db_session.query(AiExtractionRun).all()
    assert runs, "布局识别应当留下 AI 运行记录"
    for run in runs:
        assert run.model_name, "model_name 不应为空"
        assert "Mock 模拟配置" not in run.model_name


def test_real_profile_present_means_no_mock(mock_task, db_session):
    """一旦存在真实配置，候选链里就不能再出现 Mock。"""
    service = mock_task["service"]
    settings = mock_task["settings"]
    profile_service = AiProfileService(db_session, settings=settings)
    profile_service.create_profile(
        "真实配置", "https://real.example.com/v1", "sk-real", "vision-model", 60, 0
    )

    candidates = profile_service.build_provider_candidates(None)

    assert [c.name for c in candidates] == ["真实配置"]
    assert not isinstance(candidates[0].factory(), MockVisionProvider)
