"""
Multi-Tier Deterministic & Semantic Junk Firewall (Step 3).

This module eliminates non-commercial leads, blogs, listicles, review directories
(Clutch, Yelp, Medium, Wikipedia), news outlets, affiliate sites, and thin parked
domains before heavy scraping and deep LLM evaluation.

Pipeline:
1. Tier 1: Deterministic Pre-LLM Filter (Domain blacklists, path regexes, JSON-LD schema guard, thin content guard).
2. Tier 2: Lightweight Semantic Entity Classifier (Determines whether candidate is an active commercial operating entity).
3. Combined Entry: run_junk_firewall.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

logger = logging.getLogger("junk_firewall")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s")

# ─── Tier 1 Constants: Review Directories & Aggregators ─────────────────────────
REVIEW_DIRECTORIES: Set[str] = {
    # B2B & Agency Review Platforms
    "clutch.co", "g2.com", "capterra.com", "goodfirms.co", "upcity.com",
    "designrush.com", "sortlist.com", "topdevelopers.co", "agencyspotter.com",
    "trustpilot.com", "trustradius.com", "getapp.com", "softwareadvice.com",
    "peerspot.com", "comparably.com", "gartner.com", "ggfirms.com",
    # Consumer & Local Directories
    "yelp.com", "yellowpages.com", "superpages.com", "whitepages.com",
    "bbb.org", "manta.com", "chamberofcommerce.com", "bizapedia.com",
    "opencorporates.com", "companieshouse.gov.uk", "angi.com",
    "homeadvisor.com", "thumbtack.com", "bark.com", "expertise.com",
    "tripadvisor.com", "foursquare.com",
    # B2B Supplier & Marketplace Portals
    "kompass.com", "europages.com", "thomasnet.com", "dnb.com", "hoovers.com",
    "zoominfo.com", "apollo.io", "lusha.com", "hunter.io", "clearbit.com",
    "crunchbase.com", "pitchbook.com", "dealroom.co", "glassdoor.com",
    "indeed.com", "zippia.com", "salary.com", "builtin.com",
    "made-in-china.com", "alibaba.com", "aliexpress.com", "globalsources.com",
    "tradeindia.com", "indiamart.com", "ec21.com"
}

# ─── Tier 1 Constants: Publishing, Media, Social & Forum Platforms ──────────────
PUBLISHING_AND_SOCIAL_PLATFORMS: Set[str] = {
    # Blogging & Independent Publishing
    "medium.com", "substack.com", "wordpress.com", "blogspot.com", "wixsite.com",
    "weebly.com", "tumblr.com", "ghost.org", "dev.to", "hashnode.com",
    # Reference & Knowledge Repositories
    "wikipedia.org", "wikimedia.org", "wikidata.org", "wikihow.com", "archive.org",
    # Code & Technical Repositories
    "github.com", "gitlab.com", "bitbucket.org", "sourceforge.net", "npm.js",
    "pypi.org", "crates.io",
    # Social Media & Messaging
    "reddit.com", "news.ycombinator.com", "quora.com", "stackexchange.com",
    "stackoverflow.com", "youtube.com", "facebook.com", "instagram.com",
    "twitter.com", "x.com", "linkedin.com", "pinterest.com", "tiktok.com",
    # News & PR Outlets
    "businesswire.com", "prnewswire.com", "globenewswire.com", "prweb.com",
    "forbes.com", "fortune.com", "inc.com", "businessinsider.com",
    "techcrunch.com", "theverge.com", "wired.com", "reuters.com", "bloomberg.com"
}

# ─── Tier 1 Constants: Non-Commercial URL Path Regexes ─────────────────────────
BLOG_AND_ARTICLE_PATH_PATTERNS: List[re.Pattern] = [
    # Article / Blog / News prefixes
    re.compile(r"/(blog|article|articles|news|press-release|press-releases|post|posts|insights|stories|opinion)(/|\.html?|$)", re.IGNORECASE),
    # Listicle & comparison patterns
    re.compile(r"/(top-\d+|best-\d+|top\d+|best\d+|top-|best-)", re.IGNORECASE),
    # Review & comparison subpaths
    re.compile(r"/(reviews?|ratings?|comparison|versus|vs)(/|\.html?|$)", re.IGNORECASE),
    # Author / Category / Tag taxonomies
    re.compile(r"/(category|tag|tags|author|archives?|topic)/", re.IGNORECASE),
    # LinkedIn Pulse article posts
    re.compile(r"linkedin\.com/pulse/", re.IGNORECASE),
    # Non-web document files
    re.compile(r"\.(pdf|doc|docx|ppt|pptx|zip|tar|gz)$", re.IGNORECASE),
]

# ─── Tier 1 Constants: JSON-LD Schema Entity Classification ────────────────────
JSONLD_COMMERCIAL_TYPES: Set[str] = {
    "Organization", "Corporation", "LocalBusiness", "AutomotiveBusiness",
    "ManufacturingBusiness", "Store", "ProfessionalService", "FinancialService",
    "LegalService", "MedicalBusiness", "WholesaleStore", "GeneralContractor",
    "Dentist", "Bakery", "Brewery", "HVACBusiness", "HomeAndConstructionBusiness",
    "HealthAndBeautyBusiness", "FoodEstablishment", "EmergencyService",
    "EducationalOrganization", "RecyclingCenter"
}

JSONLD_REJECT_TYPES: Set[str] = {
    "Article", "BlogPosting", "NewsArticle", "ItemPage", "SearchResultsPage",
    "CollectionPage", "TechArticle", "DiscussionForumPosting", "WebPageElement",
    "QAPage", "ProfilePage"
}

# ─── Tier 1 Constants: Parked Domain & Thin Content Indicators ─────────────────
PARKED_DOMAIN_TERMS: List[str] = [
    "domain is for sale", "buy this domain", "parked free by", "domain for sale",
    "godaddy", "namecheap", "hugedomains", "dan.com", "sedo", "afternic",
    "under construction", "coming soon", "apache2 default page", "iis windows server",
    "cloudflare ray id", "website coming soon", "this site is parked"
]


def clean_domain_key(url_or_domain: str) -> str:
    """Extracts lowercase root domain, stripping ports, scheme, and www."""
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


def is_in_domain_set(domain: str, domain_set: Set[str]) -> bool:
    """Checks exact match or subdomain matching against a set of root domains."""
    if not domain:
        return False
    clean_d = clean_domain_key(domain)
    if clean_d in domain_set:
        return True
    return any(clean_d.endswith("." + blk) for blk in domain_set)


def extract_jsonld_types(html: str) -> List[str]:
    """Extracts all @type definitions from HTML JSON-LD script blocks."""
    if not html or "<script" not in html:
        return []

    types_found: List[str] = []
    matches = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)

    for script_content in matches:
        script_content = script_content.strip()
        if not script_content:
            continue
        try:
            data = json.loads(script_content)
            _collect_types(data, types_found)
        except Exception:
            # Fallback regex for dirty JSON-LD
            raw_types = re.findall(r'"@type"\s*:\s*"([a-zA-Z0-9_-]+)"', script_content)
            types_found.extend(raw_types)

    return types_found


def _collect_types(obj: Any, out_types: List[str]) -> None:
    """Recursively collects '@type' from nested JSON-LD dicts and arrays."""
    if isinstance(obj, dict):
        if "@type" in obj:
            t = obj["@type"]
            if isinstance(t, str):
                out_types.append(t)
            elif isinstance(t, list):
                out_types.extend([item for item in t if isinstance(item, str)])
        if "@graph" in obj and isinstance(obj["@graph"], list):
            for item in obj["@graph"]:
                _collect_types(item, out_types)
        for val in obj.values():
            if isinstance(val, (dict, list)):
                _collect_types(val, out_types)
    elif isinstance(obj, list):
        for item in obj:
            _collect_types(item, out_types)


# ─── 1. Tier 1: Deterministic Pre-LLM Filter ──────────────────────────────────
def is_deterministic_junk(
    url: str,
    domain: str = "",
    html_content: str = "",
    text_content: str = "",
    is_search_snippet: bool = False
) -> Tuple[bool, str]:
    """
    Zero-cost deterministic check that evaluates URL, domain, JSON-LD, and text length.
    Returns (is_junk, reason).
    """
    clean_d = clean_domain_key(domain or url)
    raw_url = (url or "").strip()

    # 1. Review & Aggregator Directory Blacklist
    if is_in_domain_set(clean_d, REVIEW_DIRECTORIES):
        return True, f"Review directory / directory aggregator: {clean_d}"

    # 2. Article / Blog / Listicle URL Path Regex (Check paths on any domain first)
    if raw_url:
        try:
            path = urlparse(raw_url).path or ""
            for pat in BLOG_AND_ARTICLE_PATH_PATTERNS:
                if pat.search(path) or pat.search(raw_url):
                    return True, f"Non-commercial article / blog URL pattern: {path or raw_url}"
        except Exception:
            pass

    # 3. Publishing, Media & Social Platforms Blacklist
    if is_in_domain_set(clean_d, PUBLISHING_AND_SOCIAL_PLATFORMS):
        # Allow corporate company pages if not pulse / general forum
        if clean_d in ("linkedin.com", "twitter.com", "x.com") and not any(p in raw_url.lower() for p in ("/pulse/", "/status/")):
            pass
        else:
            return True, f"Publishing / social / media platform: {clean_d}"

    # 4. JSON-LD Schema Guard
    if html_content:
        schema_types = extract_jsonld_types(html_content)
        if schema_types:
            has_commercial_pass = any(st in JSONLD_COMMERCIAL_TYPES for st in schema_types)
            has_reject_type = any(st in JSONLD_REJECT_TYPES for st in schema_types)

            # If article/blog is declared without an encompassing organization/business schema, reject
            if has_reject_type and not has_commercial_pass:
                matched_rejects = [st for st in schema_types if st in JSONLD_REJECT_TYPES]
                return True, f"Non-commercial JSON-LD schema (@type={matched_rejects[0]})"

    # 5. Thin Content & Word Count Guard
    # Check text content if available (or strip HTML if only html_content was passed)
    active_text = text_content.strip()
    if not active_text and html_content:
        stripped = re.sub(r"<[^>]+>", " ", html_content)
        active_text = re.sub(r"\s+", " ", stripped).strip()

    if active_text:
        words = active_text.split()
        word_count = len(words)
        text_lower = active_text.lower()

        # Check parked domain signatures
        for term in PARKED_DOMAIN_TERMS:
            if term in text_lower and word_count < 150:
                return True, f"Thin content / parked domain placeholder ('{term}')"

        if not is_search_snippet:
            core_indicators = ("about", "contact", "services", "products", "operations", "solutions", "copyright", "terms", "company")
            has_indicators = any(ci in text_lower for ci in core_indicators)

            # Ultra-thin text or text lacking core business indicators
            if word_count < 40 or (word_count < 80 and not has_indicators):
                return True, f"Thin content: only {word_count} words extracted"
        else:
            # Search snippets are inherently concise (10-25 words); reject only if empty (< 4 words)
            if word_count < 4:
                return True, f"Thin snippet: only {word_count} words"

    return False, "Passed Tier 1 deterministic filter"


# ─── 2. Tier 2: Semantic Entity Classifier ────────────────────────────────────
async def evaluate_semantic_junk(
    domain: str,
    page_text: str,
    use_llm: bool = True
) -> Dict[str, Any]:
    """
    Lightweight semantic entity classifier. Determines whether domain represents
    an active commercial operating entity (factory, warehouse, B2B firm, agency, etc.)
    vs a blog, directory, news outlet, or affiliate site.
    """
    clean_d = clean_domain_key(domain)
    text_sample = (page_text or "").strip()[:1400]

    # Attempt 1: Call lightweight LLM check
    if use_llm and len(text_sample) > 80:
        try:
            from discover import async_call_ollama

            prompt = f"""You are a Senior B2B Commercial Entity Classifier.

