param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$SkipMigrationCheck
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $RootDir "backend"
$BackendPython = Join-Path $RootDir "backend\.venv\Scripts\python.exe"
$MigrationCheck = Join-Path $RootDir "backend\scripts\check_migration_status.py"

function Stop-WithMessage {
    param([string]$Message)
    Write-Host ""
    Write-Host $Message -ForegroundColor Red
    exit 1
}

function Invoke-BackendNativeCommand {
    param([string[]]$Arguments)

    Push-Location $BackendDir
    try {
        $previousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $output = & $BackendPython @Arguments 2>&1
        $exitCode = $LASTEXITCODE
        return [pscustomobject]@{
            ExitCode = $exitCode
            Output = $output
        }
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
        Pop-Location
    }
}

Write-Host "PDFAI backend production-style startup check" -ForegroundColor Cyan
Write-Host "Project: $RootDir"

if (-not (Test-Path $BackendPython)) {
    Stop-WithMessage "Backend virtual environment was not found. Expected: $BackendPython"
}

if (-not (Test-Path (Join-Path $BackendDir ".env"))) {
    Stop-WithMessage "Backend .env was not found. Create it from backend\.env.example before starting."
}

if (-not (Test-Path $MigrationCheck)) {
    Stop-WithMessage "Migration check script was not found. Expected: $MigrationCheck"
}

Write-Host "Checking backend dependencies..."
$dependencyResult = Invoke-BackendNativeCommand @(
    "-c",
    "import fastapi, pymysql, alembic, fitz, PIL, openpyxl"
)
if ($dependencyResult.ExitCode -ne 0) {
    if ($dependencyResult.Output) {
        $dependencyResult.Output | Write-Host
    }
    Stop-WithMessage "Backend dependencies are missing. Run: cd $BackendDir; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
}

Write-Host "Preparing storage directories..."
$storageResult = Invoke-BackendNativeCommand @(
    "-c",
    "from app.core.config import get_settings; s=get_settings(); [s.get_storage_path(d).mkdir(parents=True, exist_ok=True) for d in ['uploads','pages','regions','ai_outputs','exports']]; print(s.storage_root_path)"
)
if ($storageResult.ExitCode -ne 0) {
    if ($storageResult.Output) {
        $storageResult.Output | Write-Host
    }
    Stop-WithMessage "Unable to prepare storage directories."
}
if ($storageResult.Output) {
    Write-Host "Storage root: $($storageResult.Output[-1])"
}

if (-not $SkipMigrationCheck) {
    Write-Host "Checking Alembic migration status..."
    $migrationResult = Invoke-BackendNativeCommand @($MigrationCheck)
    if ($migrationResult.Output) {
        $migrationResult.Output | Write-Host
    }
    if ($migrationResult.ExitCode -ne 0) {
        exit $migrationResult.ExitCode
    }
}

Write-Host ""
Write-Host "Starting backend on http://${HostAddress}:$Port" -ForegroundColor Green
Write-Host "Production command example: backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

Push-Location $BackendDir
try {
    & $BackendPython -m uvicorn app.main:app --host $HostAddress --port $Port
}
finally {
    Pop-Location
}
