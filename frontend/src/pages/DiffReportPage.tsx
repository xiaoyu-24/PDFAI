import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Button,
  Card,
  Descriptions,
  Drawer,
  Input,
  Row,
  Col,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  ArrowLeftOutlined,
  DownloadOutlined,
  FullscreenOutlined,
  ReloadOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { useParams } from "react-router-dom";
import {
  getExportUrl,
  getTask,
  getTaskDiffSummary,
  getTaskReportTable,
  reviewDiff,
} from "../api/tasks";
import PageBackButton from "../components/PageBackButton";
import type { CompareTask, DiffSummary, ReportTableRow, ReviewStatus } from "../types";

const { Text } = Typography;

const MANUAL_OPTIONS = [
  { label: "需要人工确认", value: "是" },
  { label: "无需人工确认", value: "否" },
];

const REVIEW_STATUS_OPTIONS = [
  { label: "待审核", value: "pending" },
  { label: "已确认", value: "confirmed" },
  { label: "已忽略", value: "ignored" },
  { label: "AI误判", value: "misjudged" },
  { label: "已修改", value: "modified" },
];

function confidenceLabel(value: number | null) {
  return value != null ? `${Math.round(value * 100)}%` : "-";
}

function compareText(a?: string | null, b?: string | null) {
  return String(a || "").localeCompare(String(b || ""), "zh-Hans-CN");
}

function renderHighlightedConclusion(row: ReportTableRow) {
  const text = row.conclusion || "-";
  const highlights = row.conclusion_highlights || [];
  if (!row.conclusion || highlights.length === 0) return text;

  const parts: ReactNode[] = [];
  let cursor = 0;
  highlights
    .filter((range) => range.start >= 0 && range.end > range.start && range.start < text.length)
    .sort((a, b) => a.start - b.start)
    .forEach((range, index) => {
      const start = Math.max(cursor, range.start);
      const end = Math.min(text.length, range.end);
      if (start > cursor) {
        parts.push(text.slice(cursor, start));
      }
      if (end > start) {
        parts.push(
          <mark className="report-highlight" key={`${start}-${end}-${index}`}>
            {text.slice(start, end)}
          </mark>
        );
        cursor = end;
      }
    });
  if (cursor < text.length) {
    parts.push(text.slice(cursor));
  }
  return parts.length > 0 ? parts : text;
}

