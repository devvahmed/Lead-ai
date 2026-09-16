"""
Dynamic DOM Header/Footer/Nav Link Parser & Semantic Crawler (Step 6).

Replaces hardcoded subpage path guesses (/about, /contact, /careers) with real-time
DOM navigation analysis. Extracts internal links across structural zones (<nav>, <header>,
<footer>, and <body>), categorizes them semantically into operational buckets, and
concurrently crawls the highest-value subpages to build rich evidentiary context for
downstream qualification engines.
"""

import asyncio
import gzip
import logging
import re
import ssl
import urllib.parse
import urllib.request
import zlib
from typing import Any, Dict, List, Optional, Set, Tuple

from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger("smart_dom_crawler")

# ─── Configuration & Network Headers ──────────────────────────────────────────

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

# External social & aggregator platforms to filter out
DISALLOWED_DOMAINS = {
    "linkedin.com", "twitter.com", "x.com", "facebook.com", "instagram.com",
    "youtube.com", "github.com", "tiktok.com", "pinterest.com", "google.com",
    "apple.com", "play.google.com", "medium.com", "reddit.com", "t.co",
    "bit.ly", "whatsapp.com", "vimeo.com", "clutch.co", "yelp.com", "wikipedia.org"
}

# Non-HTML static assets to discard
ASSET_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".zip", ".tar", ".gz", ".rar", ".7z", ".exe", ".dmg", ".apk",
    ".mp4", ".mp3", ".wav", ".avi", ".mov", ".wmv", ".webm",
    ".css", ".js", ".xml", ".json", ".woff", ".woff2", ".ttf", ".eot",
    ".csv", ".xlsx", ".docx", ".pptx"
)

# Common homepage root paths
HOMEPAGE_PATHS = {
    "", "/", "/en", "/en/", "/us", "/us/", "/home", "/home/",
    "/index.html", "/index.php", "/default.aspx", "/main"
}

# SSL context for urllib fallback
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


# ─── 1. URL Normalization & Validation Helpers ────────────────────────────────

def get_base_domain(url: str) -> str:
    """Extracts registered host from URL, removing www. and ports."""
    try:
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
    return target_domain == base_domain or target_domain.endswith("." + base_domain)


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

    # Filter out protocols / fragments
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

    # Scheme must be http or https
    if parsed.scheme not in ("http", "https"):
        return None

    # Remove fragment
    clean_url = urllib.parse.urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        parsed.query,
        ""  # strip fragment
    ))

    # Check domain
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
        # If query parameters exist, it might be a page, but pure homepage path should be skipped
        if not parsed.query:
            return None

    return clean_url


# ─── 2. DOM Link Extraction Engine ────────────────────────────────────────────

