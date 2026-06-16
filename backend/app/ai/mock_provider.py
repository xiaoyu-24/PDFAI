from __future__ import annotations

import random
import hashlib
from typing import Any, Dict, List

from app.ai.base import VisionModelProvider


class MockVisionProvider(VisionModelProvider):
    def __init__(self, seed: int = 42):
        self._rng = random.Random(seed)

    def detect_layout(
        self, page_no: int, image_width: int, image_height: int, image_path: str | None = None
    ) -> Dict[str, Any]:
        self._rng.seed(hashlib.md5(f"layout_{page_no}".encode()).hexdigest())
        regions = []
        y_cursor = int(image_height * 0.05)

        region_configs = [
            ("main_view", "主视图", 0.04, 0.40),
            ("p1_connector", "P1端连接器", 0.46, 0.08),
            ("p2_tail", "P2端尾部处理", 0.56, 0.08),
            ("wiring_table", "接线定义表", 0.66, 0.10),
            ("bom_table", "BOM物料清单", 0.78, 0.08),
            ("technical_requirements", "技术要求", 0.88, 0.06),
        ]

        for region_type, region_name, y_ratio, h_ratio in region_configs:
            y = int(image_height * y_ratio)
            h = int(image_height * h_ratio)
            x = int(image_width * 0.03)
            w = image_width - 2 * x

            confidence = round(self._rng.uniform(0.72, 0.98), 2)
            regions.append({
                "region_type": region_type,
                "region_name": region_name,
                "bbox": {"x": x, "y": y, "width": w, "height": h},
                "reason": self._reason_for(region_type),
                "confidence": confidence,
            })

        return {
            "page_no": page_no,
            "page_summary": f"产品图纸第{page_no}页，包含主视图、BOM、技术要求等区域。",
            "regions": regions,
            "risks": ["局部文字密集区域建议重点审核"],
        }

    def _reason_for(self, region_type: str) -> str:
        reasons = {
            "main_view": "包含产品整体结构和主要尺寸标注",
            "p1_connector": "包含连接器端面形态和针脚配置",
            "p2_tail": "包含剥线长度、镀锡和热缩管规格",
            "wiring_table": "包含线色定义和P1/P2对应关系",
            "bom_table": "包含物料名称、规格、用量和单位",
            "technical_requirements": "包含测试标准、材料要求和包装规范",
        }
        return reasons.get(region_type, "需要重点识别的区域")

    def extract_elements(
        self, image_path: str, context: str, region_type: str
    ) -> Dict[str, Any]:
        hash_val = hashlib.md5(f"{image_path}_{context}_{region_type}".encode()).hexdigest()
        self._rng.seed(int(hash_val[:8], 16))

        count = self._rng.randint(3, 8) if context == "region" else self._rng.randint(8, 15)
        elements = []
        for i in range(count):
            elem = self._generate_element(i, region_type)
            if context == "full_page":
                elem["confidence"] = round(elem["confidence"] * 0.85, 2)
            elements.append(elem)

        return {"elements": elements}

    def _generate_element(self, index: int, region_type: str) -> Dict[str, Any]:
        templates = {
            "main_view": [
                ("尺寸", "总长", "L=1200mm", "1200", "mm", "high"),
                ("尺寸", "宽度", "W=800mm", "800", "mm", "high"),
                ("尺寸", "高度", "H=150mm", "150", "mm", "medium"),
                ("结构", "产品形态", "直式线束", "直式线束", "", "high"),
                ("基础信息", "产品名称", "USB-C to USB-A Cable", "", "", "high"),
            ],
            "bom_table": [
                ("BOM", "USB-C连接器", "P1-CON-001", "", "pcs", "high"),
                ("BOM", "USB-A连接器", "P2-CON-002", "", "pcs", "high"),
                ("BOM", "屏蔽线缆", "AWG28 x 4C", "", "mm", "high"),
                ("BOM", "热缩管", "Φ3.0mm 黑色", "", "mm", "medium"),
                ("BOM", "标签", "PET白标 30x15mm", "", "pcs", "low"),
            ],
            "wiring_table": [
                ("接线", "VCC线色", "红色", "红", "", "high"),
                ("接线", "GND线色", "黑色", "黑", "", "high"),
                ("接线", "D+信号", "绿色", "绿", "", "high"),
                ("接线", "D-信号", "白色", "白", "", "high"),
            ],
            "technical_requirements": [
                ("技术要求", "耐压测试", "DC 500V 1min", "500V", "V", "high"),
                ("技术要求", "绝缘电阻", "≥100MΩ", "100", "MΩ", "high"),
                ("技术要求", "工作温度", "-20°C ~ +80°C", "-20~80", "°C", "medium"),
                ("技术要求", "RoHS", "符合RoHS 2.0", "", "", "medium"),
            ],
        }

        defaults = [
            ("基础信息", f"参数{index + 1}", f"值{index + 1}", "", "", "medium"),
        ]
        options = templates.get(region_type, defaults)
        idx = index % len(options)
        category, name, raw, normalized, unit, importance = options[idx]

        return {
            "category": category,
            "element_name": name,
            "raw_value": raw,
            "normalized_value": normalized,
            "unit": unit,
            "importance": importance,
            "confidence": round(self._rng.uniform(0.75, 0.98), 2),
            "need_manual_check": False,
            "evidence": f"从{region_type}区域识别",
        }

    def compare_elements(
        self, base_elements: List[Dict[str, Any]], compare_elements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        self._rng.seed(42)

        matches = []
        diffs = []

        if not base_elements and not compare_elements:
            return {"matches": [], "diffs": []}

        base_lookup = {e["element_name"]: e for e in base_elements}
        compare_lookup = {e["element_name"]: e for e in compare_elements}
        base_names = set(base_lookup.keys())
        compare_names = set(compare_lookup.keys())

        common = base_names & compare_names

        for name in common:
            base = base_lookup[name]
            compare = compare_lookup[name]
            match_ref = f"match:{name}"
            matches.append({
                "match_type": "semantic",
                "base_element_ref": base.get("id", f"base:{name}"),
                "compare_element_ref": compare.get("id", f"compare:{name}"),
                "match_reason": f"名称语义匹配: {name}",
                "confidence": 0.92,
            })

            if base.get("raw_value") != compare.get("raw_value") or base.get("normalized_value") != compare.get("normalized_value"):
                risk = "high" if base.get("importance") == "high" or compare.get("importance") == "high" else "medium"
                diffs.append({
                    "base_element_ref": base.get("id", f"base:{name}"),
                    "compare_element_ref": compare.get("id", f"compare:{name}"),
                    "risk_level": risk,
                    "diff_category": base.get("category", "其他"),
                    "base_content": base.get("raw_value", ""),
                    "compare_content": compare.get("raw_value", ""),
                    "diff_summary": f"{name}存在差异: {base.get('raw_value','')} vs {compare.get('raw_value','')}",
                    "impact": "可能影响产品质量和客户验收",
                    "suggestion": "建议人工确认是否为允许的设计变更",
                    "confidence": round(self._rng.uniform(0.78, 0.95), 2),
                    "need_manual_check": True,
                })
            else:
                diffs.append({
                    "base_element_ref": base.get("id", f"base:{name}"),
                    "compare_element_ref": compare.get("id", f"compare:{name}"),
                    "risk_level": "low",
                    "diff_category": base.get("category", "其他"),
                    "base_content": base.get("raw_value", ""),
                    "compare_content": compare.get("raw_value", ""),
                    "diff_summary": f"{name}内容一致",
                    "impact": "无影响",
                    "suggestion": "无需操作",
                    "confidence": 0.95,
                    "need_manual_check": False,
                })

        for name in base_names - compare_names:
            base = base_lookup[name]
            diffs.append({
                "base_element_ref": base.get("id", f"base:{name}"),
                "compare_element_ref": None,
                "risk_level": "manual_check",
                "diff_category": base.get("category", "其他"),
                "base_content": base.get("raw_value", ""),
                "compare_content": "",
                "diff_summary": f"{name} 仅在基准PDF中存在",
                "impact": "需确认是否为新增或遗漏",
                "suggestion": "人工确认是否应在对比PDF中体现",
                "confidence": 0.95,
                "need_manual_check": True,
            })

        for name in compare_names - base_names:
            compare = compare_lookup[name]
            diffs.append({
                "base_element_ref": None,
                "compare_element_ref": compare.get("id", f"compare:{name}"),
                "risk_level": "manual_check",
                "diff_category": compare.get("category", "其他"),
                "base_content": "",
                "compare_content": compare.get("raw_value", ""),
                "diff_summary": f"{name} 仅在对比PDF中存在",
                "impact": "需确认是否为新增或遗漏",
                "suggestion": "人工确认是否应在基准PDF中体现",
                "confidence": 0.95,
                "need_manual_check": True,
            })

        return {"matches": matches, "diffs": diffs}
