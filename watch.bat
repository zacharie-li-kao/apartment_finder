@echo off
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
"C:\Program Files\Python313\python.exe" -u run.py >> watch_run.log 2>&1
