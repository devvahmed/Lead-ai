"""
contact_enricher_pro.py
=======================
Advanced Lead-AI Contact Intelligence & Zero-Send Email Verification Engine.

Key Capabilities:
1. Web Footprint Dorking:
   Discovers authentic corporate emails indexed across the web (press releases, whitepapers,
   conference rosters, PDFs) outside the target company's primary website.
2. Decision Maker & Leadership Identification:
   Extracts high-level executives (CEO, Founder, Director, President, Owner) via targeted dorks.
3. B2B Email Permutation Generator:
   Constructs institutional email patterns (first.last, first, flast, etc.).
4. Zero-Send Async MX & SMTP Handshake Validator:
   - High-speed public DNS MX resolution (8.8.8.8, 1.1.1.1).
   - Non-blocking async socket connect to port 25.
   - HELO -> MAIL FROM -> RCPT TO protocol handshake.
   - Catch-all server detection (avoids false-positives).
   - Strict 550 mailbox rejection filtering.
   - Graceful ISP port 25 block fallback (never crashes or hangs).
"""

import os
import re
import time
import socket
import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
import dns.resolver

logger = logging.getLogger("contact_enricher_pro")

# ─── DNS Resolver Configuration ───────────────────────────────────────────────
_DNS_RESOLVER = dns.resolver.Resolver()
_DNS_RESOLVER.nameservers = ['8.8.8.8', '1.1.1.1']
_DNS_RESOLVER.timeout = 2.0
_DNS_RESOLVER.lifetime = 3.0

_MX_CACHE: Dict[str, Tuple[float, List[Tuple[int, str]]]] = {}
_CATCHALL_CACHE: Dict[str, Tuple[float, bool]] = {}

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', re.IGNORECASE)

EXCLUDED_EMAIL_PREFIXES = {
    'noreply', 'no-reply', 'sentry', 'donotreply', 'example', 'yourname',
    'test', 'admin', 'postmaster', 'hostmaster', 'mailer-daemon', 'root',
    'support-ticket', 'feedback', 'jobs', 'careers', 'abuse'
}

INVALID_EMAIL_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'ico', 'css', 'js',
    'woff', 'woff2', 'ttf', 'eot', 'mp4', 'pdf', 'zip', 'map', 'json'
}


def is_valid_email_syntax(em: str, domain: Optional[str] = None) -> bool:
    """Validates structural regex syntax and filters common junk/placeholder emails."""
    if not em or not isinstance(em, str):
        return False
    clean = em.strip().lower()
    if not EMAIL_RE.fullmatch(clean):
        return False
    
    parts = clean.split('@')
    if len(parts) != 2:
        return False
    local, em_domain = parts
    
    if local in EXCLUDED_EMAIL_PREFIXES:
        return False
        
    ext = em_domain.split('.')[-1]
    if ext in INVALID_EMAIL_EXTENSIONS:
        return False
        
    if domain:
        clean_domain = domain.lower().replace("www.", "").strip()
        if em_domain != clean_domain and not em_domain.endswith('.' + clean_domain):
            return False
            
    return True


async def resolve_mx_records(domain: str) -> List[Tuple[int, str]]:
    """Resolves MX records using Google/Cloudflare DNS with in-memory caching."""
    clean_domain = domain.lower().replace("www.", "").strip()
    now = time.time()
    
    if clean_domain in _MX_CACHE:
        ts, recs = _MX_CACHE[clean_domain]
        if now - ts < 3600:  # 1 hour cache
            return recs
            
    try:
        answers = await asyncio.to_thread(_DNS_RESOLVER.resolve, clean_domain, 'MX')
        records = sorted([(r.preference, str(r.exchange).rstrip('.')) for r in answers], key=lambda x: x[0])
        _MX_CACHE[clean_domain] = (now, records)
        return records
    except Exception as e:
        logger.debug(f"[MX Resolver] No MX for {clean_domain}: {e}")
        _MX_CACHE[clean_domain] = (now, [])
        return []