def extract_internal_dom_links(
    html_content: str,
    base_url: str
) -> Dict[str, List[Dict[str, str]]]:
    """
    Parses HTML content and extracts internal hyperlinks categorized by structural zones:
    - `nav_links`: extracted from <nav>, <header>, or containers with nav/menu/header classes/IDs.
    - `footer_links`: extracted from <footer> or containers with footer classes/IDs.
    - `body_links`: all remaining internal <a> tags.

    Returns:
        {
            "nav_links": [{"url": ..., "text": ..., "zone": "nav", "path": ...}, ...],
            "footer_links": [...],
            "body_links": [...],
            "all_links": [...]
        }
    """
    if not html_content or not base_url:
        return {
            "nav_links": [],
            "footer_links": [],
            "body_links": [],
            "all_links": []
        }

    try:
        soup = BeautifulSoup(html_content, "html.parser")
    except Exception as e:
        logger.debug(f"[DOMParser] BeautifulSoup parse error: {e}")
        return {
            "nav_links": [],
            "footer_links": [],
            "body_links": [],
            "all_links": []
        }

    nav_links: List[Dict[str, str]] = []
    footer_links: List[Dict[str, str]] = []
    body_links: List[Dict[str, str]] = []
    all_links: List[Dict[str, str]] = []

    seen_urls: Set[str] = set()

    # Identify structural containers
    nav_elements = soup.find_all(
        lambda tag: tag.name in ("nav", "header") or (
            tag.has_attr("class") and any("nav" in c.lower() or "menu" in c.lower() or "header" in c.lower() for c in tag["class"] if isinstance(c, str))
        ) or (
            tag.has_attr("id") and any(k in str(tag["id"]).lower() for k in ("nav", "menu", "header", "main-nav", "primary-menu"))
        )
    )

    footer_elements = soup.find_all(
        lambda tag: tag.name == "footer" or (
            tag.has_attr("class") and any("footer" in c.lower() for c in tag["class"] if isinstance(c, str))
        ) or (
            tag.has_attr("id") and "footer" in str(tag["id"]).lower()
        )
    )

    # 1. Process Navigation Zone Links (Highest Structural Priority)
    for container in nav_elements:
        for a in container.find_all("a", href=True):
            validated_url = normalize_and_validate_url(a["href"], base_url)
            if validated_url and validated_url not in seen_urls:
                seen_urls.add(validated_url)
                text = re.sub(r"\s+", " ", a.get_text(separator=" ")).strip()
                path = urllib.parse.urlparse(validated_url).path
                item = {
                    "url": validated_url,
                    "href": a["href"].strip(),
                    "text": text,
                    "zone": "nav",
                    "path": path
                }
                nav_links.append(item)
                all_links.append(item)

    # 2. Process Footer Zone Links (Secondary Structural Priority)
    for container in footer_elements:
        for a in container.find_all("a", href=True):
            validated_url = normalize_and_validate_url(a["href"], base_url)
            if validated_url and validated_url not in seen_urls:
                seen_urls.add(validated_url)
                text = re.sub(r"\s+", " ", a.get_text(separator=" ")).strip()
                path = urllib.parse.urlparse(validated_url).path
                item = {
                    "url": validated_url,
                    "href": a["href"].strip(),
                    "text": text,
                    "zone": "footer",
                    "path": path
                }
                footer_links.append(item)
                all_links.append(item)

    # 3. Process Remaining Body Zone Links
    for a in soup.find_all("a", href=True):
        validated_url = normalize_and_validate_url(a["href"], base_url)
        if validated_url and validated_url not in seen_urls:
            seen_urls.add(validated_url)
            text = re.sub(r"\s+", " ", a.get_text(separator=" ")).strip()
            path = urllib.parse.urlparse(validated_url).path
            item = {
                "url": validated_url,
                "href": a["href"].strip(),
                "text": text,
                "zone": "body",
                "path": path
            }
            body_links.append(item)
            all_links.append(item)

    return {
        "nav_links": nav_links,
        "footer_links": footer_links,
        "body_links": body_links,
        "all_links": all_links
    }


# ─── 3. Semantic Link Router & Categorizer ───────────────────────────────────

# Target operational categories and their matching keyword lexicons
OPERATIONAL_CATEGORIES = {
    "about": {
        "exact_texts": {"about", "about us", "about company", "our company", "who we are", "company profile", "our story", "overview", "corporate overview"},
        "path_terms": ["about", "about-us", "our-company", "who-we-are", "profile", "company-profile", "overview", "our-story", "corporate"],
        "text_terms": ["about", "our company", "who we are", "company profile", "our story", "overview", "history", "mission"]
    },
    "services_operations": {
        "exact_texts": {"services", "our services", "solutions", "what we do", "capabilities", "products", "operations", "facilities", "manufacturing", "technology"},
        "path_terms": ["services", "our-services", "solutions", "capabilities", "operations", "facilities", "manufacturing", "plants", "products", "what-we-do", "technology", "engineering"],
        "text_terms": ["services", "solutions", "capabilities", "operations", "facilities", "manufacturing", "products", "what we do", "technology", "equipment", "production"]
    },
    "contact": {
        "exact_texts": {"contact", "contact us", "get in touch", "reach us", "locations", "offices", "our offices", "support", "inquiry"},
        "path_terms": ["contact", "contact-us", "get-in-touch", "reach-us", "locations", "offices", "support", "inquiry", "enquiry", "office-locations"],
        "text_terms": ["contact", "get in touch", "reach us", "locations", "offices", "support", "inquiry", "connect"]
    },
    "careers_hiring": {
        "exact_texts": {"careers", "jobs", "work with us", "join us", "openings", "join our team", "vacancies", "employment"},
        "path_terms": ["careers", "jobs", "work-with-us", "openings", "join-us", "join-our-team", "vacancies", "employment", "hiring"],
        "text_terms": ["careers", "jobs", "work with us", "openings", "join us", "join our team", "vacancies", "employment", "hiring"]
    }
}

# Negative path terms to demote (blogs, news, announcements, press releases)
DISQUALIFYING_PATH_TERMS = [
    "/blog/", "/news/", "/press-release/", "/articles/", "/tag/", "/category/",
    "/author/", "/events/", "/webinars/", "/podcast/", "/insights/"
]


