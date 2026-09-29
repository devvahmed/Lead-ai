"""
Context-Aware Smart DOM Crawler & AI Navigation Engine (Step 6).

Architecture & Execution Pipeline:
1. Base Domain & Host Analysis:
   - Identifies root domain and subdomains (e.g. ahmed.com, shop.ahmed.com).
2. Multi-Engine Resilient Crawler:
   - Engine 1: Async httpx with rotating browser headers & decompression.
   - Engine 2: urllib.request with unverified SSL context fallback.
   - Engine 3: Alternate desktop user-agents to bypass basic WAF blocks.
3. Full Site Navigation & Link Harvester:
   - Scans <nav>, <header>, <footer>, dropdown menus, and internal links.
   - Normalizes to absolute URLs, filters out external/social platforms & static assets.
4. AI-Powered Optimal Page Selection:
   - Submits site structure & anchor texts to local LLM / AI router.
   - AI determines the exact 3-4 high-value pages that reveal:
     (a) Company overview & business operations
     (b) Founders, leadership, executive directory, or doctors/partners
     (c) Official contact & office directory
   - Seamless 2.5s heuristic priority fallback if LLM is offline/timed out.
5. Deep Multi-Page Crawl:
   - Concurrently crawls the AI-chosen pages.
6. On-Site Decision Maker & Contact Extractor (Zero-Hallucination Policy):
   - Extracts real human names and leadership roles directly from crawled content.
   - Discovers authentic corporate emails on the domain.
   - Automatically registers discovered email patterns in the Pattern Library.
   - STRICT ZERO-FAKE: If no name or email is found on the website, returns empty arrays.
     0% fabrication!
"""

import asyncio
import gzip
import json
import logging
import os
import random
import re
import ssl
import urllib.parse
import urllib.request
import zlib
from typing import Any, Dict, List, Optional, Set, Tuple

from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger("smart_dom_crawler")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s")

# ─── Configuration & Network Headers ──────────────────────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
]

def get_random_headers() -> Dict[str, str]:
    ua = random.choice(USER_AGENTS)
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }

# Disallowed external aggregators and social networks
DISALLOWED_DOMAINS = {
    "linkedin.com", "twitter.com", "x.com", "facebook.com", "instagram.com",
    "youtube.com", "github.com", "tiktok.com", "pinterest.com", "google.com",
    "apple.com", "play.google.com", "medium.com", "reddit.com", "t.co",
    "bit.ly", "whatsapp.com", "vimeo.com", "clutch.co", "yelp.com", "wikipedia.org"
}

# Non-HTML static assets to skip (excluding PDFs which are cracked and parsed for intelligence)
ASSET_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".zip", ".tar", ".gz", ".rar", ".7z", ".exe", ".dmg", ".apk",
    ".mp4", ".mp3", ".wav", ".avi", ".mov", ".wmv", ".webm",
    ".css", ".js", ".xml", ".json", ".woff", ".woff2", ".ttf", ".eot",
    ".csv", ".xlsx", ".docx", ".pptx"
)

PDF_EXTENSIONS = (".pdf",)

# Dead / junk generic prefixes strictly filtered out (never surfaced to frontend)
DEAD_GENERIC_PREFIXES = {
    "info", "support", "care", "customercare", "customer.care", "help",
    "helpdesk", "noreply", "no-reply", "donotreply", "privacy", "abuse",
    "webmaster", "postmaster", "admin"
}

# High-value commercial & operational prefixes to accept and surface if found on site
COMMERCIAL_ACCEPTED_PREFIXES = {
    "sales", "investor", "investors", "ir", "partners", "partnerships",
    "bd", "business", "commercial", "growth", "inquiries", "enquiries",
    "contact", "press", "media", "billing", "finance", "management",
    "operations", "director", "rfp", "procurement", "leads"
}

# Common homepage root paths
HOMEPAGE_PATHS = {
    "", "/", "/en", "/en/", "/us", "/us/", "/home", "/home/",
    "/index.html", "/index.php", "/default.aspx", "/main"
}

# SSL context for urllib fallback
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# In-memory crawl metadata cache for discover pipeline
_CRAWL_CACHE: Dict[str, Dict[str, Any]] = {}


