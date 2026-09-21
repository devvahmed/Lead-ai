# 🚀 Lead-AI — Autonomous B2B Sales & Lead Generation Platform

[![Next.js 16](https://img.shields.io/badge/Frontend-Next.js%2016%20(React%2019)-black?style=for-the-badge&logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20(Python%203.10+)-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Tailwind CSS v4](https://img.shields.io/badge/Styling-Tailwind%20CSS%20v4-38B2AC?style=for-the-badge&logo=tailwind-css)](https://tailwindcss.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite%203-003B57?style=for-the-badge&logo=sqlite)](https://www.sqlite.org/)
[![Groq & Ollama](https://img.shields.io/badge/AI%20LLM-Groq%20%7C%20Ollama%20%7C%20Gemini-FF6F00?style=for-the-badge)](https://groq.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

An enterprise-grade, fully autonomous B2B lead generation, intelligence extraction, and cold outreach platform. **Lead-AI** replaces manual lead prospecting by automatically discovering operating commercial businesses, filtering out junk and directories, auditing website operational bottlenecks, extracting verified direct decision-maker contact details, drafting hyper-personalized cold outreach emails, and managing deals through an interactive CRM Kanban board with an integrated AI Negotiation Assistant.

---

## 📑 Table of Contents

- [💡 Project Overview & Core Value](#-project-overview--core-value)
- [🏗️ End-to-End System Architecture & Data Flow](#️-end-to-end-system-architecture--data-flow)
- [🌟 In-Depth Feature Breakdown (Ak Ak Feature Ki Detail)](#-in-depth-feature-breakdown-ak-ak-feature-ki-detail)
  - [1. Multi-Source Async Ingestion Engine](#1-multi-source-async-ingestion-engine-multi_source_ingestionpy)
  - [2. Context-Aware Dynamic Industry Generator](#2-context-aware-dynamic-industry-generator-dynamic_industry_generatorpy)
  - [3. Multi-Tier Deterministic & Semantic Junk Firewall](#3-multi-tier-deterministic--semantic-junk-firewall-junk_firewallpy)
  - [4. Strict Geo-Lock & Country Verification Engine](#4-strict-geo-lock--country-verification-engine-geo_lock_enginepy)
  - [5. Strict Buyer Intent & Non-Job Contract Classifier](#5-strict-buyer-intent--non-job-contract-classifier-intent_classifierpy)
  - [6. Smart DOM Header/Footer/Nav Link Parser & Crawler](#6-smart-dom-headerfooternav-link-parser--crawler-smart_dom_crawlerpy)
  - [7. Service-Agnostic Operational Bottleneck Audit Engine](#7-service-agnostic-operational-bottleneck-audit-engine-operational_audit_enginepy)
  - [8. Deep 3-Way Match Matrix Engine](#8-deep-3-way-match-matrix-engine-three_way_match_matrixpy)
  - [9. Evidence-Based Scoring & 360° Post-Click Audit](#9-evidence-based-scoring--360-post-click-audit-evidence_scoring_360py)
  - [10. Real-Time NDJSON Streaming Discovery Engine](#10-real-time-ndjson-streaming-discovery-engine-discoverpy)
  - [11. 24/7 Autonomous Lead Harvester Daemon](#11-247-autonomous-lead-harvester-daemon-automation_enginepy)
  - [12. Programmatic Contact Extraction & Deep Enrichment](#12-programmatic-contact-extraction--deep-enrichment-email_outreachpy)
  - [13. AI Personalized Cold Email Generator](#13-ai-personalized-cold-email-generator)
  - [14. Direct Gmail SMTP Outreach Engine](#14-direct-gmail-smtp-outreach-engine)
  - [15. Interactive CRM Kanban Pipeline & Deal Tracker](#15-interactive-crm-kanban-pipeline--deal-tracker)
  - [16. AI Sales Negotiation & Counter-Offer Assistant](#16-ai-sales-negotiation--counter-offer-assistant)
  - [17. Multi-Tenant Authentication & AI Profile Onboarding](#17-multi-tenant-authentication--ai-profile-onboarding)
  - [18. One-Click Native Desktop Launcher](#18-one-click-native-desktop-launcher-launch_apppy)
- [🛠️ Technology Stack](#️-technology-stack)
- [📁 Project Folder Structure](#-project-folder-structure)
- [🗄️ Database Architecture & Relational Schema](#️-database-architecture--relational-schema)
- [🚀 Quickstart Installation Guide (Step-by-Step)](#-quickstart-installation-guide-step-by-step)
- [⚙️ Environment Variables Configuration (.env)](#️-environment-variables-configuration-env)
- [📡 API Reference (Endpoints & Protocols)](#-api-reference-endpoints--protocols)
- [📊 Evaluation Benchmarks & Accuracy](#-evaluation-benchmarks--accuracy)
- [📄 License & Author](#-license--author)

---

## 💡 Project Overview & Core Value

### 🔴 The Problem:
Traditional B2B lead generation is broken:
1. **Time Wasted**: Sales reps spend 60%+ of their day searching Google, clicking non-commercial blogs/directories (Clutch, Yelp, Medium, Forbes), and copying emails manually.
2. **Low Lead Precision**: Web searches return listicles, news articles, and competing agencies rather than actual buyers.
3. **Contact Scrape Failures**: Emails are buried in JavaScript, contact subpages, or obfuscated behind anti-scraping tags.
4. **Impersonal Outreach**: Mass blast templates bounce or land in spam because they lack genuine company-specific context.
5. **Disconnected Tool Stack**: Companies pay thousands of dollars for separate tools: search (Apollo/ZoomInfo), scraping (Phantombuster), enrichment (Clearbit), email warmup (Instantly), and CRM (HubSpot).

### 🟢 The Lead-AI Solution:
Lead-AI provides an **all-in-one autonomous platform**:
- Type an **Industry** and **Target Country** (or turn on the 24/7 background Harvester).
- The engine concurrently crawls multiple search and job channels, applies a deterministic & LLM junk firewall, verifies geographic registration, identifies operational bottlenecks, and computes a 100-point evidence score.
- Direct emails, phone numbers, and LinkedIn URLs are programmatically scraped and validated.
- Personalized cold emails referencing the company's real pain points are generated on the fly.
- Outreaches are dispatched directly via Gmail SMTP, with deals tracked on a visual 4-stage Kanban CRM with an intelligent negotiation analyzer.
- Sourcing 10 qualified, enriched prospects drops from **3+ hours down to under 30 seconds**.

---

## 🏗️ End-to-End System Architecture & Data Flow

```
                                  USER QUERY OR 24/7 DAEMON
                                             │
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │ 1. Multi-Source Async Ingestion Engine       │
                      │ (SearXNG, DDG Scraper, Reddit, HN, Job RSS)  │
                      └──────────────────────┬───────────────────────┘
                                             │ Raw Candidates
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │ 2. Dynamic Industry & Dork Generator         │
                      │ (Niche expansion, inurl/intitle dorks)       │
                      └──────────────────────┬───────────────────────┘
                                             │ Formulated Queries
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │ 3. Deterministic & Semantic Junk Firewall    │
                      │ (Blocks Clutch, Yelp, Medium, Wiki, Listicles)│
                      └──────────────────────┬───────────────────────┘
                                             │ Commercial Entities
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │ 4. Strict Geo-Lock & Country Engine          │
                      │ (ccTLD hard lock, dialing code, city regex)  │
                      └──────────────────────┬───────────────────────┘
                                             │ Verified Local Leads
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │ 5. Strict Buyer Intent Classifier            │
                      │ (Drops seller agencies & 9-to-5 job posts)   │
                      └──────────────────────┬───────────────────────┘
                                             │ True Contract Buyers
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │ 6. Smart DOM Crawler & Link Parser           │
                      │ (Analyzes <nav>, <header>, <footer> subpages)│
                      └──────────────────────┬───────────────────────┘
                                             │ Multi-Page Clean Text
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │ 7. Operational Bottleneck Audit Engine       │
                      │ (Detects manual QC, paper logs, legacy tech) │
                      └──────────────────────┬───────────────────────┘
                                             │ Extracted Verbatim Pain
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │ 8. Deep 3-Way Match Matrix                   │
                      │ (Pain Fit 45% + Scale 35% + Readiness 20%)   │
                      └──────────────────────┬───────────────────────┘
                                             │ Gatekeeper (Pass >= 0.70)
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │ 9. Evidence-Based Scoring 360° Audit         │
                      │ (100% Grounded 0–100 Score Breakdown)        │
                      └──────────────────────┬───────────────────────┘
                                             │
                     ┌───────────────────────┴───────────────────────┐
                     ▼                                               ▼
      ┌──────────────────────────────┐                ┌──────────────────────────────┐
      │ 10. Real-Time NDJSON Stream  │                │ 11. Contact Enrichment Engine│
      │ (Live emit to Next.js UI)    │                │ (Emails, Phones, LinkedIn)   │
      └──────────────┬───────────────┘                └──────────────┬───────────────┘
                     │                                               │
                     └───────────────────────┬───────────────────────┘
                                             │
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │ 12. AI Personalized Email Generator          │
                      │ (Tailored cold outreach referencing pain)    │
                      └──────────────────────┬───────────────────────┘
                                             │
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │ 13. Direct Gmail SMTP Dispatcher             │
                      │ (1-Click send with delivery verification)    │
                      └──────────────────────┬───────────────────────┘
                                             │
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │ 14. CRM Kanban Pipeline & Negotiation AI     │
                      │ (New Leads → Contacted → Negotiating → Won)  │
                      └──────────────────────────────────────────────┘
```

---

## 🌟 In-Depth Feature Breakdown (Ak Ak Feature Ki Detail)

### 1. Multi-Source Async Ingestion Engine (`multi_source_ingestion.py`)
- **What it does**: Sourcing prospects from a single search engine often hits rate limits or returns stale pages. This engine ingests potential leads concurrently from **5 distinct web streams**.
- **How it works**:
  1. **SearXNG Aggregator**: Queries self-hosted or cloud SearXNG instances aggregating Google, Bing, Brave, Qwant, and DuckDuckGo in parallel.
  2. **Direct DuckDuckGo Fallback**: If SearXNG is unavailable, the system transparently switches to DuckDuckGo HTML scraping with rotating User-Agent headers, automated referrer injection, and pagination offsets.
  3. **Reddit Public JSON Stream**: Scrapes subreddits like `r/forhire`, `r/DigitalMarketing`, `r/entrepreneur`, and `r/smallbusiness` for real-time commercial service requests.
  4. **Hacker News Firebase REST API**: Ingests `Ask HN` and `Who is Hiring` items directly via official endpoints.
  5. **Remote Job Board XML/RSS Feeds**: Parses RemoteOK and WeWorkRemotely RSS feeds to detect companies expanding operations or hiring technical contractors.
  6. **Deduplication Engine**: Uses domain normalization and MD5 content hashes to eliminate duplicates across platforms. If a lead appears across multiple channels, its priority rank is automatically boosted.
  7. **Strict Timeouts**: Every channel runs under non-blocking 6-second asyncio timeouts to prevent hanging.

### 2. Context-Aware Dynamic Industry Generator (`dynamic_industry_generator.py`)
- **What it does**: Instead of searching generic keywords like "AI services" or "Logistics", this module automatically crafts targeted sub-verticals and advanced search dorks.
- **How it works**:
  - Analyzes your company's profile (`ai_enriched_profile`), extracts your exact capabilities (e.g., Computer Vision for Quality Inspection, Automated Invoicing, Warehouse Route Optimization), and formulates tailored search angles.
  - Automatically synthesizes Google dorks:
    - `intitle:"pharmaceutical manufacturing" site:.pk "contact"`
    - `inurl:about "cold storage warehouse" "Lahore" -directory -blog`
  - **Persistent History Log**: Tracks scanned queries in `searched_industries_history.json`. It guarantees that consecutive discovery sessions never search the same niche sub-vertical twice, continuously unlocking fresh market segments.

### 3. Multi-Tier Deterministic & Semantic Junk Firewall (`junk_firewall.py`)
- **What it does**: Stops junk websites, affiliate sites, directories, blogs, and listicles before heavy scraping or expensive LLM tokens are consumed.
- **How it works**:
  - **Tier 1 (Deterministic Domain Blacklist)**: Instantly blocks 150+ known directories and platforms:
    - *B2B & Review Directories*: Clutch.co, G2, Capterra, GoodFirms, Yelp, YellowPages, UpCity, BBB, Manta, Crunchbase, ZoomInfo, ThomasNet, Alibaba, etc.
    - *Blogging & Media*: Medium, Substack, WordPress.com, Blogspot, WixSite, Wikipedia, Dev.to, Hashnode, Forbes, BusinessInsider.
    - *Social & Code Repositories*: GitHub, GitLab, Reddit, YouTube, Quora, LinkedIn, Twitter/X.
  - **URL Path Regex Quarantine**: Disqualifies URLs containing `/blog/`, `/tag/`, `/category/`, `/news/`, `/top-10/`, `/best-software/`, `/article/`, `/author/`, `/wp-content/`.
  - **Tier 2 (Semantic Entity Classifier)**: When ambiguous domains pass Tier 1, a lightweight LLM audit evaluates the page headline and metadata to ensure it represents an active commercial operating business with its own product or service.

### 4. Strict Geo-Lock & Country Verification Engine (`geo_lock_engine.py`)
- **What it does**: Ensures that when you filter for a specific country (e.g. Pakistan, United Kingdom, United States, Germany, UAE, Saudi Arabia), you **only** get companies with genuine operational presence inside that country.
- **How it works**:
  - **Country-Specific ccTLD Hard-Pass / Hard-Disqualify**:
    - If targeting Pakistan, `.pk`, `.com.pk`, `.org.pk` get a 100% confidence pass.
    - If a candidate has a foreign ccTLD (e.g. `.de`, `.fr`, `.in`, `.co.uk`) while targeting Pakistan, it is immediately disqualified.
  - **Telephony Dialing Code & Mobile Pattern Verification**:
    - Scans for domestic phone patterns (e.g., Pakistan: `+92`, `0092`, `0300-XXXXXXX`, landline codes `021`, `042`, `051`).
  - **Major City Address Database**: Matches physical addresses against comprehensive city lists (e.g. Lahore, Karachi, Islamabad, Faisalabad, Sialkot, etc.).
  - **Contextual LLM Fallback**: If a company uses a neutral `.com` domain, an LLM checks the scraped text to verify whether regional offices or headquarters exist in the target country.

### 5. Strict Buyer Intent & Non-Job Contract Classifier (`intent_classifier.py`)
- **What it does**: Discards two major types of false leads:
  1. **Seller Agencies**: Competitor dev agencies, digital marketing shops, or freelancers pitching their own services (e.g., *"We are a leading web agency, hire our developers"*).
  2. **9-to-5 Salaried Employment**: Corporate job postings requiring full-time W-2/employee arrangements with 401(k), health insurance, and annual salaries.
- **How it works**:
  - Uses regex patterns to detect agency pitch markers (`book a discovery call with us`, `our case studies`, `our tech stack includes`).
  - Uses regex patterns to identify employment markers (`full-time employee`, `W-2 only`, `annual base salary $80k-$120k`, `health dental vision 401k`).
  - Approves genuine commercial buyers, manufacturing facilities, logistics hubs, enterprise procurement teams, and organizations seeking vendor partnerships or issuing RFPs/RFQs.

### 6. Smart DOM Header/Footer/Nav Link Parser & Crawler (`smart_dom_crawler.py`)
- **What it does**: Traditional scrapers guess subpage URLs by blindly pinging `/about` or `/contact` (which often returns 404 errors). Smart DOM Crawler dynamically parses the actual HTML structure of the homepage.
- **How it works**:
  - Analyzes semantic structural tags: `<nav>`, `<header>`, `<footer>`, and high-relevance `<a>` tags.
  - Categorizes discovered internal links into operational buckets:
    - `CONTACT`: `/contact-us`, `/get-in-touch`, `/locations`, `/reach-us`
    - `ABOUT`: `/about-us`, `/our-story`, `/company-profile`, `/overview`
    - `SERVICES_PRODUCTS`: `/services`, `/solutions`, `/capabilities`, `/manufacturing`
    - `MANAGEMENT_TEAM`: `/leadership`, `/board-of-directors`, `/team`
  - Concurrently crawls the top priority subpages in parallel, stripping scripts, styles, SVG paths, and cookie banners to produce clean, high-density text for downstream audit engines.

### 7. Service-Agnostic Operational Bottleneck Audit Engine (`operational_audit_engine.py`)
- **What it does**: Scans the scraped multi-page text to detect real operational inefficiencies and manual workflows within the prospect's business.
- **How it works**:
  - Identifies 5 critical operational bottleneck categories:
    1. **Manual Quality Control**: Visual inspection, manual defect sorting, physical grading, human QA checkers.
    2. **Repetitive Data Entry**: Paper forms, paper logs, manual spreadsheet entry, clipboard checklists, Excel manifests.
    3. **Legacy Software & Dispatch Delay**: Outdated desktop software, phone-based dispatch, manual scheduling, lack of API integration.
    4. **High Labor Turnover & Staffing**: Constant warehouse hiring, training bottlenecks, repetitive manual packing lines.
    5. **Unautomated Inventory Flow**: Manual stock counts, barcode clipboards, physical warehouse audits.
  - **Verbatim Evidence Extraction**: Pulls the exact quote from the prospect's website describing the process. This evidence is passed directly to the email generation engine, creating compelling, personalized cold outreach.

### 8. Deep 3-Way Match Matrix Engine (`three_way_match_matrix.py`)
- **What it does**: Replaces simple keyword matching with a multi-dimensional qualification matrix.
- **How it works**:
  - Evaluates 3 weighted pillars:
    - **Pillar 1: Solution-to-Pain Alignment (Weight: 45%)**: Does our service offering directly solve the prospect's detected operational bottleneck?
    - **Pillar 2: ICP Scale & Market Fit (Weight: 35%)**: Is the prospect an operating enterprise with sufficient scale (headcount, manufacturing volume, multiple facilities) to afford our solutions?
    - **Pillar 3: Technical & Operational Readiness (Weight: 20%)**: Does the prospect have active digital contact channels, modern infrastructure, and business readiness to deploy external vendor solutions?
  - **Strict Decision Gates**:
    - `QUALIFIED_LEAD`: Composite Score $\ge 0.70$ **AND** Solution-to-Pain Score $\ge 0.60$.
    - `MARGINAL_FIT`: Composite Score $\ge 0.50$ (flagged for review).
    - `DISQUALIFIED`: Composite Score $< 0.50$ (automatically dropped before reaching the user).

### 9. Evidence-Based Scoring & 360° Post-Click Audit (`evidence_scoring_360.py`)
- **What it does**: Generates a 100% evidence-grounded Trust & Fit Score (0–100 points) instead of arbitrary or hallucinated numbers.
- **Scoring Breakdown**:
  | Category | Maximum Points | Verification Logic |
  |---|---|---|
  | **Geo-Lock Evidence** | 20 pts | +20 for verified domestic ccTLD, +15 for verified local phone/address, +10 for LLM confirmed presence |
  | **Buyer Intent Strength** | 20 pts | +20 for active RFP/procurement signal, +15 for operating commercial target |
  | **Operational Bottleneck Evidence** | 25 pts | +25 for verbatim extracted quote from DOM, +15 for deterministic pattern match |
  | **Solution-to-Pain Alignment** | 20 pts | Calculated directly from Pillar 1 of the 3-Way Match Matrix |
  | **ICP Scale & Technical Readiness** | 15 pts | Calculated from Pillars 2 & 3 of the 3-Way Match Matrix |
  | **Total Composite Score** | **100 pts** | Transparently displayed with full rationale on the company details card |

### 10. Real-Time NDJSON Streaming Discovery Engine (`discover.py`)
- **What it does**: Eliminates loading spinners. As soon as any prospect passes the firewall, geo-lock, and 3-way match, its qualified profile is streamed live to the Next.js frontend.
- **How it works**:
  - Uses **NDJSON (Newline Delimited JSON)** streaming over HTTP chunked transfer encoding.
  - Sends immediate progress status events (`{"type": "status", "message": "Analyzing company X..."}`).
  - Emits fully-formed company cards (`{"type": "company", "data": {...}}`) with real-time UI card rendering.
  - Includes a streaming completion summary with total searched, filtered, and qualified metrics.

### 11. 24/7 Autonomous Lead Harvester Daemon (`automation_engine.py`)
- **What it does**: A persistent background service that runs continuously on your server, harvesting verified B2B leads 24 hours a day without manual input.
- **Key Capabilities**:
  - **100% Server Reboot Resilience**: Daemon state, current niche, progress, and settings are continuously synchronized to the SQLite database (`automation_jobs` table). If the server restarts or loses power, the daemon automatically resumes where it left off.
  - **Dynamic Niche Rotation**: Automatically iterates through target industry verticals without repeating keywords.
  - **Strict Corporate Email Gatekeeper**: Unlike basic scrapers that save junk leads, the Harvester **only** commits leads to the vault if they possess a verified, non-generic direct email.
  - **Live CSV Streaming**: Writes qualified leads in real time directly to an exportable CSV file (`fsync` to disk), downloadable anytime from the dashboard.
  - **3D Futuristic Radar Interface**: Features an interactive Three.js/Framer Motion radar scanner displaying real-time scan pulses, verified lead counters, and activity feeds.

### 12. Programmatic Contact Extraction & Deep Enrichment (`email_outreach.py`)
- **What it does**: Crawls the prospect's digital footprint to extract verified contact information for outreach.
- **Capabilities**:
  - **Deep Multi-Page Harvest**: Recursively extracts emails and phone numbers from the homepage, `/contact`, `/about`, `/team`, and `/impressum`.
  - **Corporate Email Filtering**: Eliminates junk/placeholder emails (`sentry.io`, `example.com`, `user@domain.com`, `wixpress.com`, `wordpress@...`, image assets `.png@`).
  - **Phone Format Normalization**: Extracts domestic and international phone numbers, cleaning extensions and formatting them with country codes.
  - **LinkedIn Company Handle Discovery**: Extracts official LinkedIn company pages (`linkedin.com/company/...`).
  - **Source Transparency**: Stores the exact URL where the contact information was discovered.

### 13. AI Personalized Cold Email Generator
- **What it does**: Writes personalized, high-converting B2B cold emails tailored to each specific company.
- **How it works**:
  - Feeds the prospect's company name, business description, and their **exact operational bottleneck** (with verbatim website quotes) into the LLM.
  - Injects your company's profile, core service offerings, and value proposition.
  - Generates a compelling email with:
    - High-open subject line (under 60 characters, curiosity-driven).
    - Executive, professional body (under 150 words, addressing their specific pain point, zero generic marketing buzzwords).
    - Low-friction call-to-action (e.g., *"Are you open to a brief 10-minute workflow review this Thursday?"*).
  - Offers tone options: **Direct Value**, **Problem-Solution Focused**, and **Strategic Advisory**.

### 14. Direct Gmail SMTP Outreach Engine
- **What it does**: Dispatches cold emails straight from your verified Gmail or Google Workspace inbox with a single click.
- **How it works**:
  - Uses standard Python `smtplib` over secure **TLS (Port 587)**.
  - Authenticates via Google App Passwords, avoiding third-party API costs or deliverability penalties.
  - Automatically records the email in the SQLite `email_history` table with timestamps, recipient, subject, body, and status (`Sent`).
  - Live test connection button in Settings to verify SMTP credentials instantly.

### 15. Interactive CRM Kanban Pipeline & Deal Tracker (`app/tasks/page.tsx`)
- **What it does**: A full-featured sales pipeline tracking prospects through every stage of the sales cycle.
- **Pipeline Stages**:
  1. 🟦 **New Leads**: Newly discovered and enriched prospects.
  2. 🟨 **Contacted**: Prospects who have received cold outreach emails.
  3. 🟪 **In Negotiation**: Prospects who have replied and are in discussions.
  4. 🟩 **Closed Won**: Deals successfully closed.
- **Features**: Real-time stage updates, search and filter by company name/industry, direct link to company website, view full contact details, and open the AI Negotiation Assistant.

### 16. AI Sales Negotiation & Counter-Offer Assistant (`/api/analyze-negotiation`)
- **What it does**: Helps sales reps handle prospect replies, objections, price pushbacks, and technical questions.
- **How it works**:
  - Paste the client's email reply into the modal.
  - The LLM analyzes the reply and returns structured strategic guidance:
    1. **Objection Classification**: Categorizes the reply into *Price & Budget*, *Technical Feasibility*, *Implementation Timeline*, *Competitor Comparison*, *Scope & Customization*, or *General Interest*.
    2. **Intent Analysis**: Identifies what the client is actually asking for beneath their words.
    3. **Actionable Strategy Tip**: Recommends proven sales tactics (e.g. propose a phased pilot, offer milestone-based billing, provide technical documentation).
    4. **Ready-to-Send Counter-Reply**: Drafts a persuasive, context-aware reply email signed with your company name.
    5. **Win Probability Metric**: Updates deal closing probability based on sentiment.

### 17. Multi-Tenant Authentication & AI Profile Onboarding
- **What it does**: Full account creation, login, session management, and automated onboarding.
- **AI-Enriched Company Onboarding**:
  - When a user signs up with their company name and website, the system automatically scrapes their website.
  - An LLM extracts their core services, target customer profile (ICP), value propositions, and elevator pitch.
  - These values are stored in `companies.ai_enriched_profile` and automatically used across all discovery, matching, and email generation tasks.
- Secure JWT/token-based authentication with password hashing (`auth_utils.py`).

### 18. One-Click Native Desktop Launcher (`launch_app.py`)
- **What it does**: Allows non-technical users to run Lead-AI like a native Windows desktop software without typing terminal commands.
- **How it works**:
  - Automatically locates Python venv and launches the FastAPI backend on port 8000.
  - Launches the Next.js production or development server on port 3000.
  - Waits for health check initialization.
  - Launches Microsoft Edge in `--app=http://localhost:3000` mode, rendering the dashboard as a standalone window without browser address bars.

---

## 🛠️ Technology Stack

| Layer | Technology | Description |
|---|---|---|
| **Frontend Framework** | **Next.js 16 (App Router)** | React 19, TypeScript, Server Components & Client Hooks |
| **Styling & Icons** | **Tailwind CSS v4 & Lucide React** | Modern dark-mode dashboard styling with glassmorphism |
| **Motion & Graphics** | **Framer Motion & Three.js** | Smooth pipeline transitions, 3D interactive radar scanner |
| **Backend API Server** | **FastAPI & Uvicorn** | High-performance Python async REST API & NDJSON streaming |
| **Database & ORM** | **SQLite 3 & aiosqlite** | Multi-table relational database with schema auto-migrations |
| **Search Providers** | **SearXNG & DuckDuckGo** | Multi-engine meta-search with zero-config HTML fallback |
| **Web Crawling & Parsing** | **httpx, aiohttp & BeautifulSoup4** | High-speed concurrent async page crawling & DOM parsing |
| **Primary LLM Providers** | **Groq Cloud (llama-3.1-8b / 3.3-70b)** | Ultra-fast inference (< 800ms) for qualification & drafting |
| **Local / Private LLMs** | **Ollama (llama3.2 / llama3)** | 100% private, offline, cost-free local AI inference |
| **Cloud Fallback LLMs** | **Google Gemini (gemini-2.0 / 3.6-flash)**| Secondary enterprise cloud fallback |
| **Outreach Delivery** | **Python smtplib (TLS Port 587)** | Direct Gmail / Google Workspace SMTP delivery |
| **Desktop Packaging** | **PyInstaller & Edge App Mode** | Native Windows desktop packaging capability |

---

## 📁 Project Folder Structure

```
Lead-AI/
├── app/                              # Next.js Frontend Application
│   ├── api/                          # Next.js API Route Handlers
│   │   ├── analyze-company/          # Company profile analyzer
│   │   ├── analyze-negotiation/      # AI Sales Negotiation Assistant
│   │   ├── auth/                     # Frontend auth proxy
│   │   ├── automation/               # Harvester daemon control
│   │   ├── clients/                  # Saved CRM leads CRUD
│   │   ├── dashboard-stats/          # Live metrics & charts
│   │   ├── deep-enrich/              # Deep scraping trigger
│   │   ├── discover-companies/       # NDJSON streaming discovery proxy
│   │   ├── generate-outreach-email/  # AI email drafting
│   │   ├── send-email/               # Gmail SMTP outreach dispatcher
│   │   └── suggest-industries/       # Dynamic niche suggestions
│   ├── automation/                   # 24/7 Harvester UI with 3D Radar
│   ├── clients/                      # Saved Leads CRM Table view
│   ├── discover/                     # Live Lead Discovery Engine UI
│   ├── tasks/                        # Visual 4-Stage Kanban Board & Deal Tracker
│   ├── settings/                     # User Profile & SMTP Credentials
│   ├── login/                        # User Login Page
│   ├── signup/                       # AI-Enriched Company Registration
│   ├── layout.tsx                    # Root Layout & Theme Provider
│   └── page.tsx                      # Main Executive Dashboard
├── backend/                          # Python FastAPI Server & AI Engines
│   ├── auth_models.py                # Pydantic Authentication schemas
│   ├── auth_routes.py                # JWT Login, Register, Profile endpoints
│   ├── auth_utils.py                 # Password hashing & JWT helpers
│   ├── automation_engine.py          # 24/7 Autonomous Lead Harvester Daemon
│   ├── database.py                   # SQLite schema, tables & operations
│   ├── discover.py                   # Discovery orchestrator & NDJSON streaming
│   ├── dynamic_industry_generator.py # Dynamic niche & search dork generator
│   ├── email_outreach.py             # Contact extraction & Gmail SMTP dispatcher
│   ├── evidence_scoring_360.py       # 100-point grounded scoring engine
│   ├── geo_lock_engine.py            # Country & ccTLD verification engine
│   ├── intent_classifier.py          # Buyer intent & non-job contract classifier
│   ├── junk_firewall.py              # Multi-tier deterministic & semantic firewall
│   ├── multi_source_ingestion.py     # 5-channel async web ingestion
│   ├── operational_audit_engine.py   # DOM bottleneck detection & quote extractor
│   ├── smart_dom_crawler.py          # Structural <nav>/<footer> link crawler
│   ├── three_way_match_matrix.py     # 3-Way qualification matrix engine
│   ├── llm_utils.py                  # Multi-provider LLM caller (Groq/Ollama/Gemini)
│   ├── requirements.txt              # Python package dependencies
│   ├── run_server.bat                # Windows quick start script
│   └── run_server.ps1                # PowerShell quick start script
├── components/                       # Shared React Components
│   ├── LayoutShell.tsx               # Sidebar navigation & header
│   └── automation/                   # 3D Radar & live scan widgets
├── lib/                              # Client utilities, auth helpers & API clients
├── launch_app.py                     # One-click desktop launcher
├── ACCURACY_SHEET.md                 # Model accuracy & benchmarking sheet
├── PROJECT_REPORT.md                 # Technical architecture & project report
├── package.json                      # Node.js project manifest & dependencies
└── README.md                         # Project documentation
```

---

## 🗄️ Database Architecture & Relational Schema

Lead-AI uses SQLite (`clientplus_sales.db`) for lightweight, serverless persistence:

```mermaid
erDiagram
    COMPANIES ||--o{ CLIENTS : owns
    COMPANIES ||--o{ LEADS : owns
    COMPANIES ||--o{ EMAIL_HISTORY : sends
    COMPANIES ||--|| AUTOMATION_JOBS : configures
    COMPANIES ||--o{ AUTOMATION_VERIFIED_LEADS : collects
    CLIENTS ||--o{ EMAIL_HISTORY : receives

    COMPANIES {
        int id PK
        string email
        string hashed_password
        string company_name
        string website_url
        string services
        string target_countries
        text ai_enriched_profile
        string smtp_email
        string smtp_password
    }

    CLIENTS {
        int id PK
        int company_id FK
        string name
        string website
        string industry
        string country
        int trust_score
        string relevance_reason
        string status
        string email
        string phone
        string linkedin_company
        string contact_source_url
        string created_at
    }

    EMAIL_HISTORY {
        int id PK
        int client_id FK
        int company_id FK
        string email_type
        string subject
        text body
        string recipient_email
        string status
        string created_at
    }

    AUTOMATION_JOBS {
        int id PK
        int company_id FK
        string status
        string target_service
        string target_countries
        int min_trust_score
        int total_leads_scanned
        int verified_emails_found
        string current_niche
        string current_query
        string csv_file_path
        string last_heartbeat
    }

    AUTOMATION_VERIFIED_LEADS {
        int id PK
        int company_id FK
        string name
        string website
        string domain
        string email
        string phone
        string country
        string industry
        int trust_score
        text outreach_angle
        string created_at
    }
```

---

## 🚀 Quickstart Installation Guide (Step-by-Step)

### Prerequisites
- **Node.js**: v18.0.0 or higher ([Download Node.js](https://nodejs.org/))
- **Python**: v3.10 or higher ([Download Python](https://www.python.org/))
- **Git**: Installed on your system

---

### Step 1: Clone the Repository
```bash
git clone https://github.com/devvahmed/Lead-AI.git
cd Lead-AI
```

---

### Step 2: Setup and Run the Python Backend

#### On Windows (PowerShell):
```powershell
# 1. Navigate to backend directory
cd backend

# 2. Create Python virtual environment
python -m venv venv

# 3. Activate virtual environment
.\venv\Scripts\Activate.ps1

# 4. Install backend dependencies
pip install -r requirements.txt

# 5. Copy environment file and add your keys
cp .env.example .env

# 6. Start FastAPI backend server
python -m uvicorn email_outreach:app --host 127.0.0.1 --port 8000 --reload
```

#### On Linux / macOS:
```bash
# 1. Navigate to backend directory
cd backend

# 2. Create Python virtual environment
python3 -m venv venv

# 3. Activate virtual environment
source venv/bin/activate

# 4. Install backend dependencies
pip install -r requirements.txt

# 5. Copy environment file and configure
cp .env.example .env

# 6. Start FastAPI backend server
uvicorn email_outreach:app --host 127.0.0.1 --port 8000 --reload
```

Backend will be active at: `http://localhost:8000` (API Docs at `http://localhost:8000/docs`).

---

### Step 3: Setup and Run the Next.js Frontend

Open a **new terminal window** in the root project folder:

```bash
# 1. Install frontend npm packages
npm install

# 2. Start Next.js development server
npm run dev
```

Frontend will be active at: **`http://localhost:3000`**.

---

### 🖥️ Option B: One-Click Desktop Launcher
For convenience, you can launch both backend and frontend together with native app window mode:
```powershell
python launch_app.py
```

---

## ⚙️ Environment Variables Configuration (.env)

Create a `.env` file in the root folder (or inside `backend/.env`):

```ini
# ==========================================
# 🔍 Search Engine Setup (Optional)
# ==========================================
# Zero-config default: If left empty, DuckDuckGo HTML scraper is used automatically.
# For high-speed meta-search, provide your SearXNG URL:
SEARXNG_URL=https://capable-emotion-production-6cad.up.railway.app

# ==========================================
# 🤖 AI LLM Provider Configuration
# ==========================================
# Select provider: "groq", "ollama", or "gemini"
AI_PROVIDER=groq

# --- Option A: Groq Cloud (Recommended: Ultra-fast <800ms) ---
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=llama-3.1-8b-instant

# --- Option B: Ollama (100% Free & Local) ---
OLLAMA_URL=http://localhost:11434
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.2

# --- Option C: Google Gemini (Fallback) ---
GEMINI_API_KEY=AIzaSy_your_gemini_api_key_here
GEMINI_MODEL=gemini-2.0-flash

# ==========================================
# 🌐 Network & URL Configuration
# ==========================================
NEXT_PUBLIC_API_URL=/api
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000

# ==========================================
# ✉️ Default Gmail SMTP (Can also be set in UI Settings)
# ==========================================
SMTP_EMAIL=your_email@gmail.com
SMTP_PASSWORD=your_16_character_google_app_password
```

> **Tip for Gmail SMTP**: Go to your Google Account → Security → 2-Step Verification → **App passwords**. Generate an app password for "Mail" and paste the 16-character code into `SMTP_PASSWORD`.

---

## 📡 API Reference (Endpoints & Protocols)

### 1. Discovery & Streaming
- `POST /discover` (or `GET /discover` with query params):
  - Streams real-time NDJSON company cards matching the target industry and country.
  - Headers: `Accept: application/x-ndjson`

### 2. Contact Extraction & Deep Enrichment
- `POST /enrich-contacts`:
  - Scrapes target company homepage and subpages to extract emails, phones, and LinkedIn handles.
  - Body: `{"url": "https://example.com", "company_name": "Example Corp"}`

### 3. AI Cold Outreach Generation & Dispatch
- `POST /generate-outreach-email`:
  - Generates tailored cold email based on extracted bottleneck.
- `POST /send-email`:
  - Dispatches email directly via Gmail SMTP.
  - Body: `{"to_email": "ceo@example.com", "subject": "...", "body": "..."}`

### 4. 24/7 Autonomous Harvester Daemon
- `GET /automation/status`: Returns current daemon loop status, total leads scanned, verified emails, and live niches.
- `POST /automation/start`: Launches background autonomous harvesting loop.
- `POST /automation/stop`: Pauses background daemon.
- `GET /automation/download-csv`: Downloads the real-time generated CSV file.

### 5. AI Sales Negotiation
- `POST /api/analyze-negotiation`:
  - Takes prospect objection email and returns structured objection classification, sales strategy hint, and ready-to-send counter-offer email.

### 6. Authentication & Profiles
- `POST /auth/register`: Creates new tenant account with AI-enriched company onboarding.
- `POST /auth/login`: Authenticates credentials and returns JWT bearer token.
- `GET /auth/me`: Retrieves current company profile and settings.

---

## 📊 Evaluation Benchmarks & Accuracy

As documented in [PROJECT_REPORT.md](PROJECT_REPORT.md) and [ACCURACY_SHEET.md](ACCURACY_SHEET.md):

- **Junk Filtering Accuracy**: **94.0%** (Filters out directories, blogs, review portals, and non-commercial domains).
- **Direct Contact Extraction Yield**: **78.0%** across live operating commercial websites.
- **Geographic Precision**: **96.5%** adherence to selected target countries via ccTLD and domestic dialing patterns.
- **End-to-End Speed**: Sourcing, qualifying, scoring, and enriching 10 target businesses takes **22–35 seconds** total.
- **Zero Single-Point-of-Failure**: 3-tier search fallback guarantees continuous uptime even if a search provider rate-limits.

---

## 📄 License & Author

This project is licensed under the **MIT License** — free to use, modify, and distribute for personal and commercial projects.

**Developed with ❤️ by devvahmed**  
For inquiries, contributions, or enterprise customization, open a GitHub issue or pull request.
