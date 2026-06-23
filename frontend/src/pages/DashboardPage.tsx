import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Card, Input, Popconfirm, Select, Space, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  DeleteOutlined,
  ExportOutlined,
  FileSearchOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { Link } from "react-router-dom";
import { deleteTask, getExportUrl, getSettings, listTasks, pauseTask, resumeTask, retryTask } from "../api/tasks";
import type { TaskListItem } from "../types";

const { Text } = Typography;

const STATUS_LABELS: Record<string, string> = {
  queued: "排队中",
  paused: "已暂停",
  uploaded: "已上传",
  rendering_pages: "PDF 转图",
  rendered: "转图完成",
  detecting_regions: "识别区域",
  regions_detected: "区域完成",
  cropping_regions: "裁剪区域",
  regions_cropped: "裁剪完成",
  extracting_full_page_elements: "整页识别",
  full_page_elements_skipped: "跳过整页",
  extracting_region_elements: "区域识别",
  region_elements_skipped: "跳过区域",
  merging_elements: "合并元素",
  saving_elements: "保存元素",
  comparing_elements: "生成差异",
  saving_diffs: "保存差异",
  completed: "已完成",
  failed: "失败",
};

const ACTIVE_STATUSES = new Set([
  "queued",
  "uploaded",
  "rendering_pages",
  "rendered",
  "detecting_regions",
  "regions_detected",
  "cropping_regions",
  "regions_cropped",
  "extracting_full_page_elements",
  "full_page_elements_skipped",
  "extracting_region_elements",
  "region_elements_skipped",
  "merging_elements",
  "saving_elements",
  "comparing_elements",
  "saving_diffs",
]);

function statusColor(status: string) {
  if (status === "completed") return "green";
  if (status === "failed") return "red";
  if (status === "paused") return "orange";
  if (status === "queued") return "cyan";
  if (status === "uploaded") return "default";
  return "blue";
}

