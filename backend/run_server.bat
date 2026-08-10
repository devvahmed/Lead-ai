@echo off
title ClientPlus AI Backend Server
echo ======================================================
echo        Starting ClientPlus AI Backend Server
echo ======================================================
cd /d "%~dp0"
set PYTHONUNBUFFERED=1
.\venv\Scripts\python.exe -m uvicorn email_outreach:app --host 127.0.0.1 --port 8000 --reload
pause