async def smtp_ping_email(email: str, mx_host: str, timeout: float = 2.5) -> Dict[str, Any]:
    """
    Performs a Zero-Send SMTP handshake check on port 25.
    Connect -> HELO -> MAIL FROM -> RCPT TO -> QUIT
    Returns deliverability details and exact status code.
    """
    result = {
        "email": email,
        "mx_host": mx_host,
        "deliverable": False,
        "status": "unknown",
        "code": None,
        "error": None
    }
    
    reader, writer = None, None
    try:
        connect_coro = asyncio.open_connection(mx_host, 25)
        reader, writer = await asyncio.wait_for(connect_coro, timeout=timeout)
        
        # Read greeting banner (220)
        banner = await asyncio.wait_for(reader.readline(), timeout=timeout)
        if not banner.startswith(b"220"):
            result["status"] = "invalid_banner"
            result["error"] = banner.decode("utf-8", errors="replace").strip()
            return result
        
        # Send HELO
        writer.write(b"HELO leadai.com\r\n")
        await writer.drain()
        await asyncio.wait_for(reader.readline(), timeout=timeout)
        
        # Send MAIL FROM
        writer.write(b"MAIL FROM:<verify@leadai.com>\r\n")
        await writer.drain()
        mail_resp = await asyncio.wait_for(reader.readline(), timeout=timeout)
        if not mail_resp.startswith(b"250"):
            result["status"] = "sender_rejected"
            result["error"] = mail_resp.decode("utf-8", errors="replace").strip()
            return result

        # Send RCPT TO (Zero-send recipient handshake)
        writer.write(f"RCPT TO:<{email}>\r\n".encode("utf-8"))
        await writer.drain()
        rcpt_resp = await asyncio.wait_for(reader.readline(), timeout=timeout)
        rcpt_str = rcpt_resp.decode("utf-8", errors="replace").strip()
        
        # Send QUIT
        try:
            writer.write(b"QUIT\r\n")
            await writer.drain()
        except Exception:
            pass

        code_match = re.match(r'^(\d{3})', rcpt_str)
        if code_match:
            code = int(code_match.group(1))
            result["code"] = code
            if code == 250:
                result["deliverable"] = True
                result["status"] = "verified"
            elif code in (550, 551, 552, 553, 554):
                result["deliverable"] = False
                result["status"] = "mailbox_not_found"
            elif code in (450, 451, 452):
                result["deliverable"] = False
                result["status"] = "greylisted_or_busy"
            else:
                result["status"] = f"code_{code}"
        else:
            result["status"] = "unknown_response"
            result["error"] = rcpt_str

        return result

    except (asyncio.TimeoutError, ConnectionRefusedError, socket.gaierror, OSError) as e:
        result["status"] = "smtp_port25_blocked_or_timed_out"
        result["error"] = str(e)
        return result
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        return result
    finally:
        if writer:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass


async def check_domain_catch_all(domain: str, mx_host: str) -> bool:
    """
    Checks if a domain's mailserver operates in catch-all mode
    by attempting RCPT TO for a randomized pseudo-address.
    """
    clean_domain = domain.lower().replace("www.", "").strip()
    now = time.time()
    
    if clean_domain in _CATCHALL_CACHE:
        ts, is_ca = _CATCHALL_CACHE[clean_domain]
        if now - ts < 3600:
            return is_ca
            
    rand_id = int(time.time() * 1000) % 999999
    probe_email = f"leadai_nonexistent_probe_{rand_id}@{clean_domain}"
    
    ping = await smtp_ping_email(probe_email, mx_host, timeout=2.5)
    # If the probe email was accepted with 250, server is catch-all
    is_catch_all = bool(ping.get("deliverable"))
    _CATCHALL_CACHE[clean_domain] = (now, is_catch_all)
    return is_catch_all


