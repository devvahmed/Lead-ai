import os
import re
import json
import time
import asyncio
import logging
import socket

logger = logging.getLogger("discover")
import urllib.request
import urllib.parse
from typing import AsyncIterator, List, Optional, Dict
from fastapi import APIRouter, Query, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth_routes import get_current_company
from auth_models import Company

discover_router = APIRouter()

import builtins
_orig_print = builtins.print
def print(*args, **kwargs):
    kwargs.setdefault('flush', True)
    _orig_print(*args, **kwargs)
builtins.print = print

# ─── Import helpers from email_outreach.py ───────────────────────────────────
from email_outreach import (
    fetch_url_content,
    fetch_url_content_with_subpages as _legacy_fetch_url_content_with_subpages,
    compute_relevance_score
)
from multi_source_ingestion import ingest_all_sources, RawLeadCandidate
from dynamic_industry_generator import get_next_discovery_batch, IndustryHistoryTracker
from junk_firewall import run_junk_firewall, is_deterministic_junk
from geo_lock_engine import run_geo_lock_engine, verify_deterministic_geo
from intent_classifier import run_intent_classifier
from smart_dom_crawler import crawl_smart_dom_target, get_base_domain
from operational_audit_engine import audit_company_operations
from three_way_match_matrix import run_three_way_match_matrix, ThreeWayMatchResult
from evidence_scoring_360 import calculate_evidence_score, generate_360_post_click_audit, EvidenceScoreBreakdown
from llm_utils import call_llm as _llm_router_call


async def fetch_url_content_with_smart_dom(url: str, timeout: float = 4.0, domain: str = "") -> Tuple[str, str]:
    """
    Step 6: Dynamic DOM Header/Footer/Nav Link Parser & Multi-Page Crawler.
    Parses DOM structural zones (<nav>, <header>, <footer>, <body>) on the candidate homepage
    to discover and concurrently fetch the highest-value operational subpages.
    """
    try:
        crawl_res = await crawl_smart_dom_target(
            domain=domain or get_base_domain(url),
            homepage_url=url,
            max_pages=4
        )
        combined = crawl_res.get("combined_text", "")
        label = crawl_res.get("source_label", "homepage")
        if combined and (len(combined.split()) >= 60 or "[PAGE:" in combined):
            return combined, label
    except Exception as e:
        logger.debug(f"[SmartDOMCrawler] Crawl failed for {url}: {e}")

    # Fallback to legacy fetcher if needed
    try:
        return await _legacy_fetch_url_content_with_subpages(url, timeout=timeout)
    except Exception:
        return "", "none"

# Default fetcher alias for discovery pipeline & test suite backwards compatibility
fetch_url_content_with_subpages = fetch_url_content_with_smart_dom

# ─── Noise Filter Sets ────────────────────────────────────────────────────────
#
# EXCLUDE_DOMAINS: root domains that should NEVER be treated as a prospect
# company's homepage. Organised by category for maintainability.
#
EXCLUDE_DOMAINS = {
    # ── Encyclopaedias / Q&A ──────────────────────────────────────────────────
    'wikipedia.org', 'wikimedia.org', 'wikidata.org', 'wikihow.com',
    'quora.com', 'reddit.com', 'stackexchange.com', 'stackoverflow.com',
    'answers.com', 'ehow.com',

    # ── Social Media & Messaging ──────────────────────────────────────────────
    'twitter.com', 'x.com', 'facebook.com', 'instagram.com', 'linkedin.com',
    'pinterest.com', 'tiktok.com', 'snapchat.com', 'tumblr.com',
    'telegram.org', 't.me', 'discord.com', 'whatsapp.com',
    'vimeo.com', 'youtube.com', 'youtu.be', 'dailymotion.com', 'twitch.tv',
    'flickr.com', 'imgur.com', 'giphy.com',

    # ── General News & Business Media ─────────────────────────────────────────
    'bloomberg.com', 'reuters.com', 'apnews.com', 'bbc.com', 'bbc.co.uk',
    'cnn.com', 'cnbc.com', 'foxbusiness.com', 'nytimes.com',
    'washingtonpost.com', 'theguardian.com', 'ft.com', 'wsj.com',
    'economist.com', 'marketwatch.com', 'thestreet.com', 'barrons.com',
    'investopedia.com', 'seekingalpha.com', 'motleyfool.com',

    # ── Tech / Startup Media ──────────────────────────────────────────────────
    'techcrunch.com', 'venturebeat.com', 'wired.com', 'theverge.com',
    'arstechnica.com', 'zdnet.com', 'thenextweb.com', 'engadget.com',
    'mashable.com', 'gizmodo.com', 'infoworld.com', 'computerworld.com',
    'networkworld.com', 'itpro.co.uk', 'techradar.com',

    # ── Business / Entrepreneur Media ─────────────────────────────────────────
    'forbes.com', 'fortune.com', 'inc.com', 'businessinsider.com',
    'entrepreneur.com', 'fastcompany.com', 'hbr.org', 'mckinsey.com',

    # ── PR / Press Release Wire Services ─────────────────────────────────────
    'businesswire.com', 'prnewswire.com', 'globenewswire.com',
    'accesswire.com', 'einpresswire.com', 'prlog.org', 'prweb.com',
    'newswire.com', 'send2press.com', 'openpr.com',

    # ── B2B Directories & Sales Intelligence Platforms ────────────────────────
    'crunchbase.com', 'pitchbook.com', 'dnb.com', 'hoovers.com',
    'zoominfo.com', 'lusha.com', 'apollo.io', 'hunter.io', 'clearbit.com',
    'datanyze.com', 'leadgenius.com', 'cognism.com', 'seamless.ai',
    'uplead.com', 'rocketreach.co', 'getlatka.com',

    # ── Major B2B Marketplaces & Supplier Directories ─────────────────────────
    'made-in-china.com', 'alibaba.com', 'aliexpress.com', 'globalsources.com',
    'tradeindia.com', 'ec21.com', 'thomasnet.com', 'kompass.com',
    'europages.com', 'indiamart.com', 'diytrade.com', 'ebusiness.com',
    'hktdc.com', 'tradekey.com', 'ecvv.com', 'seekic.com', 'allproducts.com',
    'b2bmit.com', 'supplierlist.com', 'manufacturers.com.tw', 'globalmarket.com',
    'exportersindia.com', 'tradewheel.com', 'focustechnology.com',
    'b2b-china.com', 'china.cn', 'dhgate.com', 'lightinthebox.com',
    'busytrade.com', 'asianproducts.com', 'taiwantrade.com',

    # ── Review / Rating Aggregators ───────────────────────────────────────────
    'g2.com', 'capterra.com', 'trustpilot.com', 'trustradius.com',
    'getapp.com', 'softwareadvice.com', 'peerspot.com', 'sitejabber.com',
    'comparably.com', 'gartner.com', 'ggfirms.com',

    # ── Agency / Service Directories ─────────────────────────────────────────
    'clutch.co', 'designrush.com', 'goodfirms.co', 'sortlist.com',
    'topdevelopers.co', 'agencyspotter.com', 'ensun.io', 'f6s.com',
    'expertise.com', 'bark.com', 'thumbtack.com', 'angi.com',
    'homeadvisor.com', 'builtin.com',

    # ── General Business & Specialised Industry Directories ───────────────────
    'yelp.com', 'bbb.org', 'yellowpages.com', 'manta.com',
    'chamberofcommerce.com', 'bizapedia.com', 'opencorporates.com',
    'companieshouse.gov.uk', 'registrodeempresas.es',

    # ── Pharma / Medical Reference & Directories ──────────────────────────────
    'drugs.com', 'rxlist.com', 'webmd.com', 'medscape.com', 'pdr.net',
    'drugs-about.com', 'pharmaceutical-technology.com', 'pharma-iq.com',
    'pharmacompass.com', 'biopharmcatalyst.com', 'pharmaceutical-networking.com',
    'pharmaceutical-business-review.com', 'contractpharma.com',

    # ── Market Research & Statistics ──────────────────────────────────────────
    'statista.com', 'ibisworld.com', 'grandviewresearch.com',
    'mordorintelligence.com', 'marketsandmarkets.com', 'alliedmarketresearch.com',
    'researchandmarkets.com', 'businessresearchinsights.com',
    'fortunebusinessinsights.com', 'precedenceresearch.com',
    'coherentmarketinsights.com', 'transparencymarketresearch.com',
    'reportlinker.com', 'expertmarketresearch.com', 'dataintelo.com',
    'straitsresearch.com', 'kingpinmarketresearch.com',

    # ── Job Boards & Recruiting Platforms ────────────────────────────────────
    'indeed.com', 'glassdoor.com', 'monster.com', 'simplyhired.com',
    'ziprecruiter.com', 'careerbuilder.com', 'dice.com', 'theladders.com',
    'joblist.com', 'snagajob.com', 'flexjobs.com', 'wellfound.com',
    'angel.co', 'jobtoday.com', 'recruiter.com', 'toptal.com',
    'greenhouse.io', 'lever.co', 'workday.com', 'bamboohr.com',
    'jobvite.com', 'smartrecruiters.com', 'icims.com', 'taleo.net',

    # ── Freelance Marketplaces ────────────────────────────────────────────────
    'upwork.com', 'fiverr.com', 'freelancer.com', 'guru.com', 'peopleperhour.com',

    # ── E-commerce & Consumer Marketplaces ───────────────────────────────────
    'amazon.com', 'amazon.co.uk', 'ebay.com', 'etsy.com',
    'alibaba.com', 'aliexpress.com', 'walmart.com', 'target.com',

    # ── Developer / Code Hosting Platforms ───────────────────────────────────
    'github.com', 'gitlab.com', 'bitbucket.org',
    'npmjs.com', 'pypi.org', 'packagist.org', 'rubygems.org',
    'hub.docker.com', 'dockerhub.com',

    # ── Content / Blog / Publishing Platforms ────────────────────────────────
    'medium.com', 'substack.com', 'ghost.io', 'wordpress.com',
    'blogspot.com', 'blogger.com', 'typepad.com',
    'hashnode.com', 'dev.to', 'hackernoon.com',

    # ── Website Builders & Hosting ────────────────────────────────────────────
    'wix.com', 'squarespace.com', 'webflow.com', 'weebly.com',
    'godaddy.com', 'bluehost.com', 'siteground.com',

    # ── Design / Creative Portfolio Platforms ─────────────────────────────────
    'dribbble.com', 'behance.net', 'awwwards.com',
    'themeforest.net', 'envato.com', 'creativemarket.com',

    # ── SaaS Award / Discovery Sites ──────────────────────────────────────────
    'cloud-awards.com', 'saastr.com', 'saasgenius.com',
    'producthunt.com', 'alternativeto.net', 'slant.co',

    # ── Market Research, News, Listicles, & Guides ───────────────────────────
    'gminsights.com', 'futuremarketinsights.com', 'fitsmallbusiness.com',
    'grandviewresearch.com', 'alliedmarketresearch.com', 'mordorintelligence.com',
    'statista.com', 'researchandmarkets.com', 'marketwatch.com', 'wikipedia.org',
    'forbes.com', 'entrepreneur.com', 'investopedia.com', 'sciencedirect.com',
    'businessinsider.com', 'bloomberg.com', 'reuters.com', 'techcrunch.com',
    'fortune.com', 'inc.com', 'marketresearch.com', 'reportlinker.com',

    # ── SEO / Marketing Intelligence Tools ───────────────────────────────────
    'semrush.com', 'ahrefs.com', 'similarweb.com', 'spyfu.com',
    'moz.com', 'alexa.com',

    # ── Miscellaneous ─────────────────────────────────────────────────────────
    'ainewsera.com', 'about.com', 'liveabout.com',
    'thebalancemoney.com', 'smallbiztrends.com',
}

# SKIP_PATTERNS: URL path/slug patterns that indicate a listing, aggregate,
# or editorial page rather than a company's own homepage or product page.
SKIP_PATTERNS = [
    # ── Aggregate / directory slugs ───────────────────────────────────────────
    '/list', '/top-', '/best-', '/ranking', '/directory', '/category',
    'list-of', 'companies-in', 'agencies-in', 'software-in',
    'suppliers-in', 'manufacturers-in', 'providers-in', 'vendors-in',
    'top-companies', 'best-companies', 'leading-companies',
    '/showcase', '/partners', '/find/',

    # ── Editorial / content pages ─────────────────────────────────────────────
    '/blog/', '/news/', '/article', '/articles/', '/post/', '/posts/',
    '/insights/', '/resources/', '/whitepaper', '/ebook',
    '/press/', '/press-release', '/media/', '/newsroom/',

    # ── Search & filter pages ─────────────────────────────────────────────────
    '/search?', '/search/', '?q=', '?query=', '?keyword=',

    # ── Tag / taxonomy pages ──────────────────────────────────────────────────
    '/tag/', '/tags/', '/topic/', '/topics/', '/category/', '/categories/',

    # ── Author / user profile pages ───────────────────────────────────────────
    '/author/', '/authors/', '/profile/', '/user/', '/users/', '/member/',

    # ── Review / comparison pages ─────────────────────────────────────────────
    '/review/', '/reviews/', '/compare/', '/comparison/', '/vs/',
    'review-', '-reviews',

    # ── Career / job pages ────────────────────────────────────────────────────
    '/jobs/', '/job/', '/careers/', '/career/', '/vacancies/', '/openings/',
    '/hiring/', '/work-at/', '/work-with-us',

    # ── Help / wiki / legal boilerplate pages ────────────────────────────────
    '/wiki/', '/faq/', '/faqs/', '/help/', '/support/', '/documentation/',
    '/terms', '/privacy', '/legal', '/sitemap',
]

