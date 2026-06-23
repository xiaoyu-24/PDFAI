param(
    [switch]$SkipInstall,
    [switch]$SkipValidation
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendDir = Join-Path $RootDir "frontend"
$DistDir = Join-Path $FrontendDir "dist"

function Stop-WithMessage {
    param([string]$Message)
    Write-Host ""
    Write-Host $Message -ForegroundColor Red
    exit 1
}

Write-Host "PDFAI frontend production build" -ForegroundColor Cyan
Write-Host "Project: $RootDir"

if (-not (Test-Path (Join-Path $FrontendDir "package.json"))) {
    Stop-WithMessage "Frontend package.json was not found. Expected: $FrontendDir"
}

Push-Location $FrontendDir
try {
    if (-not $SkipInstall) {
        Write-Host "Installing frontend dependencies with npm ci..."
        npm ci
        if ($LASTEXITCODE -ne 0) {
            Stop-WithMessage "npm ci failed."
        }
    }

    if (-not $SkipValidation) {
        Write-Host "Running navigation regression check..."
        npm run test:navigation
        if ($LASTEXITCODE -ne 0) {
            Stop-WithMessage "npm run test:navigation failed."
        }

        Write-Host "Running frontend lint..."
        npm run lint
        if ($LASTEXITCODE -ne 0) {
            Stop-WithMessage "npm run lint failed."
        }
    }

    Write-Host "Building production frontend..."
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Stop-WithMessage "npm run build failed."
    }
}
finally {
    Pop-Location
}

if (-not (Test-Path (Join-Path $DistDir "index.html"))) {
    Stop-WithMessage "Frontend build finished but dist\index.html was not found."
}

Write-Host ""
Write-Host "Frontend build is ready: $DistDir" -ForegroundColor Green
Write-Host "Use deploy\nginx.windows.intranet.conf.example to serve this directory through Nginx."
