from __future__ import annotations

import datetime
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

from app.ai.base import VisionModelProvider


# 内容类错误：配置本身是通的，换配置不会改善结果，只会把确定的失败变成不确定的结果。
_CONTENT_ERROR_MARKERS = (
    "json解析失败",
    "jsondecodeerror",
    "expecting value",
    "invalid json",
    "未识别到任何元素",
    "缺少 elements",
    "缺少 category",
    "不是对象",
    "空结果",
    "empty result",
)

# 能力缺陷：不是可用性问题，但换配置确实能解决，默认不触发切换。
# 只匹配足够具体的短语：裸 "vision" 会命中 "invalid api key for model gpt-4o-vision"
# 这类认证错误，把本应切换的可用性问题误判成能力问题。
_CAPABILITY_ERROR_MARKERS = (
    "does not support image",
    "do not support image",
    "not support image",
    "unsupported image",
    "image input is not supported",
    "image_url is not supported",
    "does not support vision",
    "no vision support",
    "模型不支持图片",
    "不支持图片输入",
)

# 可用性类错误：说明这份配置当前不可用，应当切换到下一个候选。
_AVAILABILITY_ERROR_MARKERS = (
    # 认证与权限
    "401",
    "403",
    "unauthorized",
    "invalid api key",
    "incorrect api key",
    "invalid_api_key",
    "permission denied",
    "认证错误",
    # 模型或端点不存在
    "404",
    "model_not_found",
    "does not exist",
    "no such model",
    # 限流与配额
    "429",
    "rate limit",
    "限流",
    "quota",
    "insufficient_quota",
    # 服务端故障
    "500",
    "502",
    "503",
    "504",
    "bad gateway",
    "service unavailable",
    "internal server error",
    "overloaded",
    # 网络与超时
    "timeout",
    "timed out",
    "超时",
    "connection",
    "connecterror",
    "transport",
    "server disconnected",
    "connection reset",
    "unexpected_eof",
    "remote protocol",
    "ssl",
    "dns",
    "ai网络连接中断",
)


def is_failover_worthy(error: Exception | str, *, include_capability_errors: bool = False) -> bool:
    """判断这个错误是否说明"当前配置不可用"，值得切换到下一套配置。

    判定顺序刻意如此：内容错误 → 能力错误 → 可用性错误。
    能力错误必须排在可用性错误之前，因为服务商常把"模型不支持图片"包装成 400/404 之类的
    状态码；先看可用性标记会让 AI_FAILOVER_ON_VISION_UNSUPPORTED=False 形同虚设。
    """
    text = str(error).lower()
    if any(marker in text for marker in _CONTENT_ERROR_MARKERS):
        return False
    if any(marker in text for marker in _CAPABILITY_ERROR_MARKERS):
        return include_capability_errors
    if any(marker in text for marker in _AVAILABILITY_ERROR_MARKERS):
        return True
    return False


@dataclass(frozen=True)
class FailoverAttempt:
    profile_id: int | None
    name: str
    error: str


class AiFailoverExhaustedError(Exception):
    """所有候选 AI 配置都不可用。

    消息中保留每个配置的原始报错，让 classify_ai_error() / classify_task_error() 仍能
    从聚合文案里识别出认证、限流、网络等类别。
    """

    def __init__(self, attempts: List[FailoverAttempt]):
        self.attempts = list(attempts)
        if not self.attempts:
            super().__init__("所有AI配置均不可用")
            return
        names = "、".join(attempt.name for attempt in self.attempts)
        details = "; ".join(f"{attempt.name}: {attempt.error}" for attempt in self.attempts)
        super().__init__(f"所有AI配置均不可用（已尝试：{names}）：{details}")


@dataclass(frozen=True)
class FailoverEvent:
    """一次配置切换。由工作线程记录，主线程统一落库。"""

    from_profile_id: int | None
    from_name: str
    to_profile_id: int | None
    to_name: str
    error: str
    occurred_at: datetime.datetime


@dataclass
class ProviderCandidate:
    profile_id: int | None
    name: str
    model: str
    factory: Callable[[], VisionModelProvider]


@dataclass
class FailoverOutcome:
    """一个阶段结束后需要持久化的健康状态变更。"""

    events: List[FailoverEvent] = field(default_factory=list)
    # profile_id -> 该配置自己的最后一条错误，便于分别写入 last_health_error。
    failed_profiles: Dict[int, str] = field(default_factory=dict)
    succeeded_profile_ids: List[int] = field(default_factory=list)

    @property
    def switched(self) -> bool:
        return bool(self.events)


