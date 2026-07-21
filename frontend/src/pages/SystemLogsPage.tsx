import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Col, Input, InputNumber, Pagination, Row, Segmented, Select, Space, Statistic, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { ReloadOutlined } from "@ant-design/icons";
import { getSystemLogs, getSystemLogSummary } from "../api/tasks";
import type { TaskLog, TaskLogSummary, LogViewMode, TaskLogListResponse, FullLogListResponse } from "../types";
import {
  ERROR_CATEGORY_OPTIONS,
  EVENT_TYPE_OPTIONS,
  LOG_LEVEL_OPTIONS,
  TASK_STAGE_OPTIONS,
  errorCategoryLabel,
  eventTypeLabel,
  logLevelLabel,
  taskStageLabel,
} from "../utils/logLabels";
import { useAutoRefresh } from "../hooks/useAutoRefresh";

const PAGE_SIZE = 50;

const VIEW_OPTIONS = [
  { value: "timeline", label: "简洁时间线" },
  { value: "exceptions", label: "仅看异常" },
  { value: "full", label: "完整日志" },
];

function formatDuration(value: number | null | undefined) {
  if (value === null || value === undefined) return "-";
  return value < 1000 ? `${value} ms` : `${(value / 1000).toFixed(1)} 秒`;
}

function formatFullLogValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "-";
  return String(value);
}

function isFullLogResponse(data: TaskLogListResponse | FullLogListResponse): data is FullLogListResponse {
  return "cursor" in data;
}

