Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "       Starting ClientPlus AI Backend Server          " -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Cyan
Set-Location -Path $PSScriptRoot
$env:PYTHONUNBUFFERED="1"
.\venv\Scripts\python.exe -m uvicorn email_outreach:app --host 127.0.0.1 --port 8000 --reload
