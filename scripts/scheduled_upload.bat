@echo off
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "E:\New folder\BENXAUTOMATION"
echo ======================================================= >> "output\daily_scheduler.log"
echo [%date% %time%] STARTING DAILY AUTONOMOUS MULTI-AGENT PRODUCTION >> "output\daily_scheduler.log"
"C:\Users\Admin\python311\tools\python.exe" scripts\daily_autonomous_scheduler.py --mode longform --publish --privacy unlisted >> "output\daily_scheduler.log" 2>&1
echo [%date% %time%] DAILY PRODUCTION COMPLETED (Exit Code: %errorlevel%) >> "output\daily_scheduler.log"
echo ======================================================= >> "output\daily_scheduler.log"
