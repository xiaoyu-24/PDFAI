"""FailoverVisionProvider 与错误分类的单元测试。"""
from __future__ import annotations

import threading

import pytest

from app.ai.failover_provider import (
    AiFailoverExhaustedError,
    FailoverVisionProvider,
    is_failover_worthy,
)
from tests.conftest import fail_with, make_candidate, succeed_with


# ─── 1/2/3. 错误分类 ───
@pytest.mark.parametrize(
    "message",
    [
        "AI调用失败（已重试2次）: 401 unauthorized",
        "invalid api key",
        "permission denied",
        "403 forbidden",
        "404 model_not_found",
        "The model `x` does not exist",
        "429 rate limit reached",
        "insufficient_quota",
        "500 internal server error",
        "502 bad gateway",
        "503 service unavailable",
        "504 gateway timeout",
        "server overloaded",
        "Read timed out",
        "请求超时",
        "httpx.ConnectError: connection refused",
        "SSL handshake failed",
        "DNS lookup failed",
        "AI网络连接中断: server disconnected",
        "connection reset by peer",
    ],
)
def test_availability_errors_trigger_failover(message):
    assert is_failover_worthy(message) is True


@pytest.mark.parametrize(
    "message",
    [
        "AI输出JSON解析失败 (elements): Expecting value",
        "invalid json returned",
        "AI返回缺少 elements 数组",
        "AI未识别到任何元素",
        "AI返回的元素缺少 category 或 element_name",
        "AI返回的元素不是对象",
        "empty result",
    ],
)
def test_content_errors_do_not_trigger_failover(message):
    assert is_failover_worthy(message) is False
    # 即便同时带有可用性关键字，内容错误也优先判定为"不切换"。
    assert is_failover_worthy(message, include_capability_errors=True) is False


@pytest.mark.parametrize(
    "message",
    [
        "This model does not support image input",
        "unsupported image type",
        "模型不支持图片",
        "does not support vision",
    ],
)
def test_capability_errors_respect_setting(message):
    assert is_failover_worthy(message) is False
    assert is_failover_worthy(message, include_capability_errors=True) is True


def test_capability_error_wrapped_in_status_code_still_respects_setting():
    """服务商常把"不支持图片"包装成 400/404；能力判定必须优先于可用性判定。"""
    message = "404 error: the model does not support image input"
    assert is_failover_worthy(message) is False
    assert is_failover_worthy(message, include_capability_errors=True) is True


def test_auth_error_mentioning_vision_model_still_fails_over():
    """裸 'vision' 曾把认证错误误判成能力错误，这里锁住回归。"""
    assert is_failover_worthy("invalid api key for model gpt-4o-vision") is True


# ─── 4. 主失败、备用成功 ───
def test_primary_fails_backup_succeeds_records_one_switch():
    primary, primary_stub = make_candidate("主配置", profile_id=1, behavior=fail_with("503 service unavailable"))
    backup, backup_stub = make_candidate("备用配置", profile_id=2, behavior=succeed_with({"ok": True}))
    provider = FailoverVisionProvider([primary, backup])

    result = provider.compare_elements([], [])

    assert result == {"ok": True}
    assert primary_stub.calls == 1
    assert backup_stub.calls == 1
    assert provider.switch_count == 1
    assert provider.active_profile_name == "备用配置"
    assert provider._model == "model-备用配置"

    outcome = provider.drain_outcome()
    assert list(outcome.failed_profiles) == [1]
    assert "503" in outcome.failed_profiles[1]
    assert outcome.succeeded_profile_ids == [2]
    assert len(outcome.events) == 1
    event = outcome.events[0]
    assert (event.from_profile_id, event.to_profile_id) == (1, 2)
    assert (event.from_name, event.to_name) == ("主配置", "备用配置")
    # drain 之后队列清空，避免同一事件被重复落库。
    assert provider.drain_outcome().events == []


