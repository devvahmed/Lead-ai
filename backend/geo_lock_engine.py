"""
Strict Local Entity & Country Lock Engine (Step 4).

Guarantees that when a user filters by a target country (e.g. Pakistan, UK, USA, Germany, UAE),
the discovery system exclusively qualifies entities with a genuine registered presence, local operational
facilities, or regional headquarters inside that target country.

Architecture:
- Country Metadata & Telephony Database (COUNTRY_GEO_MAP, ALL_CCTLDS_MAP)
- Tier 1: Deterministic TLD, Telephony & City Address Verifier (verify_deterministic_geo)
  * Local TLD Hard Pass (e.g. .pk, .co.uk -> confidence=1.0)
  * Foreign ccTLD Hard Disqualification (e.g. .de, .fr when target is Pakistan -> confidence=0.0)
  * Phone Dialing Code & Major City Address Scan
- Tier 2: Contextual LLM Geo-Gatekeeper (evaluate_contextual_geo)
- Unified Orchestrator (run_geo_lock_engine)
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

logger = logging.getLogger("geo_lock_engine")
logger.setLevel(logging.INFO)

# ─── 1. Comprehensive Country Metadata & Telephony Database ───────────────────

COUNTRY_GEO_MAP: Dict[str, Dict[str, Any]] = {
    "pakistan": {
        "canonical_name": "Pakistan",
        "iso_code": "PK",
        "tlds": [".pk", ".com.pk", ".org.pk", ".net.pk", ".edu.pk", ".gov.pk", ".biz.pk", ".web.pk"],
        "phone_prefixes": ["+92", "0092"],
        "phone_regexes": [
            r"\+92[\s\-.]?\d{2,3}[\s\-.]?\d{6,8}",
            r"\b0092[\s\-.]?\d{2,3}[\s\-.]?\d{6,8}\b",
            r"\b03\d{2}[\s\-.]?\d{7}\b",  # Pakistani mobile: 0300, 0321, 0333, etc.
            r"\b(?:021|042|051|041|052|061|091|081)[\s\-.]?\d{6,8}\b",  # Landlines
        ],
        "cities": [
            "Karachi", "Lahore", "Islamabad", "Rawalpindi", "Faisalabad", "Multan",
            "Sialkot", "Gujranwala", "Peshawar", "Quetta", "Hyderabad", "Gujrat",
            "Sheikhupura", "Sahiwal", "Rahim Yar Khan", "Sargodha", "Kasur"
        ],
        "aliases": ["pakistan", "pk", "pak", "islamic republic of pakistan"]
    },
    "united kingdom": {
        "canonical_name": "United Kingdom",
        "iso_code": "GB",
        "tlds": [".co.uk", ".uk", ".org.uk", ".gov.uk", ".me.uk", ".net.uk", ".ltd.uk", ".plc.uk"],
        "phone_prefixes": ["+44", "0044"],
        "phone_regexes": [
            r"\+44[\s\-.]?\d{2,4}[\s\-.]?\d{6,8}",
            r"\b0044[\s\-.]?\d{2,4}[\s\-.]?\d{6,8}\b",
            r"\b(?:020|0121|0161|0113|0141|0117|0114|0191|0115|0151)[\s\-.]?\d{6,8}\b",
        ],
        "cities": [
            "London", "Manchester", "Birmingham", "Leeds", "Glasgow", "Edinburgh",
            "Bristol", "Liverpool", "Sheffield", "Cardiff", "Belfast", "Newcastle",
            "Nottingham", "Southampton", "Leicester", "Coventry", "Aberdeen", "Cambridge", "Oxford"
        ],
        "aliases": ["united kingdom", "uk", "great britain", "gb", "britain", "england", "scotland", "wales"]
    },
    "united states": {
        "canonical_name": "United States",
        "iso_code": "US",
        "tlds": [".us", ".gov", ".mil"],
        "phone_prefixes": ["+1", "001"],
        "phone_regexes": [
            r"\+1[\s\-.]?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}",
            r"\b001[\s\-.]?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b",
            r"\b\(?\d{3}\)[\s\-.]\d{3}[\s\-.]\d{4}\b",
        ],
        "cities": [
            "New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia",
            "San Antonio", "San Diego", "Dallas", "Austin", "San Jose", "San Francisco",
            "Seattle", "Boston", "Atlanta", "Miami", "Denver", "Detroit", "Minneapolis",
            "Charlotte", "Orlando", "Portland", "Salt Lake City", "Pittsburgh"
        ],
        "aliases": ["united states", "usa", "us", "america", "united states of america"]
    },
    "germany": {
        "canonical_name": "Germany",
        "iso_code": "DE",
        "tlds": [".de"],
        "phone_prefixes": ["+49", "0049"],
        "phone_regexes": [
            r"\+49[\s\-.]?\(?0?\d{2,4}\)?[\s\-.]?\d{5,9}",
            r"\b0049[\s\-.]?\(?0?\d{2,4}\)?[\s\-.]?\d{5,9}\b",
        ],
        "cities": [
            "Berlin", "Munich", "Hamburg", "Frankfurt", "Cologne", "Stuttgart",
            "Dusseldorf", "Dortmund", "Essen", "Leipzig", "Bremen", "Dresden",
            "Hannover", "Nuremberg", "Duisburg", "Bochum", "Wuppertal", "Bonn"
        ],
        "aliases": ["germany", "de", "deutschland", "ger"]
    },
    "united arab emirates": {
        "canonical_name": "United Arab Emirates",
        "iso_code": "AE",
        "tlds": [".ae"],
        "phone_prefixes": ["+971", "00971"],
        "phone_regexes": [
            r"\+971[\s\-.]?\(?0?\d{1,2}\)?[\s\-.]?\d{6,8}",
            r"\b00971[\s\-.]?\(?0?\d{1,2}\)?[\s\-.]?\d{6,8}\b",
            r"\b(?:04|02|06|07|09)[\s\-.]?\d{7}\b",
        ],
        "cities": [
            "Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Ras Al Khaimah", "Fujairah",
            "Umm Al Quwain", "Al Ain"
        ],
        "aliases": ["united arab emirates", "uae", "ae", "dubai", "abu dhabi", "emirates"]
    },
    "saudi arabia": {
        "canonical_name": "Saudi Arabia",
        "iso_code": "SA",
        "tlds": [".sa", ".com.sa", ".org.sa", ".net.sa", ".edu.sa", ".gov.sa"],
        "phone_prefixes": ["+966", "00966"],
        "phone_regexes": [
            r"\+966[\s\-.]?\(?0?\d{1,2}\)?[\s\-.]?\d{7,8}",
            r"\b00966[\s\-.]?\(?0?\d{1,2}\)?[\s\-.]?\d{7,8}\b",
            r"\b(?:011|012|013|014|016|017)[\s\-.]?\d{7}\b",
        ],
        "cities": [
            "Riyadh", "Jeddah", "Mecca", "Medina", "Dammam", "Khobar", "Dhahran",
            "Tabuk", "Jubail", "Buraidah", "Abha", "Taif", "Khamis Mushait", "Najran"
        ],
        "aliases": ["saudi arabia", "saudi", "ksa", "sa", "kingdom of saudi arabia"]
    },
    "canada": {
        "canonical_name": "Canada",
        "iso_code": "CA",
        "tlds": [".ca"],
        "phone_prefixes": ["+1", "001"],
        "phone_regexes": [
            r"\+1[\s\-.]?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}",
        ],
        "cities": [
            "Toronto", "Montreal", "Vancouver", "Calgary", "Edmonton", "Ottawa",
            "Winnipeg", "Quebec City", "Hamilton", "Kitchener", "Waterloo", "Victoria", "Halifax"
        ],
        "aliases": ["canada", "ca", "can"]
    },
    "australia": {
        "canonical_name": "Australia",
        "iso_code": "AU",
        "tlds": [".com.au", ".au", ".net.au", ".org.au", ".edu.au", ".gov.au"],
        "phone_prefixes": ["+61", "0061"],
        "phone_regexes": [
            r"\+61[\s\-.]?\(?0?\d{1,2}\)?[\s\-.]?\d{8,9}",
            r"\b0061[\s\-.]?\(?0?\d{1,2}\)?[\s\-.]?\d{8,9}\b",
            r"\b(?:02|03|07|08)[\s\-.]?\d{8}\b",
        ],
        "cities": [
            "Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide", "Gold Coast",
            "Canberra", "Newcastle", "Wollongong", "Hobart", "Geelong", "Darwin"
        ],
        "aliases": ["australia", "au", "aus"]
    },
    "india": {
        "canonical_name": "India",
        "iso_code": "IN",
        "tlds": [".in", ".co.in", ".org.in", ".net.in", ".gov.in"],
        "phone_prefixes": ["+91", "0091"],
        "phone_regexes": [
            r"\+91[\s\-.]?\d{2,4}[\s\-.]?\d{6,8}",
            r"\b0091[\s\-.]?\d{2,4}[\s\-.]?\d{6,8}\b",
            r"\b[6-9]\d{9}\b",
        ],
        "cities": [
            "Mumbai", "Delhi", "Bangalore", "Bengaluru", "Hyderabad", "Ahmedabad",
            "Chennai", "Kolkata", "Surat", "Pune", "Jaipur", "Lucknow", "Kanpur",
            "Nagpur", "Indore", "Thane", "Bhopal", "Visakhapatnam", "Noida", "Gurgaon", "Gurugram"
        ],
        "aliases": ["india", "in", "ind", "bharat"]
    },
    "france": {
        "canonical_name": "France",
        "iso_code": "FR",
        "tlds": [".fr"],
        "phone_prefixes": ["+33", "0033"],
        "phone_regexes": [
            r"\+33[\s\-.]?\(?0?\d{1}\)?[\s\-.]?\d{2}[\s\-.]?\d{2}[\s\-.]?\d{2}[\s\-.]?\d{2}",
        ],
        "cities": ["Paris", "Marseille", "Lyon", "Toulouse", "Nice", "Nantes", "Strasbourg", "Bordeaux", "Lille", "Rennes"],
        "aliases": ["france", "fr", "fra"]
    },
    "netherlands": {
        "canonical_name": "Netherlands",
        "iso_code": "NL",
        "tlds": [".nl"],
        "phone_prefixes": ["+31", "0031"],
        "phone_regexes": [
            r"\+31[\s\-.]?\(?0?\d{1,3}\)?[\s\-.]?\d{6,8}",
        ],
        "cities": ["Amsterdam", "Rotterdam", "The Hague", "Den Haag", "Utrecht", "Eindhoven", "Groningen", "Tilburg"],
        "aliases": ["netherlands", "nl", "holland", "nld"]
    },
    "spain": {
        "canonical_name": "Spain",
        "iso_code": "ES",
        "tlds": [".es"],
        "phone_prefixes": ["+34", "0034"],
        "phone_regexes": [
            r"\+34[\s\-.]?\d{2,3}[\s\-.]?\d{6,7}",
        ],
        "cities": ["Madrid", "Barcelona", "Valencia", "Seville", "Zaragoza", "Malaga", "Murcia", "Palma", "Bilbao"],
        "aliases": ["spain", "es", "esp", "espana"]
    },
    "italy": {
        "canonical_name": "Italy",
        "iso_code": "IT",
        "tlds": [".it"],
        "phone_prefixes": ["+39", "0039"],
        "phone_regexes": [
            r"\+39[\s\-.]?\d{2,4}[\s\-.]?\d{6,8}",
        ],
        "cities": ["Rome", "Milan", "Naples", "Turin", "Palermo", "Genoa", "Bologna", "Florence", "Bari", "Venice", "Verona"],
        "aliases": ["italy", "it", "ita", "italia"]
    },
    "switzerland": {
        "canonical_name": "Switzerland",
        "iso_code": "CH",
        "tlds": [".ch"],
        "phone_prefixes": ["+41", "0041"],
        "phone_regexes": [
            r"\+41[\s\-.]?\(?0?\d{1,2}\)?[\s\-.]?\d{7,8}",
        ],
        "cities": ["Zurich", "Geneva", "Basel", "Lausanne", "Bern", "Lucerne", "Lugano", "St. Gallen"],
        "aliases": ["switzerland", "ch", "che", "swiss"]
    },
    "singapore": {
        "canonical_name": "Singapore",
        "iso_code": "SG",
        "tlds": [".sg", ".com.sg"],
        "phone_prefixes": ["+65", "0065"],
        "phone_regexes": [
            r"\+65[\s\-.]?\d{4}[\s\-.]?\d{4}",
        ],
        "cities": ["Singapore"],
        "aliases": ["singapore", "sg", "sgp"]
    },
    "malaysia": {
        "canonical_name": "Malaysia",
        "iso_code": "MY",
        "tlds": [".my", ".com.my"],
        "phone_prefixes": ["+60", "0060"],
        "phone_regexes": [
            r"\+60[\s\-.]?\(?0?\d{1,2}\)?[\s\-.]?\d{7,8}",
        ],
        "cities": ["Kuala Lumpur", "George Town", "Penang", "Johor Bahru", "Ipoh", "Shah Alam", "Petaling Jaya", "Subang Jaya"],
        "aliases": ["malaysia", "my", "mys"]
    }
}

# ─── 2. Global Registry of Country-Code Top-Level Domains (ccTLDs) ───────────
ALL_CCTLDS_MAP: Dict[str, str] = {
    ".pk": "pakistan",
    ".com.pk": "pakistan",
    ".org.pk": "pakistan",
    ".net.pk": "pakistan",
    ".edu.pk": "pakistan",
    ".gov.pk": "pakistan",
    ".biz.pk": "pakistan",
    ".uk": "united kingdom",
    ".co.uk": "united kingdom",
    ".org.uk": "united kingdom",
    ".gov.uk": "united kingdom",
    ".us": "united states",
    ".de": "germany",
    ".ae": "united arab emirates",
    ".sa": "saudi arabia",
    ".com.sa": "saudi arabia",
    ".ca": "canada",
    ".au": "australia",
    ".com.au": "australia",
    ".net.au": "australia",
    ".in": "india",
    ".co.in": "india",
    ".fr": "france",
    ".nl": "netherlands",
    ".es": "spain",
    ".it": "italy",
    ".ch": "switzerland",
    ".sg": "singapore",
    ".com.sg": "singapore",
    ".my": "malaysia",
    ".com.my": "malaysia",
    ".jp": "japan",
    ".cn": "china",
    ".ru": "russia",
    ".br": "brazil",
    ".com.br": "brazil",
    ".mx": "mexico",
    ".com.mx": "mexico",
    ".co.za": "south africa",
    ".co.nz": "new zealand",
    ".se": "sweden",
    ".no": "norway",
    ".dk": "denmark",
    ".fi": "finland",
    ".pl": "poland",
    ".tr": "turkey",
    ".com.tr": "turkey",
    ".id": "indonesia",
    ".co.id": "indonesia",
    ".vn": "vietnam",
    ".th": "thailand",
    ".co.th": "thailand",
    ".ph": "philippines",
    ".com.ph": "philippines",
    ".ie": "ireland",
    ".be": "belgium",
    ".at": "austria",
}


def clean_domain_key(url_or_domain: str) -> str:
    """Normalizes URL or domain string to lowercase root domain without schemes, ports, or www."""
    if not url_or_domain:
        return ""
    target = url_or_domain.strip().lower()
    if not target.startswith("http://") and not target.startswith("https://"):
        target = "http://" + target
    try:
        parsed = urlparse(target)
        netloc = parsed.netloc or parsed.path
        netloc = netloc.split(":")[0]  # strip port
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc.strip()
    except Exception:
        return url_or_domain.strip().lower()


def get_country_profile(country_name: str) -> Optional[Dict[str, Any]]:
    """Resolves country name or alias to canonical country geo profile."""
    if not country_name:
        return None
    raw = country_name.strip().lower()

    # Direct map lookup
    if raw in COUNTRY_GEO_MAP:
        return COUNTRY_GEO_MAP[raw]

    # Alias scan
    for key, data in COUNTRY_GEO_MAP.items():
        if raw == key or raw in data["aliases"]:
            return data
        # Check partial word boundary match
        for alias in data["aliases"]:
            if re.search(r'\b' + re.escape(alias) + r'\b', raw):
                return data

    return None


# ─── 3. Tier 1: Deterministic TLD, Telephony & City Address Verifier ───────────

def verify_deterministic_geo(
    domain: str,
    html_content: str = "",
    text_content: str = "",
    target_country: str = ""
) -> Tuple[bool, str, float]:
    """
    Zero-cost deterministic verification of local presence in target_country.
    
    Returns:
        (is_local: bool, reason: str, confidence: float)
        
    Confidence tiers:
        - 1.0: Local ccTLD verified hard pass
        - 0.0: Foreign ccTLD hard disqualification OR strictly foreign headquarters
        - 0.7 - 0.95: Strong domestic phone prefix / local city address match
        - < 0.7: Ambiguous signals (requires Tier 2 Contextual LLM evaluation)
    """
    clean_d = clean_domain_key(domain)
    target_profile = get_country_profile(target_country)

    if not target_profile:
        # If target country is unrecognized or generic, pass with neutral confidence
        return True, f"Target country '{target_country}' has no strict geo profile; bypassing lock", 0.5

    target_key = target_profile["aliases"][0]
    target_tlds: List[str] = sorted(target_profile["tlds"], key=len, reverse=True)

    # 1. Local ccTLD Hard Pass (check longest suffix first)
    for tld in target_tlds:
        if clean_d.endswith(tld):
            return True, f"Local ccTLD match: {tld} ({target_profile['canonical_name']})", 1.0

    # 2. Foreign ccTLD Hard Disqualification
    # If domain has an explicit country-code TLD belonging to another nation, reject immediately
    for foreign_tld, foreign_country_key in sorted(ALL_CCTLDS_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if clean_d.endswith(foreign_tld):
            if foreign_country_key != target_key:
                return False, f"Foreign ccTLD disqualification: '{foreign_tld}' belongs to {foreign_country_key.title()}, not {target_profile['canonical_name']}", 0.0

    # 3. Telephony & Major City Address Scan on page text / raw HTML
    corpus = f"{text_content}\n{html_content}".strip()
    if not corpus:
        return False, "No page text or HTML available for geo-telephony verification", 0.0

    corpus_lower = corpus.lower()
    score = 0.0
    matched_signals: List[str] = []

    # A. Country Name Mention
    country_mentions = 0
    for alias in target_profile["aliases"]:
        if re.search(r'\b' + re.escape(alias) + r'\b', corpus_lower):
            country_mentions += 1
    if country_mentions > 0:
        score += 0.3
        matched_signals.append(f"Country mention: {target_profile['canonical_name']}")

    # B. Phone Prefix & Regex Match
    phone_matched = False
    for pat in target_profile.get("phone_regexes", []):
        if re.search(pat, corpus):
            score += 0.6
            phone_matched = True
            matched_signals.append("Local telephony format/dialing code")
            break

    if not phone_matched:
        for prefix in target_profile.get("phone_prefixes", []):
            if prefix in corpus:
                score += 0.5
                phone_matched = True
                matched_signals.append(f"Local phone prefix: {prefix}")
                break

    # C. Major City Match
    cities_found: List[str] = []
    for city in target_profile.get("cities", []):
        # Match city as whole word
        if re.search(r'\b' + re.escape(city.lower()) + r'\b', corpus_lower):
            cities_found.append(city)

    if cities_found:
        # 1 city = +0.4, multiple cities = +0.5
        city_score = 0.5 if len(cities_found) > 1 else 0.4
        score += city_score
        matched_signals.append(f"Local city matches: {', '.join(cities_found[:3])}")

    # D. Foreign Conflicting Signals Disqualification
    # Scan if another country's explicit headquarters or dialing code is overwhelmingly present
    foreign_conflicts: List[str] = []
    for f_country_key, f_profile in COUNTRY_GEO_MAP.items():
        if f_country_key == target_key:
            continue
        # If text explicitly states "headquarters in [foreign country]" or "based in [foreign country]"
        f_name = f_profile["canonical_name"]
        if f"headquarters in {f_name.lower()}" in corpus_lower or f"based in {f_name.lower()}" in corpus_lower:
            foreign_conflicts.append(f_name)

    if foreign_conflicts and not phone_matched and not cities_found:
        return False, f"Explicit foreign headquarters detected in {', '.join(foreign_conflicts)}", 0.0

    score = min(score, 1.0)

    if score >= 0.7:
        reason_str = "; ".join(matched_signals)
        return True, f"Verified local presence: {reason_str}", score

    return False, f"Inconclusive deterministic signals (score={score:.2f})", score


# ─── 4. Tier 2: Contextual LLM Geo-Gatekeeper ──────────────────────────────────

async def evaluate_contextual_geo(
    domain: str,
    page_text: str,
    target_country: str,
    use_llm: bool = True
) -> Dict[str, Any]:
    """
    Lightweight contextual LLM evaluator for generic domains (.com, .io, .net).
    Determines whether the entity fundamentally maintains registered operations, facilities,
    or a corporate branch in target_country.
    """
    clean_d = clean_domain_key(domain)
    text_sample = (page_text or "").strip()[:1800]
    target_profile = get_country_profile(target_country)
    country_name = target_profile["canonical_name"] if target_profile else target_country

    if use_llm and len(text_sample) > 80:
        try:
            from discover import async_call_ollama

            prompt = f"""You are a Strict B2B Geo-Location & Corporate Entity Verifier.

