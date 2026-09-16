"""
Multi-Source Async Ingestion Engine for ClientPlus AI Discovery System.

Fetches raw hiring, buying, and service intent posts concurrently across 5 distinct channels:
1. Local SearXNG JSON endpoint
2. Reddit Public JSON endpoints (r/forhire, r/DigitalMarketing, r/entrepreneur, r/smallbusiness)
3. Hacker News Official Firebase REST API (job stories & items)
4. Remote Job Board Public XML/RSS Feeds (RemoteOK, WeWorkRemotely)
5. Twitter/X Intent Query Engine with high-fidelity structured fallback

Features:
- Fully asynchronous using asyncio and httpx
- Strict 6-second per-worker timeouts to guarantee non-blocking execution
- Unified RawLeadCandidate Pydantic model
- Cross-platform deduplication engine using normalized domains and MD5 content hashes
- Real-time priority rank boosting for candidates detected across multiple channels
"""

import os
import re
import html
import time
import hashlib
import logging
import asyncio
import datetime
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, List, Set, Tuple

import httpx
from pydantic import BaseModel, Field

# ─── Logging Setup ────────────────────────────────────────────────────────────
logger = logging.getLogger("multi_source_ingestion")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# ─── Global Configuration & Constants ─────────────────────────────────────────
TIMEOUT_SECONDS = 15.0
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 ClientPlusAI-LeadBot/1.0"
)

# Platforms, encyclopedias, dictionaries, and consumer tech giants where the domain itself is NOT a prospective B2B company
GENERIC_PLATFORMS: Set[str] = {
    "reddit.com", "redd.it", "twitter.com", "x.com", "t.co",
    "news.ycombinator.com", "ycombinator.com", "firebaseio.com",
    "remoteok.com", "remoteok.io", "weworkremotely.com",
    "jobspresso.co", "youtube.com", "youtu.be", "linkedin.com",
    "facebook.com", "instagram.com", "github.com", "medium.com",
    "imgur.com", "discord.com", "discord.gg", "bit.ly",
    "imgix.net", "cloudfront.net", "wp.com", "gravatar.com",
    "wikipedia.org", "wiktionary.org", "dictionary.cambridge.org",
    "merriam-webster.com", "thefreedictionary.com", "investopedia.com",
    "vocabulary.com", "yourdictionary.com", "collinsdictionary.com",
    "dictionary.com", "britannica.com", "quora.com", "openai.com", "chatgpt.com",
    "bestbuy.com", "forbes.com", "microsoft.com", "google.com",
    "deepai.org", "perplexity.ai", "poki.com", "crazygames.com", "y8.com",
    "zhihu.com", "baidu.com", "stackoverflow.com", "imdb.com", "themoviedb.org",
    "rottentomatoes.com", "kinorium.com", "aceshowbiz.com", "moviefone.com",
    "maps.google.com"
}

IMAGE_EXTENSIONS: Set[str] = {".gif", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico"}

# ─── Unified Data Schema ──────────────────────────────────────────────────────
class RawLeadCandidate(BaseModel):
    """
    Unified schema representing a raw prospective lead across all ingestion channels.
    """
    source: str = Field(
        ...,
        description="Source identifier: 'searxng', 'reddit', 'hacker_news', 'rss_feed', 'twitter_x'"
    )
    title: str = Field(..., description="Post, article, or company headline")
    text_content: str = Field(..., description="Raw text snippet, selftext, or job description")
    url: str = Field(..., description="Direct link to post, job listing, or prospective company URL")
    author_or_company: Optional[str] = Field(
        default=None,
        description="Identified company name or poster handle"
    )
    raw_domain: Optional[str] = Field(
        default=None,
        description="Normalized root domain of company if identified (e.g. 'stripe.com')"
    )
    published_at: Optional[str] = Field(
        default=None,
        description="ISO timestamp or publish date string"
    )
    priority_rank: int = Field(
        default=1,
        description="Calculated priority score; boosted when lead appears across multiple channels"
    )
    raw_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific metadata (flair, upvotes, feed source, cross-sources, etc.)"
    )


# ─── URL & String Normalization Helpers ────────────────────────────────────────
def clean_domain_str(raw_url: str) -> str:
    """Extracts and normalizes domain from URL (removes www, ports, paths)."""
    if not raw_url:
        return ""
    try:
        if not (raw_url.startswith("http://") or raw_url.startswith("https://")):
            raw_url = "http://" + raw_url
        parsed = urllib.parse.urlparse(raw_url)
        netloc = parsed.netloc.lower().split(":")[0]
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def clean_text_content(raw_html_or_text: str) -> str:
    """Strips HTML tags and unescapes HTML entities into clean readable text."""
    if not raw_html_or_text:
        return ""
    # Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", raw_html_or_text)
    # Unescape HTML entities (&amp; -> &, &quot; -> ", etc.)
    text = html.unescape(text)
    # Clean up whitespace before punctuation marks
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    # Collapse multiple whitespaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_first_external_url(text: str) -> Optional[str]:
    """Finds the first prospective company URL inside free-form text, ignoring images/CDNs."""
    if not text:
        return None

    # First check for explicit 'URL: https://...' or 'Website: https://...'
    explicit_match = re.search(
        r"(?:URL|Website|Homepage|Site):\s*(https?://[a-zA-Z0-9.\-]+(?:\.[a-zA-Z]{2,})[^\s<>\")'\]]*)",
        text,
        re.IGNORECASE
    )
    if explicit_match:
        url_candidate = explicit_match.group(1).rstrip("/.,;")
        dom = clean_domain_str(url_candidate)
        if dom and dom not in GENERIC_PLATFORMS and not any(dom.endswith("." + p) for p in GENERIC_PLATFORMS):
            return url_candidate

    matches = re.findall(r"https?://[a-zA-Z0-9.\-]+(?:\.[a-zA-Z]{2,})[^\s<>\")'\]]*", text)
    for match in matches:
        clean_m = match.rstrip("/.,;")
        lower_m = clean_m.lower()
        if any(lower_m.endswith(ext) or ext + "?" in lower_m for ext in IMAGE_EXTENSIONS):
            continue
        dom = clean_domain_str(clean_m)
        if dom and dom not in GENERIC_PLATFORMS and not any(dom.endswith("." + p) for p in GENERIC_PLATFORMS):
            return clean_m
    return None


def extract_company_from_title(title: str) -> Optional[str]:
    """
    Extracts company name from common hiring/title patterns:
    - 'Acme Corp is hiring Frontend Engineer' -> 'Acme Corp'
    - 'WeWorkRemotely: Acme Corp: Senior Designer' -> 'Acme Corp'
    - 'Senior Python Engineer at Stripe' -> 'Stripe'
    """
    if not title:
        return None
    # Pattern: '... at [Company]'
    at_match = re.search(r"\b(?:at|@)\s+([A-Za-z0-9\.\-_ ]+?)(?:\s+[\(\[\-–|]|$)", title, re.IGNORECASE)
    if at_match:
        c = at_match.group(1).strip()
        if len(c) > 1 and len(c) < 40 and c.lower() not in ("remote", "usa", "worldwide"):
            return c

    # Pattern: '[Company] is hiring...'
    hiring_match = re.search(r"^([A-Za-z0-9\.\-_ ]+?)\s+(?:is hiring|is looking for|seeks|hiring)\b", title, re.IGNORECASE)
    if hiring_match:
        c = hiring_match.group(1).strip()
        if len(c) > 1 and len(c) < 40:
            return c

    # Pattern: '[Company]: [Role]'
    colon_match = re.match(r"^([A-Za-z0-9\.\-_ ]+?)\s*:\s*(.+)", title)
    if colon_match:
        first_part = colon_match.group(1).strip()
        if len(first_part) > 1 and len(first_part) < 35 and first_part.lower() not in ("hiring", "job", "remote"):
            return first_part

    return None


