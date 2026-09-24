# PDFAI — AI-Assisted Drawing Comparison and Review

[简体中文](README.md) | **English**

PDFAI helps engineering and manufacturing teams compare technical drawings. Upload a baseline drawing and a comparison drawing to extract dimensions, text, tolerances, and technical requirements, identify structured differences, review findings, and export Excel reports. Typical uses include customer–supplier drawing checks and drawing revision reviews.

## Features

- **PDF and image input**: Each input can independently be a PDF or a PNG, JPG/JPEG, or WebP image. Preview and download the original files.
- **Drawing recognition and extraction**: Render multi-page PDFs, detect and crop drawing regions, and inspect structured elements. Configure full-page and region-based extraction separately.
- **Semantic comparison**: Use vision models to compare drawing content and generate difference reports and summaries for engineering review.
- **Human review and exports**: Confirm differences, dismiss false positives, add review notes, and export element lists, difference lists, and final Excel reports.
- **Task workspace**: Browse tasks, processing stages, and logs; queue, pause, resume, retry failed tasks, or delete tasks. A thread pool runs 2 tasks concurrently by default, configurable from 1 to 3. Pausing takes effect at processing stage boundaries.
- **Multiple AI profiles**: Manage models, API endpoints, keys, timeouts, retries, and priorities. Manual profile activation waits for active tasks to finish when necessary. Automatic failover handles availability errors, with cooldowns and visible health status.
- **Tiered logs**: Inspect task timelines, exceptions, and full logs, with system-wide filtering. Full logs are retained for 7 days and exception records for 90 days, with scheduled cleanup.

## Technology

| Layer | Stack |
| --- | --- |
| Frontend | React 19, TypeScript 6, Vite 8, Ant Design 6, React Router 7 |
| Backend | Python, FastAPI, SQLAlchemy, Alembic |
| Drawing processing and exports | PyMuPDF, Pillow, OpenCV, openpyxl |
| Data and storage | MySQL by default; local files for uploads, rendered images, logs, and reports |
| AI | Vision models compatible with the OpenAI Chat Completions API; built-in Mock mode |

## Quick start

The commands below use **Windows PowerShell**, starting from the repository root.

### 1. Prerequisites

- Python 3.10 or later; a dedicated virtual environment is recommended.
- Node.js **22.13+ on the 22.x line, or 24+**, with npm. The current Vite / ESLint toolchain does not support Node.js 18.
- MySQL: Create a database and an account with access, then set `DATABASE_URL`. Alembic creates tables; it does not create the MySQL database or account.
- A vision model API that accepts image input for real drawing recognition.

```powershell
git clone https://github.com/xiaoyu-24/PDFAI.git
cd PDFAI
```

### 2. Install the backend and configure the database

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env` and set the database connection. For real AI processing, also set the API endpoint, key, and model:

```dotenv
DATABASE_URL=mysql+pymysql://pdfai:your-password@localhost:3306/pdfai
AI_BASE_URL=https://your-provider.example/v1
AI_API_KEY=your-api-key
AI_MODEL=your-vision-model
```

Replace these placeholders with your own settings. Then run migrations from `backend`:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
cd ..
```

### 3. Install the frontend

```powershell
cd frontend
npm ci
cd ..
```

### 4. Start the application

```powershell
.\start-dev.ps1
```

Alternatively, run these commands in two separate PowerShell windows, each starting from the repository root:

```powershell
.\start-backend.ps1
```

```powershell
.\start-frontend.ps1
```

