param(
    [string] $GitHubRemote = "",

    [string] $DeployBranch = "deploy-prod",
    [string] $GitHubRemoteName = "origin",
    [string] $ApiBaseUrl = "https://api.ocrconnect.wltlink.com/api",
    [switch] $SkipTests,
    [switch] $NoPush
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$worktreePath = Join-Path ([System.IO.Path]::GetTempPath()) ("pdfai-deploy-prod-" + [Guid]::NewGuid().ToString("N"))

function Run-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]] $Args)
    & git -C $repoRoot @Args
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Args -join ' ') failed"
    }
}

function Run-Command {
    param(
        [string] $WorkingDirectory,
        [string] $FilePath,
        [string[]] $Arguments,
        [hashtable] $Environment = @{}
    )

    Push-Location $WorkingDirectory
    try {
        foreach ($key in $Environment.Keys) {
            Set-Item -Path "Env:$key" -Value $Environment[$key]
        }
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "$FilePath $($Arguments -join ' ') failed"
        }
    }
    finally {
        foreach ($key in $Environment.Keys) {
            Remove-Item -Path "Env:$key" -ErrorAction SilentlyContinue
        }
        Pop-Location
    }
}

try {
    $status = & git -C $repoRoot status --porcelain
    if ($status) {
        throw "Working tree is not clean. Commit or stash changes before publishing deploy-prod."
    }
    $sourceRef = (& git -C $repoRoot rev-parse HEAD).Trim()

    if (-not $SkipTests) {
        # Required release checks: pytest, npm run test:navigation, npm run lint.
        Run-Command -WorkingDirectory (Join-Path $repoRoot "backend") `
            -FilePath ".\.venv\Scripts\python.exe" `
            -Arguments @("-m", "pytest")

        Run-Command -WorkingDirectory (Join-Path $repoRoot "frontend") `
            -FilePath "npm" `
            -Arguments @("run", "test:navigation")

        Run-Command -WorkingDirectory (Join-Path $repoRoot "frontend") `
            -FilePath "npm" `
            -Arguments @("run", "lint")
    }

    Run-Command -WorkingDirectory (Join-Path $repoRoot "frontend") `
        -FilePath "npm" `
        -Arguments @("run", "build") `
        -Environment @{ VITE_API_BASE_URL = $ApiBaseUrl }

    $remoteExists = (& git -C $repoRoot remote) -contains $GitHubRemoteName
    if ($remoteExists) {
        if ($GitHubRemote) {
            Run-Git remote set-url $GitHubRemoteName $GitHubRemote
        }
    }
    else {
        if (-not $GitHubRemote) {
            throw "Remote '$GitHubRemoteName' does not exist. Pass -GitHubRemote git@github.com:<owner>/<repo>.git."
        }
        Run-Git remote add $GitHubRemoteName $GitHubRemote
    }

    Run-Git fetch $GitHubRemoteName

    $localBranchExists = (& git -C $repoRoot branch --list $DeployBranch)
    $remoteBranchExists = (& git -C $repoRoot branch -r --list "$GitHubRemoteName/$DeployBranch")
    if ($localBranchExists) {
        Run-Git worktree add $worktreePath $DeployBranch
    }
    else {
        if ($remoteBranchExists) {
            Run-Git worktree add -b $DeployBranch $worktreePath "$GitHubRemoteName/$DeployBranch"
        }
        else {
            Run-Git worktree add -b $DeployBranch $worktreePath HEAD
        }
    }

    if ($remoteBranchExists) {
        & git -C $worktreePath pull --ff-only $GitHubRemoteName $DeployBranch
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to fast-forward $DeployBranch from $GitHubRemoteName"
        }
    }
    else {
        Write-Host "Skipping remote pull because $GitHubRemoteName/$DeployBranch does not exist yet."
    }

    & git -C $worktreePath merge --no-edit $sourceRef
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to merge current source branch into $DeployBranch"
    }

    $distInWorktree = Join-Path $worktreePath "frontend\dist"
    if (Test-Path -LiteralPath $distInWorktree) {
        Remove-Item -Recurse -Force -LiteralPath $distInWorktree
    }
    Copy-Item -Recurse -Force -LiteralPath (Join-Path $repoRoot "frontend\dist") -Destination $distInWorktree

    # Keep this force-add behavior: git add -f frontend/dist publishes built assets on deploy-prod.
    & git -C $worktreePath add -A
    & git -C $worktreePath add -f frontend/dist
    & git -C $worktreePath diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        & git -C $worktreePath commit -m "deploy: publish $stamp"
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to commit deploy branch changes"
        }
    }
    else {
        Write-Host "No deploy changes to commit."
    }

    if (-not $NoPush) {
        & git -C $worktreePath push -u $GitHubRemoteName $DeployBranch
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to push $DeployBranch to $GitHubRemoteName"
        }
    }

    Write-Host "deploy-prod publish workflow completed"
}
finally {
    if (Test-Path -LiteralPath $worktreePath) {
        & git -C $repoRoot worktree remove --force $worktreePath | Out-Null
    }
}