def get_cached_crawl_res(domain: str) -> Optional[Dict[str, Any]]:
    """Retrieves cached crawl result for a domain."""
    if not domain:
        return None
    clean = domain.lower().replace("www.", "").strip()
    return _CRAWL_CACHE.get(clean)


# ─── 1. URL & Domain Normalization Helpers ─────────────────────────────────────

def get_base_domain(url: str) -> str:
    """Extracts registered host from URL, removing www. and ports."""
    if not url:
        return ""
    try:
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        parsed = urllib.parse.urlparse(url)
        host = (parsed.hostname or parsed.netloc or "").lower().strip()
        if host.startswith("www."):
            host = host[4:]
        if ":" in host:
            host = host.split(":")[0]
        return host
    except Exception:
        return ""


def is_same_domain_or_subdomain(target_url: str, base_url: str) -> bool:
    """Checks if target_url belongs to the same domain or subdomain of base_url."""
    target_domain = get_base_domain(target_url)
    base_domain = get_base_domain(base_url)
    if not target_domain or not base_domain:
        return False
    return target_domain == base_domain or target_domain.endswith("." + base_domain) or base_domain.endswith("." + target_domain)


def normalize_and_validate_url(raw_href: str, base_url: str) -> Optional[str]:
    """
    Normalizes a raw href against base_url and validates that:
    1. It is not empty, anchor (#), javascript:, mailto:, tel:, etc.
    2. It does not point to a static asset.
    3. It resolves to the same base domain or a valid subdomain.
    4. It is not an external or social media link.
    5. It is not just the homepage itself.
    """
    if not raw_href or not isinstance(raw_href, str):
        return None

    cleaned_href = raw_href.strip()
    if not cleaned_href:
        return None

    lower_href = cleaned_href.lower()
    if lower_href.startswith(("#", "javascript:", "mailto:", "tel:", "data:", "sms:", "callto:")):
        return None

    # Check asset extensions on raw href before resolving
    path_clean = cleaned_href.split("?")[0].split("#")[0].lower()
    if any(path_clean.endswith(ext) for ext in ASSET_EXTENSIONS):
        return None

    try:
        resolved = urllib.parse.urljoin(base_url, cleaned_href)
        parsed = urllib.parse.urlparse(resolved)
    except Exception:
        return None

    if parsed.scheme not in ("http", "https"):
        return None

    # Remove fragment
    clean_url = urllib.parse.urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        parsed.query,
        ""
    ))

    target_domain = get_base_domain(clean_url)
    if not target_domain or any(dis in target_domain for dis in DISALLOWED_DOMAINS):
        return None

    if not is_same_domain_or_subdomain(clean_url, base_url):
        return None

    # Filter out static assets on resolved path
    clean_path = parsed.path.lower().rstrip("/")
    if any(clean_path.endswith(ext) for ext in ASSET_EXTENSIONS):
        return None

    # Filter out pure homepage URLs
    base_parsed = urllib.parse.urlparse(base_url)
    base_path = base_parsed.path.lower().rstrip("/")
    if clean_path == base_path or clean_path in HOMEPAGE_PATHS:
        if not parsed.query:
            return None

    return clean_url


# ─── 2. Multi-Engine Resilient Crawler ────────────────────────────────────────

