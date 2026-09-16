"""
Context-Aware Dynamic Industry Generator (Step 2).

This module analyzes our master ai_enriched_profile (or user services) and generates
contextually aligned target industries, sub-verticals, and localized search dorks.
It maintains an active history log to ensure it NEVER scans the same industry
sub-vertical repeatedly across discovery sessions.
"""

import asyncio
import json
import logging
import os
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
    
    Examples:
    - '"{niche}" "{country}" ("contact us" OR "about us" OR "our operations")'
    - '"{niche}" "{country}" ("hiring" OR "careers" OR "manual process")'
    - 'site:.{country_tld} "{niche}" ("equipment" OR "manufacturing" OR "services")'
    """
    clean_niche = industry_niche.strip()
    clean_country = country.strip()
    tld = get_country_tld(clean_country)

    dorks: List[str] = []

    # Dork 1: Corporate Operations & Direct Contact
    if clean_country:
        dorks.append(f'"{clean_niche}" "{clean_country}" ("contact us" OR "about us" OR "our operations")')
    else:
        dorks.append(f'"{clean_niche}" ("contact us" OR "about us" OR "our operations")')

    # Dork 2: Hiring & Operational Scaling Pain Points
    if clean_country:
        dorks.append(f'"{clean_niche}" "{clean_country}" ("hiring" OR "careers" OR "manual process")')
    else:
        dorks.append(f'"{clean_niche}" ("hiring" OR "careers" OR "manual process")')

    # Dork 3: Equipment, Manufacturing & Specialized Services (TLD-scoped if country available)
    if tld and tld not in ("com", ""):
        dorks.append(f'site:.{tld} "{clean_niche}" ("equipment" OR "manufacturing" OR "services")')
    elif clean_country:
        dorks.append(f'"{clean_niche}" "{clean_country}" ("equipment" OR "manufacturing" OR "services")')
    else:
        dorks.append(f'"{clean_niche}" ("equipment" OR "manufacturing" OR "services")')

    # Dork 4: Facilities, Plants & Regional Headquarters
    if clean_country:
        dorks.append(f'"{clean_niche}" "{clean_country}" ("facility" OR "plant" OR "headquarters")')
    else:
        dorks.append(f'"{clean_niche}" ("facility" OR "plant" OR "headquarters")')

    return dorks


# ─── 3. Heuristic Industry Matrix (Robust Fallback) ───────────────────────────
HEURISTIC_INDUSTRY_MATRIX: List[Dict[str, Any]] = [
    # ── Category 1: Computer Vision & Visual AI ───────────────────────────────
    {
        "service_triggers": ["computer vision", "vision", "image processing", "visual ai", "ocr", "camera", "inspection"],
        "niche": "Textile Fabric Quality Control",
        "parent_industry": "Textile Manufacturing",
        "target_service_fit": "Automated visual defect detection on high-speed loom fabric to eliminate manual inspection scrap",
        "rationale": "High scrap rates and human fatigue during continuous fabric inspection create urgent ROI for automated vision",
        "dork_keywords": ["weaving mills", "fabric inspection", "textile quality assurance"]
    },
    {
        "service_triggers": ["computer vision", "vision", "defect", "ai", "inspection"],
        "niche": "Pharmaceutical Packaging Inspection",
        "parent_industry": "Pharmaceutical Manufacturing",
        "target_service_fit": "High-throughput optical blister pack, vial seal, and label alignment verification",
        "rationale": "Strict regulatory compliance (FDA/EMA) requires 100% verification of packaging and lot codes",
        "dork_keywords": ["blister packaging", "pharma packaging facility", "sterile vial inspection"]
    },
    {
        "service_triggers": ["computer vision", "vision", "sorting", "fmcg", "ai"],
        "niche": "FMCG Defect Detection & Sorting",
        "parent_industry": "Food & Beverage Processing",
        "target_service_fit": "Automated conveyor-belt defect grading, foreign body rejection, and container seal checking",
        "rationale": "Mass-market brand reputation and food safety regulations penalize packaging flaws and product contamination",
        "dork_keywords": ["food packaging line", "bottling plant", "sorting and grading facility"]
    },
    {
        "service_triggers": ["computer vision", "vision", "agriculture", "ai"],
        "niche": "Agricultural Produce Grading & Packing",
        "parent_industry": "Agri-Business & Post-Harvest",
        "target_service_fit": "Automated multi-spectral optical sizing and defect grading for fruit, citrus, and vegetable packing houses",
        "rationale": "Export markets enforce strict visual grade standards; manual sorting cannot meet packing-house speeds",
        "dork_keywords": ["fruit packing facility", "citrus packing house", "post-harvest grading"]
    },
    {
        "service_triggers": ["computer vision", "vision", "automotive", "hardware"],
        "niche": "Automotive Assembly Line Visual QC",
        "parent_industry": "Automotive Tier 1 Suppliers",
        "target_service_fit": "Weld bead integrity, gap-and-flush measurement, and paint surface flaw detection",
        "rationale": "Tier 1 automotive suppliers face severe OEM penalties for defective parts reaching final assembly",
        "dork_keywords": ["tier 1 auto stamping", "automotive welding facility", "chassis assembly plant"]
    },

    # ── Category 2: Automated Inventory & Logistics ───────────────────────────
    {
        "service_triggers": ["automated inventory", "inventory", "warehouse", "automation", "wms", "rfid", "barcode"],
        "niche": "Cold Storage Warehouses",
        "parent_industry": "Logistics & Temperature Controlled Storage",
        "target_service_fit": "Automated temperature-proof pallet tracking, batch expiration monitoring, and picking optimization",
        "rationale": "Freezer environments cause high worker turnover; automated inventory tracking reduces labor exposure and spoilage",
        "dork_keywords": ["cold storage facility", "refrigerated logistics", "cold chain distribution"]
    },
    {
        "service_triggers": ["automated inventory", "inventory", "spare parts", "distribution", "erp", "supply chain"],
        "niche": "Automotive Spare Parts Distributors",
        "parent_industry": "Wholesale Automotive Aftermarket",
        "target_service_fit": "High-SKU dynamic bin location mapping, automated cross-referencing, and rapid pick-and-pack tracking",
        "rationale": "Managing tens of thousands of fast-moving part numbers leads to severe inventory inaccuracies without modern automation",
        "dork_keywords": ["auto parts distribution center", "aftermarket parts warehouse", "replacement parts supplier"]
    },
    {
        "service_triggers": ["automated inventory", "inventory", "fulfillment", "ecommerce", "warehouse", "3pl"],
        "niche": "E-commerce Fulfillment Centers",
        "parent_industry": "Third-Party Logistics (3PL)",
        "target_service_fit": "Real-time multi-channel stock synchronization, automated wave picking, and automated return processing",
        "rationale": "Peak shopping seasons overwhelm manual stock counting and produce costly shipping delays and stockouts",
        "dork_keywords": ["3pl fulfillment center", "ecommerce warehousing", "contract packing facility"]
    },
    {
        "service_triggers": ["automated inventory", "inventory", "chemical", "hazardous", "materials"],
        "niche": "Chemical & Hazardous Materials Storage",
        "parent_industry": "Industrial Chemicals & Distribution",
        "target_service_fit": "Automated segregation enforcement, SDS compliance tracking, and container weight telematics",
        "rationale": "Strict environmental and safety liability mandates automated, auditable tracking of volatile substances",
        "dork_keywords": ["chemical distribution warehouse", "hazmat storage facility", "bulk chemical terminal"]
    },
    {
        "service_triggers": ["automated inventory", "inventory", "medical", "hospital", "pharma"],
        "niche": "Medical Supplies & Hospital Logistics",
        "parent_industry": "Healthcare Supply Chain",
        "target_service_fit": "Automated consignment inventory tracking, UDI compliance scanning, and sterility expiration management",
        "rationale": "Hospitals require zero-stockout reliability for surgical trays and critical disposables",
        "dork_keywords": ["medical supply distribution", "hospital logistics center", "surgical supplies warehouse"]
    },

    # ── Category 3: Web & Mobile App Development / Custom Software ────────────
    {
        "service_triggers": ["web", "mobile", "app development", "custom software", "software", "saas", "fullstack"],
        "niche": "Specialty Freight Dispatch & Brokering",
        "parent_industry": "Commercial Transportation",
        "target_service_fit": "Custom mobile driver apps with proof-of-delivery capture, route telematics, and automated broker portals",
        "rationale": "Regional trucking companies lose margins using generic spreadsheets instead of dedicated real-time dispatch tools",
        "dork_keywords": ["freight dispatch service", "heavy haul logistics", "flatbed transport operations"]
    },
    {
        "service_triggers": ["web", "mobile", "app development", "custom software", "field", "operations"],
        "niche": "Commercial HVAC & Refrigeration Service Management",
        "parent_industry": "Mechanical Contracting & Facility Services",
        "target_service_fit": "Custom field service dispatch software, technician offline mobile diagnostic checklists, and customer portals",
        "rationale": "Emergency response service agreements require rapid technician routing and digital job sign-offs",
        "dork_keywords": ["commercial hvac contractor", "industrial refrigeration services", "mechanical engineering facility services"]
    },
    {
        "service_triggers": ["web", "mobile", "custom software", "healthcare", "crm"],
        "niche": "Dental Practice Management & Patient Portals",
        "parent_industry": "Multi-Location Healthcare Clinics",
        "target_service_fit": "Custom multi-clinic patient onboarding, insurance pre-authorization workflows, and automated appointment rescheduling",
        "rationale": "Growing dental groups need customized integrations between legacy imaging equipment and modern billing engines",
        "dork_keywords": ["dental group practice", "orthodontic clinic headquarters", "multi-location dental center"]
    },
    {
        "service_triggers": ["web", "mobile", "custom software", "construction", "billing"],
        "niche": "Construction Subcontractor Field Billing",
        "parent_industry": "Commercial Construction",
        "target_service_fit": "Custom mobile progress billing, daily field log verification, and change-order approval tracking",
        "rationale": "Delayed change orders and paper field reports cause major cash-flow bottlenecks for trade subcontractors",
        "dork_keywords": ["commercial electrical contractor", "drywall and framing contractor", "steel fabrication construction"]
    },

    # ── Category 4: Digital Marketing & B2B Lead Gen ───────────────────────────
    {
        "service_triggers": ["marketing", "lead generation", "growth", "seo", "sales", "ads"],
        "niche": "Boutique Commercial Real Estate Brokerages",
        "parent_industry": "Commercial Real Estate",
        "target_service_fit": "Hyper-targeted outbound tenant acquisition, industrial property deal flow campaigns, and investor lead pipelines",
        "rationale": "Brokers need high-value commercial tenant leads for warehouse and office parks with large deal commissions",
        "dork_keywords": ["commercial real estate brokerage", "industrial leasing agency", "commercial property advisors"]
    },
    {
        "service_triggers": ["marketing", "lead generation", "sales", "industrial", "auction"],
        "niche": "Industrial Equipment Auctioneers",
        "parent_industry": "Heavy Machinery & Capital Equipment",
        "target_service_fit": "Global bidder acquisition funnels, heavy plant asset remarketing campaigns, and surplus inventory liquidation outreach",
        "rationale": "Auction houses need qualified industrial buyers within short 30-day marketing windows before scheduled sales",
        "dork_keywords": ["industrial equipment auction", "machinery liquidation company", "plant asset auctions"]
    },

    # ── Category 5: Universal / General B2B Services ──────────────────────────
    {
        "service_triggers": ["automation", "consulting", "b2b", "services", "general"],
        "niche": "Precision CNC Machine Shops",
        "parent_industry": "Industrial Precision Manufacturing",
        "target_service_fit": "Automated production scheduling, vendor quotation portal, and scrap reduction analytics",
        "rationale": "High machine capital costs require maximizing spindle uptime and fast turnaround on complex RFQs",
        "dork_keywords": ["precision cnc machining", "aerospace precision machine shop", "custom metal fabrication facility"]
    },
    {
        "service_triggers": ["automation", "consulting", "b2b", "services", "general"],
        "niche": "Commercial Solar EPC Contractors",
        "parent_industry": "Renewable Energy & Power Engineering",
        "target_service_fit": "Commercial rooftop feasibility tracking, automated permitting workflows, and asset monitoring portals",
        "rationale": "Massive influx of commercial energy transition projects creates high demand for modern operational tooling",
        "dork_keywords": ["commercial solar epc", "turnkey solar installer", "industrial solar systems provider"]
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
    Expands our services and company profile into specific, non-obvious B2B operational niches.
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
            scanned_samples = tracker.get_scanned_niches(clean_services)[:10]
            avoid_clause = f"\nDO NOT suggest any of these previously scanned niches:\n{json.dumps(scanned_samples)}" if scanned_samples else ""

            prompt = f"""You are a Senior Principal B2B Market Strategy and Industrial Engineering Architect.

