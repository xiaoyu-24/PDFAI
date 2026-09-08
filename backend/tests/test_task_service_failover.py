"""TaskService 与故障切换的集成测试。

覆盖三个 AI 阶段的接入、TaskLog 落库、人工复核标记，以及"真实配置失败绝不落到 Mock"。
"""
from __future__ import annotations

import datetime

import pytest

from app.ai.failover_provider import FailoverVisionProvider
from app.models.models import AiProfile, CompareDiff, CompareTask, PdfFile, PdfPage, TaskLog
from app.services.ai_profile_service import AiProfileService
from app.services.task_service import TaskService


# ─── 测试替身 ───
class _StubProvider:
    """可编程的假 provider：按方法名决定抛错还是返回结果。"""

    def __init__(self, name: str, *, fail_with: Exception | None = None):
        self.name = name
        self._model = f"model-{name}"
        self.fail_with = fail_with
        self.calls: list[str] = []

    def detect_layout(self, page_no, image_width, image_height, image_path=None):
        self.calls.append("detect_layout")
        if self.fail_with:
            raise self.fail_with
        return {
            "page_no": page_no,
            "regions": [
                {
                    "region_type": "title_block",
                    "region_name": "标题栏",
                    "bbox": {"x": 0, "y": 0, "width": 10, "height": 10},
                    "reason": "r",
                }
            ],
        }

    def extract_elements(self, image_path, context, region_type):
        self.calls.append("extract_elements")
        if self.fail_with:
            raise self.fail_with
        return {
            "elements": [
                {
                    "category": "尺寸",
                    "element_name": "总长",
                    "raw_value": "100mm",
                    "normalized_value": "100",
                    "unit": "mm",
                    "importance": "high",
                }
            ]
        }

    def compare_elements(self, base_elements, compare_elements):
        self.calls.append("compare_elements")
        if self.fail_with:
            raise self.fail_with
        return {
            "matches": [],
            "diffs": [
                {
                    "risk_level": "high",
                    "diff_category": "尺寸",
                    "base_content": "100mm",
                    "compare_content": "120mm",
                    "diff_summary": "总长变化",
                    "need_manual_check": False,
                }
            ],
        }


def _candidate(name, provider, profile_id=None):
    from app.ai.failover_provider import ProviderCandidate

    return ProviderCandidate(
        profile_id=profile_id, name=name, model=provider._model, factory=lambda: provider
    )


