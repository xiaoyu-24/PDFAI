from __future__ import annotations

from dataclasses import dataclass
import re

from sqlalchemy.orm import Session

from app.models.models import CompareDiff


REPORT_COLUMNS = [
    "章节",
    "序号",
    "类别",
    "风险/优先级",
    "基准内容",
    "对比内容",
    "结论/差异/原因",
    "影响范围",
    "建议动作",
    "置信度",
    "需人工确认",
    "证据/核对区域",
]

SECTION_ORDER = ["已确认一致项", "实质差异项", "不确定项", "识别不足项", "需人工确认项"]

RISK_LABELS = {
    "high": "高",
    "medium": "中",
    "low": "低",
    "manual_check": "需人工确认",
}

REVIEW_STATUS_LABELS = {
    "pending": "待审核",
    "confirmed": "已确认",
    "ignored": "已忽略",
    "misjudged": "AI误判",
    "modified": "已修改",
}

REPORT_EXCLUDE_KEYWORDS = [
    "修订记录",
    "修订历史",
    "修改历史",
    "修改记录",
    "一般公差",
    "角度公差",
    "公差",
    "logo",
    "名字",
    "料号",
    "公司名称",
    "公司信息",
    "图纸编号",
    "图纸名称",
    "图号",
    "制造商",
    "厂商",
    "厂家",
    "生产商",
    "供应商名称",
    "供应商信息",
    "客户名称",
    "项目名称",
    "零件号",
    "图纸号",
    "part no",
    "dwg no",
    "绘图信息",
    "drawn by",
    "地址",
    "电话",
    "传真",
    "邮箱",
    "网址",
    "日期",
]

REPORT_EXCLUDE_CATEGORY_KEYWORDS = [
    "图纸元信息",
    "图纸标识",
    "材料标识",
    "文档控制",
    "变更记录",
    "产品信息",
    "标识信息",
    "标题栏",
]

PARAMETER_CATEGORY_KEYWORDS = [
    "尺寸",
    "结构",
    "技术要求",
    "性能",
    "加工",
    "BOM",
    "物料",
    "线长",
    "防水",
]

PARAMETER_FRAGMENT_RE = re.compile(
    r"(?:[A-Za-z]*\d+(?:\.\d+)?\s*(?:±\s*\d+(?:\.\d+)?)?\s*(?:mm|MM|cm|CM|m|M|%|°|度|V|A|W|Ω|pcs|PCS)?)"
    r"|(?:[Xx]\d+)"
    r"|(?:[\u4e00-\u9fa5A-Za-z0-9±+\-/%]*结构[\u4e00-\u9fa5A-Za-z0-9±+\-/%]*)"
)


@dataclass(frozen=True)
class ReportRow:
    section: str
    section_index: int
    category: str
    risk_label: str
    base_content: str
    compare_content: str
    conclusion: str
    impact: str
    suggestion: str
    evidence: str
    confidence: float | None
    manual_check_label: str
    diff_id: int
    review_status: str
    review_status_label: str
    conclusion_highlights: list[dict[str, int]]

    def as_excel_values(self) -> list:
        return [
            self.section,
            self.section_index,
            self.category,
            self.risk_label,
            self.base_content,
            self.compare_content,
            self.conclusion,
            self.impact,
            self.suggestion,
            self.confidence if self.confidence is not None else "",
            self.manual_check_label,
            self.evidence,
        ]

    def as_dict(self) -> dict:
        return {
            "section": self.section,
            "section_index": self.section_index,
            "category": self.category,
            "risk_label": self.risk_label,
            "base_content": self.base_content,
            "compare_content": self.compare_content,
            "conclusion": self.conclusion,
            "impact": self.impact,
            "suggestion": self.suggestion,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "manual_check_label": self.manual_check_label,
            "diff_id": self.diff_id,
            "review_status": self.review_status,
            "review_status_label": self.review_status_label,
            "conclusion_highlights": self.conclusion_highlights,
        }