function formatTime(value: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

export default function DashboardPage() {
  const [tasks, setTasks] = useState<TaskListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | undefined>();
  const [keyword, setKeyword] = useState("");
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);
  const [taskMaxWorkers, setTaskMaxWorkers] = useState(2);

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    try {
      const result = await listTasks({
        status,
        keyword: keyword.trim() || undefined,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      });
      setTasks(result.items);
      setTotal(result.total);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "获取任务列表失败");
    } finally {
      setLoading(false);
    }
  }, [keyword, page, pageSize, status]);

  useEffect(() => {
    queueMicrotask(() => {
      void fetchTasks();
    });
  }, [fetchTasks]);

  useEffect(() => {
    queueMicrotask(async () => {
      try {
        const settings = await getSettings();
        setTaskMaxWorkers(settings.task_max_workers);
      } catch {
        setTaskMaxWorkers(2);
      }
    });
  }, []);

  const handlePause = useCallback(async (taskId: number) => {
    try {
      await pauseTask(taskId);
      message.success("任务已暂停");
      await fetchTasks();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "暂停任务失败");
    }
  }, [fetchTasks]);

  const handleResume = useCallback(async (taskId: number) => {
    try {
      await resumeTask(taskId);
      message.success("任务已继续，已进入队列");
      await fetchTasks();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "继续任务失败");
    }
  }, [fetchTasks]);

  const handleRetry = useCallback(async (taskId: number) => {
    try {
      await retryTask(taskId);
      message.success("任务已重新进入队列");
      await fetchTasks();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "重试任务失败");
    }
  }, [fetchTasks]);

  const handleDelete = useCallback(async (taskId: number) => {
    try {
      await deleteTask(taskId);
      message.success("任务已删除");
      await fetchTasks();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "删除任务失败");
    }
  }, [fetchTasks]);

  const columns: ColumnsType<TaskListItem> = useMemo(
    () => [
      {
        title: "任务",
        dataIndex: "task_no",
        key: "task_no",
        width: 230,
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Link to={`/tasks/${record.id}`}>{record.task_no}</Link>
            <Text type="secondary" ellipsis style={{ maxWidth: 260 }}>
              {record.base_file_name || "-"} → {record.compare_file_name || "-"}
            </Text>
          </Space>
        ),
      },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        width: 120,
        render: (value) => <Tag color={statusColor(value)}>{STATUS_LABELS[value] || value}</Tag>,
      },
      {
        title: "进度",
        dataIndex: "progress",
        key: "progress",
        width: 90,
        render: (value) => `${value}%`,
      },
      {
        title: "风险",
        key: "risk",
        width: 160,
        render: (_, record) => (
          <Space size={4}>
            <Tag color={record.high_risk_count > 0 ? "red" : "default"}>
              高风险 {record.high_risk_count}
            </Tag>
            <Tag color={record.pending_review_count > 0 ? "purple" : "default"}>
              待审 {record.pending_review_count}
            </Tag>
          </Space>
        ),
      },
      { title: "差异数", dataIndex: "diff_count", key: "diff_count", width: 90 },
      { title: "创建时间", dataIndex: "created_at", key: "created_at", width: 180, render: formatTime },
      { title: "更新时间", dataIndex: "updated_at", key: "updated_at", width: 180, render: formatTime },
      {
        title: "失败/备注",
        dataIndex: "summary",
        key: "summary",
        ellipsis: true,
        render: (value, record) => record.last_error || record.last_ai_error || value || "-",
      },
      {
        title: "操作",
        key: "actions",
        fixed: "right",
        width: 360,
        render: (_, record) => (
          <Space wrap size={6}>
            <Link to={`/tasks/${record.id}`}>
              <Button size="small" icon={<FileSearchOutlined />}>查看</Button>
            </Link>
            <Link to={`/tasks/${record.id}/diffs`}>
              <Button size="small" type="primary">审核</Button>
            </Link>
            {record.status === "paused" ? (
              <Button size="small" icon={<PlayCircleOutlined />} onClick={() => void handleResume(record.id)}>
                继续
              </Button>
            ) : record.status === "failed" ? (
              <Button size="small" icon={<ReloadOutlined />} onClick={() => void handleRetry(record.id)}>
                重试
              </Button>
            ) : (
              <Button
                size="small"
                icon={<PauseCircleOutlined />}
                disabled={!ACTIVE_STATUSES.has(record.status)}
                onClick={() => void handlePause(record.id)}
              >
                暂停
              </Button>
            )}
            <Button
              size="small"
              icon={<ExportOutlined />}
              disabled={record.status !== "completed"}
              onClick={() => window.open(getExportUrl(record.id, "final"))}
            >
              导出
            </Button>
            <Popconfirm
              title="删除任务"
              description="删除后任务会从工作台隐藏，正在运行的任务会在阶段边界停止。"
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
              onConfirm={() => void handleDelete(record.id)}
            >
              <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [handleDelete, handlePause, handleResume, handleRetry]
  );

  return (
    <Card className="work-card">
      <div className="toolbar-row">
        <Space wrap>
          <Select
            allowClear
            placeholder="全部状态"
            style={{ width: 150 }}
            value={status}
            onChange={(value) => {
              setStatus(value);
              setPage(1);
            }}
            options={[
              { label: "排队中", value: "queued" },
              { label: "处理中", value: "extracting_full_page_elements" },
              { label: "已暂停", value: "paused" },
              { label: "已完成", value: "completed" },
              { label: "失败", value: "failed" },
            ]}
          />
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder="搜索任务号或文件名"
            value={keyword}
            onChange={(event) => {
              setKeyword(event.target.value);
              setPage(1);
            }}
            onPressEnter={() => void fetchTasks()}
            style={{ width: 260 }}
          />
          <Button icon={<ReloadOutlined />} onClick={() => void fetchTasks()}>
            刷新
          </Button>
        </Space>
        <Text type="secondary">共 {total} 个任务，最多同时运行 {taskMaxWorkers} 个</Text>
      </div>
      <Table
        rowKey="id"
        columns={columns}
        dataSource={tasks}
        loading={loading}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          onChange: (nextPage, nextPageSize) => {
            setPage(nextPage);
            setPageSize(nextPageSize);
          },
        }}
        scroll={{ x: 1480 }}
        size="middle"
      />
    </Card>
  );
}
