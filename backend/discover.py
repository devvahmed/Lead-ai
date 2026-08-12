import os
import re
import json
import time
import asyncio
import socket
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
    fetch_url_content_with_subpages,
    compute_relevance_score
)

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
    searxng_url = os.getenv("SEARXNG_URL", "http://localhost:8085")
    searxng_urls_to_try = list({searxng_url, "http://localhost:8085", "http://localhost:8080"})
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

    # ── Attempt 2: Brave Search API (if key available) ────────────────────────
    brave_key = os.getenv("BRAVE_SEARCH_API_KEY", "")
    print(f"[Discover Search] ── Brave Search Attempt ─────────────────────────")
    if not brave_key:
        print(f"[Discover Search] Brave Search SKIPPED — BRAVE_SEARCH_API_KEY not set in environment")
    else:
        _all_providers_tried += 1
        print(f"[Discover Search] Query sent to Brave: '{query}' (page={page})")
        try:
            brave_params = urllib.parse.urlencode({"q": query, "count": 20, "offset": (page - 1) * 10})
            brave_req = urllib.request.Request(
                f"https://api.search.brave.com/res/v1/web/search?{brave_params}",
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": brave_key,
                    "User-Agent": "Mozilla/5.0"
                }
            )
            loop = asyncio.get_event_loop()

            def _fetch_brave():
                try:
                    with urllib.request.urlopen(brave_req, timeout=6.0) as resp:
                        status = resp.status
                        raw = resp.read()
                        print(f"[Discover Search] Brave HTTP status={status}, raw_bytes={len(raw)}")
                        try:
                            import gzip
                            raw = gzip.decompress(raw)
                            print(f"[Discover Search] Brave response decompressed to {len(raw)} bytes")
                        except Exception:
                            pass
                        if status == 200:
                            data = json.loads(raw.decode('utf-8'))
                            items = data.get("web", {}).get("results", [])
                            print(f"[Discover Search] Brave parsed {len(items)} result(s)")
                            return [
                                {"url": r["url"], "title": r.get("title", ""), "content": r.get("description", "")}
                                for r in items
                            ]
                        print(f"[Discover Search] Brave non-200 status {status} — no results")
                        return []
                except Exception as inner_e:
                    print(f"[Discover Search] Brave fetch exception: {type(inner_e).__name__}: {inner_e}")
                    return []

            results = await loop.run_in_executor(None, _fetch_brave)
            if results:
                print(f"[Discover Search] ✓ Brave SUCCESS: {len(results)} results")
                return results
            else:
                print(f"[Discover Search] Brave returned 0 results for query='{query}'")
        except Exception as e:
            print(f"[Discover Search] Brave outer exception: {type(e).__name__}: {e}")

    # ── Attempt 3: DuckDuckGo HTML Scraping (POST) ─────────────────────────────
    print(f"[Discover Search] ── DuckDuckGo Attempt ───────────────────────────")
    print(f"[Discover Search] Query sent to DDG: '{query}' (page={page})")
    _all_providers_tried += 1

    await asyncio.sleep(0.3)

    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
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