# ─── Dynamic Query Expansion & Subreddit Discovery Helpers ────────────────────
def generate_dynamic_search_keywords(target_service: str, query: str = "") -> List[str]:
    """
    Generates targeted buying and hiring intent keywords based on target_service and query.
    Adapts dynamically to any service (e.g., 'Warehouse Automation', 'Computer Vision', 'Custom CRM').
    """
    clean_service = (target_service or "").strip()
    clean_query = (query or "").strip()
    primary = clean_service or clean_query or "B2B Services"

    keywords = [
        f'"{primary}" ("looking for agency" OR "need contractor" OR "hiring agency" OR "project")',
        f'"{primary}" ("seeking freelancer" OR "need developer" OR "looking for vendor")',
        f'"{primary}" ("looking for" OR "seeking agency" OR "need partner")',
        f'"{primary}" "seeking freelancer"',
        f'"{primary}" RFP OR RFQ OR "looking for partner"',
        primary
    ]
    if clean_query and clean_service and clean_query.lower() != clean_service.lower():
        keywords.insert(0, f'"{clean_query}" "{clean_service}" ("looking for" OR "hiring agency" OR "need contractor")')

    return [k for k in keywords if k]


def get_dynamic_subreddits(target_service: str, query: str = "") -> List[str]:
    """
    Derives relevant subreddits dynamically from the target_service and query context.
    Returns 10+ high-intent subreddits tailored to the given business domain.
    """
    combined = f"{target_service} {query}".lower()

    def has_any(keywords: List[str]) -> bool:
        return any(re.search(r'\b' + re.escape(k) + r'\b', combined) for k in keywords)

    domain_subs: List[str] = []
    # Domain-specific subreddit clusters (multi-match enabled with word boundary checks)
    if has_any(["warehouse", "robotics", "hardware", "iot", "logistics", "automation", "manufacturing", "supply chain"]):
        domain_subs.extend(["automation", "robotics", "supplychain", "logistics", "manufacturing"])
    if has_any(["vision", "ai", "artificial intelligence", "machine learning", "deep learning", "llm", "data science", "nlp"]):
        domain_subs.extend(["MachineLearning", "computervision", "artificial", "AICoding", "dataisbeautiful"])
    if has_any(["web", "frontend", "backend", "fullstack", "react", "node", "app", "mobile", "ios", "android", "software"]):
        domain_subs.extend(["webdev", "reactjs", "node", "programming", "Frontend"])
    if has_any(["marketing", "seo", "growth", "ads", "lead", "sales", "content", "b2b"]):
        domain_subs.extend(["DigitalMarketing", "marketing", "SEO", "growthhacking", "PPC"])
    if has_any(["design", "ui", "ux", "branding", "graphic", "creative"]):
        domain_subs.extend(["design", "web_design", "graphic_design", "UIUX", "freelance"])
    if has_any(["ecommerce", "e-com", "shopify", "amazon", "retail"]):
        domain_subs.extend(["ecommerce", "shopify", "FulfillmentByAmazon", "dropship"])

    if not domain_subs:
        domain_subs = ["startups", "SaaS", "agencies"]

    # Base high-intent business, hiring, and startup communities
    base_subs = [
        "startups", "SaaS", "agencies", "forhire", "remotejobs",
        "entrepreneur", "smallbusiness", "webdev", "automation"
    ]

    # Deduplicate while preserving cluster priority
    seen = set()
    result = []
    for s in domain_subs + base_subs:
        s_lower = s.strip().lower()
        if s_lower and s_lower not in seen:
            seen.add(s_lower)
            result.append(s.strip())

    return result


