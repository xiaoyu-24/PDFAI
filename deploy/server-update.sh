#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/www/wwwroot/ocrconnect.wltlink.com/PDFAI}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-deploy-prod}"
BACKEND_SERVICE="${BACKEND_SERVICE:-pdfai-backend}"
FRONTEND_URL="${FRONTEND_URL:-https://ocrconnect.wltlink.com/tasks}"
API_HEALTH_URL="${API_HEALTH_URL:-https://api.ocrconnect.wltlink.com/api/health}"

cd "$APP_DIR"

git fetch origin "$DEPLOY_BRANCH"
git checkout "$DEPLOY_BRANCH"
git pull --ff-only origin deploy-prod

cd "$APP_DIR/backend"
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m alembic upgrade head

# Default action is equivalent to: systemctl restart pdfai-backend
systemctl restart "$BACKEND_SERVICE"

nginx -t
nginx -s reload

# Default health check is equivalent to: curl https://api.ocrconnect.wltlink.com/api/health
curl "$API_HEALTH_URL"
curl -I "$FRONTEND_URL"
systemctl status "$BACKEND_SERVICE" --no-pager -l
