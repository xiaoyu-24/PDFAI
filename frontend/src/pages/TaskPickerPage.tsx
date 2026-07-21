import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Card, Input, Select, Space, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { SearchOutlined } from "@ant-design/icons";
import { Link, useLocation } from "react-router-dom";
import { listTasks } from "../api/tasks";
import type { TaskListItem } from "../types";
import { useAutoRefresh } from "../hooks/useAutoRefresh";

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
  extracting_region_elements: "区域识别",
  saving_elements: "保存元素",
  comparing_elements: "生成差异",
  completed: "已完成",
  failed: "失败",
};

function getMode(pathname: string) {
  if (pathname.startsWith("/diffs")) {
    return { title: "选择任务查看差异报告", target: (id: number) => `/tasks/${id}/diffs`, action: "查看差异" };
  }
  if (pathname.startsWith("/elements")) {
    return { title: "选择任务查看图纸元素", target: (id: number) => `/tasks/${id}/elements`, action: "查看元素" };
  }
  return { title: "选择任务查看详情", target: (id: number) => `/tasks/${id}`, action: "查看详情" };
}

function statusColor(status: string) {
  if (status === "completed") return "green";
  if (status === "failed") return "red";
  if (status === "paused") return "orange";
  if (status === "queued") return "cyan";
  return "blue";
}

export default function TaskPickerPage() {
  const location = useLocation();
  const mode = getMode(location.pathname);
  const [tasks, setTasks] = useState<TaskListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState("");
  const [status, setStatus] = useState<string | undefined>();
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const fetchTasks = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const result = await listTasks({
        keyword: keyword.trim() || undefined,
        status,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      });
      setTasks(result.items);
      setTotal(result.total);
    } catch (error) {
      if (!silent) message.error(error instanceof Error ? error.message : "获取任务列表失败");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [keyword, page, pageSize, status]);

  useEffect(() => {
    queueMicrotask(() => {
      void fetchTasks();
    });
  }, [fetchTasks]);

  const autoRefreshTasks = useCallback(() => fetchTasks(true), [fetchTasks]);
  useAutoRefresh(autoRefreshTasks);

  const columns: ColumnsType<TaskListItem> = useMemo(
    () => [
      {
        title: "任务",
        dataIndex: "task_no",
        key: "task_no",
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Text strong>{record.task_no}</Text>
            <Text type="secondary">
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
      { title: "进度", dataIndex: "progress", key: "progress", width: 90, render: (value) => `${value}%` },
      { title: "差异数", dataIndex: "diff_count", key: "diff_count", width: 90 },
      {
        title: "操作",
        key: "action",
        width: 130,
        render: (_, record) => (
          <Link to={mode.target(record.id)}>
            <Button type="primary" size="small">{mode.action}</Button>
          </Link>
        ),
      },
    ],
    [mode]
  );

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Card className="work-card" title={mode.title}>
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
          </Space>
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
            onChange: (nextPage, nextPageSize) => {
              setPage(nextPage);
              setPageSize(nextPageSize);
            },
          }}
        />
      </Card>
    </Space>
  );
}