# ─── fixtures ───
@pytest.fixture
def task_env(db_session, settings_factory, tmp_path):
    """建一个可以跑 AI 阶段的最小任务：两个文件、各一页。"""
    settings = settings_factory(AI_MAX_CONCURRENT_CALLS_PER_TASK=2)
    image = tmp_path / "page.png"
    from PIL import Image

    Image.new("RGB", (20, 20), "white").save(image)

    files = []
    for role in ("base", "compare"):
        pdf = PdfFile(
            original_name=f"{role}.pdf",
            stored_path=str(tmp_path / f"{role}.pdf"),
            file_hash=role,
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
                width=20,
                height=20,
                dpi=300,
                image_path=str(image),
            )
        )
        files.append(pdf)
    task = CompareTask(
        task_no="TASK-TEST-1",
        base_file_id=files[0].id,
        compare_file_id=files[1].id,
        status="uploaded",
        progress=0,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    service = TaskService(db_session, settings=settings)
    return {"service": service, "task": task, "settings": settings, "image": str(image)}


# ─── 阶段接入：主配置失败、备用成功 ───
def test_detect_regions_survives_failover(task_env, db_session):
    """布局识别阶段：主配置 503，备用成功，阶段继续而不是把任务标 failed。"""
    service, task = task_env["service"], task_env["task"]
    bad = _StubProvider("bad", fail_with=Exception("503 service unavailable"))
    good = _StubProvider("good")
    provider = FailoverVisionProvider([_candidate("主配置", bad, 1), _candidate("备用", good, 2)])
    service.set_provider(provider)

    service.detect_regions(task)
    db_session.refresh(task)

    assert task.status == "regions_detected", task.summary
    assert good.calls, "备用配置应当被调用"


def test_extract_elements_survives_failover(task_env, db_session):
    service, task = task_env["service"], task_env["task"]
    bad = _StubProvider("bad", fail_with=Exception("429 rate limit"))
    good = _StubProvider("good")
    provider = FailoverVisionProvider([_candidate("主配置", bad, 1), _candidate("备用", good, 2)])
    service.set_provider(provider)

    service.extract_full_page_elements(task)
    db_session.refresh(task)

    assert task.status != "failed", task.summary
    assert good.calls


def test_compare_elements_survives_failover(task_env, db_session):
    """差异比较阶段：需要先有元素，再验证切换后任务能完成。"""
    service, task = task_env["service"], task_env["task"]
    good_extract = _StubProvider("extract")
    service.set_provider(
        FailoverVisionProvider([_candidate("主配置", good_extract, 1)])
    )
    service.extract_full_page_elements(task)
    db_session.refresh(task)
    assert task.status != "failed", task.summary

    bad = _StubProvider("bad", fail_with=Exception("502 bad gateway"))
    good = _StubProvider("good")
    provider = FailoverVisionProvider([_candidate("主配置", bad, 1), _candidate("备用", good, 2)])
    service.set_provider(provider)

    service.compare_elements(task)
    db_session.refresh(task)

    assert task.status == "completed", task.summary
    assert good.calls


def test_all_candidates_failing_fails_task_with_readable_error(task_env, db_session):
    """所有配置都失败：走正常失败流程，错误提示对用户可读。"""
    service, task = task_env["service"], task_env["task"]
    bad1 = _StubProvider("b1", fail_with=Exception("503 service unavailable"))
    bad2 = _StubProvider("b2", fail_with=Exception("401 unauthorized"))
    provider = FailoverVisionProvider([_candidate("主配置", bad1, 1), _candidate("备用", bad2, 2)])
    service.set_provider(provider)

    service.detect_regions(task)
    db_session.refresh(task)

    assert task.status == "failed"
    assert "主配置" in task.summary and "备用" in task.summary
    # 聚合错误仍然能被既有分类识别出来（不是"未知错误"）。
    assert "未知错误" not in task.summary


# ─── 真实配置绝不退化到 Mock ───
def test_real_config_failure_never_uses_mock(task_env, db_session, settings_factory):
    """两套真实配置都失败时，候选链里不应出现 Mock，结果必须是失败。"""
    from app.ai.mock_provider import MockVisionProvider

    service = task_env["service"]
    settings = task_env["settings"]
    profile_service = AiProfileService(db_session, settings=settings)
    for name in ("真实A", "真实B"):
        profile_service.create_profile(
            name, "https://real.example.com/v1", f"sk-{name}", "vision-model", 60, 0
        )
    candidates = profile_service.build_provider_candidates(None)

    assert len(candidates) == 2
    for candidate in candidates:
        instance = candidate.factory()
        assert not isinstance(instance, MockVisionProvider), "真实配置失败绝不能落到 Mock"


# ─── TaskLog ───
def test_failover_writes_tasklog_without_api_key(task_env, db_session):
    """切换事件写入 TaskLog：event_type/component/status/is_degraded/fallback_action 齐全且无密钥。"""
    service, task = task_env["service"], task_env["task"]
    secret = "sk-super-secret-key-value"
    bad = _StubProvider(
        "bad", fail_with=Exception(f"401 unauthorized; Authorization: Bearer {secret}")
    )
    good = _StubProvider("good")
    provider = FailoverVisionProvider([_candidate("主配置", bad, 1), _candidate("备用", good, 2)])
    service.set_provider(provider)
    service.bind_run_context(run_id="run-1")

    service.detect_regions(task)

    logs = db_session.query(TaskLog).filter(TaskLog.event_type == "failover").all()
    assert len(logs) == 1, "一次全局切换只记录一条"
    log = logs[0]
    assert log.component == "model_api"
    assert log.status == "degraded"
    assert log.level == "warning"
    assert log.is_degraded is True
    assert log.run_id == "run-1"
    assert log.task_id == task.id
    assert "主配置" in log.fallback_action and "备用" in log.fallback_action

    blob = " ".join(
        str(x) for x in [log.message, log.fallback_action, log.error_detail, log.metadata_json]
    )
    assert secret not in blob, "TaskLog 不得包含 API Key"


def test_concurrent_threads_log_single_switch(task_env, db_session):
    """一个阶段内多线程同时失败：只记录一次全局切换，不是每个线程一条。"""
    service, task = task_env["service"], task_env["task"]
    bad = _StubProvider("bad", fail_with=Exception("503 service unavailable"))
    good = _StubProvider("good")
    provider = FailoverVisionProvider([_candidate("主配置", bad, 1), _candidate("备用", good, 2)])
    service.set_provider(provider)
    service.bind_run_context(run_id="run-2")

    # 两个文件各一页 = 2 个并发 job，都会撞上失败的主配置。
    service.detect_regions(task)

    logs = db_session.query(TaskLog).filter(TaskLog.event_type == "failover").all()
    assert len(logs) == 1


def test_failover_marks_diffs_for_manual_review(task_env, db_session):
    """发生切换的任务，最终 CompareDiff 全部标记 need_manual_check。"""
    from app.api.tasks import _mark_degraded_results_for_manual_review

    service, task = task_env["service"], task_env["task"]
    service.bind_run_context(run_id="run-3")

    extract = _StubProvider("extract")
    service.set_provider(FailoverVisionProvider([_candidate("主配置", extract, 1)]))
    service.extract_full_page_elements(task)

    bad = _StubProvider("bad", fail_with=Exception("503 service unavailable"))
    good = _StubProvider("good")
    service.set_provider(
        FailoverVisionProvider([_candidate("主配置", bad, 1), _candidate("备用", good, 2)])
    )
    service.compare_elements(task)
    db_session.refresh(task)
    assert task.status == "completed", task.summary

    diffs = db_session.query(CompareDiff).filter(CompareDiff.compare_task_id == task.id).all()
    assert diffs, "应当至少产生一条差异"
    # 阶段结束时写了 is_degraded 日志，pipeline 收尾据此标记人工复核。
    _mark_degraded_results_for_manual_review(db_session, task.id, "run-3")
    for diff in db_session.query(CompareDiff).filter(CompareDiff.compare_task_id == task.id).all():
        assert diff.need_manual_check is True
        assert diff.review_status == "pending"


# ─── 健康状态与后续阶段偏好 ───
def test_failed_profile_gets_cooldown_after_stage(task_env, db_session):
    """阶段结束后失败配置落库为 unhealthy 并带 cooldown，成功配置标 healthy。"""
    service, task = task_env["service"], task_env["task"]
    settings = task_env["settings"]
    profile_service = AiProfileService(db_session, settings=settings)
    p_bad = profile_service.create_profile(
        "坏配置", "https://bad.example.com/v1", "sk-bad", "m", 60, 0
    )
    p_good = profile_service.create_profile(
        "好配置", "https://good.example.com/v1", "sk-good", "m", 60, 0
    )

    bad = _StubProvider("bad", fail_with=Exception("503 service unavailable"))
    good = _StubProvider("good")
    provider = FailoverVisionProvider(
        [_candidate("坏配置", bad, p_bad.id), _candidate("好配置", good, p_good.id)]
    )
    service.set_provider(provider)

    service.detect_regions(task)

    db_session.refresh(p_bad)
    db_session.refresh(p_good)
    assert p_bad.health_status == "unhealthy"
    assert p_bad.cooldown_until is not None and p_bad.cooldown_until > datetime.datetime.now()
    assert p_good.health_status == "healthy"


def test_later_stage_prefers_successful_profile(task_env, db_session):
    """后续阶段优先沿用已成功的后备配置，不再先打冷却中的故障配置。"""
    service = task_env["service"]
    settings = task_env["settings"]
    profile_service = AiProfileService(db_session, settings=settings)
    p_bad = profile_service.create_profile(
        "坏配置", "https://bad.example.com/v1", "sk-bad", "m", 60, 0
    )
    p_good = profile_service.create_profile(
        "好配置", "https://good.example.com/v1", "sk-good", "m", 60, 0
    )
    # 模拟上一阶段的结果：坏配置进冷却，好配置成为本次运行偏好。
    profile_service.mark_profile_unhealthy(p_bad.id, "503 service unavailable")
    service._run_preferred_profile_id = p_good.id

    candidates = profile_service.build_provider_candidates(
        None, preferred_profile_id=p_good.id
    )
    assert candidates[0].profile_id == p_good.id
    assert candidates[-1].profile_id == p_bad.id


def test_provider_is_plain_when_single_candidate(task_env, db_session, settings_factory):
    """只有一个候选时不需要包装器，行为与旧逻辑一致。"""
    service = task_env["service"]
    settings = task_env["settings"]
    profile_service = AiProfileService(db_session, settings=settings)
    profile_service.create_profile("唯一", "https://only.example.com/v1", "sk-a", "m", 60, 0)

    task = task_env["task"]
    provider = service._get_provider_for_task(task)
    # 单候选：不是 FailoverVisionProvider，避免多余的一层间接。
    assert not isinstance(provider, FailoverVisionProvider)
