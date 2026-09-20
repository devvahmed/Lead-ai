# 📋 ClientPlus AI / Lead-AI — Project Requirements & Setup Guide

This document contains everything required to install, configure, and run this project from scratch after cloning from GitHub.

---

## 🤖 Instructions for AI Assistants / Models
If you are an AI model / assistant setting up this repository for the user, execute these steps in order:

```bash
# 1. Setup Python Virtual Environment & Install Backend Dependencies
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
# source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium

# 2. Setup Node.js Frontend Dependencies
npm install

# 3. Setup Environment Variables
# Copy .env.example to .env if .env does not exist
# On Windows PowerShell:
Copy-Item .env.example .env -ErrorAction SilentlyContinue
# On Linux/macOS:
# cp -n .env.example .env
```

---

## ⚙️ 1. System Prerequisites

| Tool | Recommended Version | Purpose |
|------|---------------------|---------|
| **Python** | `3.10` – `3.12` | Backend FastAPI server, lead discovery & automation |
| **Node.js** | `18.x`, `20.x` or higher | Next.js frontend dashboard |
| **npm** | `9.x` or higher | Frontend package manager |
| **Git** | Latest | Version control |

---

## 🐍 2. Python Backend Requirements (`requirements.txt`)

These packages are installed via `pip install -r backend/requirements.txt`:

### Core Framework & Server
- `fastapi>=0.110.0` — High-performance asynchronous API framework
- `uvicorn[standard]>=0.28.0` — ASGI web server
- `python-multipart>=0.0.9` — Form data & file upload handling

### Schemas & Validation
- `pydantic>=2.6.0` — Data models and parsing
- `pydantic[email]>=2.6.0` — Strict email validation

### Database & Storage
- `sqlalchemy>=2.0.0` — ORM and database engine
- `aiosqlite>=0.20.0` — Asynchronous SQLite driver

### Scraping, Crawling & Automation
- `requests>=2.31.0` — Synchronous HTTP client
- `httpx>=0.27.0` — Asynchronous HTTP client for concurrent crawling
- `beautifulsoup4>=4.12.0` — HTML parsing and extraction
- `tldextract>=5.1.0` — Accurate domain and top-level domain parsing
- `duckduckgo_search>=5.0.0` — Search engine fallback for business discovery
- `crawl4ai>=0.3.0` — Deep LLM-friendly web crawler
- `playwright>=1.40.0` — Headless browser engine (*Requires `playwright install chromium`*)

### Machine Learning & AI
- `scikit-learn>=1.4.0` — TF-IDF vectorization and cosine similarity scoring
- `groq>=0.5.0` — Groq Cloud API SDK for LLaMA 3.3/3.1 inference
- *(Gemini and Ollama run over REST/JSON via Python `urllib`/`requests`, no external heavy SDK required)*

### Authentication & Security
- `bcrypt>=4.1.0` — Password hashing with salt
- `PyJWT>=2.8.0` — JSON Web Token generation and verification

### Outreach & Utilities
- `resend>=0.8.0` — Transactional & cold outreach email sending
- `python-dotenv>=1.0.0` — `.env` file loader

---

## 🌐 3. Frontend Requirements (`package.json`)

Installed via `npm install` at the project root:

### Production Dependencies
- `next`: `16.2.10` — React fullstack framework (App Router)
- `react`: `19.2.4` — UI library
- `react-dom`: `19.2.4` — React DOM renderer
- `lucide-react`: `^1.24.0` — Modern SVG icons
- `framer-motion`: `^12.42.2` — Animations and transitions
- `recharts`: `^3.9.2` — Analytics and charting components
- `@supabase/supabase-js`: `^2.110.6` — Supabase client for auth/database sync

### Dev Dependencies
- `tailwindcss`: `^4` — Utility-first CSS framework
- `@tailwindcss/postcss`: `^4` — PostCSS plugin for Tailwind v4
- `typescript`: `^5` — Type safety
- `@types/node`, `@types/react`, `@types/react-dom` — TypeScript declarations
- `eslint`, `eslint-config-next` — Linting

---

## 🔑 4. Environment Variables Configuration (`.env`)

Create a `.env` file in the root folder (or copy from `.env.example`):

```env
# SearXNG Search Engine
SEARXNG_URL=https://capable-emotion-production-6cad.up.railway.app

# AI Provider Configuration (groq / gemini / ollama)
AI_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# Ollama Local / Remote (Optional)
OLLAMA_URL=http://localhost:11434
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.2

# Gemini Cloud API (Fallback)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# Resend Email Outreach API (Optional)
RESEND_API_KEY=your_resend_key_here

# Frontend / Backend URLs
NEXT_PUBLIC_API_URL=/api
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000

# Supabase Auth / DB (Optional)
NEXT_PUBLIC_SUPABASE_URL=your_supabase_project_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
```

---

## 🚀 5. How to Run the Project

### Option A: All-In-One Desktop Launcher
```bash
python launch_app.py
```
This automatically starts both the Python backend and Next.js frontend, and opens the application window.

### Option B: Run Services Manually in 2 Terminals

**Terminal 1 — Backend (FastAPI):**
```bash
cd backend
# Windows:
..\venv\Scripts\uvicorn email_outreach:app --host 127.0.0.1 --port 8000 --reload
# Linux/macOS:
# ../venv/bin/uvicorn email_outreach:app --host 127.0.0.1 --port 8000 --reload
```
API Documentation will be live at: `http://localhost:8000/docs`

**Terminal 2 — Frontend (Next.js):**
```bash
npm run dev
```
Dashboard will be live at: `http://localhost:3000`
