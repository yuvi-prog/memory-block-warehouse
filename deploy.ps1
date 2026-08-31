# deploy.ps1 — Commit and push to GitHub (Railway auto-deploys from GitHub)
# Usage: .\deploy.ps1 "Your commit message"

param(
    [string]$Message = "Update $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
)

Set-Location "$PSScriptRoot"

Write-Host "==> Staging all changes..." -ForegroundColor Cyan
git add -A

$status = git status --porcelain
if (-not $status) {
    Write-Host "Nothing new to commit." -ForegroundColor Yellow
} else {
    Write-Host "==> Committing: $Message" -ForegroundColor Cyan
    git commit -m $Message
    if ($LASTEXITCODE -ne 0) { Write-Host "Commit failed." -ForegroundColor Red; exit 1 }
}

Write-Host "==> Pushing to GitHub..." -ForegroundColor Cyan
git push origin master
if ($LASTEXITCODE -ne 0) { Write-Host "Push failed." -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "Done! Railway will auto-deploy from GitHub." -ForegroundColor Green
