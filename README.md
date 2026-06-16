# PDFAI - 智能产品图纸对比与审核系统

PDFAI 是一个专为工程和制造行业设计的 **AI 辅助图纸对比工具**。它能够自动分析两份产品图纸（如客户原始图纸与供应商打样图纸、旧版与新版图纸），智能提取关键要素（尺寸、BOM、技术要求等），并生成高可视化的差异审核报告。

## ✨ 核心功能

- 📄 **高清 PDF 渲染与布局识别**：自动将 PDF 图纸转换为高清图像，并利用视觉 AI 识别主视图、技术要求、标题栏等重点区域。
- 🔍 **图纸元素智能提取**：针对整页或局部裁剪区域，结构化提取图纸上的工程尺寸、说明文本和公差要求。
- ⚖️ **智能语义对比**：不依赖简单的像素死板比对，而是基于 AI 语义理解对比基准图纸和对比图纸中的真实元素差异。
- 🛠️ **人工辅助审核工作流**：支持人工在前端工作台二次确认高风险差异、忽略误判或补充审核备注。
- 📊 **标准化报告与导出**：支持网页端直观预览，并可一键导出包含冻结表头、差异高亮和自动列宽的标准化 Excel 审核报告。
- ⚙️ **健壮的任务管理**：内置基于 FastAPI Background Tasks 的任务流管理，支持多任务并行排队、任务暂停/恢复、以及失败任务的一键清理重试。

## 💻 技术栈

**前端 (Frontend)**
- React + TypeScript
- Vite 构建工具
- Ant Design (UI 组件库)
- React Router (前端路由)

**后端 (Backend)**
- Python 3 + FastAPI
- SQLAlchemy + Alembic (ORM 与数据库迁移)
- PyMuPDF + Pillow (高性能 PDF 渲染与裁剪)
- 支持接入任何 OpenAI-Compatible 的视觉大模型 API

## 🚀 快速启动

### 1. 准备工作
确保你的本地环境已安装以下依赖：
- Python (推荐 3.10 或以上版本)
- Node.js (推荐 18 或以上版本)
- 本地 MySQL 或 SQLite 数据库环境

### 2. 后端服务部署
```bash
cd backend

# 1. 创建并激活虚拟环境 (Windows 示例)
python -m venv venv
venv\Scripts\activate
# (macOS/Linux 请使用: source venv/bin/activate)

# 2. 安装项目依赖
pip install -r requirements.txt

# 3. 配置环境变量
# 复制一份 .env.example 重命名为 .env，并填写其中的数据库连接和 AI 密钥
cp .env.example .env

# 4. 执行数据库迁移，创建数据表
alembic upgrade head

# 5. 启动后端开发服务器
uvicorn app.main:app --reload --port 8000
```

### 3. 前端服务部署
```bash
cd frontend

# 1. 安装 NPM 依赖
npm install

# 2. 启动前端开发服务器
npm run dev
```

成功启动后，在浏览器中打开 `http://localhost:5173` 即可进入系统工作台体验。

## 📁 主要目录结构说明

```text
PDFAI/
├── backend/            # FastAPI 后端源码目录
│   ├── app/            # 核心业务逻辑 (API 路由, 数据库模型, 核心流程控制等)
│   ├── tests/          # pytest 自动化测试用例
│   └── alembic/        # 数据库表结构迁移脚本
├── frontend/           # React + Vite 前端源码目录
│   ├── src/            # 前端业务代码 (页面 pages, 组件 components, API 接口封装等)
│   └── package.json    # 前端依赖配置文件
└── storage/            # 运行时存储目录 (Git 已忽略，用于存放解析过程中的图片、PDF和 AI 结果)
```

## 🛡️ 注意事项

- 在 `settings` 页面或 `.env` 中配置 AI 时，请确保使用的是支持图片识别的 **Vision 模型** (如 `gpt-4o`, `gpt-4-vision-preview` 等)。
- 默认 PDF 渲染 DPI 为 600，如果你发现处理过慢或本地内存吃紧，可在界面设置中适度调低 DPI 选项（如调整为 300 或 150）。