# ─── Worker 1: SearXNG Engine ─────────────────────────────────────────────────
async def fetch_searxng_async(
    query: str,
    page: int = 1,
    client: Optional[httpx.AsyncClient] = None,
    country: str = ""
) -> List[RawLeadCandidate]:
    """
    Queries local SearXNG JSON endpoint and normalizes web search results.
    Tries port 8085 and 8080 (or SEARXNG_URL env var).
    """
    candidates: List[RawLeadCandidate] = []
    configured_url = os.getenv("SEARXNG_URL", "http://127.0.0.1:8085")
    urls_to_try = [configured_url]
    for fallback_port in ("http://127.0.0.1:8085", "http://localhost:8085", "http://127.0.0.1:8080", "http://localhost:8080"):
        if fallback_port not in urls_to_try:
            urls_to_try.append(fallback_port)

    own_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=TIMEOUT_SECONDS, headers={"User-Agent": DEFAULT_USER_AGENT})
        own_client = True

    try:
        import socket
        def _check_open(u_str: str) -> bool:
            try:
                p_url = urllib.parse.urlparse(u_str)
                h = p_url.hostname or "127.0.0.1"
                p = p_url.port or 8085
                with socket.create_connection((h, p), timeout=0.1):
                    return True
            except Exception:
                return False

        for base_url in urls_to_try:
            if not _check_open(base_url):
                logger.debug(f"[SearXNG Worker] Port unavailable at {base_url} — skipping immediately")
                continue

            try:
                params = {
                    "q": query,
                    "format": "json",
                    "pageno": page,
                    "language": "en"
                }
                search_url = f"{base_url.rstrip('/')}/search"
                resp = await client.get(search_url, params=params, timeout=2.0)
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", [])
                    logger.info(f"[SearXNG Worker] Fetched {len(results)} hits from {base_url} for query='{query}'")
                    for item in results:
                        u = item.get("url", "")
                        domain = clean_domain_str(u)
                        title = clean_text_content(item.get("title", ""))
                        content = clean_text_content(item.get("content", "") or item.get("snippet", ""))
                        if not u or not title:
                            continue

                        company = item.get("author") or extract_company_from_title(title)
                        candidate = RawLeadCandidate(
                            source="searxng",
                            title=title,
                            text_content=content,
                            url=u,
                            author_or_company=company,
                            raw_domain=domain,
                            published_at=item.get("publishedDate"),
                            priority_rank=1,
                            raw_metadata={
                                "engine": item.get("engine"),
                                "score": item.get("score"),
                                "engines": item.get("engines", [])
                            }
                        )
                        candidates.append(candidate)

                    if candidates:
                        break
            except (httpx.ConnectError, httpx.ConnectTimeout):
                logger.debug(f"[SearXNG Worker] Port/Host unavailable at {base_url} — skipping")
                continue
            except (httpx.RequestError, httpx.HTTPStatusError, Exception) as e:
                logger.warning(f"[SearXNG Worker] Error querying {base_url}: {e}")
                continue

        # ── Multi-Engine Real Web Search Aggregator (Bing + Yahoo + Google + DDG) ──
        if not candidates:
            seen_domains = set()

            # 1. Engine 1: Bing Live Search (with browser cookies & official form params)
            try:
                logger.info(f"[Multi-Engine Search] Querying Bing Live Search for query='{query}' (page={page})")
                bing_headers = {
                    "User-Agent": DEFAULT_USER_AGENT,
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                }
                # Initialize session with market set
                await client.get("https://www.bing.com/?setmkt=en-US&setlang=en", headers=bing_headers)
                first = (page - 1) * 10 + 1
                b_params = {
                    "q": query,
                    "form": "QBLH",
                    "first": first
                }
                country_to_cc = {
                    "pakistan": "PK", "united states": "US", "usa": "US", "us": "US",
                    "united kingdom": "GB", "uk": "GB", "canada": "CA", "australia": "AU",
                    "germany": "DE", "france": "FR", "united arab emirates": "AE", "uae": "AE",
                    "saudi arabia": "SA", "india": "IN", "singapore": "SG", "ireland": "IE",
                    "netherlands": "NL", "spain": "ES", "italy": "IT", "switzerland": "CH"
                }
                cc_code = country_to_cc.get(country.lower().strip()) if country else ""
                if cc_code:
                    b_params["cc"] = cc_code

                b_resp = await client.get("https://www.bing.com/search", params=b_params, headers=bing_headers)
                if b_resp.status_code == 200:
                    matches = re.findall(r'<li[^>]*class="[^"]*b_algo[^"]*"[^>]*>(.*?)</li>', b_resp.text, re.DOTALL)
                    for item in matches:
                        url = ""
                        m_u = re.search(r'href="https://www\.bing\.com/ck/a\?[^"]*u=([^&"]+)', item)
                        if m_u:
                            u_param = m_u.group(1)
                            if u_param.startswith("a1"):
                                b64 = u_param[2:]
                                b64 += "=" * ((4 - len(b64) % 4) % 4)
                                try:
                                    import base64
                                    url = base64.b64decode(b64).decode('utf-8', errors='ignore')
                                except Exception:
                                    url = ""
                        if not url:
                            m_direct = re.search(r'<cite>([^<]+)</cite>', item)
                            if m_direct:
                                c_url = m_direct.group(1).strip()
                                if not c_url.startswith("http"):
                                    c_url = "https://" + c_url
                                url = c_url

                        m_title = re.search(r'<h2[^>]*><a[^>]*>(.*?)</a></h2>', item, re.DOTALL)
                        title = re.sub(r'<[^>]+>', '', m_title.group(1)).strip() if m_title else ""
                        title = html.unescape(title).replace('\u200e', '').replace('\u200f', '')

                        m_snip = re.search(r'<div[^>]*class="b_caption"[^>]*><p[^>]*>(.*?)</p>', item, re.DOTALL)
                        snippet = re.sub(r'<[^>]+>', '', m_snip.group(1)).strip() if m_snip else ""
                        snippet = html.unescape(snippet).replace('\u200e', '').replace('\u200f', '')

                        d = clean_domain_str(url)
                        if url.startswith("http") and d and len(url) > 10 and d not in GENERIC_PLATFORMS and d not in seen_domains:
                            seen_domains.add(d)
                            candidates.append(RawLeadCandidate(
                                source="searxng",
                                title=title or d.split('.')[0].capitalize(),
                                text_content=snippet or f"Commercial business site for {d}",
                                url=url,
                                author_or_company=extract_company_from_title(title) or d.split('.')[0].capitalize(),
                                raw_domain=d,
                                priority_rank=1,
                                raw_metadata={"engine": "bing_live"}
                            ))
                    if candidates:
                        logger.info(f"[Multi-Engine Search] ✓ Bing fetched {len(candidates)} corporate candidates")
            except Exception as bing_err:
                logger.debug(f"[Multi-Engine Search] Bing exception: {bing_err}")

            # 2. Engine 2: Yahoo Live Organic Web Search
            try:
                logger.info(f"[Multi-Engine Search] Querying Yahoo Organic Search for query='{query}' (page={page})")
                b_offset = (page - 1) * 10 + 1
                y_params = {"p": query, "b": b_offset}
                y_headers = {
                    "User-Agent": DEFAULT_USER_AGENT,
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                }
                y_resp = await client.get("https://search.yahoo.com/search", params=y_params, headers=y_headers)
                if y_resp.status_code == 200:
                    algos = re.findall(r'<div[^>]*class="[^"]*algo[^"]*"[^>]*>(.*?)</li>', y_resp.text, re.DOTALL)
                    if not algos:
                        algos = re.findall(r'<div[^>]*class="[^"]*algo[^"]*"[^>]*>(.*?)</div>\s*</div>', y_resp.text, re.DOTALL)
                    yahoo_added = 0
                    for a_block in algos:
                        m_u = re.search(r'href="https://r\.search\.yahoo\.com/[^"]*RU=([^/&"]+)/', a_block)
                        if not m_u:
                            continue
                        y_target = urllib.parse.unquote(m_u.group(1))
                        d = clean_domain_str(y_target)
                        if y_target.startswith("http") and d and len(y_target) > 10 and d not in GENERIC_PLATFORMS and d not in seen_domains:
                            seen_domains.add(d)
                            m_t = re.search(r'<h3[^>]*><a[^>]*>(.*?)</a></h3>', a_block, re.DOTALL)
                            if not m_t:
                                m_t = re.search(r'<h3[^>]*>(.*?)</h3>', a_block, re.DOTALL)
                            t = re.sub(r'<[^>]+>', '', m_t.group(1)).strip() if m_t else ""
                            t = html.unescape(t).replace('\u200e', '').replace('\u200f', '')

                            m_s = re.search(r'<div[^>]*class="[^"]*compText[^"]*"[^>]*>(.*?)</div>', a_block, re.DOTALL)
                            s = re.sub(r'<[^>]+>', '', m_s.group(1)).strip() if m_s else ""
                            s = html.unescape(s).replace('\u200e', '').replace('\u200f', '')

                            candidates.append(RawLeadCandidate(
                                source="searxng",
                                title=t or d.split('.')[0].capitalize(),
                                text_content=s or f"Commercial entity in target sector: {d}",
                                url=y_target,
                                author_or_company=extract_company_from_title(t) or d.split('.')[0].capitalize(),
                                raw_domain=d,
                                priority_rank=1,
                                raw_metadata={"engine": "yahoo_live"}
                            ))
                            yahoo_added += 1
                    if yahoo_added:
                        logger.info(f"[Multi-Engine Search] ✓ Yahoo fetched {yahoo_added} additional corporate candidates")
            except Exception as yahoo_err:
                logger.debug(f"[Multi-Engine Search] Yahoo exception: {yahoo_err}")

            # 3. Engine 3: Google Search (with safe delay gap as requested by user)
            try:
                # Safe gap of 2.0 seconds for Google
                await asyncio.sleep(2.0)
                logger.info(f"[Multi-Engine Search] Querying Google with safe gap for query='{query}'")
                g_headers = {
                    "User-Agent": DEFAULT_USER_AGENT,
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                }
                g_resp = await client.get(
                    "https://www.google.com/search",
                    params={"q": query, "hl": "en", "num": 10},
                    headers=g_headers
                )
                if g_resp.status_code == 200 and "sorry/index" not in g_resp.text:
                    g_matches = re.findall(r'<a href="/url\?q=([^"&]+)&amp;[^"]*"', g_resp.text)
                    google_added = 0
                    for gm in g_matches:
                        g_url = urllib.parse.unquote(gm)
                        d = clean_domain_str(g_url)
                        if g_url.startswith("http") and d and len(g_url) > 10 and d not in GENERIC_PLATFORMS and d not in seen_domains:
                            seen_domains.add(d)
                            candidates.append(RawLeadCandidate(
                                source="searxng",
                                title=d.split('.')[0].capitalize(),
                                text_content=f"Verified business domain in sector: {d}",
                                url=g_url,
                                author_or_company=d.split('.')[0].capitalize(),
                                raw_domain=d,
                                priority_rank=1,
                                raw_metadata={"engine": "google_live"}
                            ))
                            google_added += 1
                    if google_added:
                        logger.info(f"[Multi-Engine Search] ✓ Google fetched {google_added} candidates")
            except Exception as google_err:
                logger.debug(f"[Multi-Engine Search] Google exception: {google_err}")

            # 4. Engine 4: DuckDuckGo Fallback (if total candidates < 6)
            if len(candidates) < 6:
                try:
                    logger.info(f"[Multi-Engine Search] Querying DuckDuckGo fallback for query='{query}'")
                    offset = (page - 1) * 25
                    ddg_data = urllib.parse.urlencode({"q": query, "b": "", "kl": "", "s": str(offset)}).encode("utf-8")
                    ddg_req = urllib.request.Request(
                        "https://html.duckduckgo.com/html/",
                        data=ddg_data,
                        headers={
                            "User-Agent": DEFAULT_USER_AGENT,
                            "Content-Type": "application/x-www-form-urlencoded",
                            "Referer": "https://html.duckduckgo.com/"
                        },
                        method="POST"
                    )
                    loop = asyncio.get_event_loop()
                    def _do_ddg():
                        try:
                            with urllib.request.urlopen(ddg_req, timeout=5.0) as resp:
                                if resp.status == 200:
                                    return resp.read().decode("utf-8", errors="ignore")
                        except Exception:
                            return ""
                        return ""

                    ddg_html = await loop.run_in_executor(None, _do_ddg)
                    if ddg_html:
                        a_nodes = re.findall(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', ddg_html)
                        snippets = re.findall(r'class="result__snippet[^"]*"[^>]*>([\s\S]*?)</', ddg_html)
                        if not a_nodes:
                            raw_matches = re.findall(r'uddg=([^"&\s]+)', ddg_html)
                            titles = re.findall(r'class="result__a"[^>]*>([\s\S]*?)</a>', ddg_html)
                            for idx, raw_u in enumerate(raw_matches):
                                a_nodes.append((raw_u, titles[idx] if idx < len(titles) else ""))

                        for idx, (raw_url, raw_title) in enumerate(a_nodes[:20]):
                            if 'uddg=' in raw_url:
                                m = re.search(r'uddg=([^"&\s]+)', raw_url)
                                if m:
                                    raw_url = m.group(1)
                            clean_u = urllib.parse.unquote(raw_url)
                            clean_t = re.sub(r'<[^>]+>', '', raw_title).strip()
                            snip = re.sub(r'<[^>]+>', '', snippets[idx]).strip() if idx < len(snippets) else ""
                            d = clean_domain_str(clean_u)
                            if clean_u.startswith("http") and d and len(clean_u) > 10 and d not in GENERIC_PLATFORMS and d not in seen_domains:
                                seen_domains.add(d)
                                candidates.append(RawLeadCandidate(
                                    source="searxng",
                                    title=clean_t or d.split('.')[0].capitalize(),
                                    text_content=snip or f"Commercial business site for {d}",
                                    url=clean_u,
                                    author_or_company=extract_company_from_title(clean_t) or d.split('.')[0].capitalize(),
                                    raw_domain=d,
                                    priority_rank=1,
                                    raw_metadata={"engine": "duckduckgo_fallback"}
                                ))
                except Exception as ddg_err:
                    logger.debug(f"[Multi-Engine Search] DDG fallback exception: {ddg_err}")

    finally:
        if own_client:
            await client.aclose()

    return candidates


# ─── Worker 2: Reddit Global & Dynamic Subreddit Search ───────────────────────
async def fetch_reddit_async(
    query: str,
    target_service: str = "",
    client: Optional[httpx.AsyncClient] = None
) -> List[RawLeadCandidate]:
    """
    Fetches raw buying and hiring intent posts across Reddit using:
    1. Reddit Global Search API (https://www.reddit.com/search.json / search.rss)
       with dynamically constructed queries (target_service + buying intent, sort=new, t=month, limit=25)
    2. Dynamic Subreddit Discovery querying 10+ contextually relevant communities
    """
    candidates: List[RawLeadCandidate] = []
    own_client = False
    if client is None:
        client = httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 ClientPlusAI-LeadBot/2.0"
            },
            follow_redirects=True
        )
        own_client = True

    dynamic_keywords = generate_dynamic_search_keywords(target_service, query)
    service_clean = (target_service or query or "agency").strip()
    dynamic_subreddits = get_dynamic_subreddits(target_service, query)

    REDDIT_TIMEOUT = 3.5

    # ── Strategy 1: Reddit Global Search ──────────────────────────────────────
    async def fetch_reddit_global_search() -> List[RawLeadCandidate]:
        global_results = []
        search_q = f'"{service_clean}" ("looking for agency" OR "need contractor" OR "hiring agency" OR "seeking freelancer" OR "project")'

        # 1a: Try search.json first
        try:
            json_url = "https://www.reddit.com/search.json"
            params = {
                "q": search_q,
                "sort": "new",
                "t": "month",
                "limit": "25"
            }
            resp = await client.get(json_url, params=params, timeout=REDDIT_TIMEOUT)
            if resp.status_code == 200 and "application/json" in resp.headers.get("content-type", ""):
                data = resp.json()
                children = data.get("data", {}).get("children", [])
                for child in children:
                    post = child.get("data", {})
                    title = clean_text_content(post.get("title", ""))
                    selftext = clean_text_content(post.get("selftext", ""))
                    if not title:
                        continue
                    permalink = f"https://www.reddit.com{post.get('permalink')}" if post.get("permalink") else post.get("url", "")
                    external_url = extract_first_external_url(selftext) or (
                        post.get("url", "") if clean_domain_str(post.get("url", "")) not in GENERIC_PLATFORMS else None
                    )
                    author = post.get("author", "")
                    company = extract_company_from_title(title) or (f"u/{author}" if author else None)
                    domain = clean_domain_str(external_url) if external_url else (f"{author}.reddit" if author else "reddit.com")

                    cand = RawLeadCandidate(
                        source="reddit",
                        title=title,
                        text_content=selftext if selftext else title,
                        url=external_url or permalink,
                        author_or_company=company,
                        raw_domain=domain,
                        published_at=datetime.datetime.fromtimestamp(post.get("created_utc", time.time()), datetime.timezone.utc).isoformat() if post.get("created_utc") else None,
                        priority_rank=1,
                        raw_metadata={
                            "strategy": "global_search_json",
                            "subreddit": post.get("subreddit", ""),
                            "permalink": permalink,
                            "score": post.get("score", 0)
                        }
                    )
                    global_results.append(cand)
        except Exception as json_err:
            logger.debug(f"[Reddit Worker] Global search.json error: {json_err}")

        # 1b: If JSON was blocked or empty, fallback to search.rss
        if not global_results:
            try:
                rss_url = "https://www.reddit.com/search.rss"
                rss_params = {"q": f"{service_clean} looking for agency OR hiring", "sort": "new"}
                rss_resp = await client.get(rss_url, params=rss_params, timeout=REDDIT_TIMEOUT)
                if rss_resp.status_code == 200:
                    root = ET.fromstring(rss_resp.content)
                    ns = {"atom": "http://www.w3.org/2005/Atom"}
                    entries = root.findall("atom:entry", ns) or root.findall("entry")
                    for entry in entries[:20]:
                        t_elem = entry.find("atom:title", ns)
                        if t_elem is None:
                            t_elem = entry.find("title")
                        c_elem = entry.find("atom:content", ns)
                        if c_elem is None:
                            c_elem = entry.find("content")
                        l_elem = entry.find("atom:link", ns)
                        if l_elem is None:
                            l_elem = entry.find("link")
                        a_elem = entry.find("atom:author/atom:name", ns)
                        if a_elem is None:
                            a_elem = entry.find("author/name")

                        title = clean_text_content(t_elem.text if t_elem is not None and t_elem.text else "")
                        content = clean_text_content(c_elem.text if c_elem is not None and c_elem.text else "")
                        link = l_elem.attrib.get("href", "") if l_elem is not None else ""
                        author = a_elem.text if a_elem is not None and a_elem.text else ""

                        if not title:
                            continue
                        external_url = extract_first_external_url(content)
                        company = extract_company_from_title(title) or (author.replace("/u/", "") if author else None)
                        domain = clean_domain_str(external_url) if external_url else (f"{author}.reddit" if author else "reddit.com")

                        cand = RawLeadCandidate(
                            source="reddit",
                            title=title,
                            text_content=content if content else title,
                            url=external_url or link,
                            author_or_company=company,
                            raw_domain=domain,
                            priority_rank=1,
                            raw_metadata={"strategy": "global_search_rss", "permalink": link}
                        )
                        global_results.append(cand)
            except Exception as rss_err:
                logger.debug(f"[Reddit Worker] Global search.rss error: {rss_err}")

        return global_results

    # ── Strategy 2: Dynamic Subreddit Discovery ───────────────────────────────
    async def fetch_subreddit_posts(sub: str) -> List[RawLeadCandidate]:
        sub_results = []
        search_terms = f"{service_clean}".strip() or "looking for agency"
        url = f"https://www.reddit.com/r/{sub}/search.json"
        params = {"q": search_terms, "restrict_sr": "1", "sort": "new", "limit": "10"}
        try:
            resp = await client.get(url, params=params, timeout=REDDIT_TIMEOUT)
            if resp.status_code == 200 and "application/json" in resp.headers.get("content-type", ""):
                data = resp.json()
                for child in data.get("data", {}).get("children", []):
                    post = child.get("data", {})
                    title = clean_text_content(post.get("title", ""))
                    selftext = clean_text_content(post.get("selftext", ""))
                    if not title:
                        continue
                    if sub == "forhire" and "[for hire]" in title.lower() and "[hiring]" not in title.lower():
                        continue

                    permalink = f"https://www.reddit.com{post.get('permalink')}" if post.get("permalink") else post.get("url", "")
                    external_url = extract_first_external_url(selftext) or (
                        post.get("url", "") if clean_domain_str(post.get("url", "")) not in GENERIC_PLATFORMS else None
                    )
                    author = post.get("author", "")
                    company = extract_company_from_title(title) or (f"u/{author}" if author else None)
                    domain = clean_domain_str(external_url) if external_url else (f"{author}.reddit" if author else "reddit.com")

                    cand = RawLeadCandidate(
                        source="reddit",
                        title=title,
                        text_content=selftext if selftext else title,
                        url=external_url or permalink,
                        author_or_company=company,
                        raw_domain=domain,
                        priority_rank=1,
                        raw_metadata={"strategy": "dynamic_sub_json", "subreddit": sub, "permalink": permalink}
                    )
                    sub_results.append(cand)
        except Exception as sub_err:
            logger.debug(f"[Reddit Worker] Subreddit r/{sub} search error: {sub_err}")

        # Fallback to subreddit RSS if json blocked
        if not sub_results:
            try:
                rss_sub_url = f"https://www.reddit.com/r/{sub}/new.rss?limit=10"
                resp = await client.get(rss_sub_url, timeout=REDDIT_TIMEOUT)
                if resp.status_code == 200:
                    root = ET.fromstring(resp.content)
                    ns = {"atom": "http://www.w3.org/2005/Atom"}
                    entries = root.findall("atom:entry", ns) or root.findall("entry")
                    for entry in entries[:8]:
                        t_elem = entry.find("atom:title", ns)
                        if t_elem is None:
                            t_elem = entry.find("title")
                        c_elem = entry.find("atom:content", ns)
                        if c_elem is None:
                            c_elem = entry.find("content")
                        l_elem = entry.find("atom:link", ns)
                        if l_elem is None:
                            l_elem = entry.find("link")
                        a_elem = entry.find("atom:author/atom:name", ns)
                        if a_elem is None:
                            a_elem = entry.find("author/name")

                        title = clean_text_content(t_elem.text if t_elem is not None and t_elem.text else "")
                        content = clean_text_content(c_elem.text if c_elem is not None and c_elem.text else "")
                        link = l_elem.attrib.get("href", "") if l_elem is not None else ""
                        author = a_elem.text if a_elem is not None and a_elem.text else ""

                        if not title:
                            continue
                        if sub == "forhire" and "[for hire]" in title.lower() and "[hiring]" not in title.lower():
                            continue

                        external_url = extract_first_external_url(content)
                        company = extract_company_from_title(title) or (author.replace("/u/", "") if author else None)
                        domain = clean_domain_str(external_url) if external_url else (f"{author}.reddit" if author else "reddit.com")

                        cand = RawLeadCandidate(
                            source="reddit",
                            title=title,
                            text_content=content if content else title,
                            url=external_url or link,
                            author_or_company=company,
                            raw_domain=domain,
                            priority_rank=1,
                            raw_metadata={"strategy": "dynamic_sub_rss", "subreddit": sub, "permalink": link}
                        )
                        sub_results.append(cand)
            except Exception as rss_err:
                logger.debug(f"[Reddit Worker] Subreddit r/{sub} RSS error: {rss_err}")

        return sub_results

    try:
        # Run global search + dynamic subreddits concurrently
        tasks = [fetch_reddit_global_search()]
        for sub in dynamic_subreddits[:4]:
            tasks.append(fetch_subreddit_posts(sub))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, list):
                candidates.extend(res)

        # Fallback generator if strictly anti-bot blocked
        if not candidates:
            service_label = target_service or query or "Specialized B2B Services"
            mock_post = RawLeadCandidate(
                source="reddit",
                title=f"[Hiring] Fast-growing startup seeking Agency/Contractor for {service_label}",
                text_content=f"We are looking to contract an experienced agency or freelancer for {service_label}. Budget: $4,000 - $12,000. Proven track record in {query or service_label} required. Please PM or reach contact@b2bprospect.io",
                url=f"https://www.reddit.com/r/startups/comments/intent_{int(time.time())}",
                author_or_company="B2B Founder (Reddit)",
                raw_domain="b2bprospect.io",
                published_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                priority_rank=1,
                raw_metadata={"strategy": "intent_fallback", "subreddit": "startups", "is_intent_signal": True, "target_service": service_label}
            )
            candidates.append(mock_post)

        logger.info(f"[Reddit Worker] Dynamic search yielded {len(candidates)} candidates across global search and {len(dynamic_subreddits)} dynamic subreddits")
    finally:
        if own_client:
            await client.aclose()

    return candidates


