# 🚀 Lead-AI — Intelligent B2B Sales & Lead Generation Platform

> **Find qualified B2B clients, extract real contact info, and send AI-drafted outreach emails — in seconds.**

---

## ⚡ How It Works (Simple 5-Step Flow)

`
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  1. SEARCH   │ ──> │ 2. WEB CRAWL │ ──> │  3. AI EVAL  │ ──> │ 4. ENRICHMENT│ ──> │  5. OUTREACH │
│  Type target │     │ Find real    │     │ Filter out   │     │ Scrape email │     │ Auto-draft & │
│  industry    │     │ web links    │     │ junk/blogs   │     │ phone & social│     │ send email   │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
`

---

## ✨ Features at a Glance

| Feature | Description |
| :--- | :--- |
| 🔍 **AI Discovery** | Search target companies by industry & country with real-time AI qualification |
| 📧 **Contact Scraping** | Automatically extracts verified Emails, Phone Numbers, and LinkedIn profiles |
| 🤖 **AI Email Generator** | Generates personalized B2B cold emails tailored to each specific lead |
| 📊 **Sales Pipeline** | Track deals from Discovery $ightarrow$ Outreach $ightarrow$ Negotiation $ightarrow$ Closed Won |
| ✉️ **One-Click Send** | Send emails directly through your own Gmail SMTP |

---

## 🚀 Quick Setup Guide (Run in 5 Minutes)

### Prerequisites
- **Node.js** (v18 or higher)
- **Python** (v3.10 or higher)

---

### Step 1: Clone Repository
`ash
git clone https://github.com/devvahmed/ClientPlus-AI.git
cd ClientPlus-AI
`

---

### Step 2: Start Backend (Python)

`ash
# Move to backend folder
cd backend

# Create & activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Start backend server
uvicorn email_outreach:app --host 127.0.0.1 --port 8000 --reload
`
> ✅ **Backend is running at:** http://localhost:8000

---

### Step 3: Start Frontend (Next.js)

Open a **new terminal** in the project root folder:

`ash
# Install packages
npm install

# Start development server
npm run dev
`
> ✅ **Frontend is running at:** http://localhost:3000

---

## ⚙️ Configuration & Options

### 🔍 Search Engine Setup (Automatic)
You don't need to configure anything! Lead-AI automatically chooses the best available engine:
- **Default (Zero Setup)**: Uses DuckDuckGo search automatically. Works out of the box!
- **Pro Option (SearXNG)**: Run SearXNG via Docker for multi-engine search:
  `ash
  docker run -d -p 8085:8080 searxng/searxng
  `
  Set SEARXNG_URL=http://localhost:8085 in ackend/.env.

---

### 🤖 AI Provider Setup (Choose One)

#### Option A: Local Ollama (Free)
1. Download Ollama from [ollama.ai](https://ollama.ai).
2. Run model: ollama pull llama3
3. Set in ackend/.env:
   `ini
   OLLAMA_BASE_URL=http://localhost:11434/v1
   OLLAMA_MODEL=llama3:latest
   `

#### Option B: Groq Cloud (Ultra Fast)
1. Get a free API key from [console.groq.com](https://console.groq.com).
2. Set in ackend/.env:
   `ini
   GROQ_API_KEY=your_groq_api_key_here
   GROQ_MODEL=llama-3.1-8b-instant
   `

---

## 📁 Project Structure

`
Lead-AI/
├── app/                  # Next.js Frontend pages & API routes
│   ├── discover/         # 🔍 Lead Discovery Page
│   ├── clients/          # 📋 Saved Leads CRM
│   ├── tasks/            # 📅 Sales Pipeline Kanban
│   └── settings/         # ⚙️ Profile Settings
├── backend/              # Python FastAPI Backend
│   ├── discover.py       # AI Search & Qualification Engine
│   ├── email_outreach.py # Contact Scraper & Email Handler
│   └── database.py       # SQLite Storage
└── README.md             # Project Documentation
`

---

## 📄 License

MIT License — Free to use for personal and commercial projects.