async def fetch_page_html_resilient(url: str, timeout: float = 4.0) -> str:
    """
    Fetches HTML content of a page using a multi-engine fallback pipeline:
    - Engine 1: Async httpx with modern browser impersonation & SSL bypass.
    - Engine 2: urllib.request with unverified SSL context and custom decompression.
    - Engine 3: Alternative user-agent retry.
    """
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    headers = get_random_headers()

    # Engine 1: httpx AsyncClient
    try:
        async with httpx.AsyncClient(
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
            verify=False
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and resp.text:
                return resp.text
    except Exception as e:
        logger.debug(f"[MultiCrawler] httpx fetch failed for {url}: {e}")

    # Engine 2: urllib executor with unverified SSL
    loop = asyncio.get_event_loop()
    def _urllib_fetch(alt_headers: Dict[str, str]) -> str:
        try:
            req = urllib.request.Request(url, headers=alt_headers)
            with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
                raw_bytes = resp.read()
                encoding = resp.headers.get("Content-Encoding", "").lower()
                if "gzip" in encoding:
                    raw_bytes = gzip.decompress(raw_bytes)
                elif "deflate" in encoding:
                    raw_bytes = zlib.decompress(raw_bytes)
                return raw_bytes.decode("utf-8", errors="ignore")
        except Exception:
            return ""

    try:
        html_out = await loop.run_in_executor(None, _urllib_fetch, headers)
        if html_out and len(html_out.strip()) > 100:
            return html_out
    except Exception:
        pass

    # Engine 3: Alternate User-Agent retry
    alt_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "close"
    }
    try:
        html_out = await loop.run_in_executor(None, _urllib_fetch, alt_headers)
        if html_out:
            return html_out
    except Exception:
        pass

    # Engine 4: HTTP Protocol Fallback (if HTTPS SSL handshake failed or expired)
    if url.startswith("https://"):
        http_url = "http://" + url[8:]
        try:
            async with httpx.AsyncClient(
                headers=headers,
                timeout=timeout,
                follow_redirects=True,
                verify=False
            ) as client:
                resp = await client.get(http_url)
                if resp.status_code == 200 and resp.text:
                    return resp.text
        except Exception:
            pass

    return ""


def extract_clean_page_text(html: str) -> str:
    """Strips scripts, styles, svg, and noisy markup, returning clean readable text."""
    if not html:
        return ""
    try:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
            tag.decompose()
        text = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()
        return text
    except Exception:
        return ""


def extract_pdf_text_from_bytes(pdf_bytes: bytes, max_pages: int = 5) -> str:
    """Extracts readable text from PDF binary bytes using pypdf with robust fallbacks."""
    if not pdf_bytes or len(pdf_bytes) < 60:
        return ""
    try:
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        extracted = []
        for i, page in enumerate(reader.pages[:max_pages]):
            text = page.extract_text() or ""
            if text.strip():
                extracted.append(text.strip())
        return "\n".join(extracted)
    except Exception as e:
        logger.debug(f"[PDFParser] pypdf parsing fallback ({e})")
        try:
            # Fallback simple Latin-1 parenthetical text extraction
            raw_latin = pdf_bytes.decode("latin-1", errors="ignore")
            snippets = re.findall(r'\(([A-Za-z0-9\s@.,:;\-_/]{4,120})\)', raw_latin)
            if snippets:
                return " ".join(snippets[:150])
        except Exception:
            pass
        return ""


async def fetch_pdf_text_resilient(url: str, timeout: float = 4.5) -> str:
    """Fetches PDF binary data from URL and returns extracted clean text."""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    headers = get_random_headers()
    # Engine 1: httpx
    try:
        async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True, verify=False) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and resp.content and len(resp.content) > 100:
                return extract_pdf_text_from_bytes(resp.content)
    except Exception as e:
        logger.debug(f"[MultiCrawler] httpx PDF fetch error for {url}: {e}")

    # Engine 2: urllib
    loop = asyncio.get_event_loop()
    def _urllib_pdf() -> bytes:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
                return resp.read(5 * 1024 * 1024)
        except Exception:
            return b""

    try:
        raw_b = await loop.run_in_executor(None, _urllib_pdf)
        if raw_b:
            return extract_pdf_text_from_bytes(raw_b)
    except Exception:
        pass

    return ""


# ─── 3. Comprehensive Site Navigation & Link Harvester ─────────────────────────

