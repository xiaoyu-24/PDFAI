$ErrorActionPreference = "Stop"

function Assert-Contains {
    param(
        [string] $Path,
        [string] $Pattern,
        [string] $Message
    )

    $content = Get-Content -Raw -LiteralPath $Path
    if ($content -notmatch $Pattern) {
        throw $Message
    }
}

$publishScript = Join-Path $PSScriptRoot "publish-deploy-prod.ps1"
$serverScript = Join-Path $PSScriptRoot "server-update.sh"
$bootstrapScript = Join-Path $PSScriptRoot "server-bootstrap-github.sh"
$guide = Join-Path $PSScriptRoot "github-deploy.md"
$requirements = Join-Path (Split-Path -Parent $PSScriptRoot) "backend\requirements.txt"

foreach ($path in @($publishScript, $serverScript, $bootstrapScript, $guide)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Missing deployment workflow file: $path"
    }
}

Assert-Contains $publishScript "GitHubRemote" "publish script must use GitHub remote naming"
Assert-Contains $publishScript "VITE_API_BASE_URL" "publish script must build frontend with production API base URL"
Assert-Contains $publishScript "git add -f frontend/dist" "publish script must force-add frontend/dist on deploy branch"
Assert-Contains $publishScript "deploy-prod" "publish script must target deploy-prod"
Assert-Contains $publishScript "npm run test:navigation" "publish script must run frontend navigation checks"
Assert-Contains $publishScript "pytest" "publish script must run backend pytest"

Assert-Contains $serverScript "git pull --ff-only origin deploy-prod" "server update script must pull deploy-prod without rewriting local private files"
Assert-Contains $serverScript "alembic upgrade head" "server update script must apply migrations"
Assert-Contains $serverScript "systemctl restart pdfai-backend" "server update script must restart backend service"
Assert-Contains $serverScript "nginx -t" "server update script must validate nginx before reload"
Assert-Contains $serverScript "curl https://api.ocrconnect.wltlink.com/api/health" "server update script must verify backend health"

Assert-Contains $bootstrapScript "tar -czf" "bootstrap script must backup existing server directory"
Assert-Contains $bootstrapScript "git clone --branch deploy-prod" "bootstrap script must clone deploy-prod"
Assert-Contains $bootstrapScript "backend/.env" "bootstrap script must preserve backend/.env"
Assert-Contains $bootstrapScript "storage" "bootstrap script must preserve storage"
Assert-Contains $bootstrapScript "backend/.venv" "bootstrap script must preserve backend virtualenv"

Assert-Contains $guide "github.com" "guide must document GitHub SSH setup"
Assert-Contains $guide "backend/.env" "guide must state that backend/.env stays private on the server"
Assert-Contains $guide "storage/" "guide must state that storage stays persistent on the server"
Assert-Contains $guide "deploy-prod" "guide must document deploy-prod workflow"

Assert-Contains $requirements "eval_type_backport" "requirements.txt must include eval_type_backport for Python 3.9 deployment"

Write-Host "GitHub deployment workflow checks passed"
