#!/usr/bin/env bash
set -euo pipefail

GITHUB_REPO_SSH="${1:-${GITHUB_REPO_SSH:-}}"
APP_PARENT="${APP_PARENT:-/www/wwwroot/ocrconnect.wltlink.com}"
APP_NAME="${APP_NAME:-PDFAI}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-deploy-prod}"

if [[ -z "$GITHUB_REPO_SSH" ]]; then
  echo "Usage: bash deploy/server-bootstrap-github.sh git@github.com:<owner>/<repo>.git"
  echo "Or set GITHUB_REPO_SSH=git@github.com:<owner>/<repo>.git"
  exit 2
fi

APP_DIR="$APP_PARENT/$APP_NAME"
NEW_DIR="$APP_PARENT/${APP_NAME}.git-new"
OLD_DIR="$APP_PARENT/${APP_NAME}.before-git.$(date +%F-%H%M%S)"
BACKUP="/root/pdfai-before-git-$(date +%F-%H%M%S).tar.gz"

cd "$APP_PARENT"

if [[ ! -d "$APP_DIR" ]]; then
  echo "Existing app directory not found: $APP_DIR"
  exit 1
fi

tar -czf "$BACKUP" "$APP_NAME"
echo "Backup written to $BACKUP"

rm -rf "$NEW_DIR"
git clone --branch deploy-prod "$GITHUB_REPO_SSH" "$NEW_DIR"

if [[ -f "$APP_DIR/backend/.env" ]]; then
  mkdir -p "$NEW_DIR/backend"
  cp -a "$APP_DIR/backend/.env" "$NEW_DIR/backend/.env"
fi

if [[ -d "$APP_DIR/backend/.venv" ]]; then
  rm -rf "$NEW_DIR/backend/.venv"
  cp -a "$APP_DIR/backend/.venv" "$NEW_DIR/backend/.venv"
fi

if [[ -d "$APP_DIR/storage" ]]; then
  rm -rf "$NEW_DIR/storage"
  cp -a "$APP_DIR/storage" "$NEW_DIR/storage"
fi

mv "$APP_DIR" "$OLD_DIR"
mv "$NEW_DIR" "$APP_DIR"

chown -R www:www "$APP_DIR/frontend/dist" "$APP_DIR/storage" 2>/dev/null || true

echo "Old app moved to $OLD_DIR"
echo "New Git-backed app is ready at $APP_DIR"
echo "Run: bash $APP_DIR/deploy/server-update.sh"
