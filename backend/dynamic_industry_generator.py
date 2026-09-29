"""
Context-Aware Dynamic Industry Generator (Step 2).

This module analyzes our master ai_enriched_profile (or user services) and generates
contextually aligned, high-converting target industries, sub-verticals, and localized search dorks.
It focuses on plain-English, easy-to-understand industries with high lead contactability
(public team pages, reachable owners, valid domain emails) and maintains an active history log
to ensure it rotates dynamically and NEVER scans the same industry sub-vertical repeatedly.
"""

import asyncio
import json
import logging
import os
import random
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("dynamic_industry_generator")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s")

# Default history storage file
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DEFAULT_HISTORY_FILE = os.path.join(DATA_DIR, "searched_industries_history.json")

# Country to top-level domain mapping for precise search dorks
COUNTRY_TLD_MAP: Dict[str, str] = {
    "united states": "com",
    "united states of america": "com",
    "usa": "com",
    "us": "us",
    "united kingdom": "co.uk",
    "uk": "co.uk",
    "great britain": "co.uk",
    "england": "co.uk",
    "pakistan": "pk",
    "germany": "de",
    "deutschland": "de",
    "canada": "ca",
    "australia": "com.au",
    "india": "in",
    "france": "fr",
    "netherlands": "nl",
    "spain": "es",
    "italy": "it",
    "switzerland": "ch",
    "united arab emirates": "ae",
    "uae": "ae",
    "dubai": "ae",
    "saudi arabia": "sa",
    "ksa": "sa",
    "singapore": "sg",
    "japan": "jp",
    "brazil": "com.br",
    "mexico": "com.mx",
    "south africa": "co.za",
    "new zealand": "co.nz",
    "ireland": "ie",
    "sweden": "se",
    "norway": "no",
    "denmark": "dk",
    "finland": "fi",
    "poland": "pl",
    "turkey": "com.tr",
    "malaysia": "com.my",
    "indonesia": "co.id",
    "vietnam": "vn",
    "thailand": "co.th",
    "philippines": "com.ph",
}


def get_country_tld(country: str) -> Optional[str]:
    """Returns the primary commercial or national TLD for a given country name."""
    if not country:
        return None
    normalized = country.strip().lower()
    if normalized in COUNTRY_TLD_MAP:
        return COUNTRY_TLD_MAP[normalized]
    # Check partial containment
    for name, tld in COUNTRY_TLD_MAP.items():
        if name in normalized or normalized in name:
            return tld
    return None