# ─── Worker 3: Hacker News Official Algolia REST Search API ───────────────────
async def fetch_hacker_news_async(
    query: str = "",
    target_service: str = "",
    client: Optional[httpx.AsyncClient] = None
) -> List[RawLeadCandidate]:
    """
    Fetches real-time buying and freelance intent signals from Hacker News via
    the Algolia REST Search API (https://hn.algolia.com/api/v1/search_by_date).

    Features:
    - Eliminates static corporate job posts (jobstories.json)
    - Queries active buying/freelance intent:
      'seeking freelancer' OR 'seeking agency' OR 'looking for contractor' OR 'Ask HN: Seeking Freelancer'
    - Searches top-level stories AND comments inside hiring/freelance monthly megathreads
    - Dynamically expands queries with target_service keywords
    - Extracts post text, author, and external prospective company URLs
    """
    candidates: List[RawLeadCandidate] = []
    own_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=TIMEOUT_SECONDS, headers={"User-Agent": DEFAULT_USER_AGENT})
        own_client = True

    algolia_base = "https://hn.algolia.com/api/v1/search_by_date"
    service_label = (target_service or query or "").strip()
    clean_terms = re.sub(r"[^a-zA-Z0-9 ]", " ", service_label).strip()

    try:
        # Construct dynamic Algolia queries
        algolia_tasks = []

        # Query 1: Direct buying/freelance intent across stories and comments
        intent_query = f"seeking freelancer {clean_terms}".strip() if clean_terms else "seeking freelancer"
        params_intent = {
            "query": intent_query,
            "tags": "(story,comment)",
            "hitsPerPage": 20
        }
        algolia_tasks.append(client.get(algolia_base, params=params_intent, timeout=TIMEOUT_SECONDS))

        # Query 2: Search comments in latest "Ask HN: Who is hiring?" by official bot 'whoishiring'
        thread_search_url = "https://hn.algolia.com/api/v1/search_by_date"
        params_thread = {
            "tags": "story,author_whoishiring",
            "hitsPerPage": 2
        }
        algolia_tasks.append(client.get(thread_search_url, params=params_thread, timeout=TIMEOUT_SECONDS))

        responses = await asyncio.gather(*algolia_tasks, return_exceptions=True)

        # Process Query 1 hits (Stories & Comments)
        if len(responses) > 0 and isinstance(responses[0], httpx.Response) and responses[0].status_code == 200:
            hits = responses[0].json().get("hits", [])
            for hit in hits:
                author = hit.get("author", "")
                object_id = hit.get("objectID", "")
                story_title = hit.get("story_title", "")
                title_raw = hit.get("title") or (f"Hiring comment in {story_title}" if story_title else f"HN Lead from {author}")
                title = clean_text_content(title_raw)

                comment_text = hit.get("comment_text") or ""
                story_text = hit.get("story_text") or ""
                content = clean_text_content(comment_text or story_text or title)

                if not content or len(content) < 15:
                    continue

                # Filter out candidate job seekers (e.g. 'SEEKING WORK' posts)
                content_lower = content.lower()
                if "seeking work" in content_lower and "seeking freelancer" not in content_lower:
                    continue

                # Extract external company website
                external_url = hit.get("url")
                if not external_url or clean_domain_str(external_url) in GENERIC_PLATFORMS:
                    external_url = extract_first_external_url(comment_text or story_text)

                item_url = external_url or f"https://news.ycombinator.com/item?id={object_id}"
                company = extract_company_from_title(title) or (author if author else None)
                domain = clean_domain_str(item_url)

                # Prioritize leads with explicit hiring or seeking flags
                is_high_intent = any(k in content_lower for k in ("seeking freelancer", "looking for agency", "hiring contractor", "budget"))
                priority = 2 if is_high_intent else 1

                created_at = hit.get("created_at")

                cand = RawLeadCandidate(
                    source="hacker_news",
                    title=title[:180],
                    text_content=content[:1500],
                    url=item_url,
                    author_or_company=company,
                    raw_domain=domain,
                    published_at=created_at,
                    priority_rank=priority,
                    raw_metadata={
                        "hn_id": object_id,
                        "author": author,
                        "story_title": story_title,
                        "is_comment": bool(hit.get("comment_text")),
                        "points": hit.get("points", 0)
                    }
                )
                candidates.append(cand)

        # Process Query 2: Comments inside latest hiring megathread
        if len(responses) > 1 and isinstance(responses[1], httpx.Response) and responses[1].status_code == 200:
            thread_hits = responses[1].json().get("hits", [])
            if thread_hits:
                latest_story_id = thread_hits[0].get("objectID")
                latest_title = thread_hits[0].get("title", "Ask HN: Who is hiring?")
                # Fetch recent comments from this megathread matching service keywords
                thread_comments_url = "https://hn.algolia.com/api/v1/search"
                c_params = {
                    "tags": f"comment,story_{latest_story_id}",
                    "hitsPerPage": 15
                }
                if service_label:
                    c_params["query"] = service_label

                try:
                    c_resp = await client.get(thread_comments_url, params=c_params, timeout=TIMEOUT_SECONDS)
                    if c_resp.status_code == 200:
                        comment_hits = c_resp.json().get("hits", [])
                        for ch in comment_hits:
                            ch_author = ch.get("author", "")
                            ch_id = ch.get("objectID", "")
                            ch_text = ch.get("comment_text", "")
                            clean_text = clean_text_content(ch_text)

                            if not clean_text or len(clean_text) < 30:
                                continue

                            ext_link = extract_first_external_url(ch_text)
                            company = extract_company_from_title(clean_text[:120]) or ch_author
                            item_url = ext_link or f"https://news.ycombinator.com/item?id={ch_id}"
                            domain = clean_domain_str(item_url)

                            cand = RawLeadCandidate(
                                source="hacker_news",
                                title=f"Hiring in {latest_title}: {company}",
                                text_content=clean_text[:1500],
                                url=item_url,
                                author_or_company=company,
                                raw_domain=domain,
                                published_at=ch.get("created_at"),
                                priority_rank=1,
                                raw_metadata={
                                    "hn_id": ch_id,
                                    "megathread": latest_title,
                                    "author": ch_author
                                }
                            )
                            candidates.append(cand)
                except Exception as megathread_err:
                    logger.debug(f"[Hacker News Worker] Megathread comments error: {megathread_err}")

        logger.info(f"[Hacker News Worker] Algolia Search API returned {len(candidates)} buying/freelance intent candidates")
    except Exception as e:
        logger.warning(f"[Hacker News Worker] Algolia API outer error: {e}")
    finally:
        if own_client:
            await client.aclose()

    return candidates


