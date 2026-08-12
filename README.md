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
│  │  SearXNG (Search) | Ollama/Groq (AI) | Gmail SMTP (Email)      │ │
│  └──────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────┘
`

---

## 🔎 Search Engine Architecture & Configuration

Lead-AI features a **3-Tier Multi-Engine Search Fallback Architecture**:

`
                       ┌───────────────────────────┐
                       │   User Search Request     │
                       └─────────────┬─────────────┘
                                     │
                                     ▼
                  ┌────────────────────────────────────┐
                  │ Tier 1: SearXNG MetaSearch Engine  │
                  │  (Aggregates Google+Bing+Brave)   │
                  └──────────────────┬─────────────────┘
                                     │ (If offline / empty)
                                     ▼
                  ┌────────────────────────────────────┐
                  │ Tier 2: Brave Search API           │
                  │  (Requires BRAVE_SEARCH_API_KEY)   │
                  └──────────────────┬─────────────────┘
                                     │ (If key missing / failed)
                                     ▼
                  ┌────────────────────────────────────┐
                  │ Tier 3: DuckDuckGo HTML Direct     │
                  │  (Zero API key, 100% Automatic)    │
                  └──────────────────┬─────────────────┘
                                     │ (If offline / no internet)
                                     ▼
                  ┌────────────────────────────────────┐
                  │ Tier 4: LLM Synthetic Fallback     │
                  │  (Tagged as source=ai_generated)   │
                  └────────────────────────────────────┘
`

### Search Engine Options for New Users:

- **Option A: SearXNG Self-Hosted (Recommended — Free & Unlimited)**
  `ash
  docker run -d -p 8085:8080 searxng/searxng
  `
  Set SEARXNG_URL=http://localhost:8085 in .env.

- **Option B: Cloud-Hosted SearXNG**
  Set SEARXNG_URL=https://your-searxng-instance.up.railway.app in .env.

- **Option C: Zero-Config DuckDuckGo (Automatic Fallback)**
  No configuration needed! If SearXNG or Brave API keys are not provided, Lead-AI automatically falls back to DuckDuckGo HTML search.

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
| **Ollama** | Latest | Local AI (optional) |

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
