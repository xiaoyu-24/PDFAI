import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Row,
  Space,
  Tag,
  Typography,
  Upload,
  message,
} from "antd";
import type { UploadProps } from "antd";
import { FileSearchOutlined, InboxOutlined, RocketOutlined } from "@ant-design/icons";
import { getSettings, uploadPdfs } from "../api/tasks";
import type { CompareTask, PublicSettings } from "../types";

const { Dragger } = Upload;
const { Text } = Typography;

function formatSize(file: File | null) {
  if (!file) return "-";
  if (file.size < 1024 * 1024) return `${(file.size / 1024).toFixed(1)} KB`;
  return `${(file.size / 1024 / 1024).toFixed(2)} MB`;
}

function makeUploadProps(onSelect: (file: File | null) => void): UploadProps {
  return {
    accept: "application/pdf",
    maxCount: 1,
    beforeUpload: (file) => {
      if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
        message.error("请上传 PDF 文件");
        return Upload.LIST_IGNORE;
      }
      onSelect(file);
      return false;
    },
    onRemove: () => {
      onSelect(null);
    },
  };
}

export default function UploadPage() {
  const [baseFile, setBaseFile] = useState<File | null>(null);
  const [compareFile, setCompareFile] = useState<File | null>(null);
  const [settings, setSettings] = useState<PublicSettings | null>(null);
  const [uploading, setUploading] = useState(false);
  const [lastTask, setLastTask] = useState<CompareTask | null>(null);
  const [resetKey, setResetKey] = useState(0);

  useEffect(() => {
    getSettings().then(setSettings).catch(() => setSettings(null));
  }, []);

  const handleUpload = async () => {
    if (!baseFile || !compareFile) {
      message.warning("请先选择基准 PDF 和对比 PDF");
      return;
    }
    setUploading(true);
    try {
      const task = await uploadPdfs(baseFile, compareFile);
      setLastTask(task);
      setBaseFile(null);
      setCompareFile(null);
      setResetKey((value) => value + 1);
      message.success(`任务 ${task.task_no} 已提交队列，可以继续上传新任务`);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "上传失败");
    } finally {
      setUploading(false);
    }
  };

  const strategy = settings?.recognition_strategy;

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Alert
        type="info"
        showIcon
        title="上传后任务会进入后台队列，系统最多同时运行 3 个任务；你可以继续提交新的 PDF 对比任务。"
      />
      {lastTask && (
        <Alert
          type="success"
          showIcon
          title={`任务 ${lastTask.task_no} 已提交`}
          action={
            <Link to={`/tasks/${lastTask.id}`}>
              <Button size="small" icon={<FileSearchOutlined />}>查看任务</Button>
            </Link>
          }
        />
      )}
      <Row gutter={16}>
        <Col xs={24} lg={12}>
          <Card title="基准 PDF" className="work-card">
            <Dragger key={`base-${resetKey}`} {...makeUploadProps(setBaseFile)}>
              <p className="ant-upload-drag-icon"><InboxOutlined /></p>
              <p className="ant-upload-text">点击或拖拽上传基准图纸</p>
              <p className="ant-upload-hint">客户图纸、标准图纸或旧版本</p>
            </Dragger>
            <Descriptions size="small" column={1} className="file-meta">
              <Descriptions.Item label="文件名">{baseFile?.name || "-"}</Descriptions.Item>
              <Descriptions.Item label="大小">{formatSize(baseFile)}</Descriptions.Item>
              <Descriptions.Item label="校验">{baseFile ? <Tag color="green">格式通过</Tag> : <Tag>待选择</Tag>}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="对比 PDF" className="work-card">
            <Dragger key={`compare-${resetKey}`} {...makeUploadProps(setCompareFile)}>
              <p className="ant-upload-drag-icon"><InboxOutlined /></p>
              <p className="ant-upload-text">点击或拖拽上传对比图纸</p>
              <p className="ant-upload-hint">供应商图纸、新版本或待审核图纸</p>
            </Dragger>
            <Descriptions size="small" column={1} className="file-meta">
              <Descriptions.Item label="文件名">{compareFile?.name || "-"}</Descriptions.Item>
              <Descriptions.Item label="大小">{formatSize(compareFile)}</Descriptions.Item>
              <Descriptions.Item label="校验">{compareFile ? <Tag color="green">格式通过</Tag> : <Tag>待选择</Tag>}</Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
      </Row>
      <Card title="当前识别策略" className="work-card">
        <Descriptions size="small" column={{ xs: 1, md: 3 }}>
          <Descriptions.Item label="整页识别">
            <Tag color={strategy?.full_page_enabled ? "blue" : "default"}>
              {strategy?.full_page_enabled ? "开启" : "关闭"}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="区域小图识别">
            <Tag color={strategy?.region_enabled ? "blue" : "default"}>
              {strategy?.region_enabled ? "开启" : "关闭"}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="PDF DPI">{strategy?.pdf_dpi ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="最大图像边长">{strategy?.image_max_edge ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="JPEG 质量">{strategy?.jpeg_quality ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="模型">{settings?.ai_model || "-"}</Descriptions.Item>
        </Descriptions>
        <div className="form-actions">
          <Text type="secondary">开始分析前请确认两份文件角色正确。</Text>
          <Button
            type="primary"
            size="large"
            icon={<RocketOutlined />}
            loading={uploading}
            disabled={!baseFile || !compareFile}
            onClick={handleUpload}
          >
            提交到任务队列
          </Button>
        </div>
      </Card>
    </Space>
  );
}