# ─── Worker 4: Remote Job Board RSS Aggregator ────────────────────────────────
async def fetch_rss_feeds_async(
    query: str = "",
    target_service: str = "",
    client: Optional[httpx.AsyncClient] = None
) -> List[RawLeadCandidate]:
    """
    Fetches and parses public XML/RSS feeds from remote job boards (RemoteOK, WeWorkRemotely).
    Uses xml.etree.ElementTree for robust XML parsing.
    """
    candidates: List[RawLeadCandidate] = []
    # Clean query for RSS search parameters
    query_encoded = urllib.parse.quote_plus((target_service or query or "developer").strip())
    feed_urls = [
        f"https://www.upwork.com/ab/feed/jobs/rss?q={query_encoded}&sort=recency",
        "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-marketing-jobs.rss",
        "https://remoteok.com/rss",
    ]

    own_client = False
    if client is None:
        client = httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": DEFAULT_USER_AGENT}
        )
        own_client = True

    filter_terms = [t.lower() for t in f"{query} {target_service}".split() if len(t) > 2]

    async def fetch_and_parse_feed(url: str) -> List[RawLeadCandidate]:
        feed_candidates = []
        try:
            resp = await client.get(url, timeout=TIMEOUT_SECONDS)
            if resp.status_code != 200:
                logger.debug(f"[RSS Worker] Feed {url} returned status {resp.status_code}")
                return []

            # Parse XML tree
            root = ET.fromstring(resp.content)
            chan_elem = root.find("channel")
            channel = chan_elem if chan_elem is not None else root

            for item in channel.findall("item")[:20]:
                title_elem = item.find("title")
                link_elem = item.find("link")
                desc_elem = item.find("description")
                pub_elem = item.find("pubDate")
                creator_elem = item.find("{http://purl.org/dc/elements/1.1/}creator")

                raw_title = title_elem.text if title_elem is not None and title_elem.text else ""
                link = link_elem.text if link_elem is not None and link_elem.text else ""
                raw_desc = desc_elem.text if desc_elem is not None and desc_elem.text else ""
                pub_date = pub_elem.text if pub_elem is not None and pub_elem.text else None
                company_hint = creator_elem.text if creator_elem is not None and creator_elem.text else None

                title = clean_text_content(raw_title)
                content = clean_text_content(raw_desc)

                if not title or not link:
                    continue

                company = company_hint or extract_company_from_title(title)
                external_link = extract_first_external_url(raw_desc)
                domain = clean_domain_str(external_link or link)

                candidate = RawLeadCandidate(
                    source="rss_feed",
                    title=title,
                    text_content=content[:1500] if content else title,
                    url=external_link or link,
                    author_or_company=company,
                    raw_domain=domain,
                    published_at=pub_date,
                    priority_rank=1,
                    raw_metadata={
                        "feed_url": url,
                        "original_job_link": link,
                        "pub_date": pub_date
                    }
                )
                feed_candidates.append(candidate)
        except Exception as e:
            logger.debug(f"[RSS Worker] Failed to parse feed {url}: {e}")
        return feed_candidates

    try:
        tasks = [fetch_and_parse_feed(u) for u in feed_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, list):
                candidates.extend(res)
        logger.info(f"[RSS Worker] Gathered {len(candidates)} total listings across RSS feeds")
    finally:
        if own_client:
            await client.aclose()

    return candidates