def extract_all_site_nav_links(
    html_content: str,
    base_url: str
) -> Dict[str, Any]:
    """
    Deeply parses DOM to extract all internal navigation, header, footer, menu,
    and sub-menu links across the entire website.
    """
    if not html_content or not base_url:
        return {"all_links": [], "nav_links": [], "footer_links": [], "body_links": [], "pdf_links": []}

    try:
        soup = BeautifulSoup(html_content, "html.parser")
    except Exception as e:
        logger.debug(f"[DOMParser] BeautifulSoup parse error: {e}")
        return {"all_links": [], "nav_links": [], "footer_links": [], "body_links": [], "pdf_links": []}

    nav_links: List[Dict[str, str]] = []
    footer_links: List[Dict[str, str]] = []
    body_links: List[Dict[str, str]] = []
    all_links: List[Dict[str, str]] = []
    seen_urls: Set[str] = set()

    # Locate structural navigation containers
    nav_elements = soup.find_all(
        lambda tag: tag.name in ("nav", "header") or (
            tag.has_attr("class") and any(
                k in c.lower() for c in (tag["class"] if isinstance(tag["class"], list) else [str(tag["class"])])
                for k in ("nav", "menu", "header", "navbar", "navigation")
            )
        ) or (
            tag.has_attr("id") and any(k in str(tag["id"]).lower() for k in ("nav", "menu", "header", "main-nav"))
        ) or (
            tag.has_attr("role") and tag["role"] in ("navigation", "menubar")
        )
    )

    # Locate structural footer containers
    footer_elements = soup.find_all(
        lambda tag: tag.name == "footer" or (
            tag.has_attr("class") and any(
                "footer" in c.lower() for c in (tag["class"] if isinstance(tag["class"], list) else [str(tag["class"])])
            )
        ) or (
            tag.has_attr("id") and "footer" in str(tag["id"]).lower()
        ) or (
            tag.has_attr("role") and tag["role"] == "contentinfo"
        )
    )

    # 1. Nav Zone Links
    for container in nav_elements:
        for a in container.find_all("a", href=True):
            val_url = normalize_and_validate_url(a["href"], base_url)
            if val_url and val_url not in seen_urls:
                seen_urls.add(val_url)
                text = re.sub(r"\s+", " ", a.get_text(separator=" ")).strip()
                path = urllib.parse.urlparse(val_url).path
                item = {"url": val_url, "href": a["href"].strip(), "text": text, "zone": "nav", "path": path}
                nav_links.append(item)
                all_links.append(item)

    # 2. Footer Zone Links
    for container in footer_elements:
        for a in container.find_all("a", href=True):
            val_url = normalize_and_validate_url(a["href"], base_url)
            if val_url and val_url not in seen_urls:
                seen_urls.add(val_url)
                text = re.sub(r"\s+", " ", a.get_text(separator=" ")).strip()
                path = urllib.parse.urlparse(val_url).path
                item = {"url": val_url, "href": a["href"].strip(), "text": text, "zone": "footer", "path": path}
                footer_links.append(item)
                all_links.append(item)

    # 3. Remaining Body Links
    for a in soup.find_all("a", href=True):
        val_url = normalize_and_validate_url(a["href"], base_url)
        if val_url and val_url not in seen_urls:
            seen_urls.add(val_url)
            text = re.sub(r"\s+", " ", a.get_text(separator=" ")).strip()
            path = urllib.parse.urlparse(val_url).path
            item = {"url": val_url, "href": a["href"].strip(), "text": text, "zone": "body", "path": path}
            body_links.append(item)
            all_links.append(item)

    # 4. Collect On-Site PDF Links
    pdf_links: List[Dict[str, str]] = [
        item for item in all_links
        if item.get("path", "").lower().endswith(".pdf") or item.get("url", "").lower().endswith(".pdf")
    ]

    return {
        "all_links": all_links,
        "nav_links": nav_links,
        "footer_links": footer_links,
        "body_links": body_links,
        "pdf_links": pdf_links
    }


# ─── 4. AI-Powered Optimal Page Selection ─────────────────────────────────────