export default function DiffReportPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const numericTaskId = taskId ? Number(taskId) : NaN;
  const [task, setTask] = useState<CompareTask | null>(null);
  const [summary, setSummary] = useState<DiffSummary | null>(null);
  const [rows, setRows] = useState<ReportTableRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [section, setSection] = useState<string | undefined>();
  const [risk, setRisk] = useState<string | undefined>();
  const [manualCheck, setManualCheck] = useState<string | undefined>();
  const [reviewStatus, setReviewStatus] = useState<ReviewStatus | undefined>();
  const [keyword, setKeyword] = useState("");
  const [selectedRow, setSelectedRow] = useState<ReportTableRow | null>(null);
  const [reviewingStatus, setReviewingStatus] = useState<ReviewStatus | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const loadData = useCallback(async () => {
    if (!Number.isFinite(numericTaskId)) return;
    setLoading(true);
    try {
      const [nextTask, nextReport, nextSummary] = await Promise.all([
        getTask(numericTaskId),
        getTaskReportTable(numericTaskId),
        getTaskDiffSummary(numericTaskId),
      ]);
      setTask(nextTask);
      setRows(nextReport.rows);
      setSummary(nextSummary);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "获取差异报告失败");
    } finally {
      setLoading(false);
    }
  }, [numericTaskId]);

  useEffect(() => {
    queueMicrotask(() => {
      void loadData();
    });
  }, [loadData]);

  const sections = useMemo(
    () => Array.from(new Set(rows.map((row) => row.section))).filter(Boolean),
    [rows]
  );

  const riskOptions = useMemo(
    () => Array.from(new Set(rows.map((row) => row.risk_label))).filter(Boolean),
    [rows]
  );

  const filteredRows = useMemo(() => {
    const lowerKeyword = keyword.trim().toLowerCase();
    return rows.filter((row) => {
      if (section && row.section !== section) return false;
      if (risk && row.risk_label !== risk) return false;
      if (manualCheck && row.manual_check_label !== manualCheck) return false;
      if (reviewStatus && row.review_status !== reviewStatus) return false;
      if (!lowerKeyword) return true;
      return [
        row.section,
        row.category,
        row.base_content,
        row.compare_content,
        row.conclusion,
        row.impact,
        row.suggestion,
        row.evidence,
        row.review_status_label,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(lowerKeyword));
    });
  }, [keyword, manualCheck, reviewStatus, risk, rows, section]);

  const submitReview = async (status: ReviewStatus) => {
    if (!selectedRow) return;
    try {
      setReviewingStatus(status);
      await reviewDiff(selectedRow.diff_id, { review_status: status });
      const [nextReport, nextSummary] = await Promise.all([
        getTaskReportTable(numericTaskId),
        getTaskDiffSummary(numericTaskId),
      ]);
      setRows(nextReport.rows);
      setSummary(nextSummary);
      setSelectedRow(nextReport.rows.find((row) => row.diff_id === selectedRow.diff_id) || selectedRow);
      message.success("审核结果已保存");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存审核结果失败");
    } finally {
      setReviewingStatus(null);
    }
  };

  const columns: ColumnsType<ReportTableRow> = [
    {
      title: "章节",
      dataIndex: "section",
      key: "section",
      width: 150,
      sorter: (a, b) => compareText(a.section, b.section),
      render: (value: string) => <Tag color="blue">{value}</Tag>,
    },
    {
      title: "序号",
      dataIndex: "section_index",
      key: "section_index",
      width: 80,
      sorter: (a, b) => a.section_index - b.section_index,
    },
    {
      title: "类别",
      dataIndex: "category",
      key: "category",
      width: 130,
      sorter: (a, b) => compareText(a.category, b.category),
    },
    {
      title: "风险/优先级",
      dataIndex: "risk_label",
      key: "risk_label",
      width: 130,
      sorter: (a, b) => compareText(a.risk_label, b.risk_label),
      render: (value: string) => value || "-",
    },
    { title: "基准内容", dataIndex: "base_content", key: "base_content", width: 320, ellipsis: true },
    { title: "对比内容", dataIndex: "compare_content", key: "compare_content", width: 320, ellipsis: true },
    {
      title: "结论/差异/原因",
      dataIndex: "conclusion",
      key: "conclusion",
      width: 380,
      ellipsis: true,
      render: (_value, record) => renderHighlightedConclusion(record),
    },
    { title: "影响范围", dataIndex: "impact", key: "impact", width: 260, ellipsis: true },
    { title: "建议动作", dataIndex: "suggestion", key: "suggestion", width: 300, ellipsis: true },
    {
      title: "置信度",
      dataIndex: "confidence",
      key: "confidence",
      width: 90,
      sorter: (a, b) => (a.confidence ?? -1) - (b.confidence ?? -1),
      render: confidenceLabel,
    },
    {
      title: "需人工确认",
      dataIndex: "manual_check_label",
      key: "manual_check_label",
      width: 120,
      sorter: (a, b) => compareText(a.manual_check_label, b.manual_check_label),
      render: (value: string) => value === "是" ? <Tag color="purple">是</Tag> : <Tag>否</Tag>,
    },
    { title: "证据/核对区域", dataIndex: "evidence", key: "evidence", width: 260, ellipsis: true },
    {
      title: "审核状态",
      dataIndex: "review_status_label",
      key: "review_status_label",
      width: 120,
      fixed: "right",
      sorter: (a, b) => compareText(a.review_status_label, b.review_status_label),
    },
  ];

  const closeFullscreenReport = () => {
    setIsFullscreen(false);
    setSelectedRow(null);
  };

  const renderReportToolbar = (fullscreen = false) => (
    <div className="toolbar-row report-toolbar">
      <Space wrap>
        <Select
          allowClear
          placeholder="报告章节"
          style={{ width: 170 }}
          value={section}
          onChange={setSection}
          options={sections.map((item) => ({ label: item, value: item }))}
        />
        <Select
          allowClear
          placeholder="风险/优先级"
          style={{ width: 150 }}
          value={risk}
          onChange={setRisk}
          options={riskOptions.map((item) => ({ label: item, value: item }))}
        />
        <Select
          allowClear
          placeholder="人工确认"
          style={{ width: 150 }}
          value={manualCheck}
          onChange={setManualCheck}
          options={MANUAL_OPTIONS}
        />
        <Select
          allowClear
          placeholder="审核状态"
          style={{ width: 150 }}
          value={reviewStatus}
          onChange={setReviewStatus}
          options={REVIEW_STATUS_OPTIONS}
        />
        <Input
          allowClear
          prefix={<SearchOutlined />}
          placeholder="搜索报告内容"
          value={keyword}
          onChange={(event) => setKeyword(event.target.value)}
          style={{ width: 240 }}
        />
        <Button icon={<ReloadOutlined />} onClick={() => void loadData()}>刷新</Button>
      </Space>
      <Space direction="vertical" size={8} align="end">
        <Text type="secondary">{task?.task_no}</Text>
        <Space wrap>
          {!fullscreen && (
            <Button icon={<FullscreenOutlined />} onClick={() => setIsFullscreen(true)}>
              全屏查看
            </Button>
          )}
          <Button type="primary" icon={<DownloadOutlined />} onClick={() => window.open(getExportUrl(numericTaskId, "diffs"))}>
            导出差异报告
          </Button>
        </Space>
      </Space>
    </div>
  );

  const renderReportTable = (fullscreen = false) => (
    <Table
      className="report-table-wrap"
      rowKey="diff_id"
      columns={columns}
      dataSource={filteredRows}
      loading={loading}
      pagination={{ pageSize: fullscreen ? 30 : 15, showSizeChanger: true }}
      scroll={{ x: 2920, y: fullscreen ? "calc(100vh - 250px)" : undefined }}
      size="middle"
      locale={{ emptyText: task?.status === "completed" ? "暂无差异报告数据" : "任务完成后可查看完整差异报告" }}
      onRow={(record) => ({ onClick: () => setSelectedRow(record) })}
    />
  );

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <PageBackButton fallbackTo="/diffs" />
      <Row gutter={16}>
        <Col xs={12} md={6}><Card><Statistic title="总差异" value={summary?.total_count ?? 0} /></Card></Col>
        <Col xs={12} md={6}><Card><Statistic title="高风险" value={summary?.risk_counts.high ?? 0} valueStyle={{ color: "#cf1322" }} /></Card></Col>
        <Col xs={12} md={6}><Card><Statistic title="待审核" value={summary?.review_counts.pending ?? 0} valueStyle={{ color: "#722ed1" }} /></Card></Col>
        <Col xs={12} md={6}><Card><Statistic title="已确认" value={summary?.review_counts.confirmed ?? 0} valueStyle={{ color: "#389e0d" }} /></Card></Col>
      </Row>
      <Card className="work-card">
        {renderReportToolbar()}
        {renderReportTable()}
      </Card>
      {isFullscreen && (
        <div className="fullscreen-report">
          <div className="fullscreen-report-header">
            <Button icon={<ArrowLeftOutlined />} onClick={closeFullscreenReport}>
              返回
            </Button>
            <Space direction="vertical" size={0}>
              <Text strong>差异报告</Text>
              <Text type="secondary">{task?.task_no}</Text>
            </Space>
          </div>
          <div className="fullscreen-report-body">
            {renderReportToolbar(true)}
            {renderReportTable(true)}
          </div>
        </div>
      )}
      <Drawer
        title={selectedRow ? `报告详情 #${selectedRow.diff_id}` : "报告详情"}
        open={Boolean(selectedRow)}
        onClose={() => setSelectedRow(null)}
        width={620}
        zIndex={isFullscreen ? 2100 : undefined}
        extra={
          <Space>
            <Button loading={reviewingStatus === "ignored"} onClick={() => void submitReview("ignored")}>忽略</Button>
            <Button danger loading={reviewingStatus === "misjudged"} onClick={() => void submitReview("misjudged")}>AI 误判</Button>
            <Button type="primary" loading={reviewingStatus === "confirmed"} onClick={() => void submitReview("confirmed")}>确认差异</Button>
          </Space>
        }
      >
        {selectedRow && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="章节">{selectedRow.section}</Descriptions.Item>
            <Descriptions.Item label="序号">{selectedRow.section_index}</Descriptions.Item>
            <Descriptions.Item label="类别">{selectedRow.category || "-"}</Descriptions.Item>
            <Descriptions.Item label="风险/优先级">{selectedRow.risk_label || "-"}</Descriptions.Item>
            <Descriptions.Item label="审核状态">{selectedRow.review_status_label || "-"}</Descriptions.Item>
            <Descriptions.Item label="基准内容">{selectedRow.base_content || "-"}</Descriptions.Item>
            <Descriptions.Item label="对比内容">{selectedRow.compare_content || "-"}</Descriptions.Item>
            <Descriptions.Item label="结论/差异/原因">{renderHighlightedConclusion(selectedRow)}</Descriptions.Item>
            <Descriptions.Item label="影响范围">{selectedRow.impact || "-"}</Descriptions.Item>
            <Descriptions.Item label="建议动作">{selectedRow.suggestion || "-"}</Descriptions.Item>
            <Descriptions.Item label="置信度">{confidenceLabel(selectedRow.confidence)}</Descriptions.Item>
            <Descriptions.Item label="需人工确认">{selectedRow.manual_check_label}</Descriptions.Item>
            <Descriptions.Item label="证据/核对区域">{selectedRow.evidence || "-"}</Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </Space>
  );
}