Analyze the website content for:
DOMAIN: "{clean_d}"
WEBSITE CONTENT SNIPPET:
\"\"\"{text_sample}\"\"\"

YOUR TASK:
Determine whether this domain represents a REAL COMMERCIAL OPERATING ENTITY (a company, manufacturer, agency, factory, service provider, healthcare clinic, or contractor) that operates real commercial business.

VERSUS JUNK:
A blog, review site, directory, listicle, news portal, personal hobby site, or affiliate marketing aggregator.

Respond ONLY with a valid JSON object. No preamble, no markdown codeblocks:
{{
  "is_junk": true or false,
  "entity_type": "COMMERCIAL_BUSINESS" | "DIRECTORY_OR_LISTICLE" | "BLOG_OR_NEWS" | "AFFILIATE_OR_PARKED",
  "reason": "Clear 1-sentence explanation of why it is commercial or junk"
}}"""

            raw = await async_call_ollama(
                prompt=prompt,
                system_prompt="You are a B2B Commercial Entity Classifier. Respond with valid JSON only.",
                temperature=0.1,
                max_tokens=200,
                timeout=7.0
            )

            if raw:
                cleaned = re.sub(r"^```json\s*", "", raw.strip(), flags=re.MULTILINE)
                cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE)
                start = cleaned.find("{")
                end = cleaned.rfind("}")
                if start != -1 and end != -1:
                    parsed = json.loads(cleaned[start:end + 1])
                    if isinstance(parsed, dict) and "is_junk" in parsed:
                        return {
                            "is_junk": bool(parsed["is_junk"]),
                            "entity_type": parsed.get("entity_type", "COMMERCIAL_BUSINESS" if not parsed["is_junk"] else "BLOG_OR_NEWS"),
                            "reason": parsed.get("reason", "Semantic classification verdict")
                        }
        except Exception as e:
            logger.debug(f"[JunkFirewall] Semantic LLM classifier error for {clean_d}: {e}")

    # Attempt 2: Deterministic / Heuristic semantic fallback
    text_lower = text_sample.lower()

    # Commercial operating entity indicators
    commercial_signals = [
        "our services", "our products", "request a quote", "contact us", "about us",
        "headquarters", "clients", "industries served", "solutions", "capabilities",
        "iso 9001", "facilities", "rfq", "equipment", "manufactur"
    ]
    # Non-commercial / content publisher indicators
    junk_signals = [
        "affiliate link", "amazon associate", "top 10", "best of 202", "leave a reply",
        "written by", "published on", "tags:", "filed under", "related posts",
        "guest post", "sponsored content", "disclaimer: this post contains affiliate"
    ]

    c_score = sum(1 for s in commercial_signals if s in text_lower)
    j_score = sum(2 for s in junk_signals if s in text_lower)

    if j_score > c_score and j_score >= 2:
        return {
            "is_junk": True,
            "entity_type": "BLOG_OR_NEWS",
            "reason": f"Heuristic semantic check flagged publishing / affiliate patterns (junk_score={j_score})"
        }

    return {
        "is_junk": False,
        "entity_type": "COMMERCIAL_BUSINESS",
        "reason": "Heuristic semantic check confirmed commercial operating footprint"
    }


# ─── 3. Main Combined Entry Point: run_junk_firewall ──────────────────────────
async def run_junk_firewall(
    url: str,
    domain: str,
    html_content: str = "",
    text_content: str = "",
    is_search_snippet: bool = False,
    use_llm: bool = True
) -> Tuple[bool, str]:
    """
    Main firewall entry point.
    Executes Tier 1 deterministic check first. If it passes, executes Tier 2 semantic check.
    Returns (is_junk, reason).
    """
    # ── Tier 1: Deterministic Filter ──────────────────────────────────────────
    is_tier1_junk, tier1_reason = is_deterministic_junk(
        url=url,
        domain=domain,
        html_content=html_content,
        text_content=text_content,
        is_search_snippet=is_search_snippet
    )
    if is_tier1_junk:
        return True, f"[Tier 1 Deterministic] {tier1_reason}"

    # ── Tier 2: Semantic Entity Classifier ────────────────────────────────────
    semantic_res = await evaluate_semantic_junk(
        domain=domain or url,
        page_text=text_content,
        use_llm=use_llm
    )
    if semantic_res.get("is_junk"):
        return True, f"[Tier 2 Semantic] {semantic_res.get('reason', 'Non-commercial entity')}"

    return False, "Passed firewall: Verified commercial operating entity"