| Service | URL |
| --- | --- |
| Web workspace | [http://localhost:5173](http://localhost:5173) |
| API documentation | [http://localhost:8000/docs](http://localhost:8000/docs) |
| Health check | [http://localhost:8000/api/health](http://localhost:8000/api/health) |

The startup scripts check the project virtual environment, dependencies, and Alembic migration status. They do not automatically upgrade the database. If migrations are behind, run `.\.venv\Scripts\python.exe -m alembic upgrade head` from `backend`, then restart.

The frontend development server proxies `/api` to `http://127.0.0.1:8000` by default. Always start the backend with the project virtual environment. Errors such as `No module named 'pymysql'` can indicate that the system Python is being used instead.

## Workflow

1. Open Settings (系统设置), configure and activate a vision model, and adjust recognition options as needed.
2. Create a task, select the format of each input, and upload the baseline and comparison files.
3. Follow processing stages, timeline events, and exceptions on the task progress page. Pause, resume, or retry as needed.
4. Inspect source files, extracted elements, and the difference report. Review findings and add notes.
5. Export an Excel element list, difference list, or final report.

If no real AI configuration is available, the application uses **Mock data** for development and workflow demonstrations. Mock output is not a real analysis of your drawings. Results from real models also require human review.

## Configuration

See [`backend/.env.example`](backend/.env.example) for the environment template and [`backend/app/core/config.py`](backend/app/core/config.py) for configuration definitions.

| Setting | Default / behavior |
| --- | --- |
| `DATABASE_URL` | MySQL connection string; update for your environment |
| `STORAGE_ROOT` | `../storage`; relative paths resolve from the `backend` directory |
| `TASK_MAX_WORKERS` | `2`; accepts `1–3`, requires a backend restart |
| `PDF_RENDER_DPI` | `300`; adjustable in Settings |
| `AI_ENABLE_FULL_PAGE_EXTRACTION` | `true`; enables full-page element extraction |
| `AI_ENABLE_REGION_EXTRACTION` | `false`; enable region extraction as needed |
| `AI_IMAGE_MAX_EDGE` / `AI_IMAGE_JPEG_QUALITY` | `1600` / `75`; controls the size and quality of images sent to the model |
| `AI_TIMEOUT_SECONDS` / `AI_MAX_RETRIES` | `120` / `2` |
| `AI_ENABLE_AUTO_FAILOVER` | `true`; availability errors trigger a switch to another candidate |
| `AI_FAILOVER_COOLDOWN_SECONDS` | `300`; cooldown for failed profiles |
| `AI_FAILOVER_MAX_SWITCHES` | `0`; no extra cap, bounded by the available candidate chain |
| `AI_FAILOVER_ON_VISION_UNSUPPORTED` | `false`; lack of image support does not trigger failover by default |
| `CORS_ORIGINS` | Comma-separated additional frontend origins; local development origins are always included |
| `VITE_API_BASE_URL` | Frontend default: `/api`; set at build time when using a separate API domain |

AI profiles created in Settings are stored in the database with encrypted API keys. The encryption key file is stored at `storage/config/ai-config.key` (under the configured `STORAGE_ROOT`). Back up and migrate this file together with the database; existing profile secrets cannot be decrypted without it. Manage existing profiles directly in Settings.

## Development and validation

Backend tests, from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Frontend checks, from `frontend`:

```powershell
npm run test:navigation
npm run lint
npm run build
```

Additional frontend checks cover API base URLs, worker-limit display, full logs, pagination, and AI profiles. See [`frontend/package.json`](frontend/package.json).

When changing SQLAlchemy models, add a matching Alembic migration. Run the following from `backend` and inspect the generated migration before applying it:

```powershell
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe_change"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m pytest
```

## Deployment

The repository includes a Windows intranet deployment guide and scripts for Linux server releases:

- [Windows intranet deployment guide (Chinese)](deploy/windows-intranet.md)
- [Linux server bootstrap script](deploy/server-bootstrap-github.sh)
- [Local production publishing script](deploy/publish-deploy-prod.ps1)
- [Server update script](deploy/server-update.sh)

For an existing production installation, update in this order:

```powershell
# Local repository root; requires a clean working tree
.\deploy\publish-deploy-prod.ps1
```

```bash
# Project directory on the server
bash deploy/server-update.sh
```

The local publishing script runs checks, builds the frontend, and updates the `deploy-prod` branch on GitHub. The server script pulls deployment code, installs backend dependencies, applies migrations, and restarts services. These scripts contain this project's current domains, paths, and service names; review their parameters and configuration before deploying elsewhere.

Updating only the GitHub README does not require a production deployment. Local file changes are not automatically uploaded to GitHub.

## Repository layout

```text
PDFAI/
├── backend/
│   ├── app/
│   │   ├── ai/           # Vision providers, Mock mode, and failover
│   │   ├── api/          # Task, settings, and system log endpoints
│   │   ├── services/     # Drawing processing, scheduling, AI profiles, and logs
│   │   ├── models/       # Database models
│   │   └── exports/      # Excel exports
│   ├── alembic/          # Database migrations
│   ├── scripts/          # Startup and migration checks
│   └── tests/            # Backend tests
├── frontend/
│   ├── src/              # Pages, components, routes, and API client
│   └── scripts/          # Frontend regression checks
├── deploy/               # Release scripts and deployment documentation
├── storage/              # Runtime data (ignored by Git)
├── start-dev.ps1          # Windows development startup
├── README.md             # Chinese documentation
└── README.en.md          # English documentation
```
