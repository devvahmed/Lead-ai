@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo   Lead-AI - Automated Project Setup & Install
echo ========================================================
echo.

:: 1. Check Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH! Please install Python 3.10-3.12.
    pause
    exit /b 1
)

:: 2. Check Node
where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js / npm is not installed! Please install Node.js 18+.
    pause
    exit /b 1
)

:: 3. Create Python Virtual Environment
echo [1/4] Setting up Python virtual environment (venv)...
if not exist "venv" (
    python -m venv venv
)

:: 4. Install Python Dependencies
echo [2/4] Installing Python requirements...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium

:: 5. Install Node Frontend Dependencies
echo [3/4] Installing Node.js frontend dependencies (npm install)...
call npm install

:: 6. Environment File
echo [4/4] Checking .env file...
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env
        echo [INFO] Created .env from .env.example. Please update your API keys!
    )
) else (
    echo [INFO] .env already exists.
)

echo.
echo ========================================================
echo   Setup Complete!
echo   Run 'python launch_app.py' or 'npm run dev' to start.
echo ========================================================
pause
