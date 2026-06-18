import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Card, Input, Select, Space, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { ReloadOutlined, SearchOutlined } from "@ant-design/icons";
import { useParams } from "react-router-dom";
import { getTask, getTaskElements } from "../api/tasks";
import PageBackButton from "../components/PageBackButton";
import type { CompareTask, DrawingElement } from "../types";

const { Paragraph, Text } = Typography;

const IMPORTANCE_COLORS: Record<string, string> = {
  high: "red",
  medium: "orange",
  low: "green",
};

function confidenceLabel(value: number | null) {
  return value != null ? `${Math.round(value * 100)}%` : "-";
}

export default function ElementsPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const numericTaskId = taskId ? Number(taskId) : NaN;
  const [task, setTask] = useState<CompareTask | null>(null);
  const [elements, setElements] = useState<DrawingElement[]>([]);
  const [loading, setLoading] = useState(false);
  const [category, setCategory] = useState<string | undefined>();
  const [fileRole, setFileRole] = useState<string | undefined>();
  const [manualOnly, setManualOnly] = useState(false);
  const [keyword, setKeyword] = useState("");

  const loadElements = useCallback(async () => {
    if (!Number.isFinite(numericTaskId)) return;
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (category) params.category = category;
      if (fileRole) params.file_role = fileRole;
      const [nextTask, nextElements] = await Promise.all([
        getTask(numericTaskId),
        getTaskElements(numericTaskId, params),
      ]);
      setTask(nextTask);
      setElements(nextElements);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "获取元素清单失败");
    } finally {
      setLoading(false);
    }
  }, [category, fileRole, numericTaskId]);

  useEffect(() => {
    queueMicrotask(() => {
      void loadElements();
    });
  }, [loadElements]);

  const categories = useMemo(
    () => Array.from(new Set(elements.map((item) => item.category))).filter(Boolean),
    [elements]
  );

  const filteredElements = useMemo(() => {
    const lowerKeyword = keyword.trim().toLowerCase();
    return elements.filter((item) => {
      if (manualOnly && !item.need_manual_check) return false;
      if (!lowerKeyword) return true;
      return [item.element_name, item.category, item.raw_value, item.region_desc]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(lowerKeyword));
    });
  }, [elements, keyword, manualOnly]);

  const columns: ColumnsType<DrawingElement> = [
    { title: "元素名称", dataIndex: "element_name", key: "element_name", width: 220 },
    { title: "类别", dataIndex: "category", key: "category", width: 130 },
    {
      title: "原始值",
      dataIndex: "raw_value",
      key: "raw_value",
      ellipsis: true,
      render: (value) => value || "-",
    },
    {
      title: "重要性",
      dataIndex: "importance",
      key: "importance",
      width: 110,
      render: (value) => <Tag color={IMPORTANCE_COLORS[value] || "default"}>{value}</Tag>,
    },
    {
      title: "置信度",
      dataIndex: "confidence",
      key: "confidence",
      width: 100,
      render: confidenceLabel,
    },
    {
      title: "人工确认",
      dataIndex: "need_manual_check",
      key: "need_manual_check",
      width: 120,
      render: (value: boolean) => value ? <Tag color="purple">需要</Tag> : <Tag>否</Tag>,
    },
    { title: "来源区域", dataIndex: "region_desc", key: "region_desc", width: 220, ellipsis: true },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <PageBackButton fallbackTo="/elements" />
      <Card className="work-card">
        <div className="toolbar-row">
          <Space wrap>
            <Select
              allowClear
              placeholder="全部 PDF"
              style={{ width: 140 }}
              value={fileRole}
              onChange={setFileRole}
              options={[
                { label: "基准 PDF", value: "base" },
                { label: "对比 PDF", value: "compare" },
              ]}
            />
            <Select
              allowClear
              placeholder="全部类别"
              style={{ width: 160 }}
              value={category}
              onChange={setCategory}
              options={categories.map((item) => ({ label: item, value: item }))}
            />
            <Select
              style={{ width: 150 }}
              value={manualOnly ? "manual" : "all"}
              onChange={(value) => setManualOnly(value === "manual")}
              options={[
                { label: "全部元素", value: "all" },
                { label: "需人工确认", value: "manual" },
              ]}
            />
            <Input
              allowClear
              prefix={<SearchOutlined />}
              placeholder="搜索元素"
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              style={{ width: 220 }}
            />
            <Button icon={<ReloadOutlined />} onClick={() => void loadElements()}>刷新</Button>
          </Space>
          <Text type="secondary">
            {task?.task_no}，当前显示 {filteredElements.length} / {elements.length} 个元素
          </Text>
        </div>
        <Table
          rowKey="id"
          columns={columns}
          dataSource={filteredElements}
          loading={loading}
          pagination={{ pageSize: 15, showSizeChanger: true }}
          scroll={{ x: 1180 }}
          size="middle"
          expandable={{
            expandedRowRender: (record) => (
              <Space direction="vertical" size={8} style={{ width: "100%" }}>
                <Paragraph><Text strong>原始识别证据：</Text>{record.raw_value || "-"}</Paragraph>
                <Paragraph><Text strong>来源图片：</Text>{record.source_image_path || "-"}</Paragraph>
                <Paragraph><Text strong>额外数据：</Text>{record.extra_json ? JSON.stringify(record.extra_json) : "-"}</Paragraph>
              </Space>
            ),
          }}
        />
      </Card>
    </Space>
  );
}