# ─── Ollama OpenAI-Compatible Chat Helper ────────────────────────────────────
def call_ollama(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 1000,
    timeout: float = 45.0,
    domain_tag: str = ""
) -> Optional[str]:
    """
    Executes a POST request to the Ollama OpenAI-compatible /v1/chat/completions endpoint.
    Reads OLLAMA_BASE_URL and OLLAMA_MODEL from environment variables with sensible defaults.
    """
    raw_base = os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_URL") or "http://100.91.220.98:11434/v1"
    base_url = raw_base.strip().rstrip("/")
    if base_url.endswith("/v1"):
        endpoint = f"{base_url}/chat/completions"
    else:
        endpoint = f"{base_url}/v1/chat/completions"

    model_name = os.getenv("OLLAMA_MODEL", "llama3:latest")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ClientPlus-AI/1.0"
    }

    tag = f"[{domain_tag}] " if domain_tag else ""
    print(f"[Ollama Request Sent] ---> {tag}Posting request to endpoint '{endpoint}' (timeout={timeout}s)", flush=True)

    import time
    start_time = time.time()
    max_retries = 2
    for attempt in range(1, max_retries + 1):
        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(endpoint, data=req_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                elapsed = time.time() - start_time
                if resp.status == 200:
                    body = json.loads(resp.read().decode("utf-8"))
                    content = body["choices"][0]["message"]["content"].strip()
                    print(f"[Ollama Response Received] <--- {tag}HTTP 200 ({len(content)} chars, {elapsed:.1f}s)", flush=True)
                    return content
                else:
                    print(f"[Ollama Call Error] <--- {tag}HTTP {resp.status} returned from endpoint '{endpoint}'", flush=True)
        except Exception as e:
            elapsed = time.time() - start_time
            is_reset_err = any(err_kw in str(e).lower() for err_kw in ["10054", "reset", "timed out", "connection", "closed"])
            if attempt < max_retries and is_reset_err:
                print(f"[Ollama Call Retry] {tag}{type(e).__name__} ({e}) on attempt {attempt}/{max_retries} — retrying in 0.5s...", flush=True)
                time.sleep(0.5)
                continue
            print(f"[Ollama Call FAILED] <--- {tag}Exhausted {attempt}/{max_retries} attempts: {type(e).__name__}: {e} (elapsed={elapsed:.1f}s)", flush=True)
            break

    return None


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
    Generates 3 focused search engine queries to find REAL INDIVIDUAL COMPANIES
    operating in the specified industry.

    IMPORTANT: The service keyword (our_services) is deliberately NOT injected
    here — we are searching for companies IN the industry, not for companies
    that already advertise they need our specific service.
    """
    clean_industry = industry.strip()
    loc_suffix = f" in {location_str}" if location_str else ""

    prompt = f"""You are a B2B web search engineer. Generate 3 search engine queries to find REAL INDIVIDUAL OPERATING ENTITIES / COMPANIES in this target industry: "{clean_industry}".

STRICT RULES:
1. Queries must find actual entity/company homepages — NOT directories, rankings, listicles, aggregators, or market reports.
2. Target actual operating entities in "{clean_industry}". Do NOT add words like "supplier", "vendor", or "provider" unless the industry name itself explicitly specifies them.
3. Keep queries short and effective for search engines (4-7 words).
4. Append '{location_str}' to each query if a location is provided.

Return ONLY a bulleted list of 3 queries, one per line. No extra text.

Example for industry "Universities":
- university official website{loc_suffix}
- higher education institution official site{loc_suffix}
- college corporate homepage{loc_suffix}"""

    system_prompt = "You are a B2B search engineer. Return ONLY raw search queries, one per line, no preamble, no numbering."

    try:
        raw_output = call_ollama(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=120,
            timeout=7.0
        )
        if raw_output and len(raw_output.strip()) > 10:
            raw_lines = [line.strip() for line in raw_output.splitlines() if line.strip()]
            valid_queries = []
            preamble_words = ("here are", "sure,", "note:", "based on", "the following", "here is", "search queries", "example")

            for line in raw_lines:
                clean_l = re.sub(r'^[-*•\d.\s]+', '', line).strip()
                if any(clean_l.lower().startswith(pw) for pw in preamble_words) or clean_l.endswith(":"):
                    continue
                if len(clean_l) > 5:
                    valid_queries.append(clean_l)

            queries = valid_queries[:3]
            if queries:
                print(f"[Search Query Builder] Industry: '{clean_industry}' → {len(queries)} queries:")
                for idx, q in enumerate(queries, 1):
                    print(f"   Query #{idx}: '{q}'")
                return queries
    except Exception as e:
        print(f"[Search Query Builder] Ollama offline — using fallback queries: {e}")

    # Deterministic fallback — industry name only, no service keyword
    return [
        f"{clean_industry} official website{loc_suffix}",
        f"{clean_industry} corporate site{loc_suffix}",
        f"{clean_industry} homepage{loc_suffix}"
    ]


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
    company_id: int = 1
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

    # ── Query construction: industry-name ONLY — service keyword is NOT injected ─
    # We are finding companies IN the industry, not companies that already advertise
    # needing our service. The keyword here is the selected industry name.
    query_variations = generate_industry_search_queries(
        industry=clean_keyword,
        location_str=location_str
    )

    primary_query = query_variations[0]

    yield json.dumps({"type": "start", "query": primary_query, "target": target_count}) + "\n"

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

    for current_page in range(start_page, start_page + max_pages):
        if qualified_total >= target_count:
            print(f"\n[Discover] ✅ Target goal of {target_count} companies reached! Stopping discovery loop.")
            break

        active_query = query_variations[variation_idx % len(query_variations)]

        print(f"\n[Discover] ─── Page {current_page} (Goal: {qualified_total}/{target_count}) | Query: '{active_query}' ───")
        raw_results = await search_searxng_or_ddg(active_query, page=current_page)
        total_raw += len(raw_results)

        if not raw_results:
            print(f"[Discover] Page {current_page} returned 0 results for '{active_query}'. Rotating query variation...")
            variation_idx += 1
            active_query = query_variations[variation_idx % len(query_variations)]
            print(f"[Discover] Retrying with query variation: '{active_query}'")
            raw_results = await search_searxng_or_ddg(active_query, page=current_page)
            total_raw += len(raw_results)

        if not raw_results:
            print(f"[Discover] Query variation '{active_query}' also empty. Trying next variation...")
            variation_idx += 1
            continue

        page_candidates = []
        for item in raw_results:
            url = item.get('url', '')
            domain = clean_domain(url)

            if not domain:
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

            seen_domains.add(domain)
            page_candidates.append(item)

        if len(page_candidates) == 0:
            print(f"[Discover] Page {current_page} yielded 0 new candidates (all duplicate/filtered). Rotating query variation...")
            variation_idx += 1
            continue

        total_noise_passed += len(page_candidates)
        page_candidates_trimmed = page_candidates[:20]

        async def evaluate_and_emit(idx: int, item: dict):
            nonlocal qualified_total, total_ollama, total_groq
            async with semaphore:
                url = item.get('url', '')
                title = item.get('title', '')
                snippet = item.get('content', '') or item.get('snippet', '')
                domain = clean_domain(url)

                try:
                    company_name = extract_clean_company_name(title, domain)

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
                        "matchConfidence": confidence,
                        "trustScore": confidence,
                        "trustStatus": "Verified Company",
                        "email": primary_email,
                        "phone": primary_phone,
                        "phones": found_phones,
                        "emails": found_emails,
                        "linkedin": found_linkedin,
                        "leadType": lead_type.lower().replace("_", "_"),  # 'needs_service' or 'has_similar_service'
                        "source": source,
                        "dataSource": item_data_source,
                        "unverified": is_ai_generated
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

    effective_services = (
        getattr(current_company, "ai_enriched_profile", None)
        or current_company.services
        or current_company.description
        or "B2B Products & Services"
    )

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
            our_company=current_company.name,
            our_services=effective_services,
            target_customers=current_company.target_customers or "",
            description=current_company.description or "",
            industry=current_company.industry or "",
            company_id=current_company.id
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
    current_company: Company = Depends(get_current_company)
):
    if not keyword or not keyword.strip():
        raise HTTPException(status_code=400, detail="Keyword is required.")

    print(f"\n[FASTAPI BACKEND] 🚀 RECEIVED FRONTEND DISCOVER GET REQUEST: keyword='{keyword}' country='{country}' city='{city}' company='{current_company.name}'", flush=True)

    min_trust = minTrustScore if minTrustScore is not None else (min_trust_score or 0.0)
    conf = int(min_confidence or min_trust or 75)  # default raised: 60→75
    page_num = int(pageno or page or 1)

    effective_services = (
        getattr(current_company, "ai_enriched_profile", None)
        or current_company.services
        or current_company.description
        or "B2B Products & Services"
    )

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
            our_company=current_company.name,
            our_services=effective_services,
            target_customers=current_company.target_customers or "",
            description=current_company.description or "",
            industry=current_company.industry or "",
            company_id=current_company.id
        ),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}
    )
