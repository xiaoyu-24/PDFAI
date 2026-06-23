import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Popconfirm,
  Progress,
  Result,
  Row,
  Space,
  Spin,
  Steps,
  Tag,
  Typography,
  message,
} from "antd";
import {
  DeleteOutlined,
  DownloadOutlined,
  FileSearchOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  TableOutlined,
} from "@ant-design/icons";
import {
  deleteTask,
  getExportUrl,
  getTask,
  getTaskReportTable,
  pauseTask,
  resumeTask,
  retryTask,
} from "../api/tasks";
import PageBackButton from "../components/PageBackButton";
import type { CompareTask, ReportTableRow } from "../types";

const { Text } = Typography;

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

const STAGES = [
  { keys: ["queued", "uploaded", "paused"], title: "上传/排队" },
  { keys: ["rendering_pages", "rendered"], title: "PDF 转图" },
  { keys: ["detecting_regions", "regions_detected"], title: "布局识别" },
  { keys: ["cropping_regions", "regions_cropped"], title: "区域裁剪" },
  {
    keys: [
      "extracting_full_page_elements",
      "full_page_elements_skipped",
      "extracting_region_elements",
      "region_elements_skipped",
      "merging_elements",
      "saving_elements",
    ],
    title: "元素识别",
  },
  { keys: ["comparing_elements", "saving_diffs"], title: "差异生成" },
  { keys: ["completed"], title: "完成" },
];

function getCurrentStage(task: CompareTask) {
  if (task.status === "failed") return STAGES.length - 1;
  if (task.status === "paused") {
    return Math.min(Math.floor(task.progress / 16), STAGES.length - 1);
  }
  const index = STAGES.findIndex((stage) => stage.keys.includes(task.status));
  return index >= 0 ? index : 0;
}