class ReportService:
    def __init__(self, db: Session):
        self.db = db

    def build_diff_report_rows(self, task_id: int) -> list[ReportRow]:
        diffs = (
            self.db.query(CompareDiff)
            .filter(CompareDiff.compare_task_id == task_id)
            .order_by(CompareDiff.id.asc())
            .all()
        )
        grouped: dict[str, list[CompareDiff]] = {section: [] for section in SECTION_ORDER}
        for diff in diffs:
            if self._should_exclude(diff):
                continue
            grouped[self._classify_section(diff)].append(diff)

        rows: list[ReportRow] = []
        for section in SECTION_ORDER:
            for index, diff in enumerate(grouped[section], 1):
                rows.append(self._to_report_row(diff, section, index))
        return rows

    def _to_report_row(self, diff: CompareDiff, section: str, section_index: int) -> ReportRow:
        return ReportRow(
            section=section,
            section_index=section_index,
            category=diff.diff_category or "",
            risk_label=RISK_LABELS.get(diff.risk_level, diff.risk_level or ""),
            base_content=diff.base_content or "",
            compare_content=diff.compare_content or "",
            conclusion=diff.diff_summary or "",
            impact=diff.impact or "",
            suggestion=diff.suggestion or "",
            evidence=self._evidence_for(diff),
            confidence=diff.confidence,
            manual_check_label="是" if diff.need_manual_check else "否",
            diff_id=diff.id,
            review_status=diff.review_status or "",
            review_status_label=REVIEW_STATUS_LABELS.get(diff.review_status, diff.review_status or ""),
            conclusion_highlights=self._conclusion_highlights(diff),
        )

    def _should_exclude(self, diff: CompareDiff) -> bool:
        category = (diff.diff_category or "").lower()
        if any(keyword.lower() in category for keyword in REPORT_EXCLUDE_CATEGORY_KEYWORDS):
            return True
        text = self._diff_search_text(diff).lower()
        return any(keyword.lower() in text for keyword in REPORT_EXCLUDE_KEYWORDS)

    def _diff_search_text(self, diff: CompareDiff) -> str:
        values = [
            diff.diff_category,
            diff.base_content,
            diff.compare_content,
            diff.diff_summary,
            diff.impact,
            diff.suggestion,
        ]
        for element in [diff.base_element, diff.compare_element]:
            if not element:
                continue
            values.extend([
                element.category,
                element.element_name,
                element.raw_value,
                element.region_desc,
            ])
        return " ".join(value for value in values if value)

    def _conclusion_highlights(self, diff: CompareDiff) -> list[dict[str, int]]:
        conclusion = diff.diff_summary or ""
        if not conclusion or not self._is_parameter_diff(diff):
            return []

        ranges = [
            {"start": match.start(), "end": match.end()}
            for match in PARAMETER_FRAGMENT_RE.finditer(conclusion)
            if match.start() < match.end()
        ]
        if ranges:
            return ranges
        return [{"start": 0, "end": len(conclusion)}]

    def _is_parameter_diff(self, diff: CompareDiff) -> bool:
        text = self._diff_search_text(diff)
        if PARAMETER_FRAGMENT_RE.search(text):
            return True
        return any(keyword in text for keyword in PARAMETER_CATEGORY_KEYWORDS)

    def _classify_section(self, diff: CompareDiff) -> str:
        text = " ".join(
            value
            for value in [
                diff.diff_summary,
                diff.base_content,
                diff.compare_content,
                diff.impact,
                diff.suggestion,
            ]
            if value
        )
        if not diff.base_content or not diff.compare_content or "识别不足" in text or "未提取" in text:
            return "识别不足项"
        if diff.need_manual_check and any(keyword in text for keyword in ["无法确认", "需核对", "描述不完整"]):
            return "不确定项"
        if diff.risk_level in {"high", "medium"}:
            return "实质差异项"
        if diff.risk_level == "low" and not diff.need_manual_check:
            return "已确认一致项"
        return "需人工确认项"

    def _evidence_for(self, diff: CompareDiff) -> str:
        for element in [diff.base_element, diff.compare_element]:
            if element and element.region_desc:
                return element.region_desc
            if element and element.source_image_path:
                return element.source_image_path
        return ""
