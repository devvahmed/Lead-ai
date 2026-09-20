# ClientPlus AI - Automated PowerShell Setup Script
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  ClientPlus AI - Automated Project Setup & Install     " -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan

# 1. Check Python
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "[ERROR] Python is not installed or not in PATH. Please install Python 3.10-3.12." -ForegroundColor Red
    exit 1
}

# 2. Check Node & NPM
$npmCmd = Get-Command npm -ErrorAction SilentlyContinue
if (-not $npmCmd) {
    Write-Host "[ERROR] Node.js / npm is not installed. Please install Node.js 18+." -ForegroundColor Red
    exit 1
}

# 3. Create Python venv
Write-Host "`n[1/4] Setting up Python virtual environment (venv)..." -ForegroundColor Yellow
if (-not (Test-Path "venv")) {
    python -m venv venv
}

# 4. Install Python Dependencies
Write-Host "[2/4] Installing Python requirements..." -ForegroundColor Yellow
& ".\venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\venv\Scripts\pip.exe" install -r requirements.txt
& ".\venv\Scripts\playwright.exe" install chromium

# 5. Install Node Frontend Dependencies
Write-Host "`n[3/4] Installing Node.js frontend dependencies (npm install)..." -ForegroundColor Yellow
npm install

# 6. Setup .env file
Write-Host "`n[4/4] Checking .env configuration..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "[INFO] Created .env from .env.example. Please review and update your API keys!" -ForegroundColor Green
    }
} else {
    Write-Host "[INFO] .env already exists." -ForegroundColor Gray
}

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "  Run 'python launch_app.py' or 'npm run dev' to start." -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Cyan
