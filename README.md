# 🚀 Lead-AI — Autonomous B2B Sales, Leadership Intelligence & Lead Generation Platform

[![Next.js 16](https://img.shields.io/badge/Frontend-Next.js%2016%20(React%2019)-black?style=for-the-badge&logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20(Python%203.10+)-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Tailwind CSS v4](https://img.shields.io/badge/Styling-Tailwind%20CSS%20v4-38B2AC?style=for-the-badge&logo=tailwind-css)](https://tailwindcss.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite%203-003B57?style=for-the-badge&logo=sqlite)](https://www.sqlite.org/)
[![Deliverability: 96.8%](https://img.shields.io/badge/Deliverability-96.8%25%20Verified%20SMTP-brightgreen?style=for-the-badge)](./ACCURACY_SHEET.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

> **Quick Deliverables Links:**  
> 📑 [Final Project & Technical Engineering Report](./PROJECT_REPORT.md)  
> 📊 [Model Accuracy & Performance Benchmarks Report](./ACCURACY_SHEET.md)  
> 📈 [Downloadable / Shareable Accuracy Spreadsheet (.CSV)](./ACCURACY_SHEET.csv)  

---

## 🌟 What is Lead-AI? (In Plain English)

Finding real commercial business clients normally requires hours of manual searching on Google, clicking on directory websites (like Yelp or Clutch), hunting for contact emails, and guessing whether the email address actually exists.

**Lead-AI is an all-in-one autonomous platform that does all of this work for you in seconds:**
- **Finds Real Companies:** Scans the live web across 5 search engines, instantly throwing away blogs, news sites, and directories.
- **Finds the Real Decision Maker:** Discovers the real names and titles of the company's CEO, Founder, or Managing Director.
- **Validates Real Emails (Zero Hallucination):** Runs a direct technical handshake with the company's email server (Zero-Send SMTP verification) to prove the email exists before saving it. No fake or broken emails.
- **Captures Multiple Inboxes:** Saves both the executive's direct inbox and general commercial/sales contacts with clean visual badges.
- **Runs 24/7 on Auto-Pilot:** The background Autonomous Harvester continuously works around the clock and streams verified leads directly into a live, formatted 12-column CSV file.
- **Drafts Tailored Emails & Tracks Deals:** Uses built-in AI to write personalized sales emails and gives you a visual Kanban CRM board with an AI Sales Negotiation Assistant.

---

## 📑 Table of Contents

- [⚡ Quickstart: How to Setup and Run in 3 Minutes](#-quickstart-how-to-setup-and-run-in-3-minutes)
  - [Prerequisites](#prerequisites)
  - [Option 1: One-Click Desktop Launcher (Recommended)](#option-1-one-click-desktop-launcher-recommended)
  - [Option 2: Manual Terminal Setup (Step-by-Step)](#option-2-manual-terminal-setup-step-by-step)
  - [Option 3: Automated Script Setup (Windows / Linux / Mac)](#option-3-automated-script-setup-windows--linux--mac)
- [⚙️ Environment Variables Configuration (.env)](#️-environment-variables-configuration-env)
- [🖥️ How to Use the Application (User Guide)](#️-how-to-use-the-application-user-guide)
- [🏗️ System Architecture & How It Works](#️-system-architecture--how-it-works)
- [🎯 Key Features Breakdown](#-key-features-breakdown)
- [📊 Performance & Accuracy Highlights](#-performance--accuracy-highlights)
- [❓ Frequently Asked Questions & Troubleshooting](#-frequently-asked-questions--troubleshooting)
- [📄 License & Authors](#-license--authors)

---

## ⚡ Quickstart: How to Setup and Run in 3 Minutes

### Prerequisites
Make sure you have these installed on your computer:
1. **Node.js**: v18.0.0 or higher ([Download Node.js](https://nodejs.org/))
2. **Python**: v3.10 to v3.14 ([Download Python](https://www.python.org/))
3. **Git**: Installed on your system ([Download Git](https://git-scm.com/))

---

### Option 1: One-Click Desktop Launcher (Recommended)

If you just want to run everything with a single command:

1. Open your terminal / command prompt in the project root:
   ```bash
   git clone https://github.com/devvahmed/Lead-AI.git
   cd Lead-AI
   ```
2. Run the native launcher:
   ```bash
   python launch_app.py
   ```
   *This automatically validates dependencies, launches the backend on port 8000, starts the frontend on port 3000, and opens your default browser automatically!*

---

### Option 2: Manual Terminal Setup (Step-by-Step)

If you prefer to start the backend and frontend separately in two terminal windows:

#### 🟢 Step 1: Start the Python Backend (Terminal 1)

**On Windows (PowerShell or Command Prompt):**
```powershell
# 1. Navigate to backend
cd backend

# 2. Create Python virtual environment
python -m venv venv

# 3. Activate virtual environment
.\venv\Scripts\activate

# 4. Install backend dependencies
pip install -r requirements.txt

# 5. Start the FastAPI server
python -m uvicorn email_outreach:app --host 127.0.0.1 --port 8000 --reload
```

**On Linux / macOS:**
```bash
# 1. Navigate to backend
cd backend

# 2. Create Python virtual environment
python3 -m venv venv

# 3. Activate virtual environment
source venv/bin/activate

# 4. Install backend dependencies
pip install -r requirements.txt

# 5. Start the FastAPI server
python3 -m uvicorn email_outreach:app --host 127.0.0.1 --port 8000 --reload
```

> **Backend is active at:** `http://localhost:8000`  
> *(Interactive API Swagger Docs: `http://localhost:8000/docs`)*

---

#### 🔵 Step 2: Start the Next.js Frontend (Terminal 2)

Open a **new terminal window** in the main project folder:

```bash
# 1. Install frontend packages
npm install

# 2. Start the development server
npm run dev
```

> **Frontend is active at:** `http://localhost:3000`  
> Open [http://localhost:3000](http://localhost:3000) in your web browser!

---

### Option 3: Automated Script Setup (Windows / Linux / Mac)

- **Windows Batch:** Double-click `setup.bat` or run `.\setup.bat`
- **Windows PowerShell:** Run `.\setup.ps1`
- **Linux / macOS:** Run `chmod +x setup.sh && ./setup.sh`

---

## ⚙️ Environment Variables Configuration (.env)

The application comes with pre-configured defaults. If you want to customize your API keys or Gmail outreach settings, create or edit the `.env` file in the project root:

```env
# ==========================================
# 🌐 Network & Host Configuration
# ==========================================
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
PORT=3000

# ==========================================
# 🤖 AI Engine Keys (Free Groq Cloud Key)
# ==========================================
# Get a free API key in 30 seconds at https://console.groq.com/keys
GROQ_API_KEY=your_groq_api_key_here

# ==========================================
# ✉️ Gmail SMTP Outreach (Optional)
# ==========================================
# Used for sending real cold emails directly from your Gmail account
SMTP_EMAIL=your_email@gmail.com
SMTP_PASSWORD=your_16_character_app_password
```

### 💡 How to Get a Free Google App Password (Non-Technical Guide):
1. Go to your **Google Account** ([myaccount.google.com](https://myaccount.google.com/)).
2. Click **Security** on the left menu.
3. Turn on **2-Step Verification** (if not already enabled).
4. In the search bar at the top, type **"App passwords"** and click it.
5. Create a new App Password named *"Lead-AI"* and copy the 16-character code.
6. Paste that code into `SMTP_PASSWORD` in your `.env` or directly on the **Settings** page in the dashboard!

---

## 🖥️ How to Use the Application (User Guide)

### 1. 🔍 Live Lead Discovery (`/discover`)
1. Open [http://localhost:3000/discover](http://localhost:3000/discover).
2. Enter your **Service / Niche** (e.g. *"Commercial Roofing"*, *"Food Packaging Machines"*, *"Cybersecurity Audits"*).
3. Select your **Target Country** (e.g. *United States*, *United Kingdom*, *Germany*, *Australia*).
4. Click **"Discover Companies"**.
5. Watch qualified companies stream in real time with company overview, CEO/Founder names, direct verified emails, and trust scores.

### 2. ⚡ 24/7 Autonomous Harvester (`/automation`)
1. Open [http://localhost:3000/automation](http://localhost:3000/automation).
2. Enter the service you are offering and choose your target countries.
3. Choose whether to start a **Fresh Dedicated CSV** or append to an existing vault.
4. Click **"Launch 24/7 Auto-Pilot"**.
5. The system will continuously source, qualify, and extract verified leads 24 hours a day in the background.
6. Click **"Download CSV"** at any time to export your clean, live 12-column spreadsheet.

### 3. 📊 Visual CRM Kanban Board (`/tasks`)
1. Open [http://localhost:3000/tasks](http://localhost:3000/tasks).
2. Track your prospect leads through 4 stages: **Prospects**, **Contacted**, **In Negotiation**, and **Closed Deals**.
3. Drag and drop prospect cards as deals progress.

### 4. 🤝 AI Sales Negotiation Assistant
1. In the CRM, click on any lead in the **Negotiation** column.
2. Paste the reply received from the client (e.g. *"Your price is too high"* or *"We already use another vendor"*).
3. The AI instantly analyzes the objection, suggests a counter-strategy, and drafts a ready-to-send reply.

---

## 🏗️ System Architecture & How It Works

Lead-AI follows an enterprise-grade 5-layer pipeline:

```text
┌─────────────────────────────────────────────────────────────┐
│ 1. Multi-Engine Search Sourcing Pool                        │
│    Queries Google, Bing, Yahoo, DuckDuckGo & Qwant          │
└──────────────────────────────┬──────────────────────────────┘
                               │ Raw Links
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Deterministic & Semantic Anti-Junk Firewall              │
│    Filters out Clutch, Yelp, Medium, Listicles, Expos       │
└──────────────────────────────┬──────────────────────────────┘
                               │ Real Operating Businesses
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Smart DOM Crawler & Executive Extraction                 │
│    Extracts CEO/Founders from Schema.org, Nav & LinkedIn    │
└──────────────────────────────┬──────────────────────────────┘
                               │ Executive Names & Inboxes
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Zero-Send SMTP Deliverability Verification               │
│    Direct Port 25 Socket Handshake (No Guessing / Fake Mail)│
└──────────────────────────────┬──────────────────────────────┘
                               │ 96.8% Valid Inboxes
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Live 12-Column CSV Streaming & CRM Kanban Board          │
│    fsync disk persistence + AI cold outreach generation     │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Key Features Breakdown

| Feature | What It Does | Why It Matters |
| :--- | :--- | :--- |
| **Smart DOM Crawler** | Scans website `<nav>`, `<footer>`, and `/about-us` or `/team` pages. | Finds real corporate emails and executive bios that basic scrapers miss. |
| **Off-Site Waterfall Intelligence** | Uses targeted search dorks (`site:linkedin.com/in/`) to find company executives. | Uncovers C-Level decision makers even when they are not listed on the website. |
| **Contact Enricher Pro** | Learns corporate domain email patterns (e.g. `first.last@company.com`). | Predicts and extracts direct personal inboxes rather than generic `info@`. |
| **Zero-Send SMTP Verification** | Connects to the company's mail server via Port 25 to check if the mailbox exists. | **Guarantees zero email bounces**, protecting your domain from getting blacklisted. |
| **Multi-Email Support** | Saves both executive emails and commercial team emails per company. | Gives you backup contacts if the CEO does not respond immediately. |
| **24/7 Autonomous Harvester** | Runs continuously in the background on the server, surviving reboots. | Generates leads for you while you sleep, saving them directly to CSV. |
| **Live 12-Column CSV Export** | Generates standard spreadsheets ready for Excel, Google Sheets, or any CRM. | Clean, standardized format with separated executive and team emails. |
| **AI Sales Negotiation Assistant** | Classifies incoming objections and writes strategic counter-offers. | Helps close deals faster without getting stuck on price or hesitation. |

---

## 📊 Performance & Accuracy Highlights

As documented in [`ACCURACY_SHEET.md`](./ACCURACY_SHEET.md) and [`PROJECT_REPORT.md`](./PROJECT_REPORT.md):

- **Junk Rejection Accuracy:** **95.8%** (Blocks directories, listicles, blogs, and expos).
- **Executive Leadership Precision:** **92.6%** (Extracts verified CEOs, Founders, and Directors).
- **Email Deliverability Rate:** **96.8%** (Real inboxes verified via live SMTP socket handshakes).
- **Multi-Email Coverage:** **2.4 authentic emails** discovered per company on average.
- **Speed:** Generates 10 fully enriched and verified company prospects in **24.8 seconds**.
- **Data Cost:** **$0** (No Apollo, ZoomInfo, or Hunter API subscriptions needed).

---

## ❓ Frequently Asked Questions & Troubleshooting

### Q1: "Port 8000 or 3000 is already in use"
If another program is using port 8000 or 3000:
- **On Windows:**
  ```powershell
  Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process -Force
  Get-Process -Id (Get-NetTCPConnection -LocalPort 3000).OwningProcess | Stop-Process -Force
  ```
- **On Linux / Mac:**
  ```bash
  kill -9 $(lsof -t -i:8000)
  kill -9 $(lsof -t -i:3000)
  ```

### Q2: "Python virtual environment script execution disabled" (Windows PowerShell)
If you see `execution of scripts is disabled on this system`:
Run PowerShell as Administrator and execute:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Q3: "Does Lead-AI send emails automatically without my permission?"
**No.** Lead-AI never sends an outreach email until you explicitly click **"Send Email"** in the dashboard. The background verification uses a **Zero-Send handshake** (it checks if the mailbox exists and disconnects without sending any message).

### Q4: "Where are my exported CSV files saved?"
All generated CSV spreadsheets are saved in the `backend/exports/` directory and can also be downloaded directly from the **/automation** page in your browser.

---

## 📁 Repository Structure

```
Lead-AI/
├── app/                          # Next.js 16 Web Dashboard & UI Pages
│   ├── discover/                 # Live Interactive Lead Sourcing
│   ├── automation/               # 24/7 Autonomous Harvester & 3D Radar
│   ├── tasks/                    # Visual 4-Stage Kanban CRM & Deal Tracker
│   ├── clients/                  # Verified Leads Table Vault
│   └── settings/                 # Profile & SMTP Credentials
├── backend/                      # FastAPI Asynchronous Python Backend
│   ├── automation_engine.py      # 24/7 Autonomous Harvester Daemon
│   ├── contact_enricher_pro.py   # Pattern Synthesizer & Zero-Send SMTP Validator
│   ├── smart_dom_crawler.py      # Structural Header/Footer/Nav Crawler
│   ├── offsite_waterfall_engine.py # LinkedIn Executive Dorking
│   ├── database.py               # SQLite Persistence & Dynamic Migrations
│   ├── discover.py               # Discovery Orchestrator & NDJSON Streaming
│   ├── email_outreach.py         # Contact Extraction & Gmail SMTP Dispatcher
│   └── requirements.txt          # Python Dependencies
├── launch_app.py                 # One-Click Desktop Application Launcher
├── ACCURACY_SHEET.md             # Detailed Accuracy & Performance Report
├── ACCURACY_SHEET.csv            # Shareable CSV Performance Metrics Spreadsheet
├── PROJECT_REPORT.md             # Complete Technical Engineering Report
├── package.json                  # Node.js Package Manifest
└── README.md                     # Master Documentation Guide
```

---

## 📄 License & Authors

This project is licensed under the **MIT License** — free for personal, academic, and commercial use.

**Developed with ❤️ by devvahmed**  
For technical inquiries, contributions, or enterprise deployment, submit an issue or pull request.
