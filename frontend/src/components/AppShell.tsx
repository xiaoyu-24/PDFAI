import { Layout, Menu, Button, Space, Tag, Typography } from "antd";
import {
  AppstoreOutlined,
  DashboardOutlined,
  FileSearchOutlined,
  PlusOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import { Link, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";

const { Header, Sider, Content } = Layout;
const { Text, Title } = Typography;

function selectedKey(pathname: string) {
  if (pathname === "/") return "/";
  if (pathname.startsWith("/tasks/new")) return "/tasks/new";
  if (pathname === "/diffs" || pathname.includes("/diffs")) return "diffs";
  if (pathname === "/elements" || pathname.includes("/elements")) return "elements";
  if (pathname.startsWith("/settings")) return "/settings";
  return "task-detail";
}

function pageTitle(pathname: string) {
  if (pathname === "/") return "任务工作台";
  if (pathname.startsWith("/tasks/new")) return "新建对比任务";
  if (pathname === "/tasks") return "选择任务";
  if (pathname === "/diffs") return "选择差异任务";
  if (pathname === "/elements") return "选择元素任务";
  if (pathname.includes("/diffs")) return "差异审核";
  if (pathname.includes("/elements")) return "图纸元素";
  if (pathname.startsWith("/settings")) return "系统设置";
  return "任务详情";
}

export default function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const params = useParams<{ taskId?: string }>();
  const taskId = params.taskId;

  const navItems = [
    { key: "/", icon: <DashboardOutlined />, label: <Link to="/">任务工作台</Link> },
    { key: "/tasks/new", icon: <PlusOutlined />, label: <Link to="/tasks/new">新建对比</Link> },
    {
      key: "task-detail",
      icon: <FileSearchOutlined />,
      label: <Link to={taskId ? `/tasks/${taskId}` : "/tasks"}>任务详情</Link>,
    },
    {
      key: "diffs",
      icon: <FileSearchOutlined />,
      label: <Link to={taskId ? `/tasks/${taskId}/diffs` : "/diffs"}>差异报告</Link>,
    },
    {
      key: "elements",
      icon: <AppstoreOutlined />,
      label: <Link to={taskId ? `/tasks/${taskId}/elements` : "/elements"}>图纸元素</Link>,
    },
    { key: "/settings", icon: <SettingOutlined />, label: <Link to="/settings">系统设置</Link> },
  ];

  return (
    <Layout className="app-shell">
      <Header className="app-header">
        <Space size={12}>
          <div className="brand-mark">P</div>
          <div>
            <Title level={4} className="brand-title">PDFAI</Title>
            <Text type="secondary">工程图纸差异审核工作台</Text>
          </div>
        </Space>
        <Space>
          <Tag color="blue">内部单用户</Tag>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/tasks/new")}>
            新建任务
          </Button>
          <Button icon={<SettingOutlined />} onClick={() => navigate("/settings")}>
            设置
          </Button>
        </Space>
      </Header>
      <Layout>
        <Sider width={232} className="app-sider">
          <Menu mode="inline" selectedKeys={[selectedKey(location.pathname)]} items={navItems} />
        </Sider>
        <Content className="app-content">
          <div className="page-heading">
            <Title level={3}>{pageTitle(location.pathname)}</Title>
            <Text type="secondary">一个好用的PDF工具。</Text>
          </div>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