def test_content_error_propagates_without_switching():
    primary, primary_stub = make_candidate(
        "主配置", profile_id=1, behavior=fail_with("AI输出JSON解析失败 (elements): Expecting value")
    )
    backup, backup_stub = make_candidate("备用配置", profile_id=2)
    provider = FailoverVisionProvider([primary, backup])

    with pytest.raises(Exception, match="JSON解析失败"):
        provider.extract_elements("x.png", "full_page", "full_page")

    assert backup_stub.calls == 0
    assert provider.switch_count == 0
    assert provider.drain_outcome().events == []


# ─── 5. 全部失败时的聚合错误 ───
def test_all_candidates_fail_aggregates_errors_recognisably():
    from app.services.task_log_service import classify_task_error
    from app.services.task_service import classify_ai_error

    primary, _ = make_candidate("主配置", profile_id=1, behavior=fail_with("503 service unavailable"))
    backup, _ = make_candidate("备用配置", profile_id=2, behavior=fail_with("429 rate limit"))
    provider = FailoverVisionProvider([primary, backup])

    with pytest.raises(AiFailoverExhaustedError) as excinfo:
        provider.detect_layout(1, 100, 100, None)

    message = str(excinfo.value)
    assert "主配置" in message and "备用配置" in message
    assert "503" in message and "429" in message
    # 聚合错误仍要能被既有分类逻辑识别。
    assert classify_task_error(message) == "model_api"
    assert "限流或超时" in classify_ai_error(message)

    outcome = provider.drain_outcome()
    assert outcome.failed_profiles == {1: "503 service unavailable", 2: "429 rate limit"}
    assert outcome.succeeded_profile_ids == []


def test_single_candidate_failure_preserves_original_exception():
    class Boom(Exception):
        pass

    def behavior(_call_no):
        raise Boom("503 service unavailable")

    only, _ = make_candidate("唯一配置", profile_id=1, behavior=behavior)
    provider = FailoverVisionProvider([only])

    with pytest.raises(Boom, match="503 service unavailable"):
        provider.detect_layout(1, 10, 10, None)


# ─── 6. 同一次调用不重复尝试同一 profile ───
def test_single_call_never_retries_same_candidate():
    primary, primary_stub = make_candidate("主配置", profile_id=1, behavior=fail_with("500 internal server error"))
    backup, backup_stub = make_candidate("备用配置", profile_id=2, behavior=fail_with("500 internal server error"))
    provider = FailoverVisionProvider([primary, backup])

    with pytest.raises(AiFailoverExhaustedError):
        provider.detect_layout(1, 10, 10, None)

    assert primary_stub.calls == 1
    assert backup_stub.calls == 1


# ─── 7. 最大切换次数 ───
def test_max_switches_zero_means_full_chain():
    """AI_FAILOVER_MAX_SWITCHES=0 由上层翻译成 None，表示"不额外限制"。"""
    a, a_stub = make_candidate("A", profile_id=1, behavior=fail_with("503 unavailable"))
    b, b_stub = make_candidate("B", profile_id=2, behavior=fail_with("503 unavailable"))
    c, c_stub = make_candidate("C", profile_id=3, behavior=succeed_with({"ok": "C"}))
    provider = FailoverVisionProvider([a, b, c], max_switches=None)

    assert provider.detect_layout(1, 10, 10, None) == {"ok": "C"}
    assert (a_stub.calls, b_stub.calls, c_stub.calls) == (1, 1, 1)
    assert provider.switch_count == 2


def test_max_switches_one_stops_after_first_switch():
    a, a_stub = make_candidate("A", profile_id=1, behavior=fail_with("503 unavailable"))
    b, b_stub = make_candidate("B", profile_id=2, behavior=fail_with("503 unavailable"))
    c, c_stub = make_candidate("C", profile_id=3, behavior=succeed_with({"ok": "C"}))
    provider = FailoverVisionProvider([a, b, c], max_switches=1)

    with pytest.raises(AiFailoverExhaustedError):
        provider.detect_layout(1, 10, 10, None)

    assert (a_stub.calls, b_stub.calls, c_stub.calls) == (1, 1, 0)
    assert provider.switch_count == 1