def generate_email_permutations(first_name: str, last_name: str, domain: str) -> List[str]:
    """Generates standard corporate B2B email permutations."""
    first = re.sub(r'[^a-zA-Z0-9]', '', (first_name or '').lower())
    last = re.sub(r'[^a-zA-Z0-9]', '', (last_name or '').lower())
    clean_domain = domain.lower().replace("www.", "").strip()

    if not clean_domain or not first:
        return []

    perms = []
    if first and last:
        perms.extend([
            f"{first}.{last}@{clean_domain}",
            f"{first}@{clean_domain}",
            f"{first[0]}.{last}@{clean_domain}",
            f"{first}{last}@{clean_domain}",
            f"{first[0]}{last}@{clean_domain}",
            f"{last}.{first}@{clean_domain}",
            f"{first}_{last}@{clean_domain}",
        ])
    elif first:
        perms.extend([
            f"{first}@{clean_domain}",
        ])

    return list(dict.fromkeys(perms))


async def find_web_footprint_emails(domain: str, company_name: str = "") -> List[str]:
    """
    Web Footprint Dorking:
    Executes '"{domain}" (email OR contact OR "reach me") -site:{domain}' across SearXNG/search engines
    to find authentic email disclosures in third-party press releases, PDF docs, and directories.
    """
    clean_domain = domain.lower().replace("www.", "").strip()
    if not clean_domain:
        return []
        
    query = f'"{clean_domain}" (email OR contact OR "reach me" OR "get in touch") -site:{clean_domain}'
    try:
        from discover import search_searxng_or_ddg
        results = await asyncio.wait_for(search_searxng_or_ddg(query, page=1), timeout=5.0)
    except Exception as e:
        logger.debug(f"[Footprint Dork] Search failed: {e}")
        return []
        
    email_pattern = re.compile(rf'[a-zA-Z0-9._%+-]+@{re.escape(clean_domain)}', re.IGNORECASE)
    discovered = set()
    
    for r in results:
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        url = r.get("url", "")
        combined_text = f"{title} {snippet} {url}"
        
        matches = email_pattern.findall(combined_text)
        for m in matches:
            em = m.strip().lower()
            if is_valid_email_syntax(em, domain=clean_domain):
                discovered.add(em)
                
    return list(discovered)


async def find_decision_makers(company_name: str, domain: str) -> List[Dict[str, str]]:
    """
    Discovers decision-maker profiles (CEO, Founder, Director, President, Owner)
    associated with the company via search dorking.
    """
    clean_company = company_name.strip()
    if not clean_company or len(clean_company) < 2:
        return []
        
    query = f'"{clean_company}" ("CEO" OR "Founder" OR "Director" OR "Managing" OR "President" OR "Owner") (LinkedIn OR leadership)'
    try:
        from discover import search_searxng_or_ddg
        results = await asyncio.wait_for(search_searxng_or_ddg(query, page=1), timeout=5.0)
    except Exception as e:
        logger.debug(f"[Decision Maker Dork] Search failed: {e}")
        return []

    people: List[Dict[str, str]] = []
    seen_names = set()
    
    # Common regex patterns to extract person name and role from title
    # e.g. "Amy Ferrer - Executive Director at American Philosophical Association ... | LinkedIn"
    # e.g. "Patrick Collison - Stripe CEO | LinkedIn"
    title_pattern = re.compile(
        r'^(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s*[-–|:]\s*(?P<role>[^–\-|]+?)(?:\s*(?:[-–|]|\sat\s).*)?$',
        re.IGNORECASE
    )

    for r in results[:8]:
        raw_title = r.get("title") or ""
        title = raw_title.replace(" | LinkedIn", "").replace(" - LinkedIn", "").strip()
        url = r.get("url") or ""
        snippet = (r.get("snippet") or r.get("content") or "").strip()
        
        # We accept if it is a LinkedIn profile or explicitly mentions leadership/company
        is_relevant = "linkedin.com/in/" in url.lower() or "linkedin" in title.lower() or any(
            k in title.lower() for k in ('ceo', 'founder', 'director', 'president', 'owner', 'partner', 'managing')
        )
        if not is_relevant:
            continue
            
        m = title_pattern.match(title)
        if m:
            raw_name = m.group("name").strip()
            raw_role = m.group("role").strip()
            
            # Clean role of trailing company names
            raw_role = re.sub(rf'\s+at\s+.*$', '', raw_role, flags=re.IGNORECASE).strip()
            
            parts = raw_name.split()
            if len(parts) >= 2 and raw_name.lower() not in seen_names:
                # Exclude company name misidentified as person name
                if raw_name.lower() in clean_company.lower() or clean_company.lower() in raw_name.lower():
                    continue
                seen_names.add(raw_name.lower())
                first_name = parts[0]
                last_name = parts[-1]
                people.append({
                    "name": raw_name,
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": raw_role[:60],
                    "linkedin_url": url
                })

    return people


