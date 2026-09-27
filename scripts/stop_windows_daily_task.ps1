# PowerShell script to stop and remove APIx Daily Scraper from Windows Task Scheduler

$TaskName = "APIx_Daily_Scraper"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   Removing APIx Daily Scheduled Task from Windows       " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($ExistingTask) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "[SUCCESS] Task '$TaskName' has been unregistered and removed." -ForegroundColor Green
} else {
    Write-Host "[INFO] Task '$TaskName' does not exist or was already removed." -ForegroundColor Yellow
}
Write-Host "==========================================================" -ForegroundColor Cyan