def test_max_switches_larger_than_chain_is_clamped():
    a, _ = make_candidate("A", profile_id=1, behavior=fail_with("503 unavailable"))
    b, b_stub = make_candidate("B", profile_id=2, behavior=succeed_with({"ok": "B"}))
    provider = FailoverVisionProvider([a, b], max_switches=20)

    assert provider.detect_layout(1, 10, 10, None) == {"ok": "B"}
    assert b_stub.calls == 1


# ─── 8. 并发不跳过候选 ───
def test_concurrent_failures_advance_pointer_only_once():
    """两个线程同时发现主配置失败时，只能前进一格，不能跳过第一个备用配置。"""
    barrier = threading.Barrier(2)

    def primary_behavior(_call_no):
        barrier.wait(timeout=5)
        raise Exception("503 service unavailable")

    primary, primary_stub = make_candidate("主配置", profile_id=1, behavior=primary_behavior)
    backup, backup_stub = make_candidate("备用A", profile_id=2, behavior=succeed_with({"ok": "A"}))
    last, last_stub = make_candidate("备用B", profile_id=3, behavior=succeed_with({"ok": "B"}))
    provider = FailoverVisionProvider([primary, backup, last])

    results: list = []
    errors: list = []

    def worker():
        try:
            results.append(provider.detect_layout(1, 10, 10, None))
        except Exception as exc:  # pragma: no cover - 失败时用于诊断
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert errors == []
    assert results == [{"ok": "A"}, {"ok": "A"}]
    assert primary_stub.calls == 2
    assert backup_stub.calls == 2
    # 关键断言：可用的"备用A"没有被跳过，"备用B"根本不该被碰到。
    assert last_stub.calls == 0
    assert provider.switch_count == 1

    outcome = provider.drain_outcome()
    assert len(outcome.events) == 1
    assert outcome.failed_profiles == {1: "503 service unavailable"}
    assert outcome.succeeded_profile_ids == [2]


def test_thread_arriving_after_exhaustion_still_reports_original_errors():
    a, _ = make_candidate("A", profile_id=1, behavior=fail_with("503 service unavailable"))
    provider = FailoverVisionProvider([a])

    with pytest.raises(Exception, match="503 service unavailable"):
        provider.detect_layout(1, 10, 10, None)

    # 候选链已耗尽；后来的调用不能越界，也不能丢失原始错误。
    with pytest.raises(AiFailoverExhaustedError) as excinfo:
        provider.detect_layout(1, 10, 10, None)
    assert "503 service unavailable" in str(excinfo.value)
    # 属性访问在耗尽后依然安全（不越界）。
    assert provider.active_profile_name == "A"
    assert provider._model == "model-A"
    assert provider.active_profile_id == 1


def test_factory_failure_is_treated_as_unavailable():
    from app.ai.failover_provider import ProviderCandidate

    def broken_factory():
        raise Exception("API Key 解密失败: InvalidToken")

    broken = ProviderCandidate(profile_id=1, name="坏配置", model="m1", factory=broken_factory)
    good, good_stub = make_candidate("好配置", profile_id=2, behavior=succeed_with({"ok": True}))
    provider = FailoverVisionProvider([broken, good])

    assert provider.detect_layout(1, 10, 10, None) == {"ok": True}
    assert good_stub.calls == 1
    outcome = provider.drain_outcome()
    assert "解密失败" in outcome.failed_profiles[1]


def test_empty_candidate_chain_is_rejected():
    with pytest.raises(ValueError, match="候选链不能为空"):
        FailoverVisionProvider([])


def test_provider_instance_is_reused_across_calls():
    """同一候选的 provider 只实例化一次，避免每次调用都新建 httpx 客户端。"""
    created = []

    from app.ai.failover_provider import ProviderCandidate

    class _Stub:
        def detect_layout(self, *args):
            return {"ok": True}

    def factory():
        stub = _Stub()
        created.append(stub)
        return stub

    candidate = ProviderCandidate(profile_id=1, name="A", model="m", factory=factory)
    provider = FailoverVisionProvider([candidate])

    provider.detect_layout(1, 10, 10, None)
    provider.detect_layout(2, 10, 10, None)

    assert len(created) == 1