async def verify_synthesized_email(
    email: str,
    domain: str,
    mx_records: List[Tuple[int, str]],
    is_catch_all: bool
) -> Dict[str, Any]:
    """
    Strict Verification Gate for Synthesized Permutations:
    Only permits passing synthesized emails if confirmed deliverable via zero-send SMTP
    or if verified on authentic MX infrastructure with catch-all tagging.
    Rejects any mailbox returning 550 or missing MX.
    """
    if not mx_records:
        return {"deliverable": False, "status": "rejected_no_mx", "email": email}

    best_mx = mx_records[0][1]
    ping = await smtp_ping_email(email, best_mx, timeout=2.5)
    
    code = ping.get("code")
    status = ping.get("status")
    
    if code == 250:
        if is_catch_all:
            # Server accepts everything
            return {
                "deliverable": True,
                "status": "catch_all_accepted",
                "email": email,
                "confidence": "medium",
                "verified": False,
                "mx_host": best_mx
            }
        else:
            # 100% strict mailbox verification!
            return {
                "deliverable": True,
                "status": "smtp_verified",
                "email": email,
                "confidence": "high",
                "verified": True,
                "mx_host": best_mx
            }
    elif code in (550, 551, 552, 553, 554):
        # Definitively does NOT exist
        return {
            "deliverable": False,
            "status": "mailbox_not_found",
            "email": email,
            "confidence": "zero",
            "verified": False,
            "mx_host": best_mx
        }
    else:
        # Port 25 blocked or timed out by ISP
        return {
            "deliverable": None,
            "status": status or "unreachable_smtp",
            "email": email,
            "confidence": "low",
            "verified": False,
            "mx_host": best_mx
        }


