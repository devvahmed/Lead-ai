Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "       Starting ClientPlus AI Backend Server          " -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Cyan
Set-Location -Path $PSScriptRoot
$env:PYTHONUNBUFFERED="1"
# 0.0.0.0 = accessible from all network interfaces (other computers on LAN)
.\venv\Scripts\python.exe -m uvicorn email_outreach:app --host 0.0.0.0 --port 8000 --reload
