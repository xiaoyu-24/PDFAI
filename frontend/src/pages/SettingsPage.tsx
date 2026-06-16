import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Row,
  Skeleton,
  Space,
  Switch,
  Tag,
  message,
} from "antd";
import { getSettings, updateSettings } from "../api/tasks";
import type { PublicSettings } from "../types";

export default function SettingsPage() {
  const [settings, setSettings] = useState<PublicSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    getSettings()
      .then((data) => {
        setSettings(data);
      })
      .catch((error) => {
        message.error(error instanceof Error ? error.message : "获取系统设置失败");
      })
      .finally(() => setLoading(false));
  }, [form]);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);

      const request = {
        ai_base_url: values.ai_base_url,
        ai_model: values.ai_model,
        ai_api_key: values.ai_api_key || undefined,
        ai_timeout_seconds: values.ai_timeout_seconds,
        ai_max_retries: values.ai_max_retries,
        pdf_render_dpi: values.pdf_dpi,
        ai_enable_full_page_extraction: values.full_page_enabled,
        ai_enable_region_extraction: values.region_enabled,
        ai_image_max_edge: values.image_max_edge,
        ai_image_jpeg_quality: values.jpeg_quality,
      };

      const updated = await updateSettings(request);
      setSettings(updated);
      message.success("设置已保存");
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message);
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Card className="work-card">
        <Skeleton active />
      </Card>
    );
  }

  if (!settings) {
    return <Alert type="error" showIcon title="无法读取系统设置" />;
  }

  const initialValues = {
    ai_base_url: settings.ai_base_url,
    ai_model: settings.ai_model,
    ai_timeout_seconds: settings.ai_timeout_seconds,
    ai_max_retries: settings.ai_max_retries,
    full_page_enabled: settings.recognition_strategy.full_page_enabled,
    region_enabled: settings.recognition_strategy.region_enabled,
    pdf_dpi: settings.recognition_strategy.pdf_dpi,
    image_max_edge: settings.recognition_strategy.image_max_edge,
    jpeg_quality: settings.recognition_strategy.jpeg_quality,
  };

  return (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      <Form form={form} layout="vertical" size="small" initialValues={initialValues}>
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Card title="AI 配置" className="work-card" size="small">
            <Row gutter={16}>
            <Col span={8}>
              <Form.Item label="运行环境" style={{ marginBottom: 8 }}>
                <Tag>{settings.app_env}</Tag>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="API Key 状态" style={{ marginBottom: 8 }}>
                <Tag color={settings.has_ai_api_key ? "green" : "red"}>
                  {settings.has_ai_api_key ? "已配置" : "未配置"}
                </Tag>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                label="重试次数"
                name="ai_max_retries"
                rules={[{ required: true, message: "必填" }]}
                style={{ marginBottom: 8 }}
              >
                <InputNumber min={0} max={10} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="AI Base URL"
                name="ai_base_url"
                rules={[{ required: true, message: "必填" }]}
                style={{ marginBottom: 8 }}
              >
                <Input placeholder="https://api.example.com/v1" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="模型名称"
                name="ai_model"
                rules={[{ required: true, message: "必填" }]}
                style={{ marginBottom: 8 }}
              >
                <Input placeholder="gpt-4-vision-preview" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="API Key"
                name="ai_api_key"
                extra={settings.has_ai_api_key ? "已配置，留空不修改" : "未配置，请输入"}
                style={{ marginBottom: 8 }}
              >
                <Input.Password placeholder="输入新的 API Key" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="超时(秒)"
                name="ai_timeout_seconds"
                rules={[{ required: true, message: "必填" }]}
                style={{ marginBottom: 8 }}
              >
                <InputNumber min={10} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            </Row>
          </Card>
          <Card title="识别与图像策略" className="work-card" size="small">
            <Row gutter={16}>
            <Col span={8}>
              <Form.Item
                label="整页识别"
                name="full_page_enabled"
                valuePropName="checked"
                style={{ marginBottom: 8 }}
              >
                <Switch />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                label="区域小图识别"
                name="region_enabled"
                valuePropName="checked"
                style={{ marginBottom: 8 }}
              >
                <Switch />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item label="存储目录" style={{ marginBottom: 8 }}>
                <Input value={settings.storage_root} disabled size="small" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                label="PDF DPI"
                name="pdf_dpi"
                rules={[{ required: true, message: "必填" }]}
                style={{ marginBottom: 8 }}
              >
                <InputNumber min={72} max={1200} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                label="最大图像边长"
                name="image_max_edge"
                rules={[{ required: true, message: "必填" }]}
                style={{ marginBottom: 8 }}
              >
                <InputNumber min={512} max={8000} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                label="JPEG 质量"
                name="jpeg_quality"
                rules={[{ required: true, message: "必填" }]}
                style={{ marginBottom: 8 }}
              >
                <InputNumber min={40} max={95} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            </Row>
          </Card>
        </Space>
      </Form>
      <Button type="primary" onClick={handleSave} loading={saving} block>
        保存设置
      </Button>
    </Space>
  );
}