Analyze our company profile and capabilities:
OUR CAPABILITIES / SERVICES: "{clean_services}"{country_context}

YOUR TASK:
Identify {limit + 3} HIGHLY SPECIFIC, NON-OBVIOUS operational B2B industries, manufacturing verticals, or specialized enterprise niches that have acute operational bottlenecks where our capabilities solve painful, expensive problems.

CRITICAL REQUIREMENTS:
1. Avoid generic high-level labels (e.g. do NOT say just "Healthcare", "Retail", "Manufacturing", or "E-commerce").
2. Choose specific operational niches (e.g., "Textile Fabric Quality Control", "Cold Storage Warehouses", "Commercial HVAC Fleet Dispatch", "FMCG Defect Sorting").
3. Explain the specific operational fit and why they have urgent commercial demand for our capabilities.{avoid_clause}

Respond ONLY with a valid JSON array of objects. Do not include markdown codeblocks or preamble.
Each object must have these exact keys:
- "niche": string (the exact specific sub-vertical name)
- "parent_industry": string (broad sector)
- "target_service_fit": string (how our services solve their operational bottleneck)
- "rationale": string (why this niche is primed to buy)
- "dork_keywords": list of strings (3 operational search keywords)"""

            raw_output = await async_call_ollama(
                prompt=prompt,
                system_prompt="You are a B2B Market Analyst. Return strictly a raw JSON array of objects. No markdown, no commentary.",
                temperature=0.3,
                max_tokens=800,
                timeout=10.0
            )

            if raw_output:
                # Clean possible markdown wrapping
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
                                        "parent_industry": item.get("parent_industry", "Industrial B2B"),
                                        "target_service_fit": item.get("target_service_fit", f"Operational deployment of {clean_services}"),
                                        "rationale": item.get("rationale", "High commercial ROI and operational need"),
                                        "dork_keywords": item.get("dork_keywords", [niche_name])
                                    })
                                    if len(niches) >= limit:
                                        break
                        logger.info(f"[DynamicIndustryGenerator] LLM generated {len(niches)} fresh niches")
        except Exception as e:
            logger.warning(f"[DynamicIndustryGenerator] LLM expansion unavailable ({e}); utilizing Heuristic Matrix")

    # Attempt 2: Fallback / Heuristic Matrix Expansion
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

        # Sort descending by match relevance
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
        # Fallback to general precision machining if all standard niches are exhausted
        default_niche = "Precision Industrial Manufacturing Facilities"
        primary = {
            "niche": default_niche,
            "parent_industry": "Advanced Manufacturing",
            "target_service_fit": f"Process automation and digital transformation for {clean_services}",
            "rationale": "High capital equipment expenditure with strong demand for operational efficiency",
            "dork_keywords": ["precision manufacturing", "industrial facility"]
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
