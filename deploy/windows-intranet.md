# PDFAI Windows 内网试用版部署手册

本手册用于把 PDFAI 部署为 Windows 内网试用版，让同一局域网用户通过 `http://服务器内网IP/` 访问。

## 1. 部署结构

```text
浏览器
  -> Nginx :80
      -> frontend/dist 静态前端
      -> /api 反向代理到 FastAPI 127.0.0.1:8000
  -> MySQL
  -> D:/projects/PDFAI/storage 持久化文件
```

后端只监听 `127.0.0.1:8000`，不要直接开放 8000 端口。

## 2. 必要软件

- Python 3.10+
- Node.js 18+
- MySQL 8.x
- Nginx for Windows
- 可选：NSSM，用于把后端和 Nginx 注册成 Windows 服务

当前项目目录假设为：

```powershell
D:\projects\PDFAI
```

## 3. 配置后端环境变量

复制模板：

```powershell
cd D:\projects\PDFAI\backend
Copy-Item .env.example .env
notepad .env
```

内网试用建议：

```env
APP_ENV=production
DATABASE_URL=mysql+pymysql://pdfai:请换成强密码@localhost:3306/pdfai
STORAGE_ROOT=D:/projects/PDFAI/storage

PDF_RENDER_DPI=300
PDF_RENDER_FORMAT=png
CROP_PADDING_RATIO=0.06

AI_BASE_URL=https://你的AI服务地址/v1
AI_API_KEY=你的AI密钥
AI_MODEL=支持图片识别的模型名
AI_TIMEOUT_SECONDS=120
AI_MAX_RETRIES=2
AI_ENABLE_FULL_PAGE_EXTRACTION=true
AI_ENABLE_REGION_EXTRACTION=false
AI_IMAGE_MAX_EDGE=1600
AI_IMAGE_JPEG_QUALITY=75
```

AI Key 只能留在后端 `.env` 或服务器环境变量里，不要写进前端和 Git。

## 4. 创建 MySQL 数据库

用 MySQL 客户端执行：

```sql
CREATE DATABASE pdfai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'pdfai'@'localhost' IDENTIFIED BY '请换成强密码';
GRANT ALL PRIVILEGES ON pdfai.* TO 'pdfai'@'localhost';
FLUSH PRIVILEGES;
```

如果 MySQL 不在本机，需要按实际来源 IP 授权，并确保数据库端口只在内网开放。

## 5. 构建前端

```powershell
cd D:\projects\PDFAI
.\start-frontend.ps1
```

脚本会执行：

- `npm ci`
- `npm run test:navigation`
- `npm run lint`
- `npm run build`

构建产物目录：

```text
D:\projects\PDFAI\frontend\dist
```

## 6. 初始化数据库迁移

```powershell
cd D:\projects\PDFAI\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts\check_migration_status.py
```

看到 `Database schema is already at Alembic head.` 后再启动后端。

## 7. 启动后端

```powershell
cd D:\projects\PDFAI
.\start-backend.ps1
```

该脚本使用：

```powershell
D:\projects\PDFAI\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

生产试用版不使用 `--reload`。

健康检查：

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/health
```

期望返回 `{"status":"ok"}`。

## 8. 配置 Nginx

复制示例配置：

```powershell
Copy-Item D:\projects\PDFAI\deploy\nginx.windows.intranet.conf.example C:\nginx\conf\nginx.conf
```

测试配置：

```powershell
cd C:\nginx
.\nginx.exe -t
```

启动或重载：

```powershell
cd C:\nginx
.\nginx.exe
.\nginx.exe -s reload
```

## 9. Windows 防火墙

只开放 80 端口：

```powershell
New-NetFirewallRule `
  -DisplayName "PDFAI HTTP 80" `
  -Direction Inbound `
  -Protocol TCP `
  -LocalPort 80 `
  -Action Allow
```

不要开放 8000 端口。

## 10. 内网验收

在服务器执行：

```powershell
ipconfig
```

假设服务器 IP 是 `192.168.1.50`，在另一台内网电脑访问：

```text
http://192.168.1.50/
```

检查：

- 页面能打开
- 刷新 `/tasks/:id`、`/tasks/:id/diffs` 不 404
- 任务列表能加载
- 系统设置能读取
- 能上传任务
- 后端能处理任务
- 差异报告能查看
- Excel 能导出

## 11. 服务化建议

手动跑通后，用 NSSM 注册后端服务：

```powershell
nssm install PDFAI-Backend
```

填写：

```text
Path:
D:\projects\PDFAI\backend\.venv\Scripts\python.exe

Startup directory:
D:\projects\PDFAI\backend

Arguments:
-m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

启动：

```powershell
nssm start PDFAI-Backend
```

## 12. 每次发布更新

```powershell
cd D:\projects\PDFAI
git pull
```

后端：

```powershell
cd D:\projects\PDFAI\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts\check_migration_status.py
.\.venv\Scripts\python.exe -m pytest
```

前端：

```powershell
cd D:\projects\PDFAI
.\start-frontend.ps1
```

重启服务：

```powershell
nssm restart PDFAI-Backend
cd C:\nginx
.\nginx.exe -s reload
```

## 13. 备份

每天备份：

- MySQL 数据库
- `D:\projects\PDFAI\storage`
- `D:\projects\PDFAI\backend\.env`

数据库和 `storage` 必须成组备份，否则数据库中的文件路径可能找不到实际文件。

## 14. 常见问题

页面能打开但接口失败：

- 检查后端是否运行：`Invoke-WebRequest http://127.0.0.1:8000/api/health`
- 检查 Nginx `/api/` 反代配置

上传失败：

- 检查 `client_max_body_size 200m`
- 检查 `storage/uploads` 是否可写

数据库报缺字段：

```powershell
cd D:\projects\PDFAI\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts\check_migration_status.py
```

任务失败：

- 检查 AI Base URL、模型、Key
- 检查模型是否支持图片输入
- 检查 `storage/ai_outputs`