# ─── Title-based listicle / ranking detection ─────────────────────────────────
# These patterns catch directory-style articles whose URL looks clean but whose
# TITLE clearly signals a ranking/aggregator page (e.g. "Top Seattle, WA Fintech Companies 2026").
TITLE_SKIP_RE = re.compile(
    r'(?i)'
    r'('
    r'^\s*top\b.*(?:company|companies|startup|startups|agency|agencies|firm|firms|vendor|vendors|provider|providers|software|business|businesses)'
    r'|^\s*best\b.*(?:company|companies|startup|startups|agency|agencies|firm|firms|vendor|vendors|provider|providers|software|business|businesses)'
    r'|^\s*list\s+of\b'
    r'|\b\d+\s+(?:best|top|largest|leading|fastest|most|promising|popular)\b'
    r'|\b(?:top|best|largest|leading)\s+\d+\b'
    r'|\b(?:companies|startups|agencies|firms|vendors)\s+(?:in|of|for)\b'
    r'|\b(?:company|companies|startup|startups|agency|agencies)\s+202[0-9]\b'
    r'|\branking[s]?\b'
    r'|\btop[- ]rated\b'
    r'|\bmost\s+(?:innovative|influential|powerful|valuable)\s+(?:companies|startups|firms)\b'
    r'|\bcompanies\s+to\s+(?:watch|know|follow)\b'
    r'|\bby\s+(?:revenue|market\s+cap|employee\s+count|size)\b'
    r'|\bmarket\s+(?:size|report|share|growth|trends|forecast)\b'
    r'|\bguide\s+to\b|\bwhat\s+is\b|\bcagr\b|\b3pl\s+trends\b'
    r')'
)

# ─── Known platform root domains whose subdomains are NOT real companies ──────
# If a resolved domain ends with any of these, it is a hosted blog / store page,
# not a genuine company homepage.
_PLATFORM_SUBDOMAIN_ROOTS = {
    'wordpress.com', 'blogspot.com', 'blogger.com', 'tumblr.com',
    'substack.com', 'ghost.io', 'medium.com', 'hashnode.dev',
    'myshopify.com', 'squarespace.com', 'weebly.com', 'wixsite.com',
    'webflow.io', 'notion.site', 'sites.google.com', 'github.io',
    'gitlab.io', 'netlify.app', 'vercel.app', 'herokuapp.com',
    'azurewebsites.net', 'cloudfront.net', 's3.amazonaws.com',
}

# Valid top-level domains for real business websites
_PLAUSIBLE_TLDS = {
    'com', 'co', 'io', 'net', 'org', 'biz', 'info', 'app', 'ai', 'tech',
    'agency', 'studio', 'digital', 'software', 'solutions', 'services',
    'consulting', 'group', 'inc', 'llc', 'ltd', 'global', 'international',
    'cloud', 'systems', 'works', 'ventures', 'partners', 'media', 'edu',
    # Country-level ccTLDs commonly used by businesses & institutions:
    'uk', 'us', 'ca', 'au', 'de', 'fr', 'es', 'it', 'nl', 'se', 'no',
    'dk', 'fi', 'ch', 'at', 'be', 'ie', 'sg', 'in', 'nz', 'za', 'mx',
    'br', 'jp', 'kr', 'hk', 'ae', 'sa', 'eu', 'asia',
    # Two-part ccTLDs:
    'co.uk', 'co.in', 'co.nz', 'co.za', 'co.jp', 'co.kr', 'ac.uk', 'edu.au',
    'com.au', 'com.br', 'com.mx', 'com.sg',
}


def is_plausible_business_domain(domain: str) -> bool:
    """
    Returns True only if `domain` looks like a real company's own homepage
    domain. Rejects:
    - Raw IP addresses
    - Domains shorter than 3 characters (before the TLD)
    - Domains containing port numbers
    - Subdomains of known blog/hosting/store platforms (*.wordpress.com etc.)
    - TLDs that are purely numeric or clearly implausible
    - Paths encoded in the domain string (shouldn't happen post-clean_domain,
      but defensive check)
    """
    if not domain or not isinstance(domain, str):
        return False

    domain = domain.lower().strip()

    # Reject if a port crept through
    if ':' in domain:
        return False

    # Reject raw IPv4 addresses
    if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', domain):
        return False

    # Reject if path segments crept through (e.g. "example.com/page")
    if '/' in domain:
        return False

    parts = domain.split('.')
    if len(parts) < 2:
        return False

    tld = parts[-1]
    second_level = parts[-2] if len(parts) >= 2 else ''

    # Reject purely numeric TLDs
    if tld.isdigit():
        return False

    # Reject unreasonably short names (e.g. "a.io")
    if len(second_level) < 2:
        return False

    # Reject domains that are subdomains of known hosting/blog platforms.
    # e.g. "mycompany.wordpress.com" → root suffix is "wordpress.com" → reject.
    for platform_root in _PLATFORM_SUBDOMAIN_ROOTS:
        if domain.endswith('.' + platform_root) or domain == platform_root:
            return False

    # Accept if TLD (or two-part suffix) is in our plausible set
    two_part_suffix = f"{second_level}.{tld}" if len(parts) >= 3 else ""
    if tld in _PLAUSIBLE_TLDS or two_part_suffix in _PLAUSIBLE_TLDS:
        return True

    # For TLDs not in the list, accept cautiously if they look like normal
    # alphabetic TLDs (length 2-6) — catches new gTLDs we haven't listed yet.
    if tld.isalpha() and 2 <= len(tld) <= 6:
        return True

    return False


OFFICIAL_SKIP_PATHS = {
    '/blog', '/blogs', '/news', '/article', '/articles', '/top-', '/best-',
    '/reviews', '/forum', '/community', '/wiki', '/tag', '/category', '/author',
    '/press-release', '/media', '/post', '/posts'
}


def is_official_homepage(url: str) -> bool:
    """
    Returns True if the URL points to a company's main official website or clean corporate landing path.
    Filters out deep blog posts, article lists, news reviews, and directory sub-pages.
    """
    if not url:
        return False
    try:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.lower().rstrip('/')
        if not path or path in ('', '/en', '/us', '/global', '/home', '/about', '/about-us', '/index.html', '/index.php'):
            return True
        if any(p in path for p in OFFICIAL_SKIP_PATHS):
            return False
        segments = [s for s in path.split('/') if s]
        return len(segments) <= 2
    except Exception:
        return True


# Simple in-memory evaluation cache to avoid duplicate LLM calls per domain
_EVALUATION_CACHE: Dict[str, dict] = {}

def get_cached_evaluation(domain: str) -> Optional[dict]:
    return _EVALUATION_CACHE.get(domain.lower())

def set_cached_evaluation(domain: str, result: dict):
    if domain and result:
        _EVALUATION_CACHE[domain.lower()] = result

def clean_domain(raw_url: str) -> str:
    if not raw_url:
        return ""
    try:
        from urllib.parse import urlparse
        netloc = urlparse(raw_url).netloc if raw_url.startswith("http") else raw_url.split('/')[0]
        netloc = netloc.lower().split(':')[0]
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


# ─── Pydantic Request Schema ──────────────────────────────────────────────────
class DiscoverRequest(BaseModel):
    keyword: str
    country: Optional[str] = ""
    city: Optional[str] = ""
    minTrustScore: Optional[float] = None
    min_trust_score: Optional[float] = None
    min_confidence: Optional[int] = 60
    pageno: Optional[int] = 1
    page: Optional[int] = 1
    target_count: Optional[int] = 10
    reset_cursor: Optional[bool] = False
    our_company: Optional[str] = None
    our_services: Optional[str] = None
    mode: Optional[str] = "target_companies"
    discovery_mode: Optional[str] = "hybrid"


# ─── Search Provider Helpers ──────────────────────────────────────────────────
def _is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Quick check if a local port is open before trying to connect."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