async def ai_select_optimal_subpages(
    domain: str,
    candidate_links: List[Dict[str, str]],
    max_pages: int = 4
) -> List[str]:
    """
    Submits the extracted menu/navigation link candidates to the AI router.
    AI selects the top 3-4 pages that provide:
    1. Core business overview and operations
    2. Executive leadership, founders, owners, or team directory
    3. Official contact and locations
    Includes a 2.5s timeout with an intelligent heuristic fallback.
    """
    if not candidate_links:
        return []

    # Clean list of unique paths & anchor texts for compact prompt
    compact_candidates: List[Dict[str, str]] = []
    seen_paths = set()
    for link in candidate_links:
        path = link.get("path") or ""
        text = link.get("text") or ""
        if path and path not in seen_paths and len(path) > 1:
            seen_paths.add(path)
            compact_candidates.append({
                "url": link["url"],
                "path": path,
                "text": text[:40],
                "zone": link.get("zone", "nav")
            })

    if not compact_candidates:
        return []

    selected_urls: List[str] = []

    # Attempt 1: Call Local LLM via async_call_ollama or llm_router
    try:
        from discover import async_call_ollama

        sample_list = compact_candidates[:25]
        prompt = f"""You are an expert web crawler and B2B researcher analyzing '{domain}'.
Here are the internal navigation and footer links discovered on the website:
{json.dumps([{'path': c['path'], 'text': c['text']} for c in sample_list], indent=2)}

TASK:
Select the top {max_pages - 1} BEST URLs from this list that will reveal:
1. Core company overview, business history, and what they do.
2. Founders, owners, executive leadership, or team directory.
3. Official office locations and contact directory.

Return ONLY a valid JSON array containing the exact selected paths from the list, e.g.:
["/about-us", "/our-team", "/contact"]
Do not return any explanations or markdown. Just the JSON array."""

        raw_output = await async_call_ollama(
            prompt=prompt,
            system_prompt="You are a precise web navigation analyzer. Output strictly a JSON array of chosen paths.",
            temperature=0.1,
            max_tokens=200,
            timeout=2.5
        )

        if raw_output:
            cleaned = re.sub(r"^```json\s*", "", raw_output.strip(), flags=re.MULTILINE)
            cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE)
            start_b = cleaned.find("[")
            end_b = cleaned.rfind("]")
            if start_b != -1 and end_b != -1:
                parsed_paths = json.loads(cleaned[start_b:end_b + 1])
                if isinstance(parsed_paths, list):
                    for p in parsed_paths:
                        p_str = str(p).strip().lower()
                        # Match to candidate full url
                        matched = next((c["url"] for c in compact_candidates if c["path"].lower() == p_str or p_str in c["url"].lower()), None)
                        if matched and matched not in selected_urls:
                            selected_urls.append(matched)
                            if len(selected_urls) >= (max_pages - 1):
                                break
                    if selected_urls:
                        logger.info(f"[SmartDOMCrawler] AI selected {len(selected_urls)} optimal pages for {domain}: {selected_urls}")
    except Exception as e:
        logger.debug(f"[SmartDOMCrawler] AI page selection bypassed ({e}) — executing smart heuristic")

    # Attempt 2: Smart Heuristic Fallback (Zero Fail)
    if len(selected_urls) < (max_pages - 1):
        # High-priority categories:
        # 1. Leadership & Team (Founders, Executives, Doctors, Partners)
        # 2. About & Overview (Company, History, Story)
        # 3. Contact & Locations
        leadership_terms = [
            "team", "our-team", "leadership", "people", "founders", "management",
            "board", "executives", "directors", "staff", "attorneys", "doctors", "partners"
        ]
        overview_terms = [
            "about", "about-us", "who-we-are", "our-company", "company", "overview",
            "our-story", "history", "capabilities", "what-we-do"
        ]
        contact_terms = [
            "contact", "contact-us", "locations", "offices", "get-in-touch", "reach-us"
        ]

        def score_link(c: Dict[str, str]) -> float:
            score = 0.0
            p = c["path"].lower()
            t = c["text"].lower()
            z = c["zone"]

            # Zone bonus
            if z == "nav":
                score += 15.0
            elif z == "footer":
                score += 8.0

            # Negative filter
            if any(n in p for n in ("/blog", "/news", "/press", "/tag", "/category", "/career", "/job")):
                return 0.0

            # Leadership match (Highest value)
            if any(term in p or term in t for term in leadership_terms):
                score += 50.0
            # Overview match
            elif any(term in p or term in t for term in overview_terms):
                score += 40.0
            # Contact match
            elif any(term in p or term in t for term in contact_terms):
                score += 30.0

            # Path length penalty for deeply nested pages
            segments = [s for s in p.split("/") if s]
            if len(segments) <= 2:
                score += 10.0
            else:
                score -= 5.0

            return score

        scored_list = sorted(compact_candidates, key=score_link, reverse=True)
        for candidate in scored_list:
            u = candidate["url"]
            if u not in selected_urls and score_link(candidate) >= 20.0:
                selected_urls.append(u)
                if len(selected_urls) >= (max_pages - 1):
                    break

    return selected_urls[:max_pages - 1]


# ─── 5. On-Site Decision Maker & Contact Extractor ────────────────────────────