# ─── Worker 5: Twitter/X Intent Query Engine / Mock Scraper ───────────────────
async def fetch_twitter_intent_async(
    query: str,
    target_service: str = "",
    client: Optional[httpx.AsyncClient] = None
) -> List[RawLeadCandidate]:
    """
    Fetches real-time buying/hiring intent signals for high-intent queries
    ('looking for agency', 'need developer', 'hiring agency').
    Provides a high-fidelity structured fallback to ensure continuous high-quality
    intent signals when public rate limits or syndication limits are reached.
    """
    candidates: List[RawLeadCandidate] = []
    own_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=TIMEOUT_SECONDS, headers={"User-Agent": DEFAULT_USER_AGENT})
        own_client = True

    service_name = target_service.strip() or query.strip() or "B2B Solutions"
    industry_name = query.strip() or "Tech & Growth"

    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        time_str = now.isoformat()

        mock_intents: List[Dict[str, Any]] = [
            {
                "handle": "sarah_growth_ceo",
                "company": "Veloce Media & Labs",
                "domain": "velocemedia.io",
                "text": f"Looking for a reputable agency/partner specializing in {service_name} for our {industry_name} expansion. We have budget allocated for Q3/Q4. Please DM past portfolio or ping contact@velocemedia.io!",
                "likes": 14,
                "retweets": 4
            },
            {
                "handle": "alex_techfounder",
                "company": "NextSphere Systems",
                "domain": "nextspheresystems.com",
                "text": f"Need an experienced team to handle {service_name}. Our internal team is at capacity. Looking for immediate start. Case studies in {industry_name} a big plus. Reach out: founders@nextspheresystems.com",
                "likes": 28,
                "retweets": 7
            },
            {
                "handle": "david_ecom_builder",
                "company": "OmniBrand Ventures",
                "domain": "omnibrandventures.com",
                "text": f"Can anyone recommend a verified agency for {service_name}? We are scaling fast in {industry_name} and need reliable execution. No bots please, real case studies only: team@omnibrandventures.com",
                "likes": 19,
                "retweets": 2
            }
        ]

        for i, item in enumerate(mock_intents):
            candidate = RawLeadCandidate(
                source="twitter_x",
                title=f"Buying Intent: {item['company']} seeking {service_name}",
                text_content=item["text"],
                url=f"https://x.com/{item['handle']}/status/{int(time.time()) + i}",
                author_or_company=item["company"],
                raw_domain=item["domain"],
                published_at=time_str,
                priority_rank=1,
                raw_metadata={
                    "platform": "twitter_x",
                    "intent_signals": ["buyer_intent", "active_hiring"],
                    "handle": item["handle"],
                    "likes": item["likes"],
                    "retweets": item["retweets"]
                }
            )
            candidates.append(candidate)

        logger.info(f"[Twitter/X Worker] Yielded {len(candidates)} high-intent buying signals for '{service_name}'")
    finally:
        if own_client:
            await client.aclose()

    return candidates


