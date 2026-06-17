from __future__ import annotations

import json
import uuid
import time
import base64
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List

import httpx
from PIL import Image

from app.ai.base import VisionModelProvider
from app.core.config import get_settings


class OpenAICompatibleProvider(VisionModelProvider):
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: int | None = None,
        max_retries: int | None = None,
    ):
        settings = get_settings()
        self._chat_completions_url = self._normalize_chat_completions_url(base_url or settings.AI_BASE_URL)
        self._api_key = api_key or settings.AI_API_KEY
        self._model = model or settings.AI_MODEL
        self._timeout = timeout_seconds or settings.AI_TIMEOUT_SECONDS
        self._max_retries = max_retries or settings.AI_MAX_RETRIES
        self._image_max_edge = settings.AI_IMAGE_MAX_EDGE
        self._image_jpeg_quality = settings.AI_IMAGE_JPEG_QUALITY
        self._client = self._new_client()
        self._output_dir = settings.get_storage_path("ai_outputs")

    def detect_layout(
        self, page_no: int, image_width: int, image_height: int, image_path: str | None = None
    ) -> Dict[str, Any]:
        system_prompt = (
            "你是产品PDF图纸审核助手，只输出合法JSON。识别这张图纸的重点区域。"
        )
        user_prompt = (
            f"请分析第{page_no}页图纸（尺寸{image_width}x{image_height}px）的布局结构，"
            "识别出所有重点区域（主视图、BOM、技术要求、接线表、标题栏等），"
            "对每个区域给出bbox坐标（像素，格式{x, y, width, height}）、区域名称、类型和识别原因。"
            "严格按照以下JSON格式输出："
            '{"page_no": 页码, "page_summary": "页面概述", '
            '"regions": [{"region_type": "类型", "region_name": "名称", '
            '"bbox": {"x": 0, "y": 0, "width": 0, "height": 0}, '
            '"reason": "原因", "confidence": 0.0}], "risks": ["风险描述"]}'
        )
        image_data = self._encode_image(image_path) if image_path and Path(image_path).exists() else None
        raw = self._call_api(system_prompt, user_prompt, image_data)
        return self._parse_json(raw, "layout")

    def extract_elements(
        self, image_path: str, context: str, region_type: str
    ) -> Dict[str, Any]:
        system_prompt = "你是产品PDF图纸审核助手，只输出合法JSON。提取图纸中的元素信息。"

        image_data = self._encode_image(image_path) if Path(image_path).exists() else None

        if context == "full_page":
            user_text = (
                f"请从整页图纸中提取所有图纸元素（尺寸、结构、BOM、接线、技术要求等）。"
            )
        else:
            user_text = (
                f"请从{region_type}区域的裁剪图中提取元素信息。"
            )

        user_text += (
            '输出格式：{"elements": [{"category": "类别", "element_name": "名称", '
            '"raw_value": "原始值", "normalized_value": "标准化值", "unit": "单位", '
            '"importance": "high/medium/low", "confidence": 0.0, '
            '"need_manual_check": false, "evidence": "依据"}]}'
        )

        raw = self._call_api(system_prompt, user_text, image_data)
        return self._parse_json(raw, "elements")

    def compare_elements(
        self, base_elements: List[Dict[str, Any]], compare_elements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        system_prompt = "你是产品PDF图纸审核助手，只输出合法JSON。对比两份图纸的元素清单。"

        user_text = (
            f"基准PDF元素：{json.dumps(base_elements, ensure_ascii=False)}\n\n"
            f"对比PDF元素：{json.dumps(compare_elements, ensure_ascii=False)}\n\n"
            "请进行语义匹配和差异分析，输出格式：\n"
            '{"matches": [{"match_type": "exact/semantic", '
            '"base_element_ref": "ref", "compare_element_ref": "ref", '
            '"match_reason": "原因", "confidence": 0.0}], '
            '"diffs": [{"risk_level": "high/medium/low/manual_check", '
            '"diff_category": "类别", "base_content": "基准内容", '
            '"compare_content": "对比内容", "diff_summary": "差异说明", '
            '"impact": "影响", "suggestion": "建议", '
            '"confidence": 0.0, "need_manual_check": true}]}'
        )

        raw = self._call_api(system_prompt, user_text)
        return self._parse_json(raw, "comparison")

    def _encode_image(self, image_path: str) -> str:
        Image.MAX_IMAGE_PIXELS = None
        with Image.open(image_path) as image:
            image = image.convert("RGB")
            longest_edge = max(image.size)
            if longest_edge > self._image_max_edge:
                scale = self._image_max_edge / longest_edge
                new_size = (
                    max(1, int(image.width * scale)),
                    max(1, int(image.height * scale)),
                )
                image = image.resize(new_size, Image.Resampling.LANCZOS)

            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=self._image_jpeg_quality, optimize=True)
            b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{b64}"

    def _call_api(
        self, system_prompt: str, user_text: str, image_data_url: str | None = None
    ) -> str:
        messages = [{"role": "system", "content": system_prompt}]

        user_content: List[Dict[str, Any]] = [{"type": "text", "text": user_text}]
        if image_data_url:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": image_data_url},
            })

        messages.append({"role": "user", "content": user_content})

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.1,
        }

        last_error = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._client.post(
                    self._chat_completions_url,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                try:
                    resp.raise_for_status()
                except Exception as exc:
                    body = getattr(resp, "text", "")
                    if body:
                        raise Exception(f"{exc}; response body: {body[:1000]}") from exc
                    raise
                content = resp.json()["choices"][0]["message"]["content"]
                self._save_raw_output(system_prompt[:30], content)
                return content
            except Exception as e:
                last_error = e
                if attempt < self._max_retries:
                    if self._is_transport_error(e):
                        self._reset_client()
                    time.sleep(1 * (attempt + 1))
                else:
                    raise Exception(
                        f"AI调用失败（已重试{self._max_retries}次）: {self._format_error(last_error)}"
                    ) from last_error

        raise Exception(f"AI调用失败: {last_error}")

    def _new_client(self) -> httpx.Client:
        return httpx.Client(timeout=self._timeout)

    def _reset_client(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            close()
        self._client = self._new_client()

    def _is_transport_error(self, exc: Exception) -> bool:
        if isinstance(exc, httpx.TransportError):
            return True
        text = str(exc).lower()
        return any(
            marker in text
            for marker in [
                "unexpected_eof",
                "server disconnected",
                "connection reset",
                "remote protocol",
                "ssl",
            ]
        )

    def _format_error(self, exc: Exception | None) -> str:
        if exc is None:
            return "未知错误"
        message = str(exc)
        if self._is_transport_error(exc):
            return (
                f"AI网络连接中断: {message}。请检查 AI Base URL、网络代理/防火墙和服务商可用性，"
                "稍后可点击重试任务"
            )
        return message

    def _parse_json(self, raw: str, context: str) -> Dict[str, Any]:
        try:
            raw = raw.strip()
            if raw.startswith("```") and raw.endswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1]) if len(lines) >= 3 else raw
            elif raw.startswith("```json"):
                raw = raw[7:]
                if raw.endswith("```"):
                    raw = raw[:-3]
            return json.loads(raw)
        except json.JSONDecodeError as e:
            self._save_raw_output(f"parse_error_{context}", raw)
            raise Exception(f"AI输出JSON解析失败 ({context}): {e}\n原始输出: {raw[:500]}") from e

    def _normalize_chat_completions_url(self, base_url: str) -> str:
        url = base_url.rstrip("/")
        if url.endswith("/chat/completions"):
            return url
        return f"{url}/chat/completions"

    def _save_raw_output(self, label: str, content: str) -> None:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4().hex[:8]}_{label}.json"
        filepath = self._output_dir / filename
        filepath.write_text(content, encoding="utf-8")