class FailoverVisionProvider(VisionModelProvider):
    """按优先级持有多个 AI 配置，遇到可用性错误时自动切换并重放当前调用。

    同一个实例会被一个阶段内的多个工作线程共用，因此切换指针受锁保护，且每个线程只推进
    自己出发时看到的那个指针：多线程同时失败时只会前进一格，不会一次跳过多个可用配置。

    数据库写入不在工作线程内进行。切换事件和健康状态变更先入队，由主线程调用
    drain_outcome() 统一落库。
    """

    def __init__(
        self,
        candidates: List[ProviderCandidate],
        *,
        max_switches: int | None = None,
        include_capability_errors: bool = False,
    ):
        if not candidates:
            raise ValueError("AI 配置候选链不能为空")
        self._candidates = list(candidates)
        # None 表示"不额外限制"，即最多把候选链走完。上层的 AI_FAILOVER_MAX_SWITCHES=0
        # 同样表示不额外限制，由调用方负责翻译成 None。
        limit = len(self._candidates) - 1
        self._max_switches = limit if max_switches is None else min(max_switches, limit)
        self._include_capability_errors = include_capability_errors
        self._lock = threading.Lock()
        # _index 始终是合法下标；候选链走完由 _exhausted 表示，避免任何越界。
        self._index = 0
        self._exhausted = False
        self._switch_count = 0
        self._providers: Dict[int, VisionModelProvider] = {}
        self._events: List[FailoverEvent] = []
        self._failed_profiles: Dict[int, str] = {}
        self._succeeded_profile_ids: List[int] = []
        # 跨线程累积的失败记录：某个线程发现候选链已被别人耗尽时，用它拼出完整错误。
        self._all_attempts: List[FailoverAttempt] = []

    # ─── VisionModelProvider ───
    def detect_layout(
        self, page_no: int, image_width: int, image_height: int, image_path: str | None = None
    ) -> Dict[str, Any]:
        return self._call("detect_layout", page_no, image_width, image_height, image_path)

    def extract_elements(self, image_path: str, context: str, region_type: str) -> Dict[str, Any]:
        return self._call("extract_elements", image_path, context, region_type)

    def compare_elements(
        self, base_elements: List[Dict[str, Any]], compare_elements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        return self._call("compare_elements", base_elements, compare_elements)

    # ─── 当前生效配置 ───
    @property
    def _model(self) -> str:
        """AiExtractionRun 通过 getattr(provider, "_model") 记录模型名，必须跟随当前生效的配置。"""
        with self._lock:
            return self._candidates[self._index].model

    @property
    def active_profile_id(self) -> int | None:
        with self._lock:
            return self._candidates[self._index].profile_id

    @property
    def active_profile_name(self) -> str:
        with self._lock:
            return self._candidates[self._index].name

    @property
    def switch_count(self) -> int:
        with self._lock:
            return self._switch_count

    @property
    def candidate_count(self) -> int:
        return len(self._candidates)

    def drain_outcome(self) -> FailoverOutcome:
        """取出待落库的切换事件与健康状态变更，并清空队列。只在主线程调用。"""
        with self._lock:
            outcome = FailoverOutcome(
                events=list(self._events),
                failed_profiles=dict(self._failed_profiles),
                succeeded_profile_ids=list(dict.fromkeys(self._succeeded_profile_ids)),
            )
            self._events.clear()
            self._failed_profiles.clear()
            self._succeeded_profile_ids.clear()
        return outcome

    # ─── 内部实现 ───
    def _call(self, method: str, *args) -> Dict[str, Any]:
        tried: set[int] = set()
        attempts: List[FailoverAttempt] = []
        first_exc: Exception | None = None

        while True:
            with self._lock:
                if self._exhausted or self._index in tried:
                    break
                index = self._index
                tried.add(index)
                candidate = self._candidates[index]
                provider = self._providers.get(index)
                if provider is None:
                    # 工厂只是构造 httpx 客户端，没有网络 I/O；持锁创建可以避免两个线程
                    # 各建一个客户端、其中一个被丢弃后连接池无人关闭。
                    try:
                        provider = candidate.factory()
                    except Exception as exc:
                        provider = None
                        factory_error: Exception | None = exc
                    else:
                        self._providers[index] = provider
                        factory_error = None
                else:
                    factory_error = None

            if factory_error is not None:
                # 配置无法实例化（例如密钥解密失败）等同于该配置不可用。
                attempts.append(
                    FailoverAttempt(candidate.profile_id, candidate.name, str(factory_error))
                )
                first_exc = first_exc or factory_error
                if self._switch_away(index, candidate, factory_error):
                    continue
                break

            try:
                result = getattr(provider, method)(*args)
            except Exception as exc:
                if not is_failover_worthy(
                    exc, include_capability_errors=self._include_capability_errors
                ):
                    raise
                attempts.append(FailoverAttempt(candidate.profile_id, candidate.name, str(exc)))
                first_exc = first_exc or exc
                if self._switch_away(index, candidate, exc):
                    continue
                break

            if candidate.profile_id is not None:
                with self._lock:
                    self._succeeded_profile_ids.append(candidate.profile_id)
            return result

        # 只试过一个配置时原样抛出，保持既有的错误分类与提示文案不变。
        if first_exc is not None and len(attempts) == 1:
            raise first_exc
        if attempts:
            raise AiFailoverExhaustedError(attempts)
        # 本线程一个配置都没试上：候选链在它进来之前就被其他线程耗尽了。
        # 用全局累积的失败记录拼错误，既保留原始报错也能被既有分类逻辑识别。
        with self._lock:
            inherited = list(self._all_attempts)
        raise AiFailoverExhaustedError(inherited)

    def _switch_away(
        self, index: int, candidate: ProviderCandidate, error: Exception
    ) -> bool:
        """把指针从 index 推进到下一个候选。返回 False 表示无处可切。"""
        with self._lock:
            if candidate.profile_id is not None:
                self._failed_profiles[candidate.profile_id] = str(error)
            self._all_attempts.append(
                FailoverAttempt(candidate.profile_id, candidate.name, str(error))
            )
            if self._exhausted:
                return False
            if self._index != index:
                # 其他线程已经切换过了，直接复用它选中的配置，不消耗切换次数。
                return True
            next_index = index + 1
            if next_index >= len(self._candidates) or self._switch_count >= self._max_switches:
                self._exhausted = True
                return False
            self._index = next_index
            self._switch_count += 1
            target = self._candidates[next_index]
            self._events.append(
                FailoverEvent(
                    from_profile_id=candidate.profile_id,
                    from_name=candidate.name,
                    to_profile_id=target.profile_id,
                    to_name=target.name,
                    error=str(error),
                    occurred_at=datetime.datetime.now(),
                )
            )
        return True
