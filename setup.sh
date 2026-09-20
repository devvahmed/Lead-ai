#!/usr/bin/env bash
set -e

echo "========================================================"
echo "  ClientPlus AI - Automated Project Setup & Install     "
echo "========================================================"

# 1. Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed or not in PATH!"
    exit 1
fi

# 2. Check Node/npm
if ! command -v npm &> /dev/null; then
    echo "[ERROR] Node.js / npm is not installed!"
    exit 1
fi

# 3. Virtual Environment
echo "[1/4] Setting up Python virtual environment (venv)..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# 4. Install Python Dependencies
echo "[2/4] Installing Python requirements..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium

# 5. Install Node Frontend Dependencies
echo "[3/4] Installing Node.js frontend dependencies (npm install)..."
npm install

# 6. Setup .env file
echo "[4/4] Checking .env configuration..."
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp .env.example .env
    echo "[INFO] Created .env from .env.example. Please review and update your API keys!"
else
    echo "[INFO] .env already exists."
fi

echo ""
echo "========================================================"
echo "  Setup Complete!"
echo "  Run 'npm run dev' and 'uvicorn email_outreach:app' to start."
echo "========================================================"
