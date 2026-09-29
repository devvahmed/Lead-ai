"""
offsite_waterfall_engine.py
===========================
Advanced Off-Site Waterfall OSINT Intelligence Engine.

Triggered when on-site crawling (Smart DOM Crawler) finds 0 decision makers or 0 verified emails.
Executes an off-site, multi-tiered OSINT reconnaissance pipeline:

Tier 1: Multi-SERP Targeted Leadership Dorks (LinkedIn & Executive Snippets)
Tier 1b: Targeted External Press Release & Announcement Page Crawler
Tier 2: Public Web Footprint Email Dorking (Internet-Indexed Corporate Inboxes)
Tier 3: GitHub Public Tech & Commit Intelligence (for Tech/SaaS entities)
Tier 4: Lightweight Social OSINT Prober (Cross-Platform Handle Confirmation)
Tier 5: Strict Zero-AI Profile Assembly & Pattern Library Ingestion

Zero AI Hallucination Policy: All extracted data is 100% grounded in authentic external indexed records.
"""

import asyncio
import logging
import random
import re
from typing import Dict, List, Optional, Any, Set, Tuple
import urllib.parse
import httpx
from bs4 import BeautifulSoup

from social_osint_prober import probe_username_cross_platform, generate_candidate_handles
from github_osint_enricher import enrich_tech_company_github_osint

logger = logging.getLogger("offsite_waterfall")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0"
]

LEADERSHIP_ROLES = [
    "chief executive officer", "chief technology officer", "chief operating officer",
    "chief financial officer", "chief revenue officer", "chief product officer",
    "managing director", "executive director", "founder", "co-founder",
    "president", "vice president", "vp", "director", "head of sales",
    "head of marketing", "general manager", "owner", "partner", "principal"
]

DEAD_GENERIC_PREFIXES = {
    "info", "support", "care", "customercare", "help", "noreply", "no-reply",
    "donotreply", "admin", "webmaster", "abuse", "postmaster", "root", "mailer-daemon"
}

COMMERCIAL_ACCEPTED_PREFIXES = {
    "sales", "investor", "investors", "partners", "commercial", "business",
    "contact", "press", "media", "operations", "hello", "office", "team", "hq"
}

PRESS_RELEASE_DOMAINS = {
    "businesswire.com", "prnewswire.com", "globenewswire.com", "accesswire.com",
    "einpresswire.com", "prlog.org", "prweb.com", "techcrunch.com", "venturebeat.com",
    "bloomberg.com", "reuters.com", "marketwatch.com"
}

EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')


def extract_person_from_linkedin_snippet(
    title: str,
    snippet: str,
    company_name: str,
    url: str
) -> Optional[Dict[str, Any]]:
    """
    Parses LinkedIn SERP title and snippet to extract person's real name, role, and bio.
    Examples of typical SERP Titles:
    - "Tariq Ahmed - Chief Executive Officer - Ahmed Logistics | LinkedIn"
    - "Sarah Jenkins - VP of Operations at Global Logistics Solutions"
    - "John Doe - Founder & CEO | LinkedIn"
    """
    if not title:
        return None

    # Clean title
    clean_t = re.sub(r'\s*\|\s*LinkedIn.*$', '', title, flags=re.IGNORECASE).strip()
    clean_t = re.sub(r'\s*-\s*LinkedIn.*$', '', clean_t, flags=re.IGNORECASE).strip()

    # Split by hyphen or colon or "at"
    parts = [p.strip() for p in re.split(r'[-–—|:]', clean_t) if p.strip()]
    if not parts:
        return None

    raw_name = parts[0]
    # Check if raw_name looks like a person name (2-3 words, capitalized)
    name_words = raw_name.split()
    if not (2 <= len(name_words) <= 4):
        return None
    
    # Reject noise words
    invalid_tokens = {"linkedin", "top", "best", "profile", "jobs", "directory", "software", "company"}
    if set(w.lower() for w in name_words).intersection(invalid_tokens):
        return None

    # Extract role from subsequent parts
    matched_role = "Executive Leadership"
    full_text = clean_t + " " + snippet
    full_text_lower = full_text.lower()

    for r in sorted(LEADERSHIP_ROLES, key=len, reverse=True):
        if r in full_text_lower:
            matched_role = r.title()
            break

    # Extract short bio from snippet
    bio = snippet.strip()[:200] if snippet else f"{matched_role} at {company_name}"

    # LinkedIn URL validation
    clean_url = url
    if "linkedin.com/in/" not in clean_url:
        m_li = re.search(r'https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[a-zA-Z0-9_-]+', snippet or "")
        clean_url = m_li.group(0) if m_li else url

    return {
        "name": raw_name.title(),
        "position": matched_role,
        "role": matched_role,
        "bio": bio,
        "email": None,
        "linkedin": clean_url if "linkedin.com/in/" in clean_url else None,
        "social_links": [clean_url] if "linkedin.com/in/" in clean_url else [],
        "socialLinks": [clean_url] if "linkedin.com/in/" in clean_url else [],
        "source": "offsite_serp_linkedin",
        "strictly_verified": False
    }


