from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict

from PIL import Image


class CropService:
    def __init__(self, padding_ratio: float = 0.06):
        self.padding_ratio = padding_ratio

    def crop_region(
        self,
        image_path: str,
        bbox: Dict[str, int],
        region_name: str,
        file_id: int,
        page_id: int,
        page_no: int,
        output_dir: Path,
    ) -> Dict[str, Any]:
        img = Image.open(image_path)
        img_w, img_h = img.size

        x = max(0, bbox["x"])
        y = max(0, bbox["y"])
        w = bbox["width"]
        h = bbox["height"]

        pad_w = int(w * self.padding_ratio)
        pad_h = int(h * self.padding_ratio)

        x1 = max(0, x - pad_w)
        y1 = max(0, y - pad_h)
        x2 = min(img_w, x + w + pad_w)
        y2 = min(img_h, y + h + pad_h)

        if x1 >= x2 or y1 >= y2:
            filename = f"file_{file_id}_page_{page_no:04d}_region_{uuid.uuid4().hex[:8]}.png"
            output_path = output_dir / filename
            img.save(str(output_path))
            return self._build_result(str(output_path), region_name, bbox)

        cropped = img.crop((x1, y1, x2, y2))
        filename = f"file_{file_id}_page_{page_no:04d}_region_{uuid.uuid4().hex[:8]}.png"
        output_path = output_dir / filename
        cropped.save(str(output_path))

        return self._build_result(str(output_path), region_name, bbox)

    def _build_result(
        self, crop_path: str, region_name: str, bbox: Dict[str, int]
    ) -> Dict[str, Any]:
        return {
            "region_name": region_name,
            "crop_image_path": crop_path,
            "bbox": bbox,
        }
