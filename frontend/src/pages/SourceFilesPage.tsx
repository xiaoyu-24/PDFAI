import { useEffect, useState } from "react";
import { Alert, Button, Card, Col, Result, Row, Space, Spin, Tag, Typography } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import { useParams } from "react-router-dom";
import PageBackButton from "../components/PageBackButton";
import { getSourceFileDownloadUrl, getSourceFilePreviewUrl, getSourceFiles } from "../api/tasks";
import type { SourceFileInfo } from "../types";

const { Text } = Typography;

export default function SourceFilesPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const parsedTaskId = taskId ? Number(taskId) : NaN;
  const [files, setFiles] = useState<SourceFileInfo[]>([]);
  const [failedRoles, setFailedRoles] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!Number.isFinite(parsedTaskId)) return;
    getSourceFiles(parsedTaskId)
      .then((response) => setFiles(response.files))
      .catch((loadError) => setError(loadError instanceof Error ? loadError.message : "获取原始文件失败"))
      .finally(() => setLoading(false));
  }, [parsedTaskId]);

  if (!Number.isFinite(parsedTaskId)) return <Result status="error" title="无效的任务 ID" />;
  if (loading) return <Spin tip="加载原始文件..." />;
  if (error) return <Alert type="error" showIcon message={error} />;

  const markFailed = (role: string) => setFailedRoles((current) => new Set(current).add(role));

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <PageBackButton fallbackTo={`/tasks/${parsedTaskId}`} />
      <Row gutter={[16, 16]}>
        {files.map((file) => {
          const failed = failedRoles.has(file.role);
          const previewUrl = getSourceFilePreviewUrl(parsedTaskId, file.role);
          return (
            <Col xs={24} xl={12} key={file.role}>
              <Card
                className="work-card source-file-card"
                title={<Space><Tag color={file.role === "base" ? "blue" : "purple"}>{file.role === "base" ? "基准文件" : "对比文件"}</Tag><Text ellipsis>{file.original_name}</Text></Space>}
                extra={<Button icon={<DownloadOutlined />} href={getSourceFileDownloadUrl(parsedTaskId, file.role)}>下载原文件</Button>}
              >
                <div className="source-file-meta">{file.file_type.toUpperCase()} · {file.page_count} 页</div>
                {failed ? (
                  <Result status="warning" title="文件无法在线预览" subTitle="您仍可以下载创建任务时上传的原文件。" extra={<Button type="primary" href={getSourceFileDownloadUrl(parsedTaskId, file.role)}>下载原文件</Button>} />
                ) : file.file_type === "pdf" ? (
                  <iframe className="source-file-preview" title={file.original_name} src={previewUrl} onError={() => markFailed(file.role)} />
                ) : (
                  <img className="source-file-preview source-file-image" alt={file.original_name} src={previewUrl} onError={() => markFailed(file.role)} />
                )}
              </Card>
            </Col>
          );
        })}
      </Row>
    </Space>
  );
}
