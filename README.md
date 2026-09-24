# PDFAI — 智能图纸对比与审核系统

**简体中文** | [English](README.en.md)

PDFAI 是面向工程与制造场景的 AI 辅助图纸对比工具。上传基准图纸和对比图纸后，系统提取尺寸、文本、公差与技术要求，生成结构化差异，支持人工复核和 Excel 导出，适用于客户与供应商图纸核对、图纸版本审核等场景。

## 核心功能

- **PDF 与图片输入**：基准文件和对比文件可分别选择 PDF 或 PNG、JPG/JPEG、WebP 图片；支持源文件预览与下载。
- **图纸识别与元素提取**：PDF 多页渲染、布局区域识别与裁剪，支持整页识别和区域识别策略，查看提取后的结构化元素。
- **语义差异对比**：通过视觉模型分析图纸内容，生成差异报告和汇总，辅助定位工程要素变化。
- **人工审核与导出**：确认差异、忽略误判、添加审核备注，导出元素清单、差异清单与最终 Excel 报告。
- **任务工作台**：查看任务列表、阶段进度和日志；支持排队、暂停、继续、失败重试与删除。线程池并发处理，默认同时执行 2 个任务，可配置为 1–3 个；暂停在处理阶段边界生效。
- **多套 AI 配置**：管理模型、API 地址、密钥、超时、重试与优先级。手动切换配置时，如有活动任务则等待其结束后生效；支持服务不可用时自动故障切换、冷却与健康状态展示。
- **分层日志**：提供任务时间线、异常日志和完整日志，支持系统日志筛选；完整日志保留 7 天，异常记录保留 90 天，并定期清理。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | React 19、TypeScript 6、Vite 8、Ant Design 6、React Router 7 |
| 后端 | Python、FastAPI、SQLAlchemy、Alembic |
| 图纸处理与导出 | PyMuPDF、Pillow、OpenCV、openpyxl |
| 数据与存储 | 默认 MySQL；本地文件系统保存原文件、渲染图片、日志与报告 |
| AI | 兼容 OpenAI Chat Completions 接口的视觉模型；内置 Mock 模式 |

## 快速开始

以下命令以 **Windows PowerShell** 为例，从仓库根目录开始执行。

### 1. 环境准备

- Python 3.10 或以上版本，建议使用独立虚拟环境。
- Node.js **22.13+（22.x）或 24+**，以及 npm；当前 Vite / ESLint 不支持旧版 Node.js 18。
- MySQL：提前创建数据库和有访问权限的账号，连接信息写入 `DATABASE_URL`。Alembic 创建表结构，不会创建 MySQL 数据库或账号。
- 真实识别需要支持图片输入的视觉模型 API。

```powershell
git clone https://github.com/xiaoyu-24/PDFAI.git
cd PDFAI
```

### 2. 安装后端并配置数据库

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

编辑 `backend/.env`，至少填写数据库连接；要使用真实 AI，还需填写 API 地址、密钥与模型：

```dotenv
DATABASE_URL=mysql+pymysql://pdfai:your-password@localhost:3306/pdfai
AI_BASE_URL=https://your-provider.example/v1
AI_API_KEY=your-api-key
AI_MODEL=your-vision-model
```

上面是占位示例，请替换为自己的配置。然后在 `backend` 目录执行迁移：

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
cd ..
```

### 3. 安装前端

```powershell
cd frontend
npm ci
cd ..
```

### 4. 启动

```powershell
.\start-dev.ps1
```

也可以在两个 PowerShell 窗口中，从仓库根目录分别运行：

```powershell
.\start-backend.ps1
```

```powershell
.\start-frontend.ps1
```

| 服务 | 地址 |
| --- | --- |
| 前端工作台 | [http://localhost:5173](http://localhost:5173) |
| 后端 API 文档 | [http://localhost:8000/docs](http://localhost:8000/docs) |
| 健康检查 | [http://localhost:8000/api/health](http://localhost:8000/api/health) |

启动脚本会检查项目虚拟环境、依赖及 Alembic 迁移状态，不会自动升级数据库。若提示迁移落后，请在 `backend` 目录运行 `.\.venv\Scripts\python.exe -m alembic upgrade head` 后重新启动。

前端开发服务器默认将 `/api` 代理到 `http://127.0.0.1:8000`。后端应使用项目虚拟环境启动；遇到 `No module named 'pymysql'` 等错误时，先检查是否误用了系统 Python。

## 使用流程

1. 打开「系统设置」，配置并启用视觉模型，按需调整识别策略。
2. 新建任务，分别选择基准文件和对比文件的格式并上传。
3. 在任务进度页查看当前阶段、时间线和异常信息；需要时暂停、继续或重试。
4. 查看源文件、提取元素和差异报告，人工确认差异并填写备注。
5. 导出 Excel 元素清单、差异清单或最终报告。

