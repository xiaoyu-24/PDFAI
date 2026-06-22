param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [switch]$SkipMigrationCheck
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"
$BackendPython = Join-Path $RootDir "backend\.venv\Scripts\python.exe"
$MigrationCheck = Join-Path $RootDir "backend\scripts\check_migration_status.py"

function Stop-WithMessage {
    param([string]$Message)
    Write-Host ""
    Write-Host $Message -ForegroundColor Red
    exit 1
}

function Run-BackendCommand {
    param([string[]]$Arguments)
    $result = Invoke-BackendNativeCommand $Arguments
    if ($result.Output) {
        $result.Output | Write-Host
    }
    return $result.ExitCode
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

Write-Host "PDFAI development startup check" -ForegroundColor Cyan
Write-Host "Project: $RootDir"

if (-not (Test-Path $BackendPython)) {
    Stop-WithMessage "Backend virtual environment was not found. Expected: $BackendPython"
}

if (-not (Test-Path $MigrationCheck)) {
    Stop-WithMessage "Migration check script was not found. Expected: $MigrationCheck"
}

if (-not (Test-Path (Join-Path $FrontendDir "package.json"))) {
    Stop-WithMessage "Frontend package.json was not found. Expected project directory: $FrontendDir"
}

if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Stop-WithMessage "Frontend dependencies are not installed. Run: cd $FrontendDir; npm install"
}

Write-Host "Checking backend dependencies..."
$dependencyExitCode = Run-BackendCommand @("-c", "import fastapi, pymysql, alembic")
if ($dependencyExitCode -ne 0) {
    Stop-WithMessage "Backend dependencies are missing. Run: cd $BackendDir; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
}

if (-not $SkipMigrationCheck) {
    Write-Host "Checking Alembic migration status..."
    $migrationResult = Invoke-BackendNativeCommand @($MigrationCheck)
    if ($migrationResult.ExitCode -ne 0) {
        if ($migrationResult.Output) {
            $migrationResult.Output | Write-Host
        }
        exit $migrationResult.ExitCode
    }
}

$backendCommand = "Set-Location '$BackendDir'; & '$BackendPython' -m uvicorn app.main:app --reload --port $BackendPort"
$frontendCommand = "Set-Location '$FrontendDir'; npm run dev -- --host 0.0.0.0 --port $FrontendPort"

Write-Host "Starting backend on http://localhost:$BackendPort"
Start-Process powershell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $backendCommand) -WindowStyle Normal

Write-Host "Starting frontend on http://localhost:$FrontendPort"
Start-Process powershell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $frontendCommand) -WindowStyle Normal

Write-Host ""
Write-Host "Development services are starting in separate PowerShell windows." -ForegroundColor Green
Write-Host "Frontend: http://localhost:$FrontendPort"
Write-Host "Backend:  http://localhost:$BackendPort"
