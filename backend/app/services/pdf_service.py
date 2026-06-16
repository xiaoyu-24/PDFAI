from __future__ import annotations

import uuid
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

import fitz


class PdfRenderService:
    def __init__(self, dpi: int = 600):
        self.dpi = dpi

    def render_to_images(
        self,
        pdf_bytes: bytes,
        file_id: int,
        output_dir: Path,
    ) -> List[Dict[str, Any]]:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        results = []

        for page_idx in range(doc.page_count):
            page = doc[page_idx]
            zoom = self.dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)

            page_no = page_idx + 1
            filename = f"file_{file_id}_page_{page_no:04d}_{uuid.uuid4().hex[:8]}.png"
            output_path = output_dir / filename
            pix.save(str(output_path))

            results.append(
                {
                    "page_no": page_no,
                    "image_path": str(output_path),
                    "width": pix.width,
                    "height": pix.height,
                    "dpi": self.dpi,
                }
            )

        doc.close()
        return results

    def render_single_page(
        self,
        pdf_bytes: bytes,
        page_no: int,
        file_id: int,
        output_dir: Path,
    ) -> Dict[str, Any]:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if page_no < 1 or page_no > doc.page_count:
            doc.close()
            raise ValueError(f"页码 {page_no} 超出范围 (1-{doc.page_count})")

        page = doc[page_no - 1]
        zoom = self.dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        filename = f"file_{file_id}_page_{page_no:04d}_{uuid.uuid4().hex[:8]}.png"
        output_path = output_dir / filename
        pix.save(str(output_path))

        result = {
            "page_no": page_no,
            "image_path": str(output_path),
            "width": pix.width,
            "height": pix.height,
            "dpi": self.dpi,
        }

        doc.close()
        return result


def compute_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