没有真实可用的 AI 配置时，系统会使用 **Mock 模拟数据**，用于开发和流程演示，不代表真实图纸识别结果。真实模型的输出也需要人工复核。

## 配置说明

完整环境变量示例见 [`backend/.env.example`](backend/.env.example)，配置定义见 [`backend/app/core/config.py`](backend/app/core/config.py)。

| 配置 | 默认值 / 说明 |
| --- | --- |
| `DATABASE_URL` | MySQL 连接串，需按实际环境修改 |
| `STORAGE_ROOT` | `../storage`；相对路径以 `backend` 目录为基准 |
| `TASK_MAX_WORKERS` | `2`；允许 `1–3`，修改后重启后端 |
| `PDF_RENDER_DPI` | `300`；可在设置页调整 |
| `AI_ENABLE_FULL_PAGE_EXTRACTION` | `true`；启用整页元素提取 |
| `AI_ENABLE_REGION_EXTRACTION` | `false`；按需启用区域元素提取 |
| `AI_IMAGE_MAX_EDGE` / `AI_IMAGE_JPEG_QUALITY` | `1600` / `75`；控制发送给模型的图像大小与质量 |
| `AI_TIMEOUT_SECONDS` / `AI_MAX_RETRIES` | `120` / `2` |
| `AI_ENABLE_AUTO_FAILOVER` | `true`；可用性错误触发候选配置切换 |
| `AI_FAILOVER_COOLDOWN_SECONDS` | `300`；失败配置的冷却时长 |
| `AI_FAILOVER_MAX_SWITCHES` | `0`；不额外限制，最多尝试候选链中的全部配置 |
| `AI_FAILOVER_ON_VISION_UNSUPPORTED` | `false`；默认不因模型不支持图片而切换 |
| `CORS_ORIGINS` | 额外允许的前端来源，逗号分隔；始终包含本地开发来源 |
| `VITE_API_BASE_URL` | 前端默认 `/api`；独立 API 域名应在构建时设置 |

在设置页创建的 AI 配置保存在数据库中，密钥加密存储；加密密钥文件位于 `storage/config/ai-config.key`（随 `STORAGE_ROOT` 改变）。迁移或备份时应一并保留数据库与该密钥文件，否则已有配置中的 API 密钥无法解密。已有配置建议直接在设置页维护。

## 开发与验证

后端测试（在 `backend` 目录）：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

前端检查（在 `frontend` 目录）：

```powershell
npm run test:navigation
npm run lint
npm run build
```

前端还提供 API 地址、任务并发显示、完整日志、分页和 AI 配置检查，详见 [`frontend/package.json`](frontend/package.json)。

修改 SQLAlchemy 模型时，需要同步 Alembic migration，在 `backend` 目录执行并检查生成的迁移内容：

```powershell
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe_change"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m pytest
```

## 部署

仓库提供 Windows 内网部署说明和 Linux 服务器发布脚本：

- [Windows 内网部署指南](deploy/windows-intranet.md)
- [Linux 服务器初始化脚本](deploy/server-bootstrap-github.sh)
- [本地生产发布脚本](deploy/publish-deploy-prod.ps1)
- [服务器更新脚本](deploy/server-update.sh)

已有生产环境的更新顺序：

```powershell
# 本地仓库根目录；发布前需要干净的工作区
.\deploy\publish-deploy-prod.ps1
```

```bash
# 服务器项目目录
bash deploy/server-update.sh
```

本地发布脚本运行检查、构建前端并更新 GitHub 的 `deploy-prod` 分支；服务器脚本拉取部署代码、安装后端依赖、执行迁移并重启服务。脚本包含当前项目的域名、目录和服务名，部署到其他环境前请核对参数与配置。

仅更新 GitHub README 不需要运行生产发布脚本。本地文件修改不会自动上传到 GitHub。

## 目录结构

```text
PDFAI/
├── backend/
│   ├── app/
│   │   ├── ai/           # 视觉模型适配、Mock 与故障切换
│   │   ├── api/          # 任务、设置与系统日志接口
│   │   ├── services/     # 图纸处理、任务调度、AI 配置与日志
│   │   ├── models/       # 数据库模型
│   │   └── exports/      # Excel 导出
│   ├── alembic/          # 数据库迁移
│   ├── scripts/          # 启动与迁移辅助检查
│   └── tests/            # 后端测试
├── frontend/
│   ├── src/              # 页面、组件、路由与 API 客户端
│   └── scripts/          # 前端回归检查
├── deploy/               # 发布脚本与部署说明
├── storage/              # 运行时数据（Git 忽略）
├── start-dev.ps1          # Windows 开发环境启动入口
├── README.md             # 中文说明
└── README.en.md          # English documentation
```