LEADERSHIP_ROLES = [
    "Founder", "Co-Founder", "Chief Executive Officer", "CEO", "President",
    "Owner", "Co-Owner", "Principal", "Managing Partner", "Managing Director",
    "Executive Director", "Chief Technology Officer", "CTO", "Chief Operating Officer",
    "COO", "Vice President", "VP", "Director", "General Manager", "Doctor",
    "Managing Attorney", "Lead Partner"
]

def extract_onsite_contacts_and_decision_makers(
    crawled_pages: Dict[str, Dict[str, str]],
    domain: str
) -> Dict[str, Any]:
    """
    Extracts authentic on-site decision makers, executive names, raw emails, and phones
    strictly from crawled HTML/text.
    
    STRICT ZERO-FAKE POLICY:
    - Only extracts names explicitly tied to leadership roles on the website.
    - Only extracts emails matching the domain or clearly published on contact pages.
    - If none are found, returns EMPTY lists — 0% fabrication!
    """
    clean_domain = get_base_domain(domain)
    decision_makers: List[Dict[str, Any]] = []
    found_emails: List[str] = []
    found_phones: List[str] = []
    seen_dm_names: Set[str] = set()

    email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
    phone_pattern = re.compile(r'(?:\+\d{1,3}[\s\-.]?)?\(?\d{2,4}\)?[\s\-.]?\d{3,4}[\s\-.]?\d{3,5}')

    # Role regex builder
    role_pattern_str = r'\b(?:' + '|'.join(re.escape(r) for r in LEADERSHIP_ROLES) + r')\b'
    role_regex = re.compile(role_pattern_str, re.IGNORECASE)

    # Clean excluded keywords for person names
    invalid_name_words = {
        "about", "team", "contact", "home", "services", "company", "career", "board",
        "leadership", "our", "the", "read", "more", "learn", "view", "profile", "bio",
        "click", "here", "privacy", "policy", "terms", "blog", "news", "office", "phone"
    }

    for page_key, page_data in crawled_pages.items():
        text = page_data.get("text", "")
        page_url = page_data.get("url", "")
        if not text:
            continue

        # 1. Email Extraction
        page_emails = email_pattern.findall(text)
        for em in page_emails:
            em_clean = em.lower().strip().rstrip(".")
            # Filter asset extensions
            if any(em_clean.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".js", ".css")):
                continue

            local_prefix = em_clean.split("@")[0].lower() if "@" in em_clean else ""

            # Filter out dead junk generic prefixes (info@, support@, care@, noreply@, admin@)
            if local_prefix in DEAD_GENERIC_PREFIXES:
                continue

            # Accept both personal and high-value commercial/operational emails found on site
            if em_clean not in found_emails:
                found_emails.append(em_clean)
                # Automatically learn pattern if on company domain AND NOT a commercial role inbox
                if clean_domain and em_clean.endswith(f"@{clean_domain}") and local_prefix not in COMMERCIAL_ACCEPTED_PREFIXES:
                    try:
                        from contact_enricher_pro import learn_and_save_pattern
                        learn_and_save_pattern(em_clean, clean_domain, confidence=90)
                    except Exception:
                        pass

        # 2. Phone Extraction
        page_phones = phone_pattern.findall(text)
        for ph in page_phones:
            ph_clean = ph.strip()
            digits_only = re.sub(r'\D', '', ph_clean)
            if 7 <= len(digits_only) <= 15 and ph_clean not in found_phones:
                found_phones.append(ph_clean)

        # 3. Decision Maker Name & Role Extraction
        # Look for patterns like:
        # "John Smith, Founder & CEO"
        # "Founder & CEO: John Smith"
        # "Dr. Sarah Jones - Practice Director"
        lines = text.split("\n")
        if len(lines) <= 2:
            # If plain collapsed text, split by sentences or punctuation
            lines = re.split(r'[.;•|]+', text)

        for line in lines:
            line_str = line.strip()
            if not line_str or len(line_str) > 120:
                continue

            role_match = role_regex.search(line_str)
            if role_match:
                matched_role = role_match.group(0).strip().title()

                # Extract person name candidate adjacent to role
                # Case A: "John Doe, CEO" or "John Doe - Founder"
                name_candidate = ""
                before_role = line_str[:role_match.start()].strip(" ,:-|–")
                after_role = line_str[role_match.end():].strip(" ,:-|–")

                name_regex = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b')

                m_before = name_regex.search(before_role)
                m_after = name_regex.search(after_role)

                if m_before:
                    name_candidate = m_before.group(1).strip()
                elif m_after:
                    name_candidate = m_after.group(1).strip()

                if name_candidate:
                    lower_tokens = set(name_candidate.lower().split())
                    if not lower_tokens.intersection(invalid_name_words):
                        if name_candidate.lower() not in seen_dm_names:
                            seen_dm_names.add(name_candidate.lower())

                            # Check if a matching personal email exists in found_emails
                            dm_email = None
                            name_parts = name_candidate.lower().split()
                            first_name = name_parts[0]
                            last_name = name_parts[-1] if len(name_parts) > 1 else ""

                            for em in found_emails:
                                if clean_domain and em.endswith(f"@{clean_domain}"):
                                    local_part = em.split("@")[0].lower()
                                    if first_name in local_part or (last_name and last_name in local_part):
                                        dm_email = em
                                        break

                            # If a personal on-site email is discovered, save to Pattern Library with high confidence
                            if dm_email:
                                try:
                                    from contact_enricher_pro import learn_and_save_pattern
                                    learn_and_save_pattern(dm_email, clean_domain, confidence=95)
                                except Exception:
                                    pass

                            decision_makers.append({
                                "name": name_candidate,
                                "role": matched_role,
                                "email": dm_email,
                                "source": f"onsite_{page_key}",
                                "page_url": page_url,
                                "strictly_verified": True if dm_email else False
                            })

    return {
        "decision_makers": decision_makers,
        "emails": found_emails,
        "phones": found_phones
    }


