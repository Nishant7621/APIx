# PowerShell script to register APIx Daily Scraper with Windows Task Scheduler
# Runs every morning at 06:00:00 AM IST automatically even if VS Code is closed.

$TaskName = "APIx_Daily_Scraper"
$PythonPath = "C:\All Folder\APIx\flight-price-index\venv\Scripts\python.exe"
$ScriptPath = "C:\All Folder\APIx\flight-price-index\scheduler\daily_auto_collector.py"
$WorkingDirectory = "C:\All Folder\APIx\flight-price-index"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   Setting up APIx Daily Scheduled Task in Windows        " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Check if task already exists
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($ExistingTask) {
    Write-Host "[INFO] Existing task '$TaskName' found. Updating configuration..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create Action: Run python.exe scheduler\daily_auto_collector.py --run-now
$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument "$ScriptPath --run-now" -WorkingDirectory $WorkingDirectory

# Create Trigger: Daily at 06:00 AM
$Trigger = New-ScheduledTaskTrigger -Daily -At "06:00AM"

# Settings: Allow on battery, start when available if missed
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Register the Scheduled Task
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "APIx Flight Price Index Daily Automated Scraping Engine (MoSPI / SIH 26056)"

Write-Host "[SUCCESS] Windows Scheduled Task '$TaskName' registered successfully!" -ForegroundColor Green
Write-Host "Schedule: Runs automatically every morning at 06:00 AM." -ForegroundColor Green
Write-Host "Target  : Inserts fresh T+1..T+45 airfares into PostgreSQL (apix_db)." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