export default function SystemLogsPage() {
  const [viewMode, setViewMode] = useState<LogViewMode>("timeline");
  const [logs, setLogs] = useState<TaskLog[]>([]);
  const [summary, setSummary] = useState<TaskLogSummary | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [taskNo, setTaskNo] = useState("");
  const [level, setLevel] = useState<string | undefined>();
  const [errorCategory, setErrorCategory] = useState<string | undefined>();
  const [stage, setStage] = useState<string | undefined>();
  const [eventType, setEventType] = useState<string | undefined>();
  const [degraded, setDegraded] = useState<boolean | undefined>();
  const [minResponseTime, setMinResponseTime] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fullLogMessage, setFullLogMessage] = useState<string | null>(null);
  const [fullLogItems, setFullLogItems] = useState<Record<string, unknown>[]>([]);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const params = {
        view: viewMode,
        task_no: taskNo.trim() || undefined,
        level,
        error_category: errorCategory,
        stage,
        event_type: eventType,
        degraded,
        min_response_time_ms: minResponseTime ?? undefined,
      };
      const [list, nextSummary] = await Promise.all([
        getSystemLogs({ ...params, limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE }),
        viewMode !== "full" ? getSystemLogSummary(params) : Promise.resolve(null),
      ]);
      if (isFullLogResponse(list)) {
        setLogs([]);
        setFullLogItems(list.items);
        setTotal(list.total);
        setFullLogMessage(list.status_message || null);
      } else {
        setLogs(list.items);
        setFullLogItems([]);
        setTotal(list.total);
        setFullLogMessage(null);
      }
      if (nextSummary) setSummary(nextSummary);
      setError(null);
    } catch (loadError) {
      if (!silent) setError(loadError instanceof Error ? loadError.message : "获取系统日志失败");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [degraded, errorCategory, eventType, level, minResponseTime, page, stage, taskNo, viewMode]);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  const autoRefreshLogs = useCallback(() => load(true), [load]);
  useAutoRefresh(autoRefreshLogs);

  const columns: ColumnsType<TaskLog> = [
    { title: "时间", dataIndex: "created_at", width: 180, render: (value: string) => new Date(value).toLocaleString() },
    { title: "任务", dataIndex: "task_no", width: 190, render: (value: string | null) => value || "-" },
    { title: "阶段", dataIndex: "stage", width: 190, render: taskStageLabel },
    { title: "事件", dataIndex: "event_type", width: 110, render: eventTypeLabel },
    {
      title: "等级",
      dataIndex: "level",
      width: 90,
      render: (value: TaskLog["level"]) => <Tag color={value === "error" ? "red" : value === "warning" ? "orange" : "blue"}>{logLevelLabel(value)}</Tag>,
    },
    { title: "错误分类", dataIndex: "error_category", width: 120, render: errorCategoryLabel },
    { title: "响应时间", dataIndex: "response_time_ms", width: 120, render: formatDuration },
    { title: "消息", dataIndex: "message", ellipsis: true },
  ];

  const fullColumns: ColumnsType<Record<string, unknown>> = [
    { title: "时间", dataIndex: "timestamp", width: 180, render: formatFullLogValue },
    { title: "任务", dataIndex: "task_no", width: 190, render: formatFullLogValue },
    { title: "阶段", dataIndex: "stage", width: 190, render: (value) => taskStageLabel(formatFullLogValue(value)) },
    { title: "事件", dataIndex: "event_type", width: 110, render: (value) => eventTypeLabel(formatFullLogValue(value)) },
    { title: "等级", dataIndex: "level", width: 90, render: (value) => logLevelLabel(formatFullLogValue(value) as TaskLog["level"]) },
    { title: "消息", dataIndex: "message", ellipsis: true, render: formatFullLogValue },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      {error && <Alert type="error" showIcon message={error} />}
      <Segmented options={VIEW_OPTIONS} value={viewMode} onChange={(v) => { setViewMode(v as LogViewMode); setPage(1); }} />
      {viewMode !== "full" && (
        <Row gutter={[16, 16]}>
          <Col xs={12} md={4}><Card><Statistic title="日志总数" value={summary?.total ?? 0} /></Card></Col>
          <Col xs={12} md={4}><Card><Statistic title="错误" value={summary?.errors ?? 0} valueStyle={{ color: "#cf1322" }} /></Card></Col>
          <Col xs={12} md={4}><Card><Statistic title="超时" value={summary?.timeouts ?? 0} /></Card></Col>
          <Col xs={12} md={4}><Card><Statistic title="重试" value={summary?.retries ?? 0} /></Card></Col>
          <Col xs={12} md={4}><Card><Statistic title="降级" value={summary?.degraded ?? 0} /></Card></Col>
          <Col xs={12} md={4}><Card><Statistic title="P95 响应" value={formatDuration(summary?.p95_response_time_ms)} /></Card></Col>
        </Row>
      )}
      {viewMode === "full" && fullLogMessage && (
        <Alert type="info" showIcon message={fullLogMessage} />
      )}
      {viewMode === "full" && (
        <Card className="work-card">
          <Space wrap style={{ marginBottom: 16 }}>
            <Input.Search placeholder="任务编号" allowClear value={taskNo} onChange={(event) => setTaskNo(event.target.value)} onSearch={() => { setPage(1); void load(); }} style={{ width: 240 }} />
            <Button icon={<ReloadOutlined />} onClick={() => void load()}>刷新</Button>
          </Space>
          <Table<Record<string, unknown>>
            rowKey={(record, index) => `${formatFullLogValue(record.task_id)}-${formatFullLogValue(record.timestamp)}-${index}`}
            columns={fullColumns}
            dataSource={fullLogItems}
            loading={loading}
            pagination={false}
            scroll={{ x: 980 }}
          />
        </Card>
      )}
      {viewMode !== "full" && (
        <Card className="work-card">
          <Space wrap style={{ marginBottom: 16 }}>
            <Input.Search placeholder="任务编号" allowClear value={taskNo} onChange={(event) => setTaskNo(event.target.value)} onSearch={() => { setPage(1); void load(); }} style={{ width: 240 }} />
            {viewMode === "exceptions" && (
              <>
                <Select placeholder="日志等级" allowClear value={level} onChange={(value) => { setLevel(value); setPage(1); }} options={LOG_LEVEL_OPTIONS} style={{ width: 140 }} />
                <Select placeholder="错误分类" allowClear value={errorCategory} onChange={(value) => { setErrorCategory(value); setPage(1); }} options={ERROR_CATEGORY_OPTIONS} style={{ width: 160 }} />
                <Select placeholder="任务阶段" allowClear showSearch optionFilterProp="label" value={stage} onChange={(value) => { setStage(value); setPage(1); }} options={TASK_STAGE_OPTIONS} style={{ width: 190 }} />
                <Select placeholder="事件类型" allowClear value={eventType} onChange={(value) => { setEventType(value); setPage(1); }} options={EVENT_TYPE_OPTIONS} style={{ width: 150 }} />
                <Select placeholder="是否降级" allowClear value={degraded} onChange={(value) => { setDegraded(value); setPage(1); }} options={[{ value: true, label: "已降级" }, { value: false, label: "未降级" }]} style={{ width: 130 }} />
                <InputNumber placeholder="最小响应 ms" min={0} value={minResponseTime} onChange={(value) => { setMinResponseTime(value); setPage(1); }} style={{ width: 150 }} />
              </>
            )}
            <Button icon={<ReloadOutlined />} onClick={() => void load()}>刷新</Button>
          </Space>
          <Table<TaskLog> rowKey="id" columns={columns} dataSource={logs} loading={loading} pagination={false} scroll={{ x: 1200 }} expandable={{ expandedRowRender: (record) => record.error_detail || record.fallback_action || "无更多详情" }} />
          <Pagination current={page} pageSize={PAGE_SIZE} total={total} showSizeChanger={false} onChange={setPage} style={{ marginTop: 16, textAlign: "right" }} />
        </Card>
      )}
    </Space>
  );
}
