import { useCallback, useEffect, useMemo, useState } from "react";
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
import { DownloadOutlined, ReloadOutlined, SearchOutlined } from "@ant-design/icons";
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

const RISK_COLORS: Record<string, string> = {
  高: "red",
  中: "orange",
  低: "green",
  需人工确认: "purple",
};

const MANUAL_OPTIONS = [
  { label: "需要人工确认", value: "是" },
  { label: "无需人工确认", value: "否" },
];

function confidenceLabel(value: number | null) {
  return value != null ? `${Math.round(value * 100)}%` : "-";
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
  const [keyword, setKeyword] = useState("");
  const [selectedRow, setSelectedRow] = useState<ReportTableRow | null>(null);

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
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(lowerKeyword));
    });
  }, [keyword, manualCheck, risk, rows, section]);

  const submitReview = async (status: ReviewStatus) => {
    if (!selectedRow) return;
    try {
      await reviewDiff(selectedRow.diff_id, { review_status: status });
      message.success("审核结果已保存");
      setSelectedRow(null);
      await loadData();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存审核结果失败");
    }
  };

  const columns: ColumnsType<ReportTableRow> = [
    {
      title: "章节",
      dataIndex: "section",
      key: "section",
      width: 150,
      render: (value: string) => <Tag color="blue">{value}</Tag>,
    },
    { title: "序号", dataIndex: "section_index", key: "section_index", width: 80 },
    { title: "类别", dataIndex: "category", key: "category", width: 120 },
    {
      title: "风险/优先级",
      dataIndex: "risk_label",
      key: "risk_label",
      width: 130,
      render: (value: string) => <Tag color={RISK_COLORS[value] || "default"}>{value}</Tag>,
    },
    { title: "基准内容", dataIndex: "base_content", key: "base_content", width: 260, ellipsis: true },
    { title: "对比内容", dataIndex: "compare_content", key: "compare_content", width: 260, ellipsis: true },
    { title: "结论/差异/原因", dataIndex: "conclusion", key: "conclusion", width: 320, ellipsis: true },
    { title: "影响范围", dataIndex: "impact", key: "impact", width: 220, ellipsis: true },
    { title: "建议动作", dataIndex: "suggestion", key: "suggestion", width: 240, ellipsis: true },
    { title: "证据/核对区域", dataIndex: "evidence", key: "evidence", width: 220, ellipsis: true },
    {
      title: "置信度",
      dataIndex: "confidence",
      key: "confidence",
      width: 90,
      render: confidenceLabel,
    },
    {
      title: "需人工确认",
      dataIndex: "manual_check_label",
      key: "manual_check_label",
      width: 120,
      render: (value: string) => value === "是" ? <Tag color="purple">是</Tag> : <Tag>否</Tag>,
    },
  ];

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
        <div className="toolbar-row">
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
          <Space>
            <Text type="secondary">{task?.task_no}</Text>
            <Button type="primary" icon={<DownloadOutlined />} onClick={() => window.open(getExportUrl(numericTaskId, "diffs"))}>
              导出差异报告
            </Button>
          </Space>
        </div>
        <Table
          rowKey="diff_id"
          columns={columns}
          dataSource={filteredRows}
          loading={loading}
          pagination={{ pageSize: 15, showSizeChanger: true }}
          scroll={{ x: 2400 }}
          size="middle"
          locale={{ emptyText: task?.status === "completed" ? "暂无差异报告数据" : "任务完成后可查看完整差异报告" }}
          onRow={(record) => ({ onClick: () => setSelectedRow(record) })}
        />
      </Card>
      <Drawer
        title={selectedRow ? `报告详情 #${selectedRow.diff_id}` : "报告详情"}
        open={Boolean(selectedRow)}
        onClose={() => setSelectedRow(null)}
        width={620}
        extra={
          <Space>
            <Button onClick={() => void submitReview("ignored")}>忽略</Button>
            <Button danger onClick={() => void submitReview("misjudged")}>AI 误判</Button>
            <Button type="primary" onClick={() => void submitReview("confirmed")}>确认差异</Button>
          </Space>
        }
      >
        {selectedRow && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="章节">{selectedRow.section}</Descriptions.Item>
            <Descriptions.Item label="序号">{selectedRow.section_index}</Descriptions.Item>
            <Descriptions.Item label="类别">{selectedRow.category || "-"}</Descriptions.Item>
            <Descriptions.Item label="风险/优先级">
              <Tag color={RISK_COLORS[selectedRow.risk_label] || "default"}>{selectedRow.risk_label}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="基准内容">{selectedRow.base_content || "-"}</Descriptions.Item>
            <Descriptions.Item label="对比内容">{selectedRow.compare_content || "-"}</Descriptions.Item>
            <Descriptions.Item label="结论/差异/原因">{selectedRow.conclusion || "-"}</Descriptions.Item>
            <Descriptions.Item label="影响范围">{selectedRow.impact || "-"}</Descriptions.Item>
            <Descriptions.Item label="建议动作">{selectedRow.suggestion || "-"}</Descriptions.Item>
            <Descriptions.Item label="证据/核对区域">{selectedRow.evidence || "-"}</Descriptions.Item>
            <Descriptions.Item label="置信度">{confidenceLabel(selectedRow.confidence)}</Descriptions.Item>
            <Descriptions.Item label="需人工确认">{selectedRow.manual_check_label}</Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </Space>
  );
}