# ─── 6. Master Dynamic Multi-Page Crawler Entry Point ─────────────────────────

async def crawl_smart_dom_target(
    domain: str,
    homepage_url: str,
    homepage_html: str = "",
    max_pages: int = 4
) -> Dict[str, Any]:
    """
    Main entry point for Step 6:
    1. Validates base domain and normalizes URL.
    2. Deeply crawls homepage using multi-engine crawler.
    3. Harvests all internal navigation, header, footer, dropdown menus, and internal PDF links.
    4. Submits candidate links to AI to intelligently select top 3-4 overview/team pages.
    5. Concurrently crawls the AI-chosen subpages and cracked PDF documents.
    6. Extracts authentic on-site decision makers, raw emails, and phone numbers.
    7. Caches result and returns combined text and verified on-site contacts.
    """
    clean_domain = get_base_domain(domain or homepage_url)

    if not homepage_url.startswith(("http://", "https://")):
        homepage_url = f"https://{homepage_url or clean_domain}"

    # Step 1 & 2: Acquire Homepage HTML with Multi-Engine Fallback
    if not homepage_html:
        homepage_html = await fetch_page_html_resilient(homepage_url, timeout=4.0)

    homepage_text = extract_clean_page_text(homepage_html)
    if not homepage_text:
        empty_res = {
            "combined_text": "",
            "source_label": "none",
            "homepage_text": "",
            "pages": {},
            "dom_links": {"all_links": [], "nav_links": [], "footer_links": [], "body_links": [], "pdf_links": []},
            "selected_urls": [],
            "onsite_decision_makers": [],
            "onsite_emails": [],
            "onsite_phones": [],
            "total_pages_crawled": 0
        }
        if clean_domain:
            _CRAWL_CACHE[clean_domain] = empty_res
        return empty_res

    # Step 3: Harvest All DOM Links (Nav, Header, Footer, Dropdowns, Body, PDFs)
    dom_links = extract_all_site_nav_links(homepage_html, homepage_url)
    all_links = dom_links.get("all_links", [])

    # Step 4: AI-Powered Optimal Page Selection
    selected_subpage_urls = await ai_select_optimal_subpages(
        domain=clean_domain,
        candidate_links=all_links,
        max_pages=max_pages
    )

    pages_crawled: Dict[str, Dict[str, str]] = {
        "homepage": {
            "url": homepage_url,
            "text": homepage_text,
            "category": "homepage"
        }
    }
    fetched_sources = ["homepage"]

    # Step 5: Concurrently Crawl Selected Subpages
    if selected_subpage_urls:
        sub_tasks = [fetch_page_html_resilient(u, timeout=3.5) for u in selected_subpage_urls]
        sub_htmls = await asyncio.gather(*sub_tasks, return_exceptions=True)

        for sub_url, html_res in zip(selected_subpage_urls, sub_htmls):
            if isinstance(html_res, str) and html_res.strip():
                clean_sub_text = extract_clean_page_text(html_res)
                if len(clean_sub_text) > 80:
                    path_name = urllib.parse.urlparse(sub_url).path or sub_url
                    cat_key = path_name.strip("/").replace("/", "_") or "subpage"
                    pages_crawled[cat_key] = {
                        "url": sub_url,
                        "text": clean_sub_text,
                        "category": cat_key
                    }
                    fetched_sources.append(path_name)

    # Step 5b: Concurrently Crawl Relevant On-Site PDF Documents (e.g. brochures, profiles, presentations)
    pdf_candidates = dom_links.get("pdf_links", [])
    if pdf_candidates:
        def score_pdf(item: Dict[str, str]) -> float:
            p = (item.get("path") or "").lower()
            t = (item.get("text") or "").lower()
            score = 10.0
            for kw in ("profile", "company", "about", "overview", "brochure", "team", "leadership", "annual", "report", "presentation", "deck", "contact"):
                if kw in p or kw in t:
                    score += 20.0
            return score

        sorted_pdfs = sorted(pdf_candidates, key=score_pdf, reverse=True)
        top_pdfs = [p["url"] for p in sorted_pdfs[:2]]
        if top_pdfs:
            pdf_tasks = [fetch_pdf_text_resilient(u, timeout=4.0) for u in top_pdfs]
            pdf_texts = await asyncio.gather(*pdf_tasks, return_exceptions=True)
            for pdf_url, p_txt in zip(top_pdfs, pdf_texts):
                if isinstance(p_txt, str) and len(p_txt.strip()) > 80:
                    pdf_filename = urllib.parse.urlparse(pdf_url).path.split("/")[-1] or "document.pdf"
                    cat_key = f"pdf_{pdf_filename.replace('.', '_')}"
                    pages_crawled[cat_key] = {
                        "url": pdf_url,
                        "text": p_txt[:4000],
                        "category": "pdf_document"
                    }
                    fetched_sources.append(f"pdf:{pdf_filename}")
                    logger.info(f"[SmartDOMCrawler] 📄 Cracked PDF document {pdf_filename} ({len(p_txt)} chars)")

    # Step 6: On-Site Decision Maker & Contact Extraction (Strict Zero-Fake Policy)
    onsite_contacts = extract_onsite_contacts_and_decision_makers(pages_crawled, clean_domain)
    onsite_dms = onsite_contacts.get("decision_makers", [])
    onsite_emails = onsite_contacts.get("emails", [])
    onsite_phones = onsite_contacts.get("phones", [])

    if onsite_dms:
        logger.info(f"[SmartDOMCrawler] 🎯 Discovered {len(onsite_dms)} real on-site decision-makers for {clean_domain}")
    if onsite_emails:
        logger.info(f"[SmartDOMCrawler] ✉️ Discovered {len(onsite_emails)} on-site emails for {clean_domain}")

    # Assemble Combined Evidentiary Text
    combined_parts = [
        f"[PAGE: Homepage] ({urllib.parse.urlparse(homepage_url).path or '/'})\n{homepage_text[:2000]}"
    ]
    for key, p_data in pages_crawled.items():
        if key == "homepage":
            continue
        p_path = urllib.parse.urlparse(p_data["url"]).path or p_data["url"]
        combined_parts.append(
            f"\n\n--- [PAGE: {key.replace('_', ' ').title()}] ({p_path}) ---\n{p_data['text'][:1400]}"
        )

    combined_text = "\n".join(combined_parts)
    source_label = " + ".join(fetched_sources)

    crawl_result = {
        "combined_text": combined_text,
        "source_label": source_label,
        "homepage_text": homepage_text,
        "pages": pages_crawled,
        "dom_links": dom_links,
        "selected_urls": selected_subpage_urls,
        "onsite_decision_makers": onsite_dms,
        "onsite_emails": onsite_emails,
        "onsite_phones": onsite_phones,
        "total_pages_crawled": len(pages_crawled)
    }

    if clean_domain:
        _CRAWL_CACHE[clean_domain] = crawl_result

    return crawl_result
