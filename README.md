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

### 2. 推荐：一键启动开发环境

Windows PowerShell：

```powershell
.\start-dev.ps1
```

脚本会同时启动：

- 后端：`http://localhost:8000`
- 前端：`http://localhost:5173`

启动前会检查：

- 后端是否使用 `backend\.venv\Scripts\python.exe`
- 前端是否已安装 `node_modules`
- Alembic 当前数据库版本是否已经升级到 `head`

也可以分别启动：

```powershell
.\start-backend.ps1
.\start-frontend.ps1
```

`.\start-backend.ps1` 和 `.\start-dev.ps1` 都会调用 `backend\scripts\check_migration_status.py` 检查迁移状态。这个检查只读数据库版本，不会自动修改数据库。

如果提示数据库表结构未升级，请先执行：

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
```

然后重新运行：

```powershell
cd ..
.\start-dev.ps1
```

### 3. 首次安装后端依赖
```powershell
cd backend

# 1. 创建并激活虚拟环境 (Windows 示例)
python -m venv .venv

# 2. 安装项目依赖
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. 配置环境变量
# 复制一份 .env.example 重命名为 .env，并填写其中的数据库连接和 AI 密钥
Copy-Item .env.example .env

# 4. 执行数据库迁移，创建数据表
.\.venv\Scripts\python.exe -m alembic upgrade head

# 5. 启动后端开发服务器
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

不要直接运行全局 `uvicorn`。如果出现 `ModuleNotFoundError: No module named 'pymysql'`，通常说明正在使用系统 Python，而不是项目虚拟环境。

### 4. 首次安装前端依赖
```powershell
cd frontend

# 1. 安装 NPM 依赖
npm install

# 2. 启动前端开发服务器
npm run dev
```

成功启动后，在浏览器中打开 `http://localhost:5173` 即可进入系统工作台体验。

## 🧱 数据库迁移规则

每次修改 SQLAlchemy 模型字段时，必须同步 Alembic migration：

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe_change"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m pytest
```

如果已经新增 migration，但真机 MySQL 还没有升级，后端启动前需要先执行：

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
```

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