def score_link_for_category(link_item: Dict[str, str], category: str) -> float:
    """
    Computes a relevance score (0 - 100) for a link candidate against a specific category.
    Evaluates DOM zone, exact anchor text match, path matching, and path conciseness.
    """
    config = OPERATIONAL_CATEGORIES.get(category)
    if not config:
        return 0.0

    url = link_item.get("url", "")
    path = link_item.get("path", "").lower()
    text = link_item.get("text", "").lower().strip()
    zone = link_item.get("zone", "body")

    # Demote noise paths
    if any(noise in path for noise in DISQUALIFYING_PATH_TERMS):
        return 0.0

    score = 0.0

    # 1. Structural Zone Weight
    if zone == "nav":
        score += 15.0
    elif zone == "body":
        score += 8.0
    elif zone == "footer":
        score += 5.0

    # 2. Anchor Text Evaluation
    if text in config["exact_texts"]:
        score += 35.0
    elif any(term in text for term in config["text_terms"]):
        score += 20.0

    # 3. URL Path Evaluation
    clean_slug = path.strip("/").replace("_", "-")
    if clean_slug in config["path_terms"]:
        score += 35.0
    elif any(term in path for term in config["path_terms"]):
        score += 18.0

    # 4. Path Conciseness Bonus (prefer /about over /company/history/2021/about-story)
    segments = [s for s in path.split("/") if s]
    if len(segments) == 1:
        score += 12.0
    elif len(segments) == 2:
        score += 6.0
    elif len(segments) > 3:
        score -= 10.0

    return score


def categorize_and_prioritize_links(
    links: List[Dict[str, str]],
    base_url: str
) -> Dict[str, str]:
    """
    Evaluates all extracted internal links and maps them to key operational categories.
    Selects the highest scoring URL for each category (about, services_operations, contact, careers_hiring).

    Returns:
        {
            "about": "https://company.com/about-us",
            "services_operations": "https://company.com/services",
            "contact": "https://company.com/contact",
            "careers_hiring": "https://company.com/careers"
        }
    """
    if not links:
        return {}

    categorized_targets: Dict[str, str] = {}
    best_scores: Dict[str, float] = {}

    for category in OPERATIONAL_CATEGORIES:
        best_url = None
        highest_score = 0.0

        for link in links:
            score = score_link_for_category(link, category)
            if score >= 20.0 and score > highest_score:
                highest_score = score
                best_url = link["url"]

        if best_url:
            categorized_targets[category] = best_url
            best_scores[category] = highest_score

    # Avoid duplicate URLs across categories (assign to the category with highest relative score)
    url_to_cat: Dict[str, str] = {}
    cleaned_targets: Dict[str, str] = {}

    for cat, url in categorized_targets.items():
        if url not in url_to_cat:
            url_to_cat[url] = cat
            cleaned_targets[cat] = url
        else:
            prev_cat = url_to_cat[url]
            if best_scores.get(cat, 0) > best_scores.get(prev_cat, 0):
                cleaned_targets.pop(prev_cat, None)
                url_to_cat[url] = cat
                cleaned_targets[cat] = url

    return cleaned_targets


# ─── 4. Subpage Text Extraction & Network Helpers ─────────────────────────────

def extract_clean_page_text(html: str) -> str:
    """Strips scripts, styles, svg, and noisy markup, returning clean readable text."""
    if not html:
        return ""
    try:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        text = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()
        return text
    except Exception:
        return ""


