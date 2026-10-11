@echo off
cd /d "E:\New folder\BENXAUTOMATION"
echo [%date% %time%] Starting scheduled YouTube upload for BENXAUTOMATION animated Shorts... >> "output\scheduled_upload.log"
"C:\Users\Admin\python311\tools\python.exe" -m benxautomation.main --workflow animated --count 25 --upload-public >> "output\scheduled_upload.log" 2>&1
echo [%date% %time%] Scheduled job finished with exit code %errorlevel%. >> "output\scheduled_upload.log"
