from __future__ import annotations

from dataclasses import dataclass

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
    "证据/核对区域",
    "置信度",
    "需人工确认",
]

SECTION_ORDER = ["已确认一致项", "实质差异项", "不确定项", "识别不足项", "需人工确认项"]

RISK_LABELS = {
    "high": "高",
    "medium": "中",
    "low": "低",
    "manual_check": "需人工确认",
}


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
            self.evidence,
            self.confidence if self.confidence is not None else "",
            self.manual_check_label,
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
        )

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