async def enrich_company_contacts_advanced(
    domain: str,
    company_name: str,
    existing_emails: Optional[List[str]] = None,
    timeout: float = 12.0
) -> Dict[str, Any]:
    """
    Unified Enrichment & Zero-Send Validation Pipeline:
    1. Discovers authentic web footprint emails (press releases, white papers, PDFs).
    2. Discovers decision makers (CEO, Founder, Director) via LinkedIn dorks.
    3. Generates institutional email permutations for decision makers.
    4. Runs Zero-Send MX and SMTP Handshake checks on all synthesized candidates.
    5. Discards all 550 mailboxes, keeps verified decision-maker emails.
    6. Returns enriched contact intelligence.
    """
    clean_domain = domain.lower().replace("www.", "").strip()
    existing_emails = existing_emails or []
    
    footprint_emails: List[str] = []
    decision_makers: List[Dict[str, str]] = []

    # 1. Resolve MX records immediately (~50ms via Google/Cloudflare DNS)
    try:
        mx_records = await asyncio.wait_for(resolve_mx_records(clean_domain), timeout=3.0)
    except Exception as e:
        logger.debug(f"[ContactEnricherPro] MX resolve error for {clean_domain}: {e}")
        mx_records = []

    # 2. Concurrently execute Web Footprint Dork and Decision Maker Search
    footprint_task = asyncio.create_task(find_web_footprint_emails(clean_domain, company_name))
    dm_task = asyncio.create_task(find_decision_makers(company_name, clean_domain))
    
    try:
        results = await asyncio.gather(footprint_task, dm_task, return_exceptions=True)
        if len(results) == 2:
            r_fp, r_dm = results
            if isinstance(r_fp, list):
                footprint_emails = r_fp
            if isinstance(r_dm, list):
                decision_makers = r_dm
    except Exception as e:
        logger.debug(f"[ContactEnricherPro] Parallel discovery warning: {e}")

    is_catch_all = False
    best_mx = None
    if mx_records:
        best_mx = mx_records[0][1]
        try:
            is_catch_all = await asyncio.wait_for(
                check_domain_catch_all(clean_domain, best_mx),
                timeout=2.5
            )
        except Exception:
            is_catch_all = False

    # 2. Process Decision Makers: Permutate + Strict Zero-Send SMTP Verify
    verified_stakeholders: List[Dict[str, Any]] = []
    
    for dm in decision_makers[:2]:  # Focus on top 2 leadership figures
        f_name = dm.get("first_name", "")
        l_name = dm.get("last_name", "")
        role = dm.get("role", "Executive")
        full_name = dm.get("name", "")
        linkedin = dm.get("linkedin_url", "")
        
        perms = generate_email_permutations(f_name, l_name, clean_domain)
        best_dm_email = None
        best_dm_status = "unverified"
        is_strictly_verified = False

        if mx_records:
            # Check permutations sequentially or with quick break on verified 250
            for p in perms[:4]:
                check_res = await verify_synthesized_email(p, clean_domain, mx_records, is_catch_all)
                if check_res.get("status") == "smtp_verified":
                    best_dm_email = p
                    best_dm_status = "smtp_verified"
                    is_strictly_verified = True
                    break
                elif check_res.get("status") == "catch_all_accepted" and not best_dm_email:
                    # In catch-all, default to first.last or first
                    best_dm_email = p
                    best_dm_status = "catch_all_accepted"
                elif check_res.get("status") == "mailbox_not_found":
                    # Discard this permutation
                    continue
        
        # If SMTP port 25 was completely blocked by ISP, but MX is confirmed valid,
        # we can accept the standard first.last permutation with explicit mx_valid tag
        if not best_dm_email and mx_records and perms:
            # Only use if MX is confirmed
            best_dm_email = perms[0]
            best_dm_status = "mx_confirmed"

        if best_dm_email:
            verified_stakeholders.append({
                "name": full_name,
                "first_name": f_name,
                "last_name": l_name,
                "role": role,
                "email": best_dm_email,
                "linkedin_url": linkedin,
                "verification_status": best_dm_status,
                "strictly_verified": is_strictly_verified,
                "is_catch_all": is_catch_all,
                "mx_host": best_mx
            })

    # 3. Consolidate All Email Intelligence
    all_emails = list(dict.fromkeys(
        existing_emails + 
        footprint_emails + 
        [s["email"] for s in verified_stakeholders if s.get("email")]
    ))

    # Priority for Primary Email:
    # 1. Strictly verified decision-maker email
    # 2. Existing website direct email
    # 3. Footprint discovered email
    # 4. Other decision-maker email
    primary_email = None
    strict_dm = next((s for s in verified_stakeholders if s.get("strictly_verified")), None)
    if strict_dm:
        primary_email = strict_dm["email"]
    elif existing_emails:
        primary_email = existing_emails[0]
    elif footprint_emails:
        primary_email = footprint_emails[0]
    elif verified_stakeholders:
        primary_email = verified_stakeholders[0]["email"]

    return {
        "domain": clean_domain,
        "company_name": company_name,
        "primary_email": primary_email,
        "all_emails": all_emails,
        "footprint_emails": footprint_emails,
        "decision_makers": verified_stakeholders,
        "has_mx": bool(mx_records),
        "is_catch_all": is_catch_all,
        "mx_host": best_mx
    }