function tagColor(status: string) {
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

function formatDuration(ms: number | undefined) {
  if (!ms) return "-";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} 秒`;
}

export default function TaskProgressPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const parsedTaskId = taskId ? Number(taskId) : NaN;
  const invalidId = Boolean(taskId) && !Number.isFinite(parsedTaskId);
  const [task, setTask] = useState<CompareTask | null>(null);
  const [reportRows, setReportRows] = useState<ReportTableRow[]>([]);
  const [reportTaskId, setReportTaskId] = useState<number | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchTask = useCallback(async () => {
    if (!taskId || invalidId) return;
    try {
      const nextTask = await getTask(parsedTaskId);
      setTask(nextTask);
      setError(null);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "获取任务失败");
    }
  }, [invalidId, parsedTaskId, taskId]);

  useEffect(() => {
    queueMicrotask(() => {
      void fetchTask();
    });
    const timer = window.setInterval(() => {
      if (task?.status !== "completed" && task?.status !== "failed" && task?.status !== "paused") {
        void fetchTask();
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [fetchTask, task?.status]);

  const currentStage = useMemo(() => (task ? getCurrentStage(task) : 0), [task]);
  const completedTaskId = task?.status === "completed" ? task.id : null;

  useEffect(() => {
    if (!completedTaskId) {
      return;
    }

    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      setReportLoading(true);
      setReportError(null);

      getTaskReportTable(completedTaskId)
        .then((report) => {
          if (cancelled) return;
          setReportTaskId(completedTaskId);
          setReportRows(report.rows);
        })
        .catch((reportFetchError) => {
          if (cancelled) return;
          setReportTaskId(completedTaskId);
          setReportRows([]);
          setReportError(reportFetchError instanceof Error ? reportFetchError.message : "获取差异结论失败");
        })
        .finally(() => {
          if (!cancelled) {
            setReportLoading(false);
          }
        });
    });

    return () => {
      cancelled = true;
    };
  }, [completedTaskId]);

  const conclusionRows = useMemo(
    () => (reportTaskId === task?.id ? reportRows.filter((row) => row.conclusion.trim()) : []),
    [reportRows, reportTaskId, task?.id]
  );

  const handlePause = async () => {
    if (!task) return;
    try {
      const nextTask = await pauseTask(task.id);
      setTask(nextTask);
      message.success("任务已暂停");
    } catch (pauseError) {
      message.error(pauseError instanceof Error ? pauseError.message : "暂停任务失败");
    }
  };

  const handleResume = async () => {
    if (!task) return;
    try {
      const nextTask = await resumeTask(task.id);
      setTask(nextTask);
      message.success("任务已继续，已进入队列");
    } catch (resumeError) {
      message.error(resumeError instanceof Error ? resumeError.message : "继续任务失败");
    }
  };

  const handleRetry = async () => {
    if (!task) return;
    try {
      const nextTask = await retryTask(task.id);
      setTask(nextTask);
      message.success("任务已重新进入队列");
    } catch (retryError) {
      message.error(retryError instanceof Error ? retryError.message : "重试任务失败");
    }
  };

  const handleDelete = async () => {
    if (!task) return;
    try {
      await deleteTask(task.id);
      message.success("任务已删除");
      navigate("/");
    } catch (deleteError) {
      message.error(deleteError instanceof Error ? deleteError.message : "删除任务失败");
    }
  };

  if (invalidId) {
    return <Result status="error" title="无效的任务 ID" subTitle="任务 ID 格式不正确。" />;
  }

  if (error) {
    return <Alert type="error" showIcon title={error} />;
  }

  if (!task) {
    return (
      <Card className="work-card">
        <Spin tip="加载任务详情..." />
      </Card>
    );
  }

  const failed = task.status === "failed";
  const completed = task.status === "completed";
  const paused = task.status === "paused";

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <PageBackButton fallbackTo="/tasks" />
      <Card className="work-card">
        <div className="task-summary">
          <div>
            <Space wrap>
              <Tag color={tagColor(task.status)}>{task.current_step_label || task.status}</Tag>
              <Text strong>{task.task_no}</Text>
            </Space>
            <div className="muted-line">
              {task.base_file_name || "基准 PDF"} → {task.compare_file_name || "对比 PDF"}
            </div>
          </div>
          <Space>
            {paused ? (
              <Button icon={<PlayCircleOutlined />} onClick={() => void handleResume()}>
                继续
              </Button>
            ) : (
              <Button
                icon={<PauseCircleOutlined />}
                disabled={!ACTIVE_STATUSES.has(task.status)}
                onClick={() => void handlePause()}
              >
                暂停
              </Button>
            )}
            <Popconfirm
              title="删除任务"
              description="删除后任务会从工作台隐藏，正在运行的任务会在阶段边界停止。"
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
              onConfirm={() => void handleDelete()}
            >
              <Button danger icon={<DeleteOutlined />}>删除</Button>
            </Popconfirm>
            <Progress
              type="circle"
              percent={task.progress}
              size={92}
              status={failed ? "exception" : completed ? "success" : paused ? "normal" : "active"}
            />
          </Space>
        </div>
        <Steps
          current={currentStage}
          status={failed ? "error" : completed ? "finish" : paused ? "wait" : "process"}
          items={STAGES.map((stage) => ({ title: stage.title }))}
          className="task-steps"
        />
      </Card>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={8}>
          <Card title="当前状态" className="work-card">
            <Alert
              type={failed ? "error" : completed ? "success" : paused ? "warning" : "info"}
              showIcon
              title={task.current_step_label || task.status}
              description={failed ? task.error_hint || task.last_error || task.summary : task.current_step_hint}
            />
            {failed && task.last_ai_error && (
              <Alert
                type="warning"
                showIcon
                title="最近 AI 错误"
                description={task.last_ai_error}
                style={{ marginTop: 12 }}
              />
            )}
            {failed && task.summary && (
              <Alert
                type="warning"
                showIcon
                title="原始错误摘要"
                description={task.summary}
                style={{ marginTop: 12 }}
              />
            )}
            <Descriptions size="small" column={1} className="file-meta">
              <Descriptions.Item label="创建时间">{formatTime(task.created_at)}</Descriptions.Item>
              <Descriptions.Item label="开始时间">{formatTime(task.started_at || null)}</Descriptions.Item>
              <Descriptions.Item label="更新时间">{formatTime(task.updated_at || null)}</Descriptions.Item>
              <Descriptions.Item label="完成时间">{formatTime(task.completed_at)}</Descriptions.Item>
              <Descriptions.Item label="失败阶段">{task.failed_stage || "-"}</Descriptions.Item>
              <Descriptions.Item label="AI 调用次数">{task.ai_call_count ?? 0}</Descriptions.Item>
              <Descriptions.Item label="AI 累计耗时">{formatDuration(task.ai_total_duration_ms)}</Descriptions.Item>
              <Descriptions.Item label="基准页数">{task.base_page_count ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="对比页数">{task.compare_page_count ?? "-"}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} lg={16}>
          <Card
            title="结论/差异/原因"
            className="work-card"
            extra={
              <div className="task-action-buttons">
                {completed ? (
                  <>
                    <Link to={`/tasks/${task.id}/diffs`}>
                      <Button type="primary" icon={<FileSearchOutlined />}>查看差异报告</Button>
                    </Link>
                    <Link to={`/tasks/${task.id}/elements`}>
                      <Button icon={<TableOutlined />}>查看元素清单</Button>
                    </Link>
                    <Button icon={<DownloadOutlined />} onClick={() => window.open(getExportUrl(task.id, "final"))}>
                      导出审核总结
                    </Button>
                  </>
                ) : failed ? (
                  <>
                    <Button type="primary" icon={<ReloadOutlined />} onClick={() => void handleRetry()}>
                      重试此任务
                    </Button>
                    <Link to="/tasks/new"><Button>重新创建任务</Button></Link>
                    <Link to="/settings"><Button>查看系统设置</Button></Link>
                  </>
                ) : null}
              </div>
            }
          >
            <div className="conclusion-list">
              {completed ? (
                reportLoading ? (
                  <Spin tip="加载差异结论..." />
                ) : reportError ? (
                  <Alert type="warning" showIcon message={reportError} />
                ) : conclusionRows.length > 0 ? (
                  conclusionRows.map((row) => (
                    <div className="conclusion-item" key={row.diff_id}>
                      <Space size={8} wrap>
                        <Tag color={row.risk_label === "高" ? "red" : row.risk_label === "中" ? "orange" : "blue"}>
                          {row.risk_label || "差异"}
                        </Tag>
                        <Text type="secondary">
                          {row.section} #{row.section_index}
                        </Text>
                      </Space>
                      <div className="conclusion-text">{row.conclusion}</div>
                    </div>
                  ))
                ) : (
                  <Text type="secondary">暂无差异结论。</Text>
                )
              ) : failed ? (
                <Alert
                  type="error"
                  showIcon
                  message={task.current_step_label || "任务失败"}
                  description={task.error_hint || task.last_error || task.summary}
                />
              ) : paused ? (
                <Text type="secondary">任务已暂停。点击“继续”后会重新进入队列。</Text>
              ) : (
                <Text type="secondary">任务完成后将在这里展示差异报告中的结论/差异/原因。</Text>
              )}
            </div>
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