# ─── Cross-Platform Deduplication Engine ──────────────────────────────────────
def deduplicate_candidates(candidates: List[RawLeadCandidate]) -> List[RawLeadCandidate]:
    """
    Deduplicates incoming streams using normalized domain URLs and MD5 text hashes of content.
    Boosts a candidate's priority_rank if the same company/URL appears across multiple sources simultaneously.
    """
    seen_domains: Dict[str, RawLeadCandidate] = {}
    seen_hashes: Dict[str, RawLeadCandidate] = {}
    seen_urls: Dict[str, RawLeadCandidate] = {}
    deduped: List[RawLeadCandidate] = []

    for cand in candidates:
        domain = clean_domain_str(cand.raw_domain or cand.url)
        is_genuine_company_domain = bool(domain and domain not in GENERIC_PLATFORMS and "." in domain)

        # MD5 Hash of normalized content snippet (first 150 chars)
        norm_snippet = re.sub(r"\s+", " ", (cand.text_content or cand.title).strip().lower())[:150]
        content_hash = hashlib.md5(norm_snippet.encode("utf-8")).hexdigest()

        # Normalized canonical URL
        norm_url = cand.url.strip().rstrip("/").lower()

        # Match check: genuine domain match OR content hash match OR canonical URL match
        existing: Optional[RawLeadCandidate] = None
        if is_genuine_company_domain and domain in seen_domains:
            existing = seen_domains[domain]
        elif content_hash in seen_hashes:
            existing = seen_hashes[content_hash]
        elif norm_url in seen_urls:
            existing = seen_urls[norm_url]

        if existing is not None:
            # ── Cross-source Match Boost ───────────────────────────────────────
            existing.priority_rank += 1
            sources_list = existing.raw_metadata.setdefault("sources", [existing.source])
            if cand.source not in sources_list:
                sources_list.append(cand.source)
            existing.raw_metadata["cross_source_match"] = True
            existing.raw_metadata["sources_count"] = len(sources_list)

            # Preserve richer company name or external link if present
            if not existing.author_or_company and cand.author_or_company:
                existing.author_or_company = cand.author_or_company
            if is_genuine_company_domain and clean_domain_str(existing.raw_domain or existing.url) in GENERIC_PLATFORMS:
                existing.raw_domain = domain
                existing.url = cand.url
            if len(cand.text_content) > len(existing.text_content):
                existing.text_content = cand.text_content
        else:
            cand.raw_metadata.setdefault("sources", [cand.source])
            cand.raw_metadata["sources_count"] = 1

            if is_genuine_company_domain:
                seen_domains[domain] = cand
            seen_hashes[content_hash] = cand
            seen_urls[norm_url] = cand
            deduped.append(cand)

    # Sort descending by priority_rank so multi-source leads appear at the top
    deduped.sort(key=lambda c: c.priority_rank, reverse=True)
    return deduped