async def fetch_page_html(url: str, timeout: float = 4.0) -> str:
    """
    Fetches HTML content of a single page asynchronously using httpx.
    Falls back to urllib in a thread pool if TLS/SSL or connection issues occur.
    """
    try:
        async with httpx.AsyncClient(
            headers=BROWSER_HEADERS,
            timeout=timeout,
            follow_redirects=True,
            verify=False
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and resp.text:
                return resp.text
    except Exception as e:
        logger.debug(f"[SmartCrawler] httpx fetch failed for {url}: {e}")

    # Fallback to urllib executor
    loop = asyncio.get_event_loop()
    def _urllib_fetch():
        try:
            req = urllib.request.Request(url, headers=BROWSER_HEADERS)
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
        return await loop.run_in_executor(None, _urllib_fetch)
    except Exception:
        return ""


# ─── 5. Dynamic Multi-Page Crawler Entry Point ───────────────────────────────

async def crawl_smart_dom_target(
    domain: str,
    homepage_url: str,
    homepage_html: str = "",
    max_pages: int = 4
) -> Dict[str, Any]:
    """
    Main entry point for Step 6: Dynamic DOM Header/Footer/Nav Link Parser.

    1. Receives or fetches homepage HTML.
    2. Parses DOM structural zones (<nav>, <header>, <footer>, <body>).
    3. Categorizes and prioritizes the top operational subpages (about, services/operations, contact, careers).
    4. Concurrently crawls the top subpages (up to max_pages total pages).
    5. Assembles combined multi-page evidence text and formatted source labels.

    Returns:
        {
            "combined_text": str,
            "source_label": str,
            "homepage_text": str,
            "pages": Dict[str, Dict[str, str]],
            "dom_links": Dict[str, List[Dict[str, str]]],
            "categorized_targets": Dict[str, str],
            "total_pages_crawled": int
        }
    """
    if not homepage_url.startswith(("http://", "https://")):
        homepage_url = f"https://{homepage_url}"

    # 1. Acquire Homepage HTML
    if not homepage_html:
        homepage_html = await fetch_page_html(homepage_url, timeout=4.0)

    homepage_text = extract_clean_page_text(homepage_html)
    if not homepage_text:
        return {
            "combined_text": "",
            "source_label": "none",
            "homepage_text": "",
            "pages": {},
            "dom_links": {"nav_links": [], "footer_links": [], "body_links": [], "all_links": []},
            "categorized_targets": {},
            "total_pages_crawled": 0
        }

    # 2. Extract DOM Structural Links
    dom_links = extract_internal_dom_links(homepage_html, homepage_url)
    all_extracted_links = dom_links.get("all_links", [])

    # 3. Categorize & Prioritize
    categorized = categorize_and_prioritize_links(all_extracted_links, homepage_url)

    # 4. Select top target subpages to crawl (up to max_pages - 1)
    # Order of priority: about, services_operations, contact, careers_hiring
    priority_order = ["about", "services_operations", "contact", "careers_hiring"]
    selected_subpages: List[Tuple[str, str]] = []  # (category, url)

    for cat in priority_order:
        if cat in categorized:
            target_url = categorized[cat]
            if target_url != homepage_url and not any(u == target_url for _, u in selected_subpages):
                selected_subpages.append((cat, target_url))
                if len(selected_subpages) >= (max_pages - 1):
                    break

    pages_crawled: Dict[str, Dict[str, str]] = {
        "homepage": {
            "url": homepage_url,
            "text": homepage_text,
            "category": "homepage"
        }
    }

    fetched_sources = ["homepage"]

    # 5. Concurrently Fetch Subpages
    if selected_subpages:
        sub_tasks = [fetch_page_html(sub_url, timeout=3.5) for _, sub_url in selected_subpages]
        sub_htmls = await asyncio.gather(*sub_tasks, return_exceptions=True)

        for (cat, sub_url), html_res in zip(selected_subpages, sub_htmls):
            if isinstance(html_res, str) and html_res.strip():
                clean_sub_text = extract_clean_page_text(html_res)
                if len(clean_sub_text) > 80:
                    path_name = urllib.parse.urlparse(sub_url).path or sub_url
                    pages_crawled[cat] = {
                        "url": sub_url,
                        "text": clean_sub_text,
                        "category": cat
                    }
                    fetched_sources.append(path_name)

    # 6. Assemble Combined Text
    combined_parts = [
        f"[PAGE: Homepage] ({urllib.parse.urlparse(homepage_url).path or '/'})\n{homepage_text[:2000]}"
    ]

    for cat, page_data in pages_crawled.items():
        if cat == "homepage":
            continue
        p_url = page_data.get("url", "")
        p_text = page_data.get("text", "")
        p_path = urllib.parse.urlparse(p_url).path or p_url
        cat_title = cat.replace("_", " ").title()
        combined_parts.append(
            f"\n\n--- [PAGE: {cat_title}] ({p_path}) ---\n{p_text[:1400]}"
        )

    combined_text = "\n".join(combined_parts)
    source_label = " + ".join(fetched_sources)

    return {
        "combined_text": combined_text,
        "source_label": source_label,
        "homepage_text": homepage_text,
        "pages": pages_crawled,
        "dom_links": dom_links,
        "categorized_targets": categorized,
        "total_pages_crawled": len(pages_crawled)
    }