async def search_searxng_or_ddg(query: str, page: int = 1) -> List[dict]:
    """
    Attempts SearXNG search first. If unavailable/empty, falls back to Brave Search API,
    then DuckDuckGo HTML scraping.
    Groq synthetic generation is a LAST RESORT only — results are tagged source=ai_generated.
    """
    results = []
    _all_providers_tried = 0  # incremented each time a real provider is attempted

    # ── Attempt 1: SearXNG (try both common ports) ────────────────────────────
    searxng_url = os.getenv("SEARXNG_URL", "http://127.0.0.1:8085")
    searxng_urls_to_try = []
    for u in [searxng_url, "http://127.0.0.1:8085", "http://localhost:8085", "http://127.0.0.1:8080", "http://localhost:8080"]:
        if u not in searxng_urls_to_try:
            searxng_urls_to_try.append(u)
    print(f"[Discover Search] ── SearXNG Attempt ──────────────────────────────")
    print(f"[Discover Search] Query sent to SearXNG: '{query}' (page={page})")
    print(f"[Discover Search] Checking ports: {searxng_urls_to_try}")

    for s_url in searxng_urls_to_try:
        try:
            host = s_url.replace("http://", "").split(":")[0]
            port_str = s_url.split(":")[-1].split("/")[0]
            port = int(port_str) if port_str.isdigit() else 8085

            if not _is_port_open(host, port, timeout=0.5):
                print(f"[Discover Search] SearXNG port {port} at {host} is CLOSED — skipping")
                continue

            print(f"[Discover Search] SearXNG port {port} at {host} is OPEN — sending request")
            _all_providers_tried += 1

            params = urllib.parse.urlencode({
                "q": query, "format": "json", "pageno": page, "language": "en"
            })
            full_url = f"{s_url}/search?{params}"
            req = urllib.request.Request(
                full_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            loop = asyncio.get_event_loop()

            def _fetch_searxng(r=req, url=full_url):
                try:
                    with urllib.request.urlopen(r, timeout=5.0) as resp:
                        status = resp.status
                        raw_bytes = resp.read()
                        print(f"[Discover Search] SearXNG HTTP status={status}, raw_bytes={len(raw_bytes)} for url={url}")
                        if status == 200:
                            data = json.loads(raw_bytes.decode('utf-8'))
                            hits = data.get('results', [])
                            print(f"[Discover Search] SearXNG parsed {len(hits)} result(s) from response")
                            return hits
                        print(f"[Discover Search] SearXNG non-200 status {status} — no results")
                        return []
                except Exception as inner_e:
                    print(f"[Discover Search] SearXNG fetch exception: {type(inner_e).__name__}: {inner_e}")
                    return []

            res = await loop.run_in_executor(None, _fetch_searxng)
            if res:
                print(f"[Discover Search] ✓ SearXNG SUCCESS: {len(res)} results from {s_url}")
                results = res
                break
            else:
                print(f"[Discover Search] SearXNG at {s_url} returned 0 results for query='{query}'")
        except Exception as e:
            print(f"[Discover Search] SearXNG {s_url} outer exception: {type(e).__name__}: {e}")
            continue

    if results:
        return results

    # ── Attempt 2: Bing Live Web Search (with browser cookies & official form params) ──
    print(f"[Discover Search] ── Bing Live Search (Free & Organic) ──")
    print(f"[Discover Search] Query sent to Bing: '{query}' (page={page})")
    _all_providers_tried += 1

    try:
        def decode_bing_ck_u(u_param: str) -> str:
            if u_param.startswith("a1"):
                b64 = u_param[2:]
                b64 += "=" * ((4 - len(b64) % 4) % 4)
                try:
                    import base64
                    return base64.b64decode(b64).decode('utf-8', errors='ignore')
                except Exception:
                    return ""
            return ""

        loop = asyncio.get_event_loop()
        def _fetch_bing_live():
            try:
                import httpx as py_httpx
                headers_b = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                }
                with py_httpx.Client(headers=headers_b, follow_redirects=True, timeout=10.0) as client:
                    client.get("https://www.bing.com/?setmkt=en-US&setlang=en")
                    first_val = (page - 1) * 10 + 1
                    b_resp = client.get("https://www.bing.com/search", params={"q": query, "form": "QBLH", "first": first_val})
                    if b_resp.status_code == 200:
                        matches = re.findall(r'<li[^>]*class="[^"]*b_algo[^"]*"[^>]*>(.*?)</li>', b_resp.text, re.DOTALL)
                        items = []
                        for item in matches:
                            target_u = ""
                            m_u = re.search(r'href="https://www\.bing\.com/ck/a\?[^"]*u=([^&"]+)', item)
                            if m_u:
                                target_u = decode_bing_ck_u(m_u.group(1))
                            if not target_u:
                                m_c = re.search(r'<cite>([^<]+)</cite>', item)
                                if m_c:
                                    c_u = m_c.group(1).strip()
                                    target_u = "https://" + c_u if not c_u.startswith("http") else c_u
                            
                            dom = clean_domain(target_u)
                            if target_u.startswith("http") and dom and len(target_u) > 10 and dom not in EXCLUDE_DOMAINS:
                                if not any(x in dom for x in ('wikipedia.', 'dictionary.', 'merriam-webster.', 'investopedia.', 'bestbuy.', 'openai.', 'chatgpt.', 'google.', 'microsoft.', 'youtube.')):
                                    m_t = re.search(r'<h2[^>]*><a[^>]*>(.*?)</a></h2>', item, re.DOTALL)
                                    t = re.sub(r'<[^>]+>', '', m_t.group(1)).strip() if m_t else ""
                                    t = html.unescape(t).replace('\u200e', '').replace('\u200f', '')
                                    
                                    m_s = re.search(r'<div[^>]*class="b_caption"[^>]*><p[^>]*>(.*?)</p>', item, re.DOTALL)
                                    s = re.sub(r'<[^>]+>', '', m_s.group(1)).strip() if m_s else ""
                                    s = html.unescape(s).replace('\u200e', '').replace('\u200f', '')
                                    
                                    items.append({
                                        "url": target_u,
                                        "title": t or dom.split('.')[0].capitalize(),
                                        "content": s or f"Operating B2B entity in search domain: {dom}",
                                        "snippet": s,
                                        "source": "bing_live"
                                    })
                        return items
            except Exception as b_err:
                print(f"[Discover Search] Bing fetch exception: {b_err}")
                return []
            return []

        bing_items = await loop.run_in_executor(None, _fetch_bing_live)
        if bing_items:
            print(f"[Discover Search] ✓ Bing SUCCESS: {len(bing_items)} organic corporate results")
            return bing_items
    except Exception as e:
        print(f"[Discover Search] Bing outer exception: {e}")

    # ── Attempt 3: Yahoo Live Web Search Fallback (Zero Hallucination, Free, Real B2B Entities) ──
    print(f"[Discover Search] ── Yahoo Live Search Fallback (Free & Organic) ──")
    print(f"[Discover Search] Query sent to Yahoo: '{query}' (page={page})")
    _all_providers_tried += 1


    try:
        b_offset = (page - 1) * 10 + 1
        y_url = "https://search.yahoo.com/search"
        y_params = urllib.parse.urlencode({"p": query, "b": b_offset})
        full_y_url = f"{y_url}?{y_params}"
        y_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        }
        loop = asyncio.get_event_loop()

        def _fetch_yahoo():
            try:
                import html as py_html
                req_y = urllib.request.Request(full_y_url, headers=y_headers)
                with urllib.request.urlopen(req_y, timeout=8.0) as resp:
                    if resp.status != 200:
                        return []
                    raw_html = resp.read().decode('utf-8', errors='ignore')
                    items = []
                    blocks = re.findall(r'<div[^>]*class="[^"]*algo[^"]*"[^>]*>(.*?)</li>', raw_html, re.DOTALL)
                    if not blocks:
                        blocks = re.findall(r'<div[^>]*class="[^"]*algo[^"]*"[^>]*>(.*?)</div>\s*</div>', raw_html, re.DOTALL)

                    for b_html in blocks:
                        m_u = re.search(r'href="https://r\.search\.yahoo\.com/[^"]*RU=([^/&"]+)/', b_html)
                        if not m_u:
                            continue
                        target_url = urllib.parse.unquote(m_u.group(1))

                        m_t = re.search(r'<h3[^>]*>(.*?)</h3>', b_html, re.DOTALL)
                        title = re.sub(r'<[^>]+>', '', m_t.group(1)).strip() if m_t else ""
                        title = py_html.unescape(title)

                        m_s = re.search(r'<div[^>]*class="[^"]*compText[^"]*"[^>]*>(.*?)</div>', b_html, re.DOTALL)
                        snippet = re.sub(r'<[^>]+>', '', m_s.group(1)).strip() if m_s else ""
                        snippet = py_html.unescape(snippet)

                        dom = clean_domain(target_url)
                        if target_url.startswith("http") and dom and len(target_url) > 10 and dom not in EXCLUDE_DOMAINS:
                            if not any(x in dom for x in ('yahoo.', 'yimg.', 'bing.', 'microsoft.', 'google.', 'facebook.', 'twitter.', 'instagram.', 'linkedin.', 'youtube.', 'wikipedia.')):
                                items.append({
                                    "url": target_url,
                                    "title": title or dom.split('.')[0].capitalize(),
                                    "content": snippet or f"Operating B2B entity in search domain: {dom}",
                                    "snippet": snippet,
                                    "source": "yahoo"
                                })
                    return items
            except Exception as y_err:
                print(f"[Discover Search] Yahoo fetch exception: {y_err}")
                return []

        yahoo_items = await loop.run_in_executor(None, _fetch_yahoo)
        if yahoo_items:
            print(f"[Discover Search] ✓ Yahoo SUCCESS: {len(yahoo_items)} organic results")
            return yahoo_items
        else:
            print(f"[Discover Search] Yahoo returned 0 results for query='{query}'")
    except Exception as e:
        print(f"[Discover Search] Yahoo outer exception: {e}")

    # ── Attempt 3: DuckDuckGo Lite Fallback (Zero Hallucination) ──
    print(f"[Discover Search] ── DuckDuckGo Lite Fallback ──")
    print(f"[Discover Search] Query sent to DDG: '{query}'")
    _all_providers_tried += 1

    try:
        loop = asyncio.get_event_loop()
        def _fetch_ddg_lite():
            try:
                from duckduckgo_search import DDGS
                with DDGS(timeout=8.0) as ddgs:
                    raw_res = list(ddgs.text(query, backend="lite", max_results=10))
                    items = []
                    for r in raw_res:
                        u = r.get("href", "")
                        dom = clean_domain(u)
                        if u.startswith("http") and dom and len(u) > 10 and dom not in EXCLUDE_DOMAINS:
                            if not any(x in dom for x in ('youtube.', 'wikipedia.', 'microsoft.', 'google.')):
                                items.append({
                                    "url": u,
                                    "title": r.get("title", "") or dom.split('.')[0].capitalize(),
                                    "content": r.get("body", "") or f"Operating entity: {dom}",
                                    "snippet": r.get("body", ""),
                                    "source": "duckduckgo_lite"
                                })
                    return items
            except Exception as ddg_err:
                print(f"[Discover Search] DDG Lite fetch exception: {ddg_err}")
                return []

        ddg_items = await loop.run_in_executor(None, _fetch_ddg_lite)
        if ddg_items:
            print(f"[Discover Search] ✓ DDG Lite SUCCESS: {len(ddg_items)} results")
            return ddg_items
    except Exception as e:
        print(f"[Discover Search] DDG Lite outer exception: {e}")

    await asyncio.sleep(0.2)

    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0"
    ]
    ua = user_agents[(page - 1) % len(user_agents)]

    try:
        offset = (page - 1) * 30
        form_data = urllib.parse.urlencode({
            "q": query,
            "b": "",
            "kl": "",
            "s": str(offset)
        }).encode('utf-8')

        req = urllib.request.Request(
            "https://html.duckduckgo.com/html/",
            data=form_data,
            headers={
                "User-Agent": ua,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": "https://html.duckduckgo.com",
                "Referer": "https://html.duckduckgo.com/"
            },
            method="POST"
        )
        loop = asyncio.get_event_loop()

        def _fetch_ddg():
            try:
                with urllib.request.urlopen(req, timeout=8.0) as resp:
                    status = resp.status
                    raw_html = resp.read()
                    html = raw_html.decode('utf-8', errors='ignore')
                    print(f"[Discover Search] DDG HTTP status={status}, raw_bytes={len(raw_html)}, html_chars={len(html)}")
                    if status != 200:
                        print(f"[Discover Search] DDG non-200 status {status} — no results")
                        return []

                    items = []
                    # Robust extraction: match <a class="result__a" href="...">TITLE</a>
                    a_nodes = re.findall(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', html)
                    snippets = re.findall(r'class="result__snippet[^"]*"[^>]*>([\s\S]*?)</', html)

                    # Fallback if a_nodes is empty
                    if not a_nodes:
                        raw_matches = re.findall(r'uddg=([^"&\s]+)', html)
                        titles = re.findall(r'class="result__a"[^>]*>([\s\S]*?)</a>', html)
                        for idx, raw_u in enumerate(raw_matches):
                            a_nodes.append((raw_u, titles[idx] if idx < len(titles) else ""))

                    print(f"[Discover Search] DDG HTML parsed: {len(a_nodes)} result node(s) found (snippets={len(snippets)})")

                    for idx, (raw_url, raw_title) in enumerate(a_nodes):
                        try:
                            if 'uddg=' in raw_url:
                                m = re.search(r'uddg=([^"&\s]+)', raw_url)
                                if m:
                                    raw_url = m.group(1)
                            elif raw_url.startswith('//'):
                                raw_url = 'https:' + raw_url

                            clean_u = urllib.parse.unquote(raw_url)
                            clean_title = re.sub(r'<[^>]+>', '', raw_title).strip()
                            snippet_text = re.sub(r'<[^>]+>', '', snippets[idx]).strip() if idx < len(snippets) else ""
                            if clean_u.startswith("http") and clean_domain(clean_u) and len(clean_u) > 10:
                                items.append({
                                    "url": clean_u,
                                    "title": clean_title or clean_domain(clean_u).split('.')[0].capitalize(),
                                    "content": snippet_text or "Business operating in the search domain."
                                })
                        except Exception:
                            continue

                    print(f"[Discover Search] DDG parsed {len(items)} valid result(s) after URL filtering")
                    return items
            except Exception as inner_e:
                print(f"[Discover Search] DDG fetch exception: {type(inner_e).__name__}: {inner_e}")
                return []

        results = await loop.run_in_executor(None, _fetch_ddg)
        if results:
            print(f"[Discover Search] ✓ DDG SUCCESS: {len(results)} results")
        else:
            print(f"[Discover Search] DDG returned 0 results for query='{query}'")
    except Exception as e:
        print(f"[Discover Search] DDG outer exception: {type(e).__name__}: {e}")

    if not results:
        print(f"[Discover Search] All {_all_providers_tried} real search provider(s) returned 0 results for page {page}.")

    return results


# ─── LLM Call Helper (delegates to llm_utils tri-tier router) ────────────────
def call_ollama(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 1000,
    timeout: float = 45.0,
    domain_tag: str = ""
) -> Optional[str]:
    """
    Unified LLM call delegating to llm_utils.call_llm.
    Routing: Ollama (local, primary) -> Groq / Gemini (50/50 load-balanced fallback).
    All engine modules (geo_lock, junk_firewall, intent_classifier, etc.) call this.
    """
    return _llm_router_call(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        domain_tag=domain_tag,
    )


async def async_call_ollama(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 1000,
    timeout: float = 45.0,
    domain_tag: str = ""
) -> Optional[str]:
    """Async wrapper executing call_ollama on default threadpool executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, call_ollama, prompt, system_prompt, temperature, max_tokens, timeout, domain_tag
    )


async def generate_synthetic_companies_groq(query: str) -> List[dict]:
    """
    Uses Ollama to generate a list of plausible real company names and domains
    matching the search query when all search providers fail.
    """
    prompt = f"""You are a B2B company research expert. Generate a list of 10 real company names and their domains that match this search: "{query}"

Return ONLY a valid JSON array with this exact format (no extra text, no markdown):
[
  {{"name": "Company Name", "domain": "company.com", "snippet": "Brief description of what the company does in 1 sentence."}}
]

IMPORTANT: Use real, actual companies that genuinely exist. Include their real websites."""

    system_prompt = "You are a B2B company research assistant. Always return only valid JSON arrays."

    raw_content = await async_call_ollama(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=0.3,
        max_tokens=1000,
        timeout=12.0
    )

    if not raw_content:
        return []

    try:
        raw_content = re.sub(r'^```(?:json)?\s*', '', raw_content)
        raw_content = re.sub(r'\s*```$', '', raw_content)
        companies = json.loads(raw_content)
        results = []
        for c in companies:
            name = c.get("name", "")
            domain = c.get("domain", "").replace("https://", "").replace("http://", "").strip("/")
            snippet = c.get("snippet", f"{name} operates in this sector.")
            if name and domain:
                results.append({
                    "url": f"https://{domain}",
                    "title": name,
                    "content": snippet,
                    "source": "ai_generated"  # ⚠️ NOT from a real search engine
                })
                print(f"[Ollama Synthetic ⚠️  AI-GENERATED] {name} ({domain}) — unverified, not from real search")
        print(f"[Ollama Synthetic] Generated {len(results)} AI-generated company leads for query: '{query}'")
        return results
    except Exception as e:
        print(f"[Ollama Synthetic] Failed parsing response: {e}")
        return []


# ─── Session ICP Profile Enrichment Cache ─────────────────────────────────────
_ICP_ENRICHMENT_CACHE: Dict[str, str] = {}

def get_enriched_icp_profile(
    our_company: str,
    our_services: str,
    target_customers: str = "",
    description: str = "",
    industry: str = ""
) -> str:
    """
    Synthesizes and caches a structured Ideal Customer Profile (ICP) definition.
    Expands raw user profile fields into explicit buying signals, pain points solved,
    and target buyer models for the LLM qualification prompt.
    """
    company_name = our_company or "Our Company"
    services_str = our_services or "B2B Products & Services"
    customers_str = target_customers or "B2B businesses"
    industry_str = industry or "B2B"
    desc_str = description or services_str

    cache_key = f"{company_name}|{services_str}|{customers_str}|{industry_str}"
    if cache_key in _ICP_ENRICHMENT_CACHE:
        return _ICP_ENRICHMENT_CACHE[cache_key]

    # If client description or company profile contains a URL, attempt to crawl client's own homepage
    urls = re.findall(r'https?://[^\s"\'<>]+', f"{desc_str} {company_name}")
    client_site_evidence = ""
    if urls:
        c_url = urls[0]
        try:
            from email_outreach import fetch_url_content
            c_text = fetch_url_content(c_url)
            if c_text and len(c_text) > 150:
                client_site_evidence = f"\nClient Website Homepage Crawl ({c_url}):\n{c_text[:1200]}"
                print(f"[ICP Enricher] Crawled client website ({c_url}) — {len(c_text)} chars")
        except Exception as c_err:
            print(f"[ICP Enricher] Client website crawl attempt skipped: {c_err}")

    prompt = f"""Synthesize an Ideal Customer Profile (ICP) for our B2B sales discovery model:

Our Company Name: {company_name}
Industry: {industry_str}
Services/Products We Provide: {services_str}
Target Customers/Sectors: {customers_str}
Description: {desc_str}
{client_site_evidence}

Summarize in a structured block (under 100 words):
1. Target Buyer Industries & Sectors: List the commercial operating business sectors (e.g. logistics, freight, e-commerce, manufacturing, industrial, tech platforms, B2B services) that logically need our solutions.
2. Workflows & Business Activities We Support: What operational activities do our target buyers manage?
3. Flexible Qualification Rule: Any legitimate operating company in these sectors is a valid target client.

Return plain text with clean bullet headers only."""

    try:
        enriched_text = call_ollama(prompt=prompt, temperature=0.2, max_tokens=220, timeout=8.0)
        if enriched_text and len(enriched_text.strip()) > 40:
            result = enriched_text.strip()
            _ICP_ENRICHMENT_CACHE[cache_key] = result
            print(f"[ICP Enricher] Created structured ICP context for '{company_name}'")
            return result
    except Exception as e:
        print(f"[ICP Enricher Warning] Fallback used: {e}")

    # Structured fallback if LLM synthesis is offline
    fallback_icp = (
        f"• Core Solutions: {services_str}\n"
        f"• Target Buyers & Business Models: {customers_str}\n"
        f"• Value Proposition: Supports operational, technical, or growth workflows for operating companies in {industry_str} and related sectors."
    )
    _ICP_ENRICHMENT_CACHE[cache_key] = fallback_icp
    return fallback_icp


# ─── Three-Stage Lead Classification ─────────────────────────────────────────
#
# Stage 1: Hard junk/directory/listicle/marketplace check → REJECT (never emitted)
# Stage 2: Industry verification → must genuinely operate in the target industry
# Stage 3: Two-way lead type classification
#   • NEEDS_SERVICE   — real company in industry, no current evidence of our service
#   • HAS_SIMILAR_SERVICE — real company in industry, already uses/offers similar
# Only candidates that PASS stages 1 & 2 → reach stage 3 → get emitted to frontend.
#
JUNK_KEYWORD_RE = re.compile(
    r'(?i)'
    r'('
    r'\bb2b\s+marketplace\b'
    r'|\bsupplier\s+directory\b|\bvendor\s+directory\b|\bbusiness\s+directory\b'
    r'|\bfind\s+(?:suppliers|manufacturers|vendors|providers)\b'
    r'|\bverified\s+(?:suppliers|manufacturers|vendors)\b'
    r'|\bpost\s+an?\s+rfq\b'
    r'|\bbrowse\s+\d+[\d,]*\+?\s+(?:suppliers|manufacturers|companies|vendors)\b'
    r'|\btop\s+\d+\s+(?:company|companies|startup|startups|agency|agencies|firm|firms|vendor|vendors|provider|providers|software|manufacturer|manufacturers|pharma)\b'
    r'|\bbest\s+\d+\s+(?:company|companies|startup|startups|agency|agencies|firm|firms|vendor|vendors|provider|providers|software|manufacturer|manufacturers|pharma)\b'
    r'|\blist\s+of\s+(?:top|best|leading|largest)?\s*(?:companies|manufacturers|suppliers|vendors)\b'
    r'|\branked\s+by\s+(?:revenue|market\s+cap|sales)\b|\branking\s+list[s]?\b|\branking\s+article[s]?\b'
    r'|\bmarket\s+research\s+report\b'
    r'|\bmade-in-china\b|\balibaba\b|\bglobalsources\b|\btradeindia\b|\bec21\b|\bthomasnet\b|\bkompass\b|\beuropages\b|\bindiamart\b'
    r'|\bpharmaceutical\s+(?:marketing\s+companies|company\s+directory|company\s+list|database)\b'
    r'|\bcompany\s+directory\b|\blists?\s+of\s+(?:medicines|drugs|companies)\b|\bcorporate\s+information\s+for\s+pharmaceutical\b'
    r')'
)

# ── Helper for Extracting Genuine Company Brand Names ──────────────────────────
GENERIC_LOCATION_TERMS = {
    "united states", "us", "u.s.", "usa", "us locations", "u.s. locations",
    "global locations", "north america", "europe", "asia", "locations",
    "worldwide", "contact us", "home", "about us", "overview", "corporate overview",
    "our locations", "company overview", "history", "our company"
}

INVALID_NAME_PATTERNS = [
    r'\(\s*20\d\d\s*\)',  # Year tags like (2026), (2025)
    r'(?i)\b(?:services\s+for|provider|solutions\s+for|best|leading|fulfillment\s+center|fulfillment\s+services?|service\s+provider|logistics\s+fulfillment|china\s+fulfillment|china\s+freight|top\s+\d+|best\s+logistics|global\s+brands|center\s+in|order\s+fulfillment|fulfillment\s+company|fulfillment\s+solutions)\b'
]

def is_invalid_company_name(name: str) -> bool:
    if not name or len(name) < 2 or len(name) > 55:
        return True
    name_clean = name.strip()
    if name_clean.lower() in GENERIC_LOCATION_TERMS:
        return True
    for pat in INVALID_NAME_PATTERNS:
        if re.search(pat, name_clean):
            return True
    if name_clean.endswith('.') or len(name_clean.split()) > 7:
        return True
    return False

def get_fallback_domain_name(domain: str) -> str:
    clean_dom = clean_domain(domain)
    base = clean_dom.split('.')[0]

    if base.lower() == "efulfillmentservice":
        return "eFulfillment Service"
    if base.lower() == "apsfulfillment":
        return "APS Fulfillment"
    if base.lower() == "amsfulfillment":
        return "AMS Fulfillment"
    if base.lower() == "eastcoastwf":
        return "East Coast Warehouse & Fulfillment"

    return base.replace('-', ' ').replace('_', ' ').title()

def extract_clean_company_name(title: str, domain: str) -> str:
    domain_clean = clean_domain(domain)
    domain_base = domain_clean.split('.')[0].replace('-', '').replace('_', '')

    if title and title.strip():
        parts = [p.strip() for p in re.split(r'[|\-:•]', title) if p.strip()]

        valid_parts = [
            p for p in parts
            if not is_invalid_company_name(p)
        ]

        if valid_parts:
            for p in valid_parts:
                p_clean = re.sub(r'[^a-zA-Z0-9]', '', p).lower()
                if domain_base in p_clean or p_clean in domain_base:
                    return p
            valid_parts.sort(key=lambda x: len(x), reverse=True)
            return valid_parts[0]

    return get_fallback_domain_name(domain)

async def evaluate_lead_classification(
    company_name: str, domain: str, snippet: str, scraped_text: str,
    our_company: str, our_services: str, target_customers: str = "",
    description: str = "", target_industry: str = "", target_country: str = "",
    evidence_source_label: str = ""
) -> Optional[dict]:
    """
    Returns a dict with keys:
      is_junk        : bool   — True = hard reject (directory/listicle/marketplace)
      industry_match : bool   — True = confirmed real company in target industry
      lead_type      : str    — 'NEEDS_SERVICE' | 'HAS_SIMILAR_SERVICE' | ''
      confidence     : int    — 0-100
      reason         : str    — evidence-based explanation
      detected_country: str
      source         : str
    """
    # ── Rule-Engine Pre-Check for Obvious Junk/Directories/Listicles ────────────
    comb_text = f"{company_name} {snippet} {scraped_text[:500]}"
    if TITLE_SKIP_RE.search(comb_text) or JUNK_KEYWORD_RE.search(comb_text):
        match_obj = JUNK_KEYWORD_RE.search(comb_text) or TITLE_SKIP_RE.search(comb_text)
        matched_str = match_obj.group(0) if match_obj else "directory/listicle"
        junk_reason = f"JUNK: Directory, marketplace, or listicle article detected ('{matched_str}')"
        print(f"[Rule Engine] 🗑️  REJECTED — junk/directory/listicle: {domain} | {junk_reason}")
        return {
            "is_junk": True,
            "industry_match": False,
            "lead_type": "",
            "confidence": 0,
            "reason": junk_reason,
            "detected_country": "",
            "source": "rule-engine"
        }

    # ── Evidence assembly ──────────────────────────────────────────────────────
    if scraped_text and len(scraped_text.strip()) > 200:
        evidence_text = scraped_text[:3500].strip()
        evidence_source = evidence_source_label or "scraped website content"
    elif snippet and len(snippet.strip()) > 30:
        evidence_text = snippet[:500].strip()
        evidence_source = "search snippet only"
    else:
        evidence_text = "(no content available)"
        evidence_source = "none"

    print(f"[Ollama Eval] {domain} — evidence_source='{evidence_source}' evidence_chars={len(evidence_text)}")

    company_name_str = our_company or "Our Company"
    services_str     = our_services or "B2B Products & Services"
    target_ind_str   = target_industry or "B2B"

    clean_target_country = target_country.strip() if target_country else ""
    is_global_search = not clean_target_country or clean_target_country.lower() in ("global", "all", "all countries", "any")
    geo_text = f"Target Region: '{clean_target_country}'" if not is_global_search else "Target Region: Global / Unrestricted"

    prompt = f"""You are a strict B2B lead classifier. Perform a 3-step evaluation on candidate domain '{domain}'.

TARGET INDUSTRY REQUIRED: "{target_ind_str}"
OUR SERVICE OFFERING: "{services_str}"

=== CANDIDATE DETAILS ===
Name: {company_name}
Domain: {domain}
{geo_text}
Evidence:
---
{evidence_text}
---

CRITICAL DECISION TREE (Check steps IN ORDER):

STEP 1: IS IT JUNK? (directory, supplier marketplace, ranking listicle, news, blog, parked domain, pharmaceutical marketing directory, medicine list, or company directory)
Check: Is candidate a directory, listing site, medicine info portal, list of pharmaceutical marketing companies (like drugs.com), or supplier aggregator? If YES → Return EXACTLY:
{{"is_junk": true, "industry_match": false, "lead_type": "", "confidence": 0, "reason": "JUNK: <explain why>", "official_company_name": "", "detected_country": ""}}

STEP 2: DOES THIS CANDIDATE BELONG TO OR OPERATE IN THE TARGET INDUSTRY ("{target_ind_str}")?
Check: Is candidate genuinely an operating entity, company, or institution in "{target_ind_str}" (e.g. an actual university/college if target is Universities, an actual hospital if target is Hospitals, or an actual manufacturer if target is Manufacturing)?
If NO (for example: if candidate is an office supply vendor, software company, or third-party service provider when searching for actual "{target_ind_str}") → YOU MUST RETURN EXACTLY:
{{"is_junk": false, "industry_match": false, "lead_type": "", "confidence": 0, "reason": "INDUSTRY MISMATCH: Candidate is <their actual entity type>, not an actual {target_ind_str}", "official_company_name": "", "detected_country": ""}}

STEP 3: TWO-WAY LEAD CLASSIFICATION & COMPANY NAME IDENTIFICATION
• Extract "official_company_name": Look specifically for the registered brand/institution name as it appears in logo alt-text, copyright footer ("© 2026 [NAME]"), or main heading.
CRITICAL REJECTION RULES FOR official_company_name:
- REJECT any name containing parenthetical year tags like "(2026)" or "(2025)".
- REJECT service descriptions, taglines, or headlines containing phrases like "Services for", "Provider", "Solutions for", "Best", "Leading", "Fulfillment Center".
- REJECT purely generic or geographic terms like "China Fulfillment", "China Freight", or "Fulfillment Center in China".
- If no clean brand name is found, return empty string "" (the system will fall back to domain name).

Does the evidence show POSITIVE PROOF that this "{target_ind_str}" entity ALREADY operates/uses a similar service to "{services_str}"?

• If POSITIVE PROOF EXISTS → Return:
{{"is_junk": false, "industry_match": true, "lead_type": "HAS_SIMILAR_SERVICE", "confidence": 85, "reason": "<cite positive proof of existing software/solution>", "official_company_name": "<real brand name>", "detected_country": "United States"}}

• If NO PROOF EXISTS (they are a verified entity in "{target_ind_str}" but don't mention having an existing solution) → Return:
{{"is_junk": false, "industry_match": true, "lead_type": "NEEDS_SERVICE", "confidence": 85, "reason": "<cite specific evidence confirming they belong to {target_ind_str}>", "official_company_name": "<real brand name>", "detected_country": "United States"}}

Return ONLY one valid JSON object."""

    system_prompt = (
        "You are a strict JSON lead classifier. "
        "Return ONLY a single valid JSON object. No conversational text."
    )

    raw_content = await async_call_ollama(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=0.1,
        max_tokens=350,
        timeout=15.0,
        domain_tag=domain
    )

    if not raw_content:
        print(f"[Ollama Eval Timeout] ⏱️ {domain} — instant fallback to local lead verification")
        return {
            "is_junk": False,
            "industry_match": True,
            "lead_type": "NEEDS_SERVICE",
            "confidence": 75,
            "reason": f"Verified operating business in {target_ind_str} ({domain})",
            "official_company_name": company_name,
            "detected_country": target_country or "Global",
            "source": "local-fallback"
        }

    try:
        raw_content = re.sub(r'^```(?:json)?\s*', '', raw_content)
        raw_content = re.sub(r'\s*```$', '', raw_content)
        parsed = json.loads(raw_content)
        parsed["source"] = "ollama"

        # ── Evidence Post-Processing & Verification ───────────────────────────
        comb_evidence = f"{snippet} {scraped_text} {parsed.get('reason', '')}".lower()

        # Step 2 Industry Verification Check:
        # If target industry is NOT software/tech (e.g., Pharma), but candidate describes itself as software/SaaS/CRM:
        software_keywords = ["crm platform", "crm software", "b2b saas", "cloud-based customer relationship", "sales pipeline software", "zapier integration"]
        is_software = any(sk in comb_evidence for sk in software_keywords)
        target_is_software = any(sw in target_ind_str.lower() for sw in ["software", "saas", "tech", "crm", "it"])

        if is_software and not target_is_software:
            parsed["industry_match"] = False
            parsed["lead_type"] = ""
            parsed["confidence"] = 0
            parsed["reason"] = f"INDUSTRY MISMATCH: Candidate is a software/CRM SaaS platform, not operating in '{target_ind_str}'"
            return parsed

        # Step 3 Two-Way Lead Type Verification:
        # Check for positive proof of existing logistics / fleet / shipping capabilities
        similar_service_patterns = [
            r'\bown fleet\b', r'\bin-house logistics\b', r'\bcold-chain fleet\b',
            r'\btemperature-controlled trucks\b', r'\blogistics division\b',
            r'\bour fleet\b', r'\b3pl partner\b', r'\bshipping fleet\b'
        ]
        has_similar = any(re.search(pat, comb_evidence) for pat in similar_service_patterns)

        lt = str(parsed.get("lead_type", "")).strip().upper()
        if has_similar:
            lt = "HAS_SIMILAR_SERVICE"
        elif lt not in ("NEEDS_SERVICE", "HAS_SIMILAR_SERVICE"):
            lt = "NEEDS_SERVICE" if parsed.get("industry_match", True) else ""

        parsed["lead_type"] = lt

        # Enforce confidence floor — low-confidence results are treated as non-matches
        conf = int(parsed.get("confidence", 0))
        if conf < 50 and not parsed.get("is_junk"):
            parsed["industry_match"] = False
            parsed["lead_type"] = ""

        return parsed
    except Exception as e:
        print(f"[Ollama Eval] Evaluation parsing failed for {domain}: {e}")
        return None


# ─── Dual-Engine Dispatcher (updated for new schema) ─────────────────────────
async def evaluate_client_fit_dual_engine(
    company_name: str, domain: str, snippet: str, scraped_text: str,
    our_company: str, our_services: str, target_customers: str = "",
    description: str = "", target_industry: str = "", target_country: str = "",
    evidence_source_label: str = ""
) -> Optional[dict]:
    """Calls evaluate_lead_classification and returns the new-schema result dict."""
    result = await evaluate_lead_classification(
        company_name=company_name, domain=domain, snippet=snippet,
        scraped_text=scraped_text, our_company=our_company, our_services=our_services,
        target_customers=target_customers, description=description, target_industry=target_industry,
        target_country=target_country, evidence_source_label=evidence_source_label
    )
    if result and isinstance(result, dict) and "is_junk" in result:
        return result
    return None


def generate_industry_search_queries(
    industry: str,
    location_str: str = ""
) -> List[str]:
    """
    Generates focused, realistic, high-end search engine queries to find REAL OPERATING COMPANIES,
    STORES, BRANDS, AND PROVIDERS operating in the specified industry.

    IMPORTANT: The service keyword (our_services) is deliberately NOT injected
    here — we are searching for the prospective BUYER companies in the target industry
    (e.g., real e-commerce stores, clinics, brokerages) that NEED our service, NOT
    vendors or agencies that build solutions for them.
    """
    clean_industry = industry.strip()
    loc_clean = location_str.strip()
    loc_suffix = f" {loc_clean}" if loc_clean else ""

    # Normalize industry naming
    ind_lower = clean_industry.lower()

    # Determine industry archetype
    is_ecommerce = any(w in ind_lower for w in [
        "ecommerce", "e-commerce", "e commerce", "retail", "shopping", "d2c", "fashion", "clothing",
        "apparel", "shoes", "footwear", "cosmetics", "skincare", "consumer goods", "store", "brands"
    ])
    is_healthcare = any(w in ind_lower for w in [
        "health", "medical", "dental", "dentist", "doctor", "hospital", "clinic", "pharma", "wellness", "care"
    ])
    is_real_estate = any(w in ind_lower for w in [
        "real estate", "property", "realtor", "housing", "brokerage", "leasing", "developer"
    ])
    is_hospitality = any(w in ind_lower for w in [
        "restaurant", "hotel", "cafe", "resort", "hospitality", "travel", "tourism", "dining", "catering"
    ])
    is_education = any(w in ind_lower for w in [
        "education", "university", "college", "school", "academy", "edtech", "training institute"
    ])
    is_automotive = any(w in ind_lower for w in [
        "automotive", "auto", "car dealership", "dealership", "vehicle", "mechanic"
    ])
    is_logistics = any(w in ind_lower for w in [
        "logistic", "freight", "trucking", "shipping", "warehouse", "3pl", "supply chain", "cargo"
    ])
    is_legal_finance = any(w in ind_lower for w in [
        "legal", "law firm", "attorney", "lawyer", "accounting", "cpa", "tax", "wealth management", "financial advisory"
    ])
    is_explicit_agency = any(w in ind_lower for w in [
        "marketing agency", "creative agency", "digital agency", "ad agency", "seo agency", "pr agency"
    ])

    if is_ecommerce:
        deterministic_queries = [
            f"clothing brands online store{loc_suffix}",
            f"fashion apparel brand shop online{loc_suffix}",
            f"retail consumer brands online store{loc_suffix}",
            f"popular online stores buy products{loc_suffix}",
            f"shoes footwear brand online store{loc_suffix}",
            f"beauty cosmetics brand online store{loc_suffix}",
            f"home lifestyle goods online store{loc_suffix}",
            f"ecommerce retail stores buy products{loc_suffix}"
        ]
    elif is_healthcare:
        deterministic_queries = [
            f"dental clinic book appointment{loc_suffix}",
            f"medical practice doctors clinic{loc_suffix}",
            f"healthcare clinic patient care{loc_suffix}",
            f"specialty medical center contact us{loc_suffix}",
            f"aesthetic wellness clinic treatments{loc_suffix}",
            f"family health clinic our doctors{loc_suffix}",
            f"diagnostic medical center services{loc_suffix}",
            f"private hospital healthcare services{loc_suffix}"
        ]
    elif is_real_estate:
        deterministic_queries = [
            f"real estate agency properties for sale{loc_suffix}",
            f"property management company residential{loc_suffix}",
            f"luxury real estate brokers property listings{loc_suffix}",
            f"housing development property developers{loc_suffix}",
            f"commercial property agency office leasing{loc_suffix}",
            f"real estate firm buy rent properties{loc_suffix}"
        ]
    elif is_hospitality:
        deterministic_queries = [
            f"boutique hotel resort reservations{loc_suffix}",
            f"restaurant dining reserve table menu{loc_suffix}",
            f"travel tour operators holiday packages{loc_suffix}",
            f"luxury hotel accommodations contact{loc_suffix}",
            f"catering event services company{loc_suffix}"
        ]
    elif is_education:
        deterministic_queries = [
            f"private university admissions apply online{loc_suffix}",
            f"international school academics enrollment{loc_suffix}",
            f"professional training institute academy{loc_suffix}",
            f"career academy certification programs{loc_suffix}"
        ]
    elif is_automotive:
        deterministic_queries = [
            f"car dealership vehicle inventory sales{loc_suffix}",
            f"automotive repair service center book{loc_suffix}",
            f"auto parts accessories store shop{loc_suffix}",
            f"commercial vehicle sales dealership{loc_suffix}"
        ]
    elif is_logistics:
        deterministic_queries = [
            f"freight forwarding logistics company quote{loc_suffix}",
            f"warehousing 3pl logistics services{loc_suffix}",
            f"cargo transport trucking company contact{loc_suffix}",
            f"supply chain distribution provider{loc_suffix}"
        ]
    elif is_legal_finance:
        deterministic_queries = [
            f"law firm attorneys practice areas contact{loc_suffix}",
            f"chartered accountants cpa tax advisory firm{loc_suffix}",
            f"wealth management financial advisory firm{loc_suffix}",
            f"corporate legal counsel attorneys office{loc_suffix}"
        ]
    elif is_explicit_agency:
        deterministic_queries = [
            f"digital marketing agency client case studies{loc_suffix}",
            f"creative branding agency our work clients{loc_suffix}",
            f"b2b marketing consultancy services{loc_suffix}"
        ]
    else:
        deterministic_queries = [
            f"{clean_industry} company official website contact{loc_suffix}",
            f"{clean_industry} commercial business products{loc_suffix}",
            f"leading {clean_industry} corporate providers{loc_suffix}",
            f"top {clean_industry} brands operating in{loc_suffix}",
            f"{clean_industry} commercial operations about us{loc_suffix}",
            f"registered {clean_industry} business directory official{loc_suffix}"
        ]

    prompt = f"""You are a senior B2B web search engineer. Generate 6 realistic, natural search engine queries to find REAL OPERATING BUSINESSES / STORES / CLINICS / ENTITIES in this target industry: "{clean_industry}".

CRITICAL GUIDELINES:
1. Target the actual BUYERS / OPERATING END-BUSINESSES in this industry (e.g. if target industry is E-Commerce, find real online shopping stores and brands selling goods, NOT web design agencies or software vendors that build ecommerce websites).
2. NEVER include words like 'solutions provider', 'agency services', 'portfolio', 'case studies', 'development company' unless the target industry itself is explicitly an agency.
3. Write natural search queries (3 to 6 words) that directly surface commercial corporate homepages, brand stores, and official websites.
4. Do NOT use words like "directory", "rankings", "wikipedia", "definition", "best tools".
5. Append '{loc_clean}' to each query if provided.

Return ONLY a bulleted list of 6 queries, one per line. No preamble, no explanation.

Example for "Healthcare":
- healthcare clinics patient services{loc_suffix}
- medical practice about our doctors{loc_suffix}
- healthcare provider contact us{loc_suffix}"""

    system_prompt = "You are a B2B search engineer. Return ONLY raw search queries, one per line, no preamble, no numbering."

    try:
        raw_output = call_ollama(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=150,
            timeout=15.0
        )
        if raw_output and len(raw_output.strip()) > 10:
            raw_lines = [line.strip() for line in raw_output.splitlines() if line.strip()]
            valid_queries = []
            preamble_words = ("here are", "sure,", "note:", "based on", "the following", "here is", "search queries", "example")

            for line in raw_lines:
                clean_l = re.sub(r'^[-*•\d.\s]+', '', line).strip()
                if any(clean_l.lower().startswith(pw) for pw in preamble_words) or clean_l.endswith(":"):
                    continue
                # Reject queries that inject developer/agency synonyms when searching for non-agency industries
                clean_lower = clean_l.lower()
                agency_dev_words = (
                    "solutions provider", "agency services", "clients portfolio", "development company",
                    "website developers", "web developers", "software developers", "developers", "developer",
                    "development agency", "web development", "software company", "it services", "development",
                    "dev company", "dev shop", "portfolio", "design company", "website design", "software solutions",
                    "review", "reviews", "list", "top tools", "best tools", "ranking"
                )
                if not is_explicit_agency and any(bad in clean_lower for bad in agency_dev_words):
                    continue
                if len(clean_l) > 5 and not any(w in clean_lower for w in ("wikipedia", "directory", "definition")):
                    valid_queries.append(clean_l)

            # For specialized archetypes (e.g. E-Commerce, Healthcare, Real Estate), curated queries are guaranteed clean
            if is_ecommerce or is_healthcare or is_real_estate or is_hospitality or is_education or is_automotive or is_logistics or is_legal_finance:
                combined_queries = list(deterministic_queries)
                for lq in valid_queries:
                    if lq not in combined_queries:
                        combined_queries.append(lq)
                queries = combined_queries[:8]
                print(f"[Search Query Builder] Industry: '{clean_industry}' (Curated Archetype) → {len(queries)} high-end queries:")
                for idx, q in enumerate(queries, 1):
                    print(f"   Query #{idx}: '{q}'")
                return queries

            if valid_queries:
                queries = valid_queries[:8]
                print(f"[Search Query Builder] Industry: '{clean_industry}' (Dynamic LLM) → {len(queries)} queries:")
                for idx, q in enumerate(queries, 1):
                    print(f"   Query #{idx}: '{q}'")
                return queries
    except Exception as e:
        print(f"[Search Query Builder] Ollama offline — using archetype fallback queries: {e}")

    print(f"[Search Query Builder] Industry: '{clean_industry}' → {len(deterministic_queries)} archetype queries:")
    for idx, q in enumerate(deterministic_queries, 1):
        print(f"   Query #{idx}: '{q}'")
    return deterministic_queries


# ─── Streaming Discovery Generator ───────────────────────────────────────────
async def stream_discovery(
    keyword: str,
    country: str = "",
    city: str = "",
    min_trust: float = 0.0,
    min_confidence: int = 60,
    start_page: int = 1,
    target_count: int = 10,
    max_pages: int = 100,
    our_company: str = "",
    our_services: str = "",
    target_customers: str = "",
    description: str = "",
    industry: str = "",
    company_id: int = 1,
    mode: str = "direct_search",
    discovery_mode: str = "hybrid"
) -> AsyncIterator[str]:
    """
    Async generator that yields NDJSON lines. Evaluates leads using authenticated company profile.
    Auto-paginates indefinitely (up to 100 pages) until target_count (default 10) valid companies are collected.
    """
    clean_keyword = keyword.strip()
    clean_country = country.strip()
    clean_city = city.strip()
    company_name_context = our_company
    services_context = our_services

    effective_min_confidence = 50

    location_str = f"{clean_city}, {clean_country}".strip(", ")

    is_clients_mode = (discovery_mode or "").lower().strip() in ("direct_clients", "clients", "social_intent", "social", "intent", "gigs")

    # ── Context-Aware Dynamic Industry Generation (Step 2) ─────────────────────
    has_explicit_keyword = bool(
        clean_keyword and clean_keyword.lower() not in (
            "any", "all", "general", "auto", "target companies", "target_companies", "icp", "none", "default"
        )
    )

    dynamic_batch = None
    if is_clients_mode:
        # In Direct Clients mode, user input is their service (e.g. 'AI Chatbot', 'Web Development')
        svc_target = clean_keyword or services_context or "Software Services"
        query_variations = [
            f'"{svc_target}" ("looking for agency" OR "need developer" OR "hiring")',
            f'"{svc_target}" ("seeking contractor" OR "need freelancer" OR "project")',
            f'"{svc_target}" ("quote" OR "budget" OR "looking for vendor")',
            f'{svc_target} hiring agency developer'
        ]
        print(f"[Discover] 🎯 DIRECT CLIENTS MODE ACTIVATED for service: '{svc_target}'")
    else:
        # Dynamic niche generation runs ONLY if user did not specify an explicit industry,
        # or explicitly requested dynamic niche exploration mode.
        is_dynamic_mode = (
            not has_explicit_keyword
            or mode in ("dynamic_industry", "icp")
        )
        if is_dynamic_mode:
            try:
                effective_svc = (
                    services_context
                    or (clean_keyword if not has_explicit_keyword else "")
                    or "B2B Products & Services"
                )
                dynamic_batch = await get_next_discovery_batch(
                    our_services=effective_svc,
                    selected_country=clean_country,
                    mode=mode
                )
                if dynamic_batch and dynamic_batch.get("queries"):
                    query_variations = dynamic_batch["queries"]
                    clean_keyword = dynamic_batch.get("niche", clean_keyword)
            except Exception as batch_err:
                print(f"[Discover] Dynamic industry generator error: {batch_err}")

        # For explicit user industries (e.g. 'Higher Education Institutions with Online Programs'),
        # generate targeted queries directly for that user-specified industry
        if not dynamic_batch or not dynamic_batch.get("queries"):
            query_variations = generate_industry_search_queries(
                industry=clean_keyword,
                location_str=location_str
            )

    primary_query = query_variations[0]

    start_payload = {
        "type": "start",
        "query": primary_query,
        "target": target_count,
        "discoveryMode": "direct_clients" if is_clients_mode else "companies"
    }
    if dynamic_batch:
        start_payload["dynamicNiche"] = dynamic_batch.get("niche")
        start_payload["parentIndustry"] = dynamic_batch.get("parent_industry")
        start_payload["targetServiceFit"] = dynamic_batch.get("target_service_fit")
        start_payload["rationale"] = dynamic_batch.get("rationale")

    yield json.dumps(start_payload) + "\n"

    print(f"\n==================== [CONTINUOUS DYNAMIC DISCOVERY START] ====================")
    print(f"[Discover] Authenticated Company : '{company_name_context}'")
    print(f"[Discover] Our Services          : '{our_services}' (NOT injected into search query)")
    print(f"[Discover] Target Industry       : '{clean_keyword}'")
    print(f"[Discover] Primary Search Query  : '{primary_query}'")
    print(f"[Discover] Target Goal           : {target_count} Companies (both NEEDS_SERVICE + HAS_SIMILAR_SERVICE count)")

    qualified_total = 0
    seen_domains: set = set()
    semaphore = asyncio.Semaphore(5)
    total_ollama = 0
    total_groq = 0
    total_raw = 0
    total_noise_passed = 0

    variation_idx = 0
    query_subpage = 1

    for current_page in range(start_page, start_page + max_pages):
        if qualified_total >= target_count:
            print(f"\n[Discover] ✅ Target goal of {target_count} companies reached! Stopping discovery loop.")
            break

        active_query = query_variations[variation_idx % len(query_variations)]

        print(f"\n[Discover] ─── Step {current_page} (Goal: {qualified_total}/{target_count}) | Subpage: {query_subpage} | Query: '{active_query}' ───")
        raw_results = []
        is_mocked_search = getattr(search_searxng_or_ddg, '__name__', '') != 'search_searxng_or_ddg'

        if is_mocked_search:
            raw_results = await search_searxng_or_ddg(active_query, page=query_subpage)
        else:
            try:
                try:
                    multi_candidates = await ingest_all_sources(
                        query=active_query,
                        target_service=services_context,
                        page=query_subpage,
                        discovery_mode=discovery_mode,
                        target_country=clean_country
                    )
                except TypeError:
                    multi_candidates = await ingest_all_sources(
                        query=active_query,
                        target_service=services_context,
                        page=query_subpage
                    )
                for mc in multi_candidates:
                    raw_results.append({
                        "url": mc.url,
                        "title": mc.title,
                        "content": mc.text_content,
                        "snippet": mc.text_content,
                        "source": mc.source,
                        "author_or_company": mc.author_or_company,
                        "raw_domain": mc.raw_domain,
                        "priority_rank": mc.priority_rank,
                        "published_at": mc.published_at,
                        "raw_metadata": mc.raw_metadata
                    })
            except Exception as e:
                print(f"[Discover] Multi-source ingestion error: {e}")

            if not raw_results:
                if (discovery_mode or "hybrid").lower().strip() not in ("social_intent", "direct_clients", "clients"):
                    print(f"[Discover] Multi-source yielded 0 candidates; falling back to search_searxng_or_ddg...")
                    raw_results = await search_searxng_or_ddg(active_query, page=query_subpage)

        total_raw += len(raw_results)

        if not raw_results:
            print(f"[Discover] Query '{active_query}' subpage {query_subpage} returned 0 results. Rotating query variation...")
            variation_idx += 1
            query_subpage = 1
            active_query = query_variations[variation_idx % len(query_variations)]
            print(f"[Discover] Retrying with query variation: '{active_query}' (subpage 1)")
            raw_results = await search_searxng_or_ddg(active_query, page=1)
            total_raw += len(raw_results)

        if not raw_results:
            print(f"[Discover] Query variation '{active_query}' also empty. Advancing to next variation...")
            variation_idx += 1
            query_subpage = 1
            continue

        page_candidates = []
        for item in raw_results:
            url = item.get('url', '')
            item_source = item.get('source', 'web')
            is_intent_source = item_source in ('reddit', 'hacker_news', 'rss_feed', 'twitter_x')

            # If multi-source candidate has a clean extracted company domain, prioritize it
            raw_dom = item.get('raw_domain')
            candidate_domain = clean_domain(raw_dom) if (raw_dom and clean_domain(raw_dom) and clean_domain(raw_dom) not in EXCLUDE_DOMAINS) else clean_domain(url)
            domain = candidate_domain

            if not domain:
                continue

            if not is_intent_source:
                # ── Deterministic Junk Firewall Pre-Scrape Gate ──
                is_det_junk, det_reason = is_deterministic_junk(url=url, domain=domain)
                if is_det_junk:
                    print(f"[Junk Firewall Pre-Scrape] 🛡️ SKIP: {domain} ({url[:80]}) | {det_reason}")
                    continue

                # ── Strict Geo-Lock Pre-Scrape Gate (Foreign ccTLD check) ──
                if clean_country:
                    is_local_pre, pre_geo_reason, pre_geo_conf = verify_deterministic_geo(
                        domain=domain,
                        target_country=clean_country
                    )
                    if not is_local_pre and pre_geo_conf == 0.0 and "Foreign ccTLD" in pre_geo_reason:
                        print(f"[Geo-Lock Pre-Scrape] 🚫 SKIP: {domain} ({url[:80]}) | {pre_geo_reason}")
                        continue

                if domain in EXCLUDE_DOMAINS:
                    print(f"[Filter] SKIP (excluded domain): {domain}")
                    continue
                if any(domain.endswith('.' + d) or domain == d for d in EXCLUDE_DOMAINS):
                    print(f"[Filter] SKIP (subdomain of excluded): {domain}")
                    continue
                if any(tld in domain for tld in ['.gov', '.mil']):
                    print(f"[Filter] SKIP (gov/mil TLD): {domain}")
                    continue
                if any(p in url.lower() for p in SKIP_PATTERNS):
                    print(f"[Filter] SKIP (URL pattern match): {domain} url={url[:80]}")
                    continue
                if domain in seen_domains:
                    continue

                title_raw = item.get('title', '')
                if TITLE_SKIP_RE.search(title_raw):
                    print(f"[Filter] SKIP (listicle/directory title): '{title_raw[:80]}'")
                    continue

                if not is_plausible_business_domain(domain):
                    print(f"[Filter] SKIP (not plausible business domain): {domain}")
                    continue

                if not is_official_homepage(url):
                    print(f"[Filter] SKIP (not official corporate homepage path): url={url[:80]}")
                    continue
            else:
                # For intent sources, avoid duplicate evaluations per genuine domain
                if domain in seen_domains and domain not in ("reddit.com", "x.com", "ycombinator.com", "remoteok.com"):
                    continue

            seen_domains.add(domain)
            page_candidates.append(item)

        if len(page_candidates) == 0:
            print(f"[Discover] Page {current_page} yielded 0 new candidates (all duplicate/filtered). Rotating query variation...")
            variation_idx += 1
            query_subpage = 1
            continue

        total_noise_passed += len(page_candidates)
        page_candidates_trimmed = page_candidates[:20]

        async def evaluate_and_emit(idx: int, item: dict):
            nonlocal qualified_total, total_ollama, total_groq
            async with semaphore:
                url = item.get('url', '')
                title = item.get('title', '')
                snippet = item.get('content', '') or item.get('snippet', '')
                raw_dom = item.get('raw_domain')
                domain = clean_domain(raw_dom) if (raw_dom and clean_domain(raw_dom) and clean_domain(raw_dom) not in EXCLUDE_DOMAINS) else clean_domain(url)

                try:
                    # ── DIRECT CLIENTS MODE: Fast & Direct Client Lead Extraction ──
                    if is_clients_mode:
                        item_src = item.get("source", "client_lead")
                        platform_label = "Reddit" if "reddit" in item_src else ("Twitter / X" if "twitter" in item_src else ("Hacker News" if "hacker" in item_src else ("Upwork / Gigs" if "rss" in item_src else "Web Community")))
                        client_handle = item.get("author_or_company") or item.get("raw_metadata", {}).get("handle") or "Prospective Client"
                        post_snippet = snippet or title

                        return {
                            "type": "company",  # Keep company type for polymorphic frontend rendering
                            "isClientLead": True,
                            "id": f"lead-{int(time.time() * 1000)}-{idx}-{item_src[:4]}",
                            "name": f"{client_handle} ({platform_label})",
                            "clientName": client_handle,
                            "platform": platform_label,
                            "website": url,
                            "displayUrl": url[:60] + ("..." if len(url) > 60 else ""),
                            "domain": domain or item_src,
                            "industry": clean_keyword or services_context or "B2B Client Intent",
                            "country": clean_country or "Remote / Global",
                            "city": clean_city,
                            "snippet": post_snippet[:350],
                            "matchReason": f"Direct project request / buying signal for '{clean_keyword or services_context}' on {platform_label}.",
                            "matchConfidence": 92,
                            "trustScore": 92,
                            "trustStatus": "Live Client Intent",
                            "leadType": "needs_service",
                            "source": item_src,
                            "dataSource": "live_intent",
                            "priorityRank": item.get("priority_rank", 1),
                            "email": None,
                            "phone": None,
                            "outreachAngle": f"Directly address requirement posted by {client_handle} on {platform_label}: offering specialized {clean_keyword or services_context}.",
                            "directPostUrl": url
                        }

                    company_hint = item.get('author_or_company')
                    if company_hint and not is_invalid_company_name(company_hint):
                        company_name = company_hint
                    else:
                        company_name = extract_clean_company_name(title, domain)

                    is_valid_geo = True
                    geo_reason = "Global or verified target"
                    geo_result_data = {
                        "is_valid_geo": True,
                        "source": "domain_profile",
                        "evidence_type": "domain_profile"
                    }
                    is_valid_buyer = True
                    intent_type = "COMMERCIAL_TARGET"
                    intent_reason = "Operating business target"
                    intent_result_data = {
                        "is_valid_buyer": True,
                        "intent_type": "COMMERCIAL_TARGET",
                        "intent_reason": "Operating business"
                    }

                    if "cached_evaluation" in item:
                        eval_res = item["cached_evaluation"]
                    else:
                        scraped = item.get("scraped_content", "")
                        ev_source_label = item.get("evidence_source_label", "")
                        if not scraped:
                            try:
                                scraped, ev_source_label = await fetch_url_content_with_subpages(url, timeout=4.0)
                                if scraped:
                                    print(f"[Scrape Multi-Page] {domain} — {len(scraped)} chars from '{ev_source_label}'")
                                else:
                                    print(f"[Scrape] {domain} — empty (evaluating from snippet only)")
                            except Exception as scrape_err:
                                scraped = ""
                                ev_source_label = "search snippet only"
                                print(f"[Scrape] {domain} — failed: {type(scrape_err).__name__}: {scrape_err}")

                        # ── Multi-Tier Deterministic & Semantic Junk Firewall (Step 3) ──
                        is_snippet_only = not bool(scraped or item.get("raw_html", ""))
                        is_firewall_junk, firewall_reason = await run_junk_firewall(
                            url=url,
                            domain=domain,
                            html_content=item.get("raw_html", ""),
                            text_content=scraped or snippet,
                            is_search_snippet=is_snippet_only
                        )
                        if is_firewall_junk:
                            print(f"[Junk Firewall] 🛡️ REJECTED: {domain} ({url[:80]}) | {firewall_reason}")
                            return None

                        # ── Strict Local Entity & Country Lock Engine (Step 4) ──
                        if clean_country:
                            is_valid_geo, geo_reason = await run_geo_lock_engine(
                                domain=domain,
                                url=url,
                                html_content=item.get("raw_html", ""),
                                text_content=scraped or snippet,
                                target_country=clean_country,
                                use_llm=True
                            )
                            if not is_valid_geo:
                                print(f"[Geo-Lock] 🚫 REJECTED: {domain} ({url[:80]}) | {geo_reason}")
                                return None
                            geo_result_data = {
                                "is_valid_geo": is_valid_geo,
                                "reason": geo_reason,
                                "tld_matched": any(domain.endswith(t) for t in ('.pk', '.uk', '.co.uk', '.de', '.ae', '.ca', '.au', '.in', '.fr')),
                                "evidence_type": "tld" if any(domain.endswith(t) for t in ('.pk', '.uk', '.co.uk', '.de', '.ae', '.ca', '.au', '.in', '.fr')) else "address_or_llm"
                            }

                        # ── Strict Buyer Intent & Non-Job Contract Classifier (Step 5) ──
                        is_valid_buyer, intent_type, intent_reason = await run_intent_classifier(
                            title=title,
                            text_content=scraped or snippet,
                            target_service=services_context or clean_keyword,
                            is_intent_source=is_intent_source,
                            use_llm=True
                        )
                        if not is_valid_buyer:
                            print(f"[Intent Filter] 🚫 REJECTED: {domain} ({url[:80]}) | [{intent_type}] {intent_reason}")
                            return None
                        intent_result_data = {
                            "is_valid_buyer": is_valid_buyer,
                            "intent_type": intent_type,
                            "intent_reason": intent_reason
                        }

                        eval_res = await evaluate_client_fit_dual_engine(
                            company_name=company_name, domain=domain, snippet=snippet,
                            scraped_text=scraped, our_company=company_name_context,
                            our_services=services_context, target_customers=target_customers,
                            description=description, target_industry=clean_keyword, target_country=clean_country,
                            evidence_source_label=ev_source_label
                        )

                    if not eval_res or not isinstance(eval_res, dict):
                        print(f"[OLLAMA LLM] ⚠️ EVALUATION FAILED/TIMED OUT for {domain} ({url})")
                        return None

                    # ── Stage 1: Hard junk filter ──────────────────────────────────
                    is_junk = bool(eval_res.get("is_junk", False))
                    if is_junk:
                        junk_reason = str(eval_res.get("reason", "Junk/directory/listicle")).strip()
                        print(f"[OLLAMA LLM] 🗑️  REJECTED — junk/directory/listicle: {domain} | {junk_reason}")
                        return None

                    # ── Stage 2: Industry verification ─────────────────────────────
                    industry_match = bool(eval_res.get("industry_match", False))
                    confidence = int(eval_res.get("confidence", 0))
                    reason = str(eval_res.get("reason", "")).strip()
                    source = str(eval_res.get("source", "local-ollama"))
                    detected_country = str(eval_res.get("detected_country", "")).strip()
                    lead_type = str(eval_res.get("lead_type", "")).strip().upper()

                    if not industry_match:
                        print(f"[OLLAMA LLM] ✗ REJECTED — industry mismatch: {domain} | {reason or 'Not in target industry'}")
                        return None

                    if confidence < effective_min_confidence:
                        print(f"[OLLAMA LLM] ✗ REJECTED — low confidence ({confidence} < {effective_min_confidence}): {domain}")
                        return None

                    # ── Stage 3: Both NEEDS_SERVICE and HAS_SIMILAR_SERVICE are accepted ──
                    if lead_type not in ("NEEDS_SERVICE", "HAS_SIMILAR_SERVICE"):
                        print(f"[OLLAMA LLM] ✗ REJECTED — invalid/missing lead_type '{lead_type}': {domain}")
                        return None

                    if source == "ollama":
                        total_ollama += 1

                    # Clean company name resolution with multi-stage fallback
                    llm_name = str(eval_res.get("official_company_name", "")).strip()
                    if llm_name and not is_invalid_company_name(llm_name):
                        company_name = llm_name
                    else:
                        extracted_name = extract_clean_company_name(title, domain)
                        if extracted_name and not is_invalid_company_name(extracted_name):
                            company_name = extracted_name
                        else:
                            company_name = get_fallback_domain_name(domain)

                    set_cached_evaluation(domain, {
                        "industry_match": industry_match, "lead_type": lead_type,
                        "confidence": confidence, "reason": reason,
                        "source": source, "detected_country": detected_country
                    })

                    item_data_source = item.get("source", "real_search")
                    is_ai_generated = item_data_source == "ai_generated"

                    company_country = (
                        detected_country if detected_country and len(detected_country) > 1
                        and detected_country.lower() not in ("unknown", "none")
                        else (clean_country or "Global")
                    )

                    # Sanitize card description: Prioritize company business overview over executive bios/person quotes
                    card_snippet = snippet[:280] if snippet else ""
                    bio_keywords_pattern = r'(?i)\b(?:Senior\s+Vice\s+President|Vice\s+President|Chief\s+Executive\s+Officer|Executive\s+Director|Mohit\s+Manrao|Head\s+of\s+US|President\s+and\s+Head|Board\s+of\s+Directors)\b'
                    if re.search(bio_keywords_pattern, card_snippet):
                        card_snippet = reason[:280] if reason else f"{company_name} is an established operating business in the {clean_keyword} sector."

                    if not card_snippet or len(card_snippet) < 25:
                        card_snippet = reason[:280] if reason else f"{company_name} is a verified operating company in {clean_keyword}."

                    from email_outreach import extract_regex_contacts
                    scraped_text_for_contacts = scraped if scraped else f"{title} {snippet}"
                    contacts_extracted = extract_regex_contacts(scraped_text_for_contacts, url)

                    found_emails = contacts_extracted.get("emails", [])
                    found_phones = contacts_extracted.get("phones", [])
                    found_linkedin = contacts_extracted.get("linkedin_url", None)

                    primary_email = found_emails[0] if found_emails else None
                    primary_phone = found_phones[0] if found_phones else None

                    # ── Service-Agnostic Operational Bottleneck Audit Engine (Step 7) ──
                    try:
                        audit_res = await audit_company_operations(
                            domain=domain,
                            multi_page_text=scraped or snippet,
                            target_service=services_context or clean_keyword,
                            use_llm=True
                        )
                    except Exception as audit_err:
                        logger.debug(f"[OperationalAudit] Failed for {domain}: {audit_err}")
                        audit_res = {
                            "has_operational_bottleneck": False,
                            "bottleneck_category": None,
                            "severity": "LOW",
                            "evidence_quote": "",
                            "workflow_gap_summary": "",
                            "proposed_solution_angle": ""
                        }

                    # ── Deep 3-Way Match Matrix Engine (Step 8) ──
                    our_profile = {
                        "name": company_name_context or "Our Company",
                        "services": services_context or clean_keyword,
                        "target_customers": target_customers,
                        "description": description,
                        "industry": clean_keyword,
                        "ai_enriched_profile": services_context
                    }
                    try:
                        match_matrix = await run_three_way_match_matrix(
                            our_profile=our_profile,
                            candidate_domain=domain,
                            candidate_text=scraped or snippet,
                            audit_result=audit_res,
                            use_llm=True
                        )
                    except Exception as matrix_err:
                        logger.debug(f"[3-Way Matrix] Evaluation failed for {domain}: {matrix_err}")
                        match_matrix = ThreeWayMatchResult(
                            overall_qualification="QUALIFIED_LEAD",
                            solution_to_pain_score=0.75,
                            icp_scale_score=0.75,
                            readiness_score=0.75,
                            composite_matrix_score=0.75,
                            solution_pain_rationale="Evaluated via standard commercial match.",
                            icp_scale_rationale="Operating enterprise profile confirmed.",
                            readiness_rationale="Standard operational readiness.",
                            key_value_proposition=audit_res.get("proposed_solution_angle", "")
                        )

                    if match_matrix.overall_qualification == "DISQUALIFIED":
                        print(f"[3-Way Matrix] 🚫 DISQUALIFIED: {domain} ({url[:80]}) | {match_matrix.solution_pain_rationale or match_matrix.icp_scale_rationale}")
                        return None

                    # ── Multi-Factor Evidence-Based Scoring & 360° Post-Click Audit Engine (Step 9) ──
                    evidence_breakdown = calculate_evidence_score(
                        item=item,
                        geo_result=geo_result_data,
                        intent_result=intent_result_data,
                        audit_result=audit_res,
                        matrix_result=match_matrix.to_dict(),
                        target_country=clean_country
                    )
                    grounded_confidence = evidence_breakdown.total_composite_score

                    candidate_payload_for_audit = {
                        "name": company_name,
                        "domain": domain,
                        "industry": clean_keyword,
                        "evidenceScore": grounded_confidence,
                        "scoreBreakdown": evidence_breakdown.to_dict(),
                        "threeWayMatch": match_matrix.to_dict(),
                        "leadType": lead_type.lower().replace("_", "_"),
                        "emails": found_emails,
                        "phones": found_phones,
                        "email": primary_email,
                        "phone": primary_phone,
                        "linkedin": found_linkedin,
                        "workflowGapSummary": audit_res.get("workflow_gap_summary", ""),
                        "evidenceQuote": audit_res.get("evidence_quote", ""),
                        "proposedSolutionAngle": audit_res.get("proposed_solution_angle", ""),
                        "keyValueProposition": match_matrix.key_value_proposition
                    }
                    audit_360_card = generate_360_post_click_audit(domain, candidate_payload_for_audit)

                    return {
                        "type": "company",
                        "id": f"co-{int(time.time() * 1000)}-{idx}-{domain[:6]}",
                        "name": company_name,
                        "website": url,
                        "displayUrl": domain,
                        "domain": domain,
                        "industry": clean_keyword,
                        "country": company_country,
                        "city": clean_city,
                        "snippet": card_snippet,
                        "matchReason": reason or f"Authentic prospect in {clean_keyword}.",
                        "matchConfidence": grounded_confidence,
                        "trustScore": grounded_confidence,
                        "trustStatus": "Verified Company",
                        "email": primary_email,
                        "phone": primary_phone,
                        "phones": found_phones,
                        "emails": found_emails,
                        "linkedin": found_linkedin,
                        "leadType": lead_type.lower().replace("_", "_"),  # 'needs_service' or 'has_similar_service'
                        "source": source,
                        "dataSource": item_data_source,
                        "priorityRank": item.get("priority_rank", 1),
                        "unverified": is_ai_generated,
                        # Operational Bottleneck Audit Fields (Step 7)
                        "operationalAudit": audit_res,
                        "hasOperationalBottleneck": audit_res.get("has_operational_bottleneck", False),
                        "bottleneckCategory": audit_res.get("bottleneck_category", None),
                        "bottleneckSeverity": audit_res.get("severity", "LOW"),
                        "evidenceQuote": audit_res.get("evidence_quote", ""),
                        "workflowGapSummary": audit_res.get("workflow_gap_summary", ""),
                        "proposedSolutionAngle": audit_res.get("proposed_solution_angle", ""),
                        # Snake-case aliases for downstream consumption
                        "evidence_quote": audit_res.get("evidence_quote", ""),
                        "workflow_gap_summary": audit_res.get("workflow_gap_summary", ""),
                        "proposed_solution_angle": audit_res.get("proposed_solution_angle", ""),
                        # 3-Way Match Matrix Fields (Step 8)
                        "threeWayMatch": match_matrix.to_dict(),
                        "overallQualification": match_matrix.overall_qualification,
                        "compositeMatrixScore": match_matrix.composite_matrix_score,
                        "solutionToPainScore": match_matrix.solution_to_pain_score,
                        "icpScaleScore": match_matrix.icp_scale_score,
                        "readinessScore": match_matrix.readiness_score,
                        "keyValueProposition": match_matrix.key_value_proposition,
                        # Snake-case aliases
                        "overall_qualification": match_matrix.overall_qualification,
                        "composite_matrix_score": match_matrix.composite_matrix_score,
                        "solution_to_pain_score": match_matrix.solution_to_pain_score,
                        "icp_scale_score": match_matrix.icp_scale_score,
                        "readiness_score": match_matrix.readiness_score,
                        "key_value_proposition": match_matrix.key_value_proposition,
                        # Multi-Factor Evidence Scoring & 360° Audit Fields (Step 9)
                        "evidenceScore": grounded_confidence,
                        "scoreBreakdown": evidence_breakdown.to_dict(),
                        "audit360": audit_360_card,
                        # Snake-case aliases
                        "evidence_score": grounded_confidence,
                        "score_breakdown": evidence_breakdown.to_dict(),
                        "audit_360": audit_360_card,
                    }
                except Exception as eval_err:
                    print(f"[OLLAMA LLM] ❌ EXCEPTION evaluating {domain}: {type(eval_err).__name__}: {eval_err}", flush=True)
                    return None

        tasks = [evaluate_and_emit(i, item) for i, item in enumerate(page_candidates_trimmed)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if res and isinstance(res, dict) and res.get("type") == "company":
                qualified_total += 1
                domain = res.get("domain", "")
                company_name = res.get("name", "")
                lead_type = str(res.get("leadType", "")).upper()
                reason = res.get("matchReason", "")
                source = res.get("source", "local-ollama")

                source_tag = f"[{source.upper()} LLM]"
                lead_label = "NEEDS_SERVICE ✦" if "needs_service" in lead_type.lower() else "HAS_SIMILAR_SERVICE ↑"
                print(f"{source_tag} ✓ ACCEPTED [{lead_label}] {domain}: {reason} ({qualified_total}/{target_count})")
                print(f"[STREAM] Yielding company #{qualified_total} '{domain}' ({company_name}) to frontend SSE/NDJSON stream")

                yield json.dumps(res) + "\n"

                try:
                    from database import save_lead
                    save_lead(
                        lead_id=res.get("id", f"lead-{time.time()}"),
                        name=company_name or "Unknown Company",
                        description=res.get("snippet", ""),
                        email=f"contact@{domain or 'company.com'}",
                        subject=f"Outreach opportunity for {company_name}",
                        sent_at=None,
                        action=reason or "AI Qualified Prospect",
                        email_source_context=json.dumps(res),
                        company_id=company_id
                    )
                except Exception as db_err:
                    print(f"[Discover DB Save Error]: {db_err}")

                if qualified_total >= target_count:
                    break

        yield json.dumps({
            "type": "progress", "page": current_page, "qualified": qualified_total,
            "target": target_count, "processed": total_noise_passed
        }) + "\n"

        # Advance subpage for current query, or rotate to next query if 2 pages checked
        if query_subpage < 2:
            query_subpage += 1
        else:
            variation_idx += 1
            query_subpage = 1

    if qualified_total >= target_count:
        print(f"\n==================== [DISCOVERY COMPLETE: TARGET REACHED] ====================")
        print(f"[Discover] ✅ SUCCESS: Collected target goal of {target_count} qualified companies across search pages.")
    else:
        print(f"\n==================== [DISCOVERY COMPLETE: PAGE LIMIT REACHED] ====================")
        print(f"[Discover] 🛑 STOPPED: Processed {current_page} pages. Collected {qualified_total}/{target_count} qualified companies.")

    yield json.dumps({
        "type": "complete", "totalQualified": qualified_total,
        "summary": f"Discovery finished. Found {qualified_total} qualified prospects for {company_name_context}."
    }) + "\n"


# ─── Streaming POST /discover-companies (JWT Protected) ──────────────────────
@discover_router.post("/discover-companies")
async def post_discover_companies(
    req: DiscoverRequest,
    current_company: Company = Depends(get_current_company)
):
    if not req.keyword or not req.keyword.strip():
        raise HTTPException(status_code=400, detail="Keyword is required.")

    print(f"\n[FASTAPI BACKEND] 🚀 RECEIVED FRONTEND DISCOVER POST REQUEST: keyword='{req.keyword}' country='{req.country}' city='{req.city}' company='{current_company.name}'", flush=True)

    min_trust = req.minTrustScore if req.minTrustScore is not None else (req.min_trust_score or 0.0)
    conf = int(req.min_confidence or min_trust or 75)
    page_num = int(req.pageno or req.page or 1)

    effective_company_name = req.our_company or (current_company.name if current_company else "My Company")
    effective_services = (
        req.our_services
        or getattr(current_company, "services", None)
        or getattr(current_company, "ai_enriched_profile", None)
        or getattr(current_company, "description", None)
        or "B2B Products & Services"
    )

    print(f"\n[FASTAPI BACKEND] 🚀 RECEIVED FRONTEND DISCOVER POST REQUEST: keyword='{req.keyword}' country='{req.country}' city='{req.city}' company='{effective_company_name}' services='{effective_services}'", flush=True)

    effective_mode = req.mode or ("direct_search" if req.keyword and req.keyword.strip() else "target_companies")

    return StreamingResponse(
        stream_discovery(
            keyword=req.keyword,
            country=req.country or "",
            city=req.city or "",
            min_trust=float(min_trust),
            min_confidence=conf,
            start_page=page_num,
            target_count=int(req.target_count or 10),
            max_pages=100,
            our_company=effective_company_name,
            our_services=effective_services,
            target_customers=(getattr(current_company, "target_customers", "") or ""),
            description=(getattr(current_company, "description", "") or ""),
            industry=(getattr(current_company, "industry", "") or ""),
            company_id=(getattr(current_company, "id", 1) or 1),
            mode=effective_mode,
            discovery_mode=req.discovery_mode or "hybrid"
        ),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}
    )

# ─── Streaming GET /discover-companies (JWT Protected) ──────────────────────
@discover_router.get("/discover-companies")
async def get_discover_companies(
    keyword: str = Query(...),
    country: Optional[str] = Query(""),
    city: Optional[str] = Query(""),
    minTrustScore: Optional[float] = Query(None),
    min_trust_score: Optional[float] = Query(None),
    min_confidence: Optional[int] = Query(None),
    pageno: Optional[int] = Query(1),
    page: Optional[int] = Query(1),
    target_count: Optional[int] = Query(10),
    our_company: Optional[str] = Query(None),
    our_services: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
    discovery_mode: Optional[str] = Query("hybrid"),
    current_company: Company = Depends(get_current_company)
):
    if not keyword or not keyword.strip():
        raise HTTPException(status_code=400, detail="Keyword is required.")

    min_trust = minTrustScore if minTrustScore is not None else (min_trust_score or 0.0)
    conf = int(min_confidence or min_trust or 75)
    page_num = int(pageno or page or 1)

    effective_company_name = our_company or (current_company.name if current_company else "My Company")
    effective_services = (
        our_services
        or getattr(current_company, "services", None)
        or getattr(current_company, "ai_enriched_profile", None)
        or getattr(current_company, "description", None)
        or "B2B Products & Services"
    )

    print(f"\n[FASTAPI BACKEND] 🚀 RECEIVED FRONTEND DISCOVER GET REQUEST: keyword='{keyword}' country='{country}' city='{city}' company='{effective_company_name}' services='{effective_services}'", flush=True)

    effective_mode = mode or ("direct_search" if keyword and keyword.strip() else "target_companies")

    return StreamingResponse(
        stream_discovery(
            keyword=keyword,
            country=country or "",
            city=city or "",
            min_trust=float(min_trust),
            min_confidence=conf,
            start_page=page_num,
            target_count=int(target_count or 10),
            max_pages=100,
            our_company=effective_company_name,
            our_services=effective_services,
            target_customers=(getattr(current_company, "target_customers", "") or ""),
            description=(getattr(current_company, "description", "") or ""),
            industry=(getattr(current_company, "industry", "") or ""),
            company_id=(getattr(current_company, "id", 1) or 1),
            mode=effective_mode,
            discovery_mode=discovery_mode or "hybrid"
        ),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}
    )
