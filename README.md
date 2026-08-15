# 🚀 Lead-AI — Intelligent B2B Sales & Lead Generation Platform

An end-to-end AI platform that discovers target B2B clients, scrapes verified contact emails/phones, and automates personalized outreach.

---

## 📄 Project Deliverables & Reports

- 📑 **[Final Project Report](PROJECT_REPORT.md)**: Detailed report explaining project architecture, methodology, pipeline design, and conclusions.
- 📊 **[Accuracy & Performance Sheet](ACCURACY_SHEET.md)**: Performance metrics, classification accuracy confusion matrix, and extraction recall benchmarks.

---

## 💡 What Is Lead-AI?

Finding B2B clients manually is slow and tedious — salespeople spend hours searching Google, sifting through directories, hunting for contact emails, and writing outreach messages one by one.

**Lead-AI** automates this entire sales process into a single streamlined dashboard:

- 🔍 **Finds Real Clients** — Enter an industry (e.g. Healthcare SaaS, Robotics, Logistics) and country. Lead-AI searches the web and uses AI (Ollama/Groq) to filter out blogs, directories, and junk — leaving only genuine operating businesses.
- 📧 **Extracts Contact Info** — Automatically crawls company websites to extract direct emails, phone numbers, and LinkedIn links.
- 🤖 **Drafts Cold Emails** — AI analyzes each company's website and writes custom outreach emails tailored specifically to them.
- ✉️ **Sends Outreach & Tracks Deals** — Send emails with one click via Gmail SMTP and manage deals on an interactive Kanban pipeline board.

---

## ⚡ How It Works

| Step | Stage | Description |
|------|-------|-------------|
| 1 | **Search** | Type target industry |
| 2 | **Web Crawl** | Find real web links |
| 3 | **AI Evaluation** | Filter out junk/blogs |
| 4 | **Enrichment** | Scrape email, phone & social |
| 5 | **Outreach** | Auto-draft & send email |

---

## ✨ Features at a Glance

| Feature | Description |
|---------|-------------|
| 🔍 AI Discovery | Search target companies by industry & country with real-time AI qualification |
| 📧 Contact Scraping | Automatically extracts verified emails, phone numbers, and LinkedIn profiles |
| 🤖 AI Email Generator | Generates personalized B2B cold emails tailored to each specific lead |
| 📊 Sales Pipeline | Track deals from Discovery → Outreach → Negotiation → Closed Won |
| ✉️ One-Click Send | Send emails directly through your own Gmail SMTP |

---

## 🚀 Quick Setup Guide (Run in 5 Minutes)

### Prerequisites
- Node.js (v18 or higher)
- Python (v3.10 or higher)

### Step 1: Clone Repository

`ash
git clone https://github.com/devvahmed/Lead-AI.git
cd Lead-AI
`

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

✅ Backend is running at: http://localhost:8000

### Step 3: Start Frontend (Next.js)

Open a new terminal in the project root folder:

`ash
# Install packages
npm install

# Start development server
npm run dev
`

✅ Frontend is running at: http://localhost:3000

---

## ⚙️ Configuration & Options

### 🔍 Search Engine Setup (Automatic)

You don't need to configure anything — Lead-AI automatically chooses the best available engine:

- **Default (Zero Setup):** Uses DuckDuckGo search automatically. Works out of the box!
- **Pro Option (SearXNG):** Run SearXNG via Docker for multi-engine search:

`ash
docker run -d -p 8085:8080 searxng/searxng
`

Then set SEARXNG_URL=http://localhost:8085 in ackend/.env.

### 🤖 AI Provider Setup (Choose One)

**Option A: Local Ollama (Free)**

1. Download Ollama from [ollama.ai](https://ollama.ai)
2. Run model: ollama pull llama3
3. Set in ackend/.env:

`ini
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3:latest
`

**Option B: Groq Cloud (Ultra Fast)**

1. Get a free API key from [console.groq.com](https://console.groq.com)
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
├── PROJECT_REPORT.md     # 📑 Comprehensive Final Project Report
├── ACCURACY_SHEET.md     # 📊 Model Accuracy & Evaluation Sheet
└── README.md             # Project Documentation
`

---

## 📄 License

MIT License — Free to use for personal and commercial projects.
