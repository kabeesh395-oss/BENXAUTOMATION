@echo off
cd /d "E:\New folder\BENXAUTOMATION"
echo [%date% %time%] Starting automated private YouTube upload for BENXAUTOMATION... >> "output\scheduled_upload.log"
python -m benxautomation.main --workflow animated --count 3 --mode upload_private >> "output\scheduled_upload.log" 2>&1
echo [%date% %time%] Scheduled job finished with exit code %errorlevel%. >> "output\scheduled_upload.log"