DOMAIN: "{clean_d}"
TARGET COUNTRY REQUIRED: "{country_name}"

PAGE CONTENT:
\"\"\"{text_sample}\"\"\"

TASK:
Determine if this company has an ACTIVE COMMERCIAL PRESENCE, BRANCH, HEADQUARTERS, OR REGISTERED OPERATING FACILITY in "{country_name}".

STRICT RULES:
1. If the company is located, headquartered, or has an explicit branch/plant in "{country_name}", return "is_local_entity": true.
2. If the company is located exclusively in another country (e.g. USA, UK, Germany, China) and has NO operational presence in "{country_name}", return "is_local_entity": false.
3. If page content does NOT clearly establish an entity or presence in "{country_name}", return "is_local_entity": false.

Respond ONLY in valid JSON. No markdown backticks:
{{
  "is_local_entity": true or false,
  "detected_country": "Name of the country where headquarters or main operations are located",
  "confidence": 85,
  "reason": "1-sentence factual explanation based on page content"
}}"""

            raw = await async_call_ollama(
                prompt=prompt,
                system_prompt="You are a strict B2B corporate entity geo-location verifier. Respond in JSON only.",
                temperature=0.1,
                max_tokens=200,
                timeout=12.0
            )

            if raw:
                cleaned = re.sub(r"^```json\s*", "", raw.strip(), flags=re.MULTILINE)
                cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE)
                start = cleaned.find("{")
                end = cleaned.rfind("}")
                if start != -1 and end != -1:
                    parsed = json.loads(cleaned[start:end + 1])
                    if isinstance(parsed, dict) and "is_local_entity" in parsed:
                        return {
                            "is_local_entity": bool(parsed["is_local_entity"]),
                            "detected_country": str(parsed.get("detected_country", country_name)),
                            "confidence": int(parsed.get("confidence", 80)),
                            "reason": str(parsed.get("reason", "Contextual LLM geo qualification"))
                        }
        except Exception as e:
            logger.debug(f"[GeoLock] Contextual LLM evaluation error for {clean_d}: {e}")

    # Fallback heuristic: check if target country or its major cities appear in text
    text_lower = text_sample.lower()
    cities = target_profile.get("cities", []) if target_profile else []
    city_hit = any(re.search(r'\b' + re.escape(c.lower()) + r'\b', text_lower) for c in cities)
    country_hit = country_name.lower() in text_lower

    if city_hit or country_hit:
        return {
            "is_local_entity": True,
            "detected_country": country_name,
            "confidence": 75,
            "reason": f"Heuristic geo-fallback confirmed local presence ({country_name})"
        }

    return {
        "is_local_entity": False,
        "detected_country": "Foreign/Unspecified",
        "confidence": 70,
        "reason": f"No operational presence or address indicators for {country_name} found in content"
    }


# ─── 5. Unified Geo-Lock Engine Entry Point ────────────────────────────────────

async def run_geo_lock_engine(
    domain: str,
    url: str = "",
    html_content: str = "",
    text_content: str = "",
    target_country: str = "",
    use_llm: bool = True
) -> Tuple[bool, str]:
    """
    Main entry point for Strict Local Entity & Country Lock Engine.
    
    Evaluates candidate:
    1. If target_country is empty or global, immediately passes.
    2. Runs Tier 1 deterministic check (ccTLDs, phone prefixes, cities).
    3. If Tier 1 is conclusive (>= 0.7 or 0.0), returns verdict.
    4. If Tier 1 is inconclusive, executes Tier 2 contextual evaluation.
    
    Returns:
        (is_valid_geo: bool, reason: str)
    """
    clean_target = (target_country or "").strip()
    if not clean_target or clean_target.lower() in ("global", "any", "worldwide", "all", "none"):
        return True, "Target country is global / unspecified — geo lock bypassed"

    # ── Tier 1: Deterministic Check ───────────────────────────────────────────
    is_local, reason, conf = verify_deterministic_geo(
        domain=domain or url,
        html_content=html_content,
        text_content=text_content,
        target_country=clean_target
    )

    # 1. Hard pass on local ccTLD or strong contact signals
    if is_local and conf >= 0.7:
        return True, f"[Tier 1 Deterministic Geo] {reason}"

    # 2. Hard disqualification on foreign ccTLD or explicit foreign headquarters
    if not is_local and conf == 0.0 and ("Foreign ccTLD" in reason or "foreign headquarters" in reason):
        return False, f"[Tier 1 Deterministic Geo] {reason}"

    # ── Tier 2: Contextual LLM Geo-Gatekeeper ─────────────────────────────────
    contextual_res = await evaluate_contextual_geo(
        domain=domain or url,
        page_text=text_content,
        target_country=clean_target,
        use_llm=use_llm
    )

    if contextual_res.get("is_local_entity"):
        return True, f"[Tier 2 Contextual Geo] {contextual_res.get('reason', 'Local presence confirmed')} ({contextual_res.get('detected_country', clean_target)})"

    return False, f"[Tier 2 Contextual Geo] {contextual_res.get('reason', f'Entity not operating in {clean_target}')}"
