# Lead-AI — Intelligent B2B Sales & Lead Generation Dashboard

> **AI-powered B2B lead discovery, contact enrichment, and outreach automation platform.**

[![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Python-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Ollama](https://img.shields.io/badge/AI-Ollama%20%2F%20Groq-purple)](https://ollama.ai/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📌 What Is Lead-AI?

Lead-AI is a full-stack **B2B Sales & Lead Generation Automation Dashboard** that:

- 🔍 **Discovers** qualified target companies using AI-powered web search
- 📧 **Enriches** each lead with real contact emails, phones, and LinkedIn
- 🤖 **Generates** personalized cold outreach emails using LLM (Ollama/Groq)
- 📊 **Tracks** your entire sales pipeline (Discovery → Outreach → Negotiation → Won)
- 📅 **Task Board** — Kanban-style deal management with AI negotiation assistant

---

## 🏗️ Architecture Overview

`
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Next.js 16)                        │
│                                                                       │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────┐  │
│  │  /discover  │  │  /clients    │  │  /tasks     │  │/settings │  │
│  │  AI Search  │  │  CRM Cards   │  │  Kanban     │  │ Profile  │  │
│  └──────┬──────┘  └──────┬───────┘  └──────┬──────┘  └──────────┘  │
│         │                │                  │                         │
│  ┌──────▼──────────────────────────────────▼───────────────────┐    │
│  │               Next.js API Routes (/app/api/*)                │    │
│  └──────────────────────────────┬────────────────────────────────┘   │
└─────────────────────────────────┼────────────────────────────────────┘
                                  │ HTTP (localhost:8000)
┌─────────────────────────────────▼────────────────────────────────────┐
│                      BACKEND (FastAPI + Python)                       │
│                                                                       │
│  ┌───────────────┐  ┌──────────────────┐  ┌────────────────────┐    │
│  │  discover.py  │  │ email_outreach.py│  │   database.py       │   │
│  │  AI Discovery │  │ Contact Scraper  │  │   SQLite ORM        │   │
│  └───────┬───────┘  └────────┬─────────┘  └─────────┬──────────┘   │
│          │                   │                        │               │
│  ┌───────▼───────────────────▼────────────────────────▼──────────┐  │
│  │             External Services                                    │ │
│  │  SearXNG/DDG (Search) | Ollama/Groq (AI) | Gmail SMTP (Email)  │ │
│  └──────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────┘
`

---

## 🔎 Search Engine Architecture (SearXNG vs. DuckDuckGo)

Lead-AI features an **Automated 3-Tier Multi-Engine Search Fallback**:

`
                       ┌───────────────────────────┐
                       │   User Search Request     │
                       └─────────────┬─────────────┘
                                     │
                                     ▼
                  ┌────────────────────────────────────┐
                  │ Tier 1: SearXNG MetaSearch Engine  │
                  │ (Aggregates 5 Engines: Google,     │
                  │  Bing, Brave, Qwant, DDG)          │
                  └──────────────────┬─────────────────┘
                                     │ (If offline / no port)
                                     ▼
                  ┌────────────────────────────────────┐
                  │ Tier 2: Brave Search API           │
                  │  (Requires BRAVE_SEARCH_API_KEY)   │
                  └──────────────────┬─────────────────┘
                                     │ (If key missing / failed)
                                     ▼
                  ┌────────────────────────────────────┐
                  │ Tier 3: DuckDuckGo HTML Direct     │
                  │ (Zero Config - AUTOMATIC FALLBACK) │
                  └──────────────────┬─────────────────┘
                                     │ (If offline / no internet)
                                     ▼
                  ┌────────────────────────────────────┐
                  │ Tier 4: LLM Synthetic Fallback     │
                  │  (Tagged as source=ai_generated)   │
                  └────────────────────────────────────┘
`

### ❓ How & When Are Search Engines Used?

#### 1. SearXNG (Primary Engine — Maximum Results)
- **When is it used?**: Whenever SearXNG is running locally (port 8085/8080) or hosted on Railway/Cloud.
- **Why use it?**: It queries **5 engines in parallel** (Google, Bing, Brave, Qwant, DDG) returning **40–60 raw links per page**.
- **How to run SearXNG locally (Docker)**:
  `ash
  docker run -d -p 8085:8080 searxng/searxng
  `
  Set SEARXNG_URL=http://localhost:8085 in ackend/.env.

- **How to use Cloud SearXNG (No Docker required)**:
  Set SEARXNG_URL=https://capable-emotion-production-6cad.up.railway.app in ackend/.env.

#### 2. DuckDuckGo (Automatic Fallback Engine — Zero Setup Required)
- **When is it used?**: If SearXNG is **not running** and no Brave API key is configured.
- **Why use it?**: Allows anyone to clone and run the project **without installing Docker or API keys**!
- **How to use it?**: Do nothing! Lead-AI automatically detects SearXNG is offline and routes queries to DuckDuckGo HTML engine.

---

## 🤖 Local Ollama AI Setup & Configuration

Lead-AI uses **Ollama** for local AI evaluation, company qualification, and contact normalization.

### How to Setup & Run Local Ollama:

#### Step 1: Install Ollama
Download and install Ollama from [https://ollama.ai](https://ollama.ai).

#### Step 2: Pull an AI Model
Open your terminal and pull a supported model (e.g. llama3 or qwen2.5:7b):
`ash
ollama pull llama3
`

#### Step 3: Start Ollama Server
Ollama automatically runs as a background service on http://localhost:11434. If not running, start it:
`ash
ollama serve
`

#### Step 4: Configure Backend Environment (ackend/.env)
Set your Ollama endpoint in ackend/.env:
`ini
# For Local Ollama (running on same PC)
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3:latest

# For Remote Ollama (e.g. GPU Server via Tailscale / LAN)
# OLLAMA_BASE_URL=http://100.91.220.98:11434/v1
`

#### Step 5: How Ollama Works in Lead-AI
1. **Qualification**: Evaluates scraped homepage content to verify if a company is a real business vs directory/blog.
2. **ICP Alignment**: Checks if the company needs your products/services.
3. **Outreach Drafting**: Drafts personalized B2B cold emails tailored to each specific company.

---

## 📁 Code Structure

`
Lead-AI/
├── app/                          # Next.js App Router (Frontend)
│   ├── api/                      # Server-side API routes
│   │   ├── discover-companies/   # Proxy -> Python /discover-companies
│   │   ├── enrich-contacts/      # Proxy -> Python /enrich-contacts
│   │   ├── save-client/          # Proxy -> Python /api/save-client
│   │   ├── clients/              # CRUD for saved leads
│   │   ├── generate-outreach-email/  # AI email drafting
│   │   ├── send-email/           # Gmail SMTP dispatcher
│   │   ├── analyze-negotiation/  # AI negotiation reply helper
│   │   ├── suggest-industries/   # AI industry tag suggestions
│   │   ├── deep-enrich/          # Stage 2 deep contact crawler
│   │   └── auth/                 # Login / Signup / JWT
│   │
│   ├── discover/page.tsx         # 🔍 Company Discovery Page (main)
│   ├── clients/page.tsx          # 📋 Saved Clients CRM List
│   ├── clients/[id]/page.tsx     # 👤 Client Detail + Outreach + History
│   ├── tasks/page.tsx            # 📅 Kanban Task Board
│   ├── settings/page.tsx         # ⚙️  Company Profile Settings
│   ├── login/page.tsx            # 🔐 Login Page
│   ├── signup/page.tsx           # 📝 Signup Page
│   ├── layout.tsx                # Root layout (sidebar nav)
│   └── globals.css               # Global CSS + Material Design tokens
│
├── backend/                      # Python FastAPI Backend
│   ├── email_outreach.py         # Main FastAPI app + all routes
│   ├── discover.py               # Company Discovery Engine
│   ├── database.py               # SQLite Database Layer
│   ├── auth_models.py            # User & Company auth models
│   ├── auth_routes.py            # JWT auth endpoints (login/signup)
│   ├── auth_utils.py             # Password hashing + JWT helpers
│   ├── requirements.txt          # Python dependencies
│   └── .env.example              # Backend environment template
│
├── components/                   # Reusable React Components
├── lib/                          # Frontend auth helpers
├── .env.example                  # Frontend environment template
├── .gitignore                    # Git ignore rules
├── next.config.ts                # Next.js configuration
├── package.json                  # Node.js dependencies
└── README.md                     # Project Documentation
`

---

## ⚙️ Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| **Node.js** | 18+ | Frontend runtime |
| **Python** | 3.10+ | Backend runtime |
| **Git** | Any | Version control |
| **Ollama** | Latest | Local AI (optional, or use Groq) |

---

## 🚀 Quick Start (Local Development)

### Step 1 — Clone & Install Frontend Dependencies

`ash
git clone https://github.com/devvahmed/ClientPlus-AI.git
cd ClientPlus-AI
npm install
`

### Step 2 — Configure Frontend Environment

`ash
cp .env.example .env.local
`

### Step 3 — Configure & Install Backend Dependencies

`ash
cp backend/.env.example backend/.env
cd backend
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
playwright install chromium
`

### Step 4 — Run Backend Server

`ash
cd backend
uvicorn email_outreach:app --host 127.0.0.1 --port 8000 --reload
`

### Step 5 — Run Frontend Server

`ash
# In project root
npm run dev
`

Open http://localhost:3000 in your browser!

---

## 🌐 Production Deployment

### Option A: Vercel (Frontend) + Railway (Backend)
- Deploy frontend to Vercel pointing NEXT_PUBLIC_BACKEND_URL to Railway.
- Deploy backend repository to Railway with Docker or Python runtime.

### Option B: VPS Deployment (Ubuntu + Nginx + PM2)
- Build frontend with 
pm run build
- Run FastAPI via uvicorn / gunicorn with PM2 process manager
- Configure Nginx reverse proxy for SSL and API routing.

---

## 🤝 Contributing & License

MIT License — free to use and modify for commercial or private projects.