# ─── 1. History & Non-Repeating Tracker ────────────────────────────────────────
class IndustryHistoryTracker:
    """
    Persists scanned industry niches/sub-verticals to disk and ensures no sub-industry
    is scanned repeatedly across discovery sessions.
    """

    def __init__(self, filepath: Optional[str] = None):
        self.filepath = filepath or DEFAULT_HISTORY_FILE
        self._ensure_dir()
        self.history: List[Dict[str, Any]] = []
        self.scanned_set: set = set()
        self.load_history()

    def _ensure_dir(self) -> None:
        folder = os.path.dirname(self.filepath)
        if folder and not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)

    def _normalize_key(self, niche: str) -> str:
        """Cleans and lowercases niche string for resilient set comparison."""
        cleaned = re.sub(r"[^a-zA-Z0-9\s]", "", niche).strip().lower()
        return re.sub(r"\s+", " ", cleaned)

    def load_history(self) -> None:
        """Loads existing history and scanned keys from JSON file."""
        if not os.path.exists(self.filepath):
            self.history = []
            self.scanned_set = set()
            return

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.history = data.get("history", [])
                    raw_set = data.get("scanned_set", [])
                    self.scanned_set = set(self._normalize_key(item) for item in raw_set)
                elif isinstance(data, list):
                    self.history = data
                    self.scanned_set = set(
                        self._normalize_key(item.get("niche", ""))
                        for item in data if isinstance(item, dict) and "niche" in item
                    )
        except Exception as e:
            logger.warning(f"[IndustryHistoryTracker] Failed to load history from {self.filepath}: {e}")
            self.history = []
            self.scanned_set = set()

    def save_history(self) -> None:
        """Atomically saves the current history log and scanned set to JSON."""
        self._ensure_dir()
        temp_file = f"{self.filepath}.tmp_{os.getpid()}"
        data = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "total_scanned": len(self.history),
            "scanned_set": sorted(list(self.scanned_set)),
            "history": self.history
        }
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_file, self.filepath)
        except Exception as e:
            logger.error(f"[IndustryHistoryTracker] Error saving history to {self.filepath}: {e}")
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass

    def is_scanned(self, niche: str, service_context: str = "") -> bool:
        """Returns True if the niche has already been scanned."""
        if not niche:
            return False
        return self._normalize_key(niche) in self.scanned_set

    def mark_scanned(
        self,
        niche: str,
        service_context: str = "",
        country: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Appends a new niche scan record and writes immediately to disk."""
        if not niche:
            return
        norm_key = self._normalize_key(niche)
        self.scanned_set.add(norm_key)

        entry = {
            "niche": niche.strip(),
            "service_context": service_context.strip(),
            "country": country.strip(),
            "scanned_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {}
        }
        self.history.append(entry)
        self.save_history()
        logger.info(f"[IndustryHistoryTracker] Marked niche as scanned: '{niche.strip()}'")

    def get_scanned_niches(self, service_context: str = "") -> List[str]:
        """Returns the list of original niche names that have been marked as scanned."""
        if not service_context:
            return [h["niche"] for h in self.history if "niche" in h]
        norm_svc = service_context.strip().lower()
        return [
            h["niche"] for h in self.history
            if "niche" in h and (norm_svc in h.get("service_context", "").lower() or not h.get("service_context"))
        ]

    def clear_history(self) -> None:
        """Clears all history and scanned sets (useful for testing or hard resets)."""
        self.history = []
        self.scanned_set = set()
        self.save_history()
        logger.info(f"[IndustryHistoryTracker] Cleared history at {self.filepath}")


# ─── 2. Dork & Search Query Builder ───────────────────────────────────────────
def build_searxng_dorks(industry_niche: str, country: str = "") -> List[str]:
    """
    Constructs high-converting operational search queries/dorks for SearXNG and Outbound Workers.
    Focuses on queries that bring up real business domains with reachable contact pages.
    """
    clean_niche = industry_niche.strip()
    clean_country = country.strip()
    tld = get_country_tld(clean_country)

    dorks: List[str] = []
    loc = f" {clean_country}" if clean_country else ""

    # Dork 1: Official Website & Contact Page
    dorks.append(f'{clean_niche} official website contact us{loc}'.strip())

    # Dork 2: Commercial Providers, Services & About Us
    dorks.append(f'{clean_niche} company services about us{loc}'.strip())

    # Dork 3: TLD-scoped or Leading Providers
    if tld and tld not in ("com", ""):
        dorks.append(f'{clean_niche} companies site:.{tld}')
    else:
        dorks.append(f'leading {clean_niche} firms{loc}'.strip())

    # Dork 4: Business Team & Leadership Directory
    dorks.append(f'{clean_niche} our team leadership contact{loc}'.strip())

    return dorks


# ─── 3. Easy-to-Understand, High-Contactability Industry Matrix ────────────────
# All categories use clear, everyday business names where finding real owner, partner,
# doctor, or director emails online is reliable and high-yield.
HEURISTIC_INDUSTRY_MATRIX: List[Dict[str, Any]] = [
    # ── Category 1: Healthcare, Dental & Wellness Clinics ──
    {
        "service_triggers": ["ai", "chatbot", "software", "marketing", "web", "healthcare", "clinic", "dental"],
        "niche": "Dental & Orthodontic Clinics",
        "parent_industry": "Healthcare & Dental Practices",
        "target_service_fit": "Automated patient booking, hygiene recall messaging, and modern digital practice tools",
        "rationale": "High-margin practices with active doctor and practice owner profiles published on their websites",
        "dork_keywords": ["dental practice clinic", "orthodontic clinic contact", "cosmetic dentistry practice"]
    },
    {
        "service_triggers": ["ai", "software", "marketing", "healthcare", "clinic", "wellness"],
        "niche": "Dermatology & Cosmetic Medical Clinics",
        "parent_industry": "Specialty Healthcare & Aesthetics",
        "target_service_fit": "Online consultation booking, patient intake automation, and local digital reputation management",
        "rationale": "High-ticket aesthetic procedures; clinic owners and medical directors are prominently listed online",
        "dork_keywords": ["dermatology clinic", "aesthetic medical center", "cosmetic skin clinic"]
    },
    {
        "service_triggers": ["software", "marketing", "automation", "healthcare", "therapy"],
        "niche": "Physical Therapy & Chiropractic Centers",
        "parent_industry": "Outpatient Healthcare & Rehabilitation",
        "target_service_fit": "Care plan reminders, online patient re-booking, and automated billing intake",
        "rationale": "Clinic owners and lead practitioners listed with direct office email and phone numbers",
        "dork_keywords": ["physical therapy clinic", "chiropractic care center", "sports rehabilitation practice"]
    },

    # ── Category 2: Commercial Trades & Contractors ──
    {
        "service_triggers": ["ai", "automation", "software", "marketing", "web", "construction", "roofing", "contractor"],
        "niche": "Commercial Roofing Contractors",
        "parent_industry": "Commercial Construction & Building Envelope",
        "target_service_fit": "Commercial building roof replacement lead generation, digital estimate proposals, and job dispatch",
        "rationale": "High average ticket size ($30k-$200k); owners, estimators, and project managers listed on websites",
        "dork_keywords": ["commercial roofing contractor", "industrial roofing company", "roof replacement specialists"]
    },
    {
        "service_triggers": ["ai", "automation", "software", "marketing", "hvac", "mechanical", "contractor"],
        "niche": "Commercial HVAC & Refrigeration Contractors",
        "parent_industry": "Mechanical Contracting & Facility Services",
        "target_service_fit": "Commercial service maintenance contract proposals, emergency dispatch, and field invoicing tools",
        "rationale": "Recurring commercial maintenance contracts; operations managers and owners readily accessible",
        "dork_keywords": ["commercial hvac contractor", "industrial refrigeration service", "heating and cooling company"]
    },
    {
        "service_triggers": ["automation", "software", "marketing", "web", "electrical", "solar", "contractor"],
        "niche": "Commercial Electrical & Solar Installers",
        "parent_industry": "Electrical Contracting & Renewable Energy",
        "target_service_fit": "Commercial energy retrofit proposals, solar rooftop feasibility pipelines, and client portals",
        "rationale": "Fast-expanding sector with active project directors and company owners seeking commercial clients",
        "dork_keywords": ["commercial electrical contractor", "turnkey solar installer", "commercial solar company"]
    },
    {
        "service_triggers": ["software", "marketing", "automation", "plumbing", "contractor", "services"],
        "niche": "Commercial Plumbing & Mechanical Services",
        "parent_industry": "Mechanical Services & Facility Contractors",
        "target_service_fit": "Preventative maintenance agreements, emergency response dispatching, and digital work orders",
        "rationale": "High commercial urgency; business principals and dispatch directors openly listed on contact pages",
        "dork_keywords": ["commercial plumbing contractor", "industrial mechanical piping", "commercial drain cleaning"]
    },

    # ── Category 3: Professional Services (Legal & Accounting) ──
    {
        "service_triggers": ["ai", "software", "marketing", "web", "legal", "law", "attorney"],
        "niche": "Corporate & Commercial Law Firms",
        "parent_industry": "Legal Advisory Services",
        "target_service_fit": "Client intake automation, secure document review, and high-authority practice area visibility",
        "rationale": "Managing partners and practice attorneys publish official business bios with direct email addresses",
        "dork_keywords": ["corporate law firm", "business attorneys practice", "commercial litigation lawyers"]
    },
    {
        "service_triggers": ["ai", "automation", "software", "marketing", "accounting", "cpa", "tax", "finance"],
        "niche": "Accounting, Tax & CPA Firms",
        "parent_industry": "Accounting & Financial Consulting",
        "target_service_fit": "Secure client document portals, automated bookkeeping reconciliation, and client advisory marketing",
        "rationale": "CPA partners and practice leaders maintain active corporate websites with direct partner emails",
        "dork_keywords": ["certified public accountants firm", "cpa accounting practice", "tax advisory consultants"]
    },
    {
        "service_triggers": ["marketing", "lead generation", "finance", "wealth", "advisory"],
        "niche": "Private Wealth & Financial Advisory Practices",
        "parent_industry": "Wealth Management & Financial Planning",
        "target_service_fit": "High-net-worth client lead generation, automated quarterly performance reporting, and CRM workflows",
        "rationale": "Licensed advisors publish verifiable business contact information on company websites and directories",
        "dork_keywords": ["wealth management advisors", "private wealth advisory firm", "financial planning consultants"]
    },

    # ── Category 4: Real Estate & Property Management ──
    {
        "service_triggers": ["ai", "chatbot", "marketing", "software", "web", "real estate", "property"],
        "niche": "Boutique Commercial Real Estate Brokerages",
        "parent_industry": "Commercial Real Estate",
        "target_service_fit": "Targeted corporate tenant acquisition, industrial property deal flow campaigns, and investor portals",
        "rationale": "Commercial brokers publish their direct emails and mobile numbers on property listing pages",
        "dork_keywords": ["commercial real estate brokerage", "industrial leasing agency", "commercial property brokers"]
    },
    {
        "service_triggers": ["ai", "software", "automation", "real estate", "property"],
        "niche": "Residential Property Management Companies",
        "parent_industry": "Real Estate Property Management",
        "target_service_fit": "Tenant maintenance ticket routing, automated lease renewal notices, and owner financial dashboards",
        "rationale": "Property managers actively monitor inboxes for new property owner management contracts",
        "dork_keywords": ["residential property management", "apartment management company", "rental property managers"]
    },

    # ── Category 5: Logistics, Trucking & Supply Chain ──
    {
        "service_triggers": ["ai", "software", "automation", "logistics", "freight", "trucking", "shipping"],
        "niche": "Freight Brokerages & Logistics Fleets",
        "parent_industry": "Commercial Freight & Transportation",
        "target_service_fit": "Automated shipper rate quoting, driver dispatch tracking, and digital bill-of-lading workflows",
        "rationale": "Freight dispatchers and logistics coordinators are responsive to tools that reduce manual dispatch friction",
        "dork_keywords": ["freight brokerage company", "specialized trucking logistics", "flatbed freight transport"]
    },
    {
        "service_triggers": ["software", "automation", "warehouse", "logistics", "inventory"],
        "niche": "E-Commerce 3PL Fulfillment Centers",
        "parent_industry": "Warehousing & Order Fulfillment",
        "target_service_fit": "Multi-channel stock synchronization, automated wave picking, and customer shipping tracking portals",
        "rationale": "Fulfillment warehouse directors actively search for software and automation partners to scale throughput",
        "dork_keywords": ["3pl fulfillment warehouse", "ecommerce fulfillment company", "contract packing logistics"]
    },
    {
        "service_triggers": ["automation", "logistics", "food", "warehouse", "cold storage"],
        "niche": "Refrigerated Cold Storage Warehouses",
        "parent_industry": "Temperature Controlled Food Logistics",
        "target_service_fit": "Automated pallet tracking, temperature logging, and expiration date monitoring",
        "rationale": "Facility managers and logistics heads listed on warehouse location pages with public office contacts",
        "dork_keywords": ["cold storage warehousing", "refrigerated logistics provider", "cold chain distribution facility"]
    },

    # ── Category 6: E-Commerce, Retail & Consumer Brands ──
    {
        "service_triggers": ["ai", "chatbot", "marketing", "ecommerce", "shopify", "retail", "web"],
        "niche": "Shopify D2C Apparel & Fashion Brands",
        "parent_industry": "E-Commerce & Online Retail",
        "target_service_fit": "24/7 AI conversational shopping assistance, cart abandonment recovery, and paid ad creative funnels",
        "rationale": "Brand founders and e-commerce directors are highly accessible via website press/support pages and social bios",
        "dork_keywords": ["clothing brand online shop", "apparel brand store", "d2c fashion brand website"]
    },
    {
        "service_triggers": ["marketing", "ecommerce", "shopify", "health", "supplements"],
        "niche": "Health, Wellness & Supplement Brands",
        "parent_industry": "Nutraceuticals & Online Consumer Health",
        "target_service_fit": "Repeat subscription automation, customer review funnels, and compliance-ready landing pages",
        "rationale": "Fast-growing consumer brands with accessible brand managers and marketing decision-makers",
        "dork_keywords": ["wellness supplement brand", "health nutrition online shop", "organic dietary supplements store"]
    },

    # ── Category 7: IT Services, Managed Services & SaaS ──
    {
        "service_triggers": ["ai", "software", "cybersecurity", "cloud", "it", "managed services"],
        "niche": "IT Support & Managed Service Providers (MSPs)",
        "parent_industry": "Information Technology Services",
        "target_service_fit": "Outbound business client acquisition funnels, cybersecurity monitoring, and cloud backup integrations",
        "rationale": "MSP owners and technical directors maintain public business sites and respond readily to B2B opportunities",
        "dork_keywords": ["managed it services provider", "business it support company", "network security it consultants"]
    },
    {
        "service_triggers": ["marketing", "sales", "lead generation", "saas", "software"],
        "niche": "B2B SaaS & Cloud Software Companies",
        "parent_industry": "Enterprise Software",
        "target_service_fit": "Targeted enterprise outbound prospecting, product-led marketing funnels, and developer integration support",
        "rationale": "Founders, CMOs, and sales leaders actively publish verified corporate emails and team rosters",
        "dork_keywords": ["b2b saas company", "cloud software provider", "enterprise software platform"]
    },

    # ── Category 8: Automotive & Equipment Dealerships ──
    {
        "service_triggers": ["ai", "chatbot", "marketing", "software", "auto", "car"],
        "niche": "Commercial Vehicle & Auto Dealerships",
        "parent_industry": "Automotive Retail & Commercial Fleets",
        "target_service_fit": "Virtual showroom appointment booking, automated trade-in value estimates, and service maintenance SMS",
        "rationale": "General managers and sales directors listed on staff pages with direct work email addresses",
        "dork_keywords": ["commercial truck dealership", "auto dealership inventory", "car sales and leasing center"]
    },

    # ── Category 9: Commercial Cleaning, Facilities & Hospitality ──
    {
        "service_triggers": ["automation", "software", "marketing", "cleaning", "facility"],
        "niche": "Commercial Cleaning & Janitorial Companies",
        "parent_industry": "Facility Management & Commercial Cleaning",
        "target_service_fit": "Automated site inspection quality reporting, crew shift dispatching, and office cleaning contract bidding",
        "rationale": "Business owners and regional operations managers actively bid on commercial contracts; transparent contact info",
        "dork_keywords": ["commercial janitorial services", "office cleaning company", "commercial facility cleaning"]
    },
    {
        "service_triggers": ["ai", "chatbot", "web", "hospitality", "hotel", "resort"],
        "niche": "Boutique Hotels & Event Venues",
        "parent_industry": "Hospitality & Event Services",
        "target_service_fit": "Direct booking website funnels, 24/7 guest concierge chatbots, and corporate event inquiry management",
        "rationale": "General managers, sales coordinators, and event directors openly publish their direct contact details",
        "dork_keywords": ["boutique hotel official website", "event venue corporate meetings", "luxury resort reservations"]
    },

    # ── Category 10: Staffing, Recruiting & Education ──
    {
        "service_triggers": ["ai", "software", "recruitment", "staffing", "hr"],
        "niche": "Staffing & Executive Recruitment Agencies",
        "parent_industry": "Human Resources & Talent Acquisition",
        "target_service_fit": "Automated candidate sourcing, resume screening workflows, and corporate client hiring pipelines",
        "rationale": "Recruitment agency partners and branch directors are in the business of networking and easily reached",
        "dork_keywords": ["executive search firm", "staffing agency services", "technical recruitment consultants"]
    },
    {
        "service_triggers": ["automation", "software", "b2b", "wholesale", "distributor"],
        "niche": "Wholesale Food & Beverage Distributors",
        "parent_industry": "Wholesale Trade & Distribution",
        "target_service_fit": "B2B wholesale customer ordering portals, tiered pricing catalogs, and automated invoice delivery",
        "rationale": "Sales directors and procurement managers listed on company catalogs with direct business email addresses",
        "dork_keywords": ["wholesale food distributor", "beverage distribution company", "specialty food supplier warehouse"]
    }
]


# ─── 4. Dynamic LLM / Heuristic Industry Expander ─────────────────────────────
async def generate_target_industry_niches(
    our_services: str,
    country: str = "",
    limit: int = 5,
    tracker: Optional[IndustryHistoryTracker] = None,
    use_llm: bool = True
) -> List[Dict[str, Any]]:
    """
    Expands our services and company profile into specific, easy-to-understand B2B operational niches
    with high lead contactability.
    First attempts LLM expansion (Ollama) if use_llm=True, filtering out previously scanned niches via tracker.
    Falls back gracefully to the rich Heuristic Industry Matrix if LLM is offline, timed out, or disabled.
    """
    if tracker is None:
        tracker = IndustryHistoryTracker()

    clean_services = our_services.strip() or "B2B Technology & Consulting Services"
    clean_country = country.strip()

    niches: List[Dict[str, Any]] = []

    # Attempt 1: Call Ollama for dynamic context-aware generation if enabled
    if use_llm:
        try:
            from discover import async_call_ollama

            country_context = f" operating in {clean_country}" if clean_country else ""
            scanned_samples = tracker.get_scanned_niches(clean_services)[-15:]
            avoid_clause = f"\nDO NOT suggest any of these previously scanned niches (MUST BE BRAND NEW):\n{json.dumps(scanned_samples)}" if scanned_samples else ""

            prompt = f"""You are a Senior Principal B2B Market Strategy and Outbound Lead Generation Architect.

Analyze our company profile and capabilities:
OUR CAPABILITIES / SERVICES: "{clean_services}"{country_context}

YOUR TASK:
Identify {limit + 3} TARGETED, COMMERCIAL B2B INDUSTRIES OR NICHES where businesses have an acute need for our capabilities and WHERE LEADS ARE EASY TO FIND ONLINE.

CRITICAL REQUIREMENTS:
1. EASY TO UNDERSTAND: Use plain, clean, universally recognized business names (e.g., "Dental Clinics", "Commercial Roofing Contractors", "Real Estate Brokerages", "Logistics & Trucking", "Accounting & CPA Firms", "Shopify E-Commerce Brands", "Law Firms", "Auto Dealerships"). Avoid complex academic or obscure manufacturing jargon (e.g. do NOT say "In-Silico Metrology" or "Textile Loom Sensor Integration").
2. HIGH LEAD CONTACTABILITY (LEADS MILNA ASAN HO): Focus strictly on industries where businesses maintain active public websites with team/staff directories, published email addresses, and accessible decision-makers (Owners, Founders, Partners, CEOs, Directors).
3. TARGETED OPERATIONAL FIT: Explain in ONE plain sentence how our services solve their everyday bottlenecks or generate revenue.{avoid_clause}

Respond ONLY with a valid JSON array of objects. Do not include markdown codeblocks or preamble.
Each object must have these exact keys:
- "niche": string (plain-English specific industry name)
- "parent_industry": string (broad sector)
- "target_service_fit": string (how our services solve their operational problem)
- "rationale": string (why this niche is primed to buy and easy to contact)
- "dork_keywords": list of strings (3 operational search keywords)"""

            raw_output = await async_call_ollama(
                prompt=prompt,
                system_prompt="You are a practical B2B lead generation strategist. Return strictly a raw JSON array of objects. Use clean, easy-to-understand industry names where finding real business leads and emails is fast and reliable.",
                temperature=0.7,
                max_tokens=850,
                timeout=10.0
            )

            if raw_output:
                cleaned = re.sub(r"^```json\s*", "", raw_output.strip(), flags=re.MULTILINE)
                cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE)
                start_bracket = cleaned.find("[")
                end_bracket = cleaned.rfind("]")
                if start_bracket != -1 and end_bracket != -1:
                    json_str = cleaned[start_bracket:end_bracket + 1]
                    parsed = json.loads(json_str)
                    if isinstance(parsed, list):
                        for item in parsed:
                            if isinstance(item, dict) and item.get("niche"):
                                niche_name = item["niche"].strip()
                                if not tracker.is_scanned(niche_name, clean_services):
                                    niches.append({
                                        "niche": niche_name,
                                        "parent_industry": item.get("parent_industry", "Commercial B2B Services"),
                                        "target_service_fit": item.get("target_service_fit", f"Operational deployment of {clean_services}"),
                                        "rationale": item.get("rationale", "High commercial ROI and reachable business decision-makers"),
                                        "dork_keywords": item.get("dork_keywords", [niche_name])
                                    })
                                    if len(niches) >= limit:
                                        break
                        logger.info(f"[DynamicIndustryGenerator] LLM generated {len(niches)} fresh niches")
        except Exception as e:
            logger.warning(f"[DynamicIndustryGenerator] LLM expansion unavailable ({e}); utilizing Heuristic Matrix")

    # Attempt 2: Fallback / Heuristic Matrix Expansion with Smart Randomization
    if len(niches) < limit:
        services_lower = clean_services.lower()

        # Score heuristic items based on keyword matching
        scored_candidates = []
        for item in HEURISTIC_INDUSTRY_MATRIX:
            triggers = item.get("service_triggers", [])
            match_score = sum(1 for trig in triggers if trig in services_lower)
            # Default weight for universal categories
            if "general" in triggers or "b2b" in triggers:
                match_score += 0.5
            scored_candidates.append((match_score, item))

        # Shuffle candidates first so items with identical scores rotate freshly
        random.shuffle(scored_candidates)
        # Sort descending by match relevance (preserving shuffle within score ties)
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        for score, item in scored_candidates:
            niche_name = item["niche"]
            if not tracker.is_scanned(niche_name, clean_services) and not any(n["niche"] == niche_name for n in niches):
                niches.append({
                    "niche": niche_name,
                    "parent_industry": item["parent_industry"],
                    "target_service_fit": item["target_service_fit"],
                    "rationale": item["rationale"],
                    "dork_keywords": item.get("dork_keywords", [niche_name])
                })
                if len(niches) >= limit:
                    break

    logger.info(f"[DynamicIndustryGenerator] Yielded {len(niches)} target industry niches for services='{clean_services}'")
    return niches


# ─── 5. Entry Point: get_next_discovery_batch ─────────────────────────────────
async def get_next_discovery_batch(
    our_services: str,
    selected_country: str = "",
    mode: str = "target_companies",
    tracker: Optional[IndustryHistoryTracker] = None,
    use_llm: bool = True
) -> Dict[str, Any]:
    """
    Coordinates dynamic industry discovery for the next ICP batch:
    1. Generates contextually aligned sub-industry niches from our services/profile.
    2. Selects the primary un-scanned niche and marks it in the history tracker.
    3. Builds high-converting SearXNG operational dorks tailored to the niche and country.
    4. Returns a complete discovery batch object for discover.py.
    """
    if tracker is None:
        tracker = IndustryHistoryTracker()

    clean_services = our_services.strip() or "B2B Technology & Consulting Services"
    clean_country = selected_country.strip()

    # Step 1: Generate fresh candidate niches
    candidate_niches = await generate_target_industry_niches(
        our_services=clean_services,
        country=clean_country,
        limit=5,
        tracker=tracker,
        use_llm=use_llm
    )

    if not candidate_niches:
        # Fallback to easy-to-reach commercial contractors if all standard niches are exhausted
        default_niche = "Commercial Real Estate & Property Management"
        primary = {
            "niche": default_niche,
            "parent_industry": "Commercial Real Estate",
            "target_service_fit": f"Process automation and digital transformation for {clean_services}",
            "rationale": "High-value commercial clients with publicly listed brokers and property executives",
            "dork_keywords": ["commercial real estate brokers", "property management company"]
        }
        candidate_niches = [primary]
    else:
        primary = candidate_niches[0]

    selected_niche = primary["niche"]

    # Step 2: Mark primary niche as scanned so consecutive sessions advance
    tracker.mark_scanned(
        niche=selected_niche,
        service_context=clean_services,
        country=clean_country,
        metadata={
            "parent_industry": primary.get("parent_industry"),
            "target_service_fit": primary.get("target_service_fit"),
            "mode": mode
        }
    )

    # Step 3: Build operational search dorks
    dorks = build_searxng_dorks(industry_niche=selected_niche, country=clean_country)
    tld = get_country_tld(clean_country)

    logger.info(
        f"[DynamicIndustryGenerator] Batch Selected: '{selected_niche}' ({primary.get('parent_industry')}) | "
        f"Country: '{clean_country or 'Global'}' | {len(dorks)} Dorks constructed"
    )

    return {
        "niche": selected_niche,
        "parent_industry": primary.get("parent_industry", "Commercial Industry"),
        "target_service_fit": primary.get("target_service_fit", ""),
        "rationale": primary.get("rationale", ""),
        "country": clean_country,
        "country_tld": tld,
        "queries": dorks,
        "all_generated_niches": candidate_niches
    }