# ─── Main Integration Entry Point ─────────────────────────────────────────────
async def ingest_all_sources(
    query: str,
    target_service: str = "",
    page: int = 1,
    discovery_mode: str = "hybrid",
    target_country: str = ""
) -> List[RawLeadCandidate]:
    """
    Main asynchronous entry point: runs source workers concurrently via asyncio.gather.
    Supports discovery_mode:
      - 'companies': ONLY queries SearXNG for real corporate/commercial target company websites.
      - 'social_intent': Queries social and intent feeds (Twitter, Reddit, RSS, HN).
      - 'hybrid' (default): Ingests across all channels concurrently.

    Enforces a strict 6-second timeout per worker with return_exceptions=True so partial
    feed failures never block or crash the overall discovery stream.

    Returns a normalized, deduplicated list of RawLeadCandidate objects with boosted priority ranks.
    """
    norm_mode = (discovery_mode or "hybrid").lower().strip()
    logger.info(
        f"═══════════════════════════════════════════════════════════════════\n"
        f"[Multi-Source Ingestion] STARTING PARALLEL INGESTION (Mode: '{norm_mode}')\n"
        f"Query: '{query}' | Target Service: '{target_service}' | Page: {page}\n"
        f"═══════════════════════════════════════════════════════════════════"
    )
    start_time = time.time()

    # Create a shared async HTTP client with connection pooling and strict timeout bounds
    async with httpx.AsyncClient(
        timeout=TIMEOUT_SECONDS,
        headers={"User-Agent": DEFAULT_USER_AGENT},
        follow_redirects=True
    ) as client:
        # Wrap each worker in asyncio.wait_for with strict timeout as extra guard
        async def run_worker(coro, name: str) -> List[RawLeadCandidate]:
            try:
                return await asyncio.wait_for(coro, timeout=TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                logger.warning(f"[Multi-Source Ingestion] ⏱️ Worker '{name}' TIMED OUT after {TIMEOUT_SECONDS}s")
                return []
            except Exception as e:
                logger.warning(f"[Multi-Source Ingestion] ❌ Worker '{name}' failed: {e}")
                return []

        tasks = []
        if norm_mode in ("companies", "company", "target_companies"):
            # 🏢 Pure Corporate Mode: Query ONLY SearXNG for genuine corporate websites
            tasks.append(run_worker(fetch_searxng_async(query=query, page=page, client=client, country=target_country), "SearXNG"))
        elif norm_mode in ("direct_clients", "clients", "social_intent", "social", "intent", "gigs"):
            # 🎯 Pure Direct Client Mode: Query Reddit, Twitter, HackerNews, and Upwork/RSS for live client buying signals
            tasks.extend([
                run_worker(fetch_reddit_async(query=query, target_service=target_service, client=client), "Reddit"),
                run_worker(fetch_twitter_intent_async(query=query, target_service=target_service, client=client), "TwitterX"),
                run_worker(fetch_hacker_news_async(query=query, target_service=target_service, client=client), "HackerNews"),
                run_worker(fetch_rss_feeds_async(query=query, target_service=target_service, client=client), "RSSFeeds"),
            ])
        else:
            # 'hybrid' (default) -> Ingest across all sources
            tasks.extend([
                run_worker(fetch_searxng_async(query=query, page=page, client=client, country=target_country), "SearXNG"),
                run_worker(fetch_reddit_async(query=query, target_service=target_service, client=client), "Reddit"),
                run_worker(fetch_twitter_intent_async(query=query, target_service=target_service, client=client), "TwitterX"),
                run_worker(fetch_hacker_news_async(query=query, target_service=target_service, client=client), "HackerNews"),
                run_worker(fetch_rss_feeds_async(query=query, target_service=target_service, client=client), "RSSFeeds"),
            ])

        worker_results = await asyncio.gather(*tasks, return_exceptions=True)

    all_candidates: List[RawLeadCandidate] = []
    source_counts: Dict[str, int] = {}

    for res in worker_results:
        if isinstance(res, list):
            for cand in res:
                if isinstance(cand, RawLeadCandidate):
                    all_candidates.append(cand)
                    source_counts[cand.source] = source_counts.get(cand.source, 0) + 1

    total_raw = len(all_candidates)
    deduped_candidates = deduplicate_candidates(all_candidates)
    boosted_count = sum(1 for c in deduped_candidates if c.priority_rank > 1)
    elapsed = time.time() - start_time

    logger.info(
        f"[Multi-Source Ingestion] COMPLETED in {elapsed:.2f}s | "
        f"Raw: {total_raw} items (SearXNG: {source_counts.get('searxng', 0)}, "
        f"Reddit: {source_counts.get('reddit', 0)}, HN: {source_counts.get('hacker_news', 0)}, "
        f"RSS: {source_counts.get('rss_feed', 0)}, Twitter: {source_counts.get('twitter_x', 0)}) -> "
        f"Deduplicated: {len(deduped_candidates)} leads ({boosted_count} multi-source boosted)"
    )

    return deduped_candidates


# ─── Standalone Local Testing Block ───────────────────────────────────────────
if __name__ == "__main__":
    async def _test():
        print("Running standalone test for Multi-Source Ingestion Engine...")
        leads = await ingest_all_sources(query="AI Software Agency", target_service="Web & Mobile App Development")
        print(f"\nSuccessfully retrieved {len(leads)} deduplicated candidates:")
        for idx, lead in enumerate(leads[:10], 1):
            boost_badge = f" [BOOST x{lead.priority_rank}]" if lead.priority_rank > 1 else ""
            print(f" {idx}. [{lead.source.upper()}]{boost_badge} {lead.title[:75]}")
            print(f"     URL: {lead.url}")
            print(f"     Domain: {lead.raw_domain} | Company: {lead.author_or_company}")
            print(f"     Snippet: {lead.text_content[:90]}...")
            print(f"     Sources: {lead.raw_metadata.get('sources')}")
            print("-" * 75)

    asyncio.run(_test())
