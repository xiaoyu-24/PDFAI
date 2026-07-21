import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  Skeleton,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import {
  activateAiProfile,
  createAiProfile,
  deleteAiProfile,
  getSettings,
  listAiProfiles,
  updateAiProfile,
  updateSettings,
} from "../api/tasks";
import { useAutoRefresh } from "../hooks/useAutoRefresh";
import type { AiProfile, AiProfileListResponse, PublicSettings, SaveAiProfileRequest } from "../types";

const emptyProfiles: AiProfileListResponse = {
  items: [],
  active_profile_id: null,
  pending_profile_id: null,
};

export default function SettingsPage() {
  const [settings, setSettings] = useState<PublicSettings | null>(null);
  const [profiles, setProfiles] = useState<AiProfileListResponse>(emptyProfiles);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);
  const [editingProfile, setEditingProfile] = useState<AiProfile | null>(null);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [switchingId, setSwitchingId] = useState<number | null>(null);
  const [strategyForm] = Form.useForm();
  const [profileForm] = Form.useForm<SaveAiProfileRequest>();

  const refreshProfiles = async () => {
    const data = await listAiProfiles();
    setProfiles(data);
  };

  useEffect(() => {
    Promise.all([getSettings(), listAiProfiles()])
      .then(([settingsData, profileData]) => {
        setSettings(settingsData);
        setProfiles(profileData);
        strategyForm.setFieldsValue({
          full_page_enabled: settingsData.recognition_strategy.full_page_enabled,
          region_enabled: settingsData.recognition_strategy.region_enabled,
          pdf_dpi: settingsData.recognition_strategy.pdf_dpi,
          image_max_edge: settingsData.recognition_strategy.image_max_edge,
          jpeg_quality: settingsData.recognition_strategy.jpeg_quality,
        });
      })
      .catch((error) => message.error(error instanceof Error ? error.message : "获取系统设置失败"))
      .finally(() => setLoading(false));
  }, [strategyForm]);

  useAutoRefresh(refreshProfiles, { enabled: !loading, intervalMs: 2000 });

  const saveStrategy = async () => {
    try {
      const values = await strategyForm.validateFields();
      setSaving(true);
      const updated = await updateSettings({
        pdf_render_dpi: values.pdf_dpi,
        ai_enable_full_page_extraction: values.full_page_enabled,
        ai_enable_region_extraction: values.region_enabled,
        ai_image_max_edge: values.image_max_edge,
        ai_image_jpeg_quality: values.jpeg_quality,
      });
      setSettings(updated);
      message.success("识别策略已保存");
    } catch (error) {
      if (error instanceof Error) message.error(error.message);
    } finally {
      setSaving(false);
    }
  };

  const openCreateModal = () => {
    setEditingProfile(null);
    profileForm.resetFields();
    profileForm.setFieldsValue({ timeout_seconds: 120, max_retries: 2 });
    setProfileModalOpen(true);
  };

  const openEditModal = (profile: AiProfile) => {
    setEditingProfile(profile);
    profileForm.setFieldsValue({
      name: profile.name,
      base_url: profile.base_url,
      model: profile.model,
      api_key: "",
      timeout_seconds: profile.timeout_seconds,
      max_retries: profile.max_retries,
    });
    setProfileModalOpen(true);
  };

  const saveProfile = async () => {
    try {
      const values = await profileForm.validateFields();
      setProfileSaving(true);
      if (editingProfile) {
        await updateAiProfile(editingProfile.id, {
          ...values,
          api_key: values.api_key || undefined,
        });
      } else {
        await createAiProfile(values);
      }
      setProfileModalOpen(false);
      await refreshProfiles();
      message.success(editingProfile ? "AI 配置已更新" : "AI 配置已新增");
    } catch (error) {
      if (error instanceof Error) message.error(error.message);
    } finally {
      setProfileSaving(false);
    }
  };

  const switchProfile = async (profile: AiProfile) => {
    try {
      setSwitchingId(profile.id);
      const result = await activateAiProfile(profile.id);
      await refreshProfiles();
      message.success(
        result.activation_status === "active"
          ? `已切换为“${profile.name}”`
          : `已设为待切换，所有运行中任务结束后自动生效`
      );
    } catch (error) {
      message.error(error instanceof Error ? error.message : "切换 AI 配置失败");
    } finally {
      setSwitchingId(null);
    }
  };

  const disableProfile = async (profile: AiProfile) => {
    try {
      await deleteAiProfile(profile.id);
      await refreshProfiles();
      message.success("AI 配置已停用");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "停用 AI 配置失败");
    }
  };

  if (loading) return <Card className="work-card"><Skeleton active /></Card>;
  if (!settings) return <Alert type="error" showIcon title="无法读取系统设置" />;

  const columns = [
    {
      title: "配置名称",
      dataIndex: "name",
      render: (name: string, profile: AiProfile) => (
        <Space>
          <Typography.Text strong>{name}</Typography.Text>
          {profile.is_active && <Tag color="green">当前使用</Tag>}
          {profile.is_pending && <Tag color="orange">等待生效</Tag>}
        </Space>
      ),
    },
    { title: "模型", dataIndex: "model" },
    { title: "API 地址", dataIndex: "base_url", ellipsis: true },
    {
      title: "调用策略",
      render: (_: unknown, profile: AiProfile) => `${profile.timeout_seconds} 秒 / 重试 ${profile.max_retries} 次`,
    },
    {
      title: "操作",
      width: 310,
      render: (_: unknown, profile: AiProfile) => (
        <Space size="small">
          <Button size="small" onClick={() => openEditModal(profile)}>编辑配置</Button>
          <Button
            size="small"
            type="primary"
            disabled={profile.is_active || profile.is_pending}
            loading={switchingId === profile.id}
            onClick={() => void switchProfile(profile)}
          >
            切换使用
          </Button>
          <Popconfirm
            title="确认停用这个 AI 配置吗？"
            okText="确认"
            cancelText="取消"
            disabled={profile.is_active || profile.is_pending}
            onConfirm={() => void disableProfile(profile)}
          >
            <Button size="small" danger disabled={profile.is_active || profile.is_pending}>停用配置</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      <Card
        title="AI 配置"
        className="work-card"
        size="small"
        extra={<Button type="primary" onClick={openCreateModal}>新增 AI 配置</Button>}
      >
        {profiles.pending_profile_id !== null && (
          <Alert
            type="info"
            showIcon
            title="新的 AI 配置正在等待生效"
            description="系统会继续让当前任务使用原配置，并在所有运行中任务结束后自动切换。"
            style={{ marginBottom: 12 }}
          />
        )}
        <Table rowKey="id" size="small" pagination={false} dataSource={profiles.items} columns={columns} />
      </Card>

      <Card title="识别与图像策略" className="work-card" size="small">
        <Form form={strategyForm} layout="vertical" size="small">
          <Row gutter={16}>
            <Col span={8}><Form.Item label="整页识别" name="full_page_enabled" valuePropName="checked"><Switch /></Form.Item></Col>
            <Col span={8}><Form.Item label="区域小图识别" name="region_enabled" valuePropName="checked"><Switch /></Form.Item></Col>
            <Col span={8}><Form.Item label="存储目录"><Input value={settings.storage_root} disabled /></Form.Item></Col>
            <Col span={8}><Form.Item label="PDF DPI" name="pdf_dpi" rules={[{ required: true, message: "必填" }]}><InputNumber min={72} max={1200} style={{ width: "100%" }} /></Form.Item></Col>
            <Col span={8}><Form.Item label="最大图像边长" name="image_max_edge" rules={[{ required: true, message: "必填" }]}><InputNumber min={512} max={8000} style={{ width: "100%" }} /></Form.Item></Col>
            <Col span={8}><Form.Item label="JPEG 质量" name="jpeg_quality" rules={[{ required: true, message: "必填" }]}><InputNumber min={40} max={95} style={{ width: "100%" }} /></Form.Item></Col>
          </Row>
          <Button type="primary" onClick={() => void saveStrategy()} loading={saving}>保存识别策略</Button>
        </Form>
      </Card>

      <Modal
        title={editingProfile ? "编辑 AI 配置" : "新增 AI 配置"}
        open={profileModalOpen}
        confirmLoading={profileSaving}
        okText="保存配置"
        cancelText="取消"
        onOk={() => void saveProfile()}
        onCancel={() => setProfileModalOpen(false)}
        destroyOnHidden
      >
        <Form form={profileForm} layout="vertical" preserve={false}>
          <Form.Item label="配置名称" name="name" rules={[{ required: true, message: "请输入配置名称" }]}><Input placeholder="例如：生产视觉模型" /></Form.Item>
          <Form.Item label="AI Base URL" name="base_url" rules={[{ required: true, message: "请输入 API 地址" }]}><Input placeholder="https://api.example.com/v1" /></Form.Item>
          <Form.Item label="模型名称" name="model" rules={[{ required: true, message: "请输入模型名称" }]}><Input /></Form.Item>
          <Form.Item
            label="API Key"
            name="api_key"
            extra={editingProfile?.has_api_key ? "已加密保存，留空表示不修改" : undefined}
            rules={editingProfile ? [] : [{ required: true, message: "请输入 API Key" }]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}><Form.Item label="超时（秒）" name="timeout_seconds" rules={[{ required: true, message: "必填" }]}><InputNumber min={10} style={{ width: "100%" }} /></Form.Item></Col>
            <Col span={12}><Form.Item label="重试次数" name="max_retries" rules={[{ required: true, message: "必填" }]}><InputNumber min={0} max={10} style={{ width: "100%" }} /></Form.Item></Col>
          </Row>
        </Form>
      </Modal>
    </Space>
  );
}