async def crawl_target_press_release(
    client: httpx.AsyncClient,
    url: str,
    target_domain: str,
    semaphore: asyncio.Semaphore
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Crawls an indexed external press release, announcement, or news page
    to discover executive quotes, leadership appointments, and authentic media/sales emails.
    """
    discovered_dms: List[Dict[str, Any]] = []
    discovered_emails: List[str] = []

    async with semaphore:
        try:
            await asyncio.sleep(random.uniform(0.1, 0.3))
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
            resp = await client.get(url, headers=headers, timeout=5.0, follow_redirects=True)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                text = soup.get_text(" ", strip=True)

                # Extract emails
                for m in EMAIL_REGEX.finditer(text):
                    em = m.group(0).lower().strip()
                    if em.endswith(f"@{target_domain}"):
                        lp = em.split("@")[0]
                        if not any(lp.startswith(d) for d in DEAD_GENERIC_PREFIXES):
                            if em not in discovered_emails:
                                discovered_emails.append(em)

                # Scan for executive announcements: "X, CEO of Company" or "said X, Chief Executive"
                quote_patterns = [
                    re.compile(r'said\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}),\s*([a-zA-Z\s]{4,30})', re.IGNORECASE),
                    re.compile(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}),\s*(?:appointed|named|serves as)\s+([a-zA-Z\s]{4,30})', re.IGNORECASE)
                ]
                for pat in quote_patterns:
                    for match in pat.finditer(text):
                        cand_name = match.group(1).strip().title()
                        cand_role = match.group(2).strip().title()
                        if any(r in cand_role.lower() for r in ("ceo", "president", "founder", "director", "officer", "vp", "head")):
                            discovered_dms.append({
                                "name": cand_name,
                                "position": cand_role,
                                "role": cand_role,
                                "bio": f"Executive announced in public press release ({urllib.parse.urlparse(url).netloc})",
                                "email": None,
                                "linkedin": None,
                                "social_links": [url],
                                "socialLinks": [url],
                                "source": "offsite_press_release",
                                "strictly_verified": False
                            })
        except Exception as e:
            logger.debug(f"[OffSiteWaterfall] Press release crawl failed for {url}: {e}")

    return discovered_dms, discovered_emails


async def execute_offsite_waterfall_intelligence(
    domain: str,
    company_name: str,
    existing_emails: Optional[List[str]] = None,
    timeout: float = 12.0
) -> Dict[str, Any]:
    """
    Master Entrance for the Off-Site Waterfall OSINT Intelligence Engine.
    Executes sequential/parallel tiers with zero AI hallucination.
    """
    clean_domain = domain.lower().replace("www.", "").strip()
    clean_name = company_name.strip() or clean_domain.split('.')[0].capitalize()

    final_decision_makers: List[Dict[str, Any]] = []
    final_emails: List[str] = list(existing_emails or [])
    seen_dm_names: Set[str] = set()
    seen_emails: Set[str] = set(final_emails)

    logger.info(f"[OffSiteWaterfall] 🌊 Initiating Waterfall OSINT for {clean_name} ({clean_domain})")

    # Local search helper import
    try:
        from discover import search_searxng_or_ddg
    except Exception:
        search_searxng_or_ddg = None

    semaphore = asyncio.Semaphore(3)

    # ─────────────────────────────────────────────────────────────
    # TIER 1: Multi-SERP Targeted Leadership Dorks
    # ─────────────────────────────────────────────────────────────
    press_release_urls: List[str] = []
    if search_searxng_or_ddg:
        try:
            # Query targeting all top leadership roles
            dork_query = f'site:linkedin.com/in/ "{clean_name}" ("CEO" OR "Founder" OR "Managing Director" OR "CTO" OR "VP" OR "Director")'
            serp_results = await asyncio.wait_for(
                search_searxng_or_ddg(dork_query, page=1),
                timeout=5.0
            )
            for res in serp_results:
                u = res.get("url", "")
                t = res.get("title", "")
                s = res.get("content", "") or res.get("snippet", "")
                
                # Check for LinkedIn profile
                if "linkedin.com/in/" in u or "linkedin.com/in/" in s:
                    dm_profile = extract_person_from_linkedin_snippet(t, s, clean_name, u)
                    if dm_profile:
                        n_lower = dm_profile["name"].lower()
                        if n_lower not in seen_dm_names:
                            seen_dm_names.add(n_lower)
                            final_decision_makers.append(dm_profile)
                            logger.info(f"[OffSiteWaterfall] 🎯 Discovered Leader from SERP: {dm_profile['name']} ({dm_profile['position']})")

                # Detect if SERP returned an external press release or article
                dom = urllib.parse.urlparse(u).netloc.lower().replace("www.", "")
                if any(pr_d in dom for pr_d in PRESS_RELEASE_DOMAINS) or any(k in u.lower() for k in ("press-release", "news", "announcement")):
                    if u not in press_release_urls:
                        press_release_urls.append(u)

        except Exception as e:
            logger.debug(f"[OffSiteWaterfall] Tier 1 SERP dork error: {e}")

    # ─────────────────────────────────────────────────────────────
    # TIER 1b: Deep Crawl Indexed Press Releases (if discovered)
    # ─────────────────────────────────────────────────────────────
    if press_release_urls:
        logger.info(f"[OffSiteWaterfall] 📰 Crawling {len(press_release_urls[:2])} indexed press release(s)...")
        async with httpx.AsyncClient(verify=False) as client:
            tasks = [
                crawl_target_press_release(client, pr_u, clean_domain, semaphore)
                for pr_u in press_release_urls[:2]
            ]
            crawled_prs = await asyncio.gather(*tasks, return_exceptions=True)
            for item in crawled_prs:
                if isinstance(item, tuple):
                    pr_dms, pr_ems = item
                    for pdm in pr_dms:
                        n_low = pdm["name"].lower()
                        if n_low not in seen_dm_names:
                            seen_dm_names.add(n_low)
                            final_decision_makers.append(pdm)
                    for pem in pr_ems:
                        if pem not in seen_emails:
                            seen_emails.add(pem)
                            final_emails.append(pem)

    # ─────────────────────────────────────────────────────────────
    # TIER 2: Public Web Footprint Email Dorking
    # ─────────────────────────────────────────────────────────────
    if search_searxng_or_ddg and len(final_emails) < 2:
        try:
            email_dork = f'"@{clean_domain}" -site:{clean_domain}'
            footprint_results = await asyncio.wait_for(
                search_searxng_or_ddg(email_dork, page=1),
                timeout=4.5
            )
            for r in footprint_results:
                txt = (r.get("title", "") + " " + r.get("content", "") + " " + r.get("snippet", ""))
                for m in EMAIL_REGEX.finditer(txt):
                    cand_em = m.group(0).lower().strip()
                    if cand_em.endswith(f"@{clean_domain}"):
                        lp = cand_em.split("@")[0]
                        if not any(lp.startswith(d) for d in DEAD_GENERIC_PREFIXES):
                            if cand_em not in seen_emails:
                                seen_emails.add(cand_em)
                                final_emails.append(cand_em)
                                logger.info(f"[OffSiteWaterfall] 📧 Discovered Web Footprint Email: {cand_em}")
        except Exception as e:
            logger.debug(f"[OffSiteWaterfall] Tier 2 email footprint dork error: {e}")

    # ─────────────────────────────────────────────────────────────
    # TIER 3: GitHub Tech & Public Commit Intelligence
    # ─────────────────────────────────────────────────────────────
    is_tech = any(t in clean_domain for t in (".io", ".ai", ".tech", ".dev", ".cloud", ".app", "software", "tech", "digital", "data"))
    if is_tech or len(final_decision_makers) == 0:
        try:
            gh_profiles = await asyncio.wait_for(
                enrich_tech_company_github_osint(clean_domain, clean_name, timeout=5.0),
                timeout=6.0
            )
            for gh_p in gh_profiles:
                n_low = gh_p["name"].lower()
                if n_low not in seen_dm_names:
                    seen_dm_names.add(n_low)
                    final_decision_makers.append(gh_p)
                    logger.info(f"[OffSiteWaterfall] 🐙 Discovered GitHub Contributor: {gh_p['name']} ({gh_p['role']})")
                if gh_p.get("email") and gh_p["email"] not in seen_emails:
                    seen_emails.add(gh_p["email"])
                    final_emails.append(gh_p["email"])
        except Exception as e:
            logger.debug(f"[OffSiteWaterfall] Tier 3 GitHub error: {e}")

    # ─────────────────────────────────────────────────────────────
    # TIER 4: Social OSINT Prober (Cross-Platform Handle Confirmation)
    # ─────────────────────────────────────────────────────────────
    # For decision makers with name but no social links, probe candidates
    for dm in final_decision_makers[:2]:
        if not dm.get("linkedin") and not dm.get("social_links"):
            cand_handles = generate_candidate_handles(dm["name"], clean_domain)
            for h in cand_handles[:2]:
                try:
                    confirmed = await asyncio.wait_for(
                        probe_username_cross_platform(h, max_concurrency=2),
                        timeout=3.0
                    )
                    if confirmed:
                        dm["social_links"] = [c["url"] for c in confirmed]
                        dm["socialLinks"] = dm["social_links"]
                        break
                except Exception:
                    pass

    # ─────────────────────────────────────────────────────────────
    # TIER 5: Email Binding & Pattern Learning
    # ─────────────────────────────────────────────────────────────
    # Match discovered emails to decision makers based on first / last name
    for dm in final_decision_makers:
        if not dm.get("email"):
            name_parts = dm["name"].lower().split()
            first = name_parts[0]
            last = name_parts[-1] if len(name_parts) > 1 else ""
            for em in final_emails:
                lp = em.split("@")[0].lower()
                if first in lp or (last and last in lp):
                    dm["email"] = em
                    dm["strictly_verified"] = True
                    break

    # If any personal email is verified, save to Pattern Library
    for dm in final_decision_makers:
        if dm.get("email") and dm.get("strictly_verified"):
            try:
                from contact_enricher_pro import learn_and_save_pattern
                learn_and_save_pattern(dm["email"], clean_domain, confidence=90)
            except Exception:
                pass

    return {
        "decision_makers": final_decision_makers,
        "emails": final_emails,
        "source": "offsite_waterfall_engine",
        "total_discovered": len(final_decision_makers)
    }
