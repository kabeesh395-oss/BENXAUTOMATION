# Register Windows Scheduled Task for BENXAUTOMATION YouTube Upload
$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument '/c "E:\New folder\BENXAUTOMATION\scripts\scheduled_upload.bat"'
$Trigger = New-ScheduledTaskTrigger -Daily -At "10:00AM"
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName "BENX_YouTube_Upload" -Action $Action -Trigger $Trigger -Settings $Settings -Description "Automated public YouTube Shorts upload for BENXAUTOMATION" -Force

Get-ScheduledTask -TaskName "BENX_YouTube_Upload" | Select-Object TaskName, State
