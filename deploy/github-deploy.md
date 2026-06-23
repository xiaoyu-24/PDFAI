# GitHub deploy-prod 部署流程

本文档用于把 PDFAI 从手动上传 zip 改成通过 GitHub `deploy-prod` 分支更新服务器。

## 分支约定

- `main`：源码分支，不提交 `frontend/dist`。
- `deploy-prod`：部署分支，包含服务器可直接使用的后端代码和 `frontend/dist`。
- 生产私有文件不进 git：`backend/.env`、`backend/.venv`、`storage/`、日志文件。

## 一次性服务器准备

在服务器生成部署密钥：

```bash
ssh-keygen -t ed25519 -C "pdfai-deploy" -f ~/.ssh/pdfai_github
cat ~/.ssh/pdfai_github.pub
```

把公钥添加到 GitHub 仓库的 Deploy keys。只需要拉取时可以勾选只读；如果服务器也要推送才勾选写权限。

配置 SSH：

```bash
cat >> ~/.ssh/config <<'EOF'
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/pdfai_github
EOF

chmod 600 ~/.ssh/config ~/.ssh/pdfai_github
ssh -T git@github.com
```

接管现有目录不要直接在旧目录 `git init && checkout`，因为现有文件可能和仓库文件冲突。使用 bootstrap 脚本会先备份，再 clone `deploy-prod` 到新目录，并迁移 `backend/.env`、`backend/.venv`、`storage/`。

服务器先手动备份一次：

```bash
cd /www/wwwroot/ocrconnect.wltlink.com
tar -czf /root/pdfai-before-git-$(date +%F-%H%M%S).tar.gz PDFAI
```

然后从 GitHub 临时克隆部署分支，并执行首次接管：

```bash
rm -rf /tmp/PDFAI-deploy-bootstrap
git clone --branch deploy-prod <GITHUB_SSH_URL> /tmp/PDFAI-deploy-bootstrap
bash /tmp/PDFAI-deploy-bootstrap/deploy/server-bootstrap-github.sh <GITHUB_SSH_URL>
```

不要执行 `git clean -fdx`，避免删除 `backend/.env`、`backend/.venv` 和 `storage/`。

## 本地发布

本地仓库当前已有 GitHub `origin`：

```text
https://github.com/xiaoyu-24/PDFAI.git
```

如果继续使用这个 remote，在 Windows 本地执行：

```powershell
cd D:\projects\PDFAI
.\deploy\publish-deploy-prod.ps1
```

如果要改成 SSH 地址：

```powershell
.\deploy\publish-deploy-prod.ps1 -GitHubRemote "git@github.com:xiaoyu-24/PDFAI.git"
```

脚本会执行：

- 后端完整 pytest
- 前端 `npm run test:navigation`
- 前端 `npm run lint`
- 使用 `VITE_API_BASE_URL=https://api.ocrconnect.wltlink.com/api` 构建前端
- 将 `frontend/dist` 强制加入 `deploy-prod`
- 推送 `deploy-prod` 到 GitHub

## 服务器更新

服务器执行：

```bash
cd /www/wwwroot/ocrconnect.wltlink.com/PDFAI
bash deploy/server-update.sh
```

脚本会执行：

- `git pull --ff-only origin deploy-prod`
- 安装后端依赖
- 执行 Alembic migration
- 重启 `pdfai-backend`
- 校验并重载 Nginx
- 验证前后端访问

## 生产配置

服务器 `backend/.env` 至少保留：

```env
APP_ENV=production
CORS_ORIGINS=https://ocrconnect.wltlink.com
TASK_MAX_WORKERS=2
AI_MAX_CONCURRENT_CALLS_PER_TASK=1
STORAGE_ROOT=/www/wwwroot/ocrconnect.wltlink.com/PDFAI/storage
```

`storage/` 继续由服务器持久化，不随 git 更新删除。
