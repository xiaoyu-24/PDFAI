from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class VisionModelProvider(ABC):
    @abstractmethod
    def detect_layout(
        self, page_no: int, image_width: int, image_height: int, image_path: str | None = None
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def extract_elements(
        self, image_path: str, context: str, region_type: str
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def compare_elements(
        self, base_elements: List[Dict[str, Any]], compare_elements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        ...
