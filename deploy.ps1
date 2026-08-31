# deploy.ps1 — Commit, push to GitHub, and deploy to Railway in one step
# Usage: .\deploy.ps1 "Your commit message"

param(
    [string]$Message = "Update $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
)

Set-Location "$PSScriptRoot"

Write-Host "==> Staging all changes..." -ForegroundColor Cyan
git add -A

$status = git status --porcelain
if (-not $status) {
    Write-Host "Nothing to commit — pushing and deploying anyway." -ForegroundColor Yellow
} else {
    Write-Host "==> Committing: $Message" -ForegroundColor Cyan
    git commit -m $Message
    if ($LASTEXITCODE -ne 0) { Write-Host "Commit failed." -ForegroundColor Red; exit 1 }
}

Write-Host "==> Pushing to GitHub..." -ForegroundColor Cyan
git push origin master
if ($LASTEXITCODE -ne 0) { Write-Host "Push failed." -ForegroundColor Red; exit 1 }

Write-Host "==> Deploying to Railway..." -ForegroundColor Cyan
Set-Location "$PSScriptRoot\warehouse-app"
railway up --detach
if ($LASTEXITCODE -ne 0) { Write-Host "Railway deploy failed." -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "Done! GitHub and Railway are both up to date." -ForegroundColor Green
