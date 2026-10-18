# Register Windows Scheduled Task for BENXAUTOMATION Daily Multi-Agent Pipeline
param(
    [string]$Time = "09:00AM",
    [string]$TaskName = "BENX_Daily_Autonomous_Pipeline"
)

$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument '/c "E:\New folder\BENXAUTOMATION\scripts\scheduled_upload.bat"' -WorkingDirectory "E:\New folder\BENXAUTOMATION"
$Trigger = New-ScheduledTaskTrigger -Daily -At $Time
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -WakeToRun

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Daily autonomous 2D animation generation (Longform + 2 Auto-Shorts) with Gemini scriptwriting and YouTube upload" -Force

Write-Host "Scheduled Task Registered Successfully:" -ForegroundColor Green
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State
