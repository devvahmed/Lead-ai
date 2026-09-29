"""
contact_enricher_pro.py
=======================
Advanced Lead-AI Contact Intelligence & Zero-Send Email Verification Engine.

Key Capabilities:
1. Decision Maker & Leadership Extraction:
   - Scans website /about, /team, and /leadership content for key executives (CEO, Founder, Director, President, Owner).
   - Executes clean targeted search dorks on Bing/SearXNG without query breakdown.
2. B2B Email Permutation Generator:
   - Synthesizes institutional email patterns (first.last, first, flast, etc.).
3. Web Footprint Dorking:
   - Discovers corporate emails outside the primary website.
4. Zero-Send Async MX & SMTP Handshake Validator:
   - High-speed public DNS MX resolution (8.8.8.8, 1.1.1.1).
   - Zero-send SMTP verification.
   - Mailbox validation and deliverability scoring.
"""

import os
import re
import html
import time
import socket
import asyncio
import logging
from functools import lru_cache
from typing import Dict, List, Optional, Tuple, Any, Set, Union
import dns.resolver
from smtp_verify import (
    async_verify_email_smtp,
    verify_email_smtp as standalone_verify_email_smtp,
    apply_smtp_policy,
    batch_verify_emails,
    get_email_tier_and_badge,
)
import database  # Pattern Library storage

logger = logging.getLogger("contact_enricher_pro")

# ─── DNS Resolver Configuration ───────────────────────────────────────────────
_DNS_RESOLVER = dns.resolver.Resolver()
_DNS_RESOLVER.nameservers = ['8.8.8.8', '1.1.1.1']
_DNS_RESOLVER.timeout = 2.0
_DNS_RESOLVER.lifetime = 3.0

_MX_CACHE: Dict[str, Tuple[float, List[Tuple[int, str]]]] = {}
_CATCHALL_CACHE: Dict[str, Tuple[float, bool]] = {}

# 🔧 FIX #1: Strict Email Regex & Validation
STRICT_EMAIL = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
)
EMAIL_RE = STRICT_EMAIL

VALID_TLDS: Set[str] = {
    # Standard & enterprise gTLDs
    'com', 'net', 'org', 'info', 'biz', 'pro', 'name',
    # Tech & modern gTLDs
    'io', 'ai', 'co', 'app', 'tech', 'dev', 'cloud', 'digital', 'global',
    'ltd', 'group', 'agency', 'consulting', 'solutions', 'expert', 'media',
    'services', 'systems', 'management', 'enterprises', 'holdings', 'international',
    'associates', 'online', 'store', 'site', 'space',
    # Country Code TLDs (ccTLDs)
    'ae', 'sa', 'uk', 'de', 'us', 'ca', 'au', 'fr', 'eu', 'nl', 'sg', 'ch',
    'es', 'it', 'qa', 'om', 'kw', 'bh', 'pk', 'in', 'my', 'jp', 'cn', 'ru',
    'br', 'za', 'me', 'tr', 'nz', 'ie', 'se', 'no', 'dk', 'fi', 'pl', 'cz',
    'at', 'be', 'hk', 'tw', 'kr', 'eg', 'ng', 'ke', 'gov', 'edu', 'mil'
}

SUSPICIOUS_LOCAL_WORDS: Set[str] = {
    'texas', 'austin', 'before', 'scott', 'bootstrap', 'jquery', 'wp-content',
    'schema', 'retina', 'sprite', 'template', 'theme', 'plugin', 'node_modules'
}

EXCLUDED_EMAIL_PREFIXES = {
    'noreply', 'no-reply', 'sentry', 'donotreply', 'example', 'yourname',
    'test', 'postmaster', 'hostmaster', 'mailer-daemon', 'root',
    'support-ticket', 'abuse'
}

GENERIC_ROLE_PREFIXES: Set[str] = {
    'info', 'contact', 'support', 'sales', 'hello', 'admin', 'office',
    'press', 'inquiries', 'help', 'media', 'team', 'jobs', 'careers',
    'hr', 'marketing', 'legal', 'privacy', 'billing', 'accounts',
    'service', 'services', 'mail', 'webmaster', 'general', 'enquiries',
    'enquiry', 'inquiry', 'customer', 'customercare', 'accounting',
    'finance', 'recruitment', 'recruiting', 'talent', 'business', 'bd', 'helpdesk'
}

INVALID_EMAIL_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'ico', 'css', 'js',
    'woff', 'woff2', 'ttf', 'eot', 'mp4', 'pdf', 'zip', 'map', 'json'
}

# 🔧 FIX #4: Cached MX Record Validation (Per Email)
@lru_cache(maxsize=10000)
def has_mx_record(domain: str) -> bool:
    """
    Cached DNS MX resolution check.
    Returns True if domain has active, resolvable MX records; False otherwise.
    Rejects fake domains like austin.before, Schlumberger.He, P.la in milliseconds.
    """
    if not domain or not isinstance(domain, str):
        return False
    clean_domain = domain.lower().replace("www.", "").strip()
    if not clean_domain or '.' not in clean_domain:
        return False
    try:
        answers = _DNS_RESOLVER.resolve(clean_domain, 'MX', lifetime=3.0)
        return len(answers) > 0
    except Exception:
        return False

# 🔧 FIX #2: Domain Ownership Verification (Anchor Check)
def email_belongs_to_company(email: str, company_domains: Union[str, Set[str], List[str]]) -> bool:
    """
    Rule: Email is only accepted if its domain matches the target company domain or subdomains.
    Rejects foreign/accidental domains (e.g. texas@austin.before, capacities@Schlumberger.He).
    """
    if not email or '@' not in email:
        return False
    email_domain = email.split('@')[1].lower().strip()

    if isinstance(company_domains, str):
        company_domains = [company_domains]

    clean_domains = set()
    for cd in (company_domains or []):
        if not cd:
            continue
        d = cd.lower().strip()
        if "://" in d:
            from urllib.parse import urlparse
            d = urlparse(d).netloc
        d = d.replace("www.", "").strip()
        if d:
            clean_domains.add(d)

    if not clean_domains:
        return True  # If company domain is unknown, cannot restrict

    # Exact match: info@dragonoil.com -> dragonoil.com
    if email_domain in clean_domains:
        return True

    # Subdomain match: mail.dragonoil.com -> dragonoil.com
    for cd in clean_domains:
        if email_domain.endswith('.' + cd):
            return True

    return False

# 🔧 FIX #3: Personal Email Matching & Context Window Filter
def is_personal_email(email: str, person_name: str) -> bool:
    """
    Verifies that the email's local part actually contains key components of the person's name.
    Ensures Saed Mohammed Al Tayer is never linked to texas@austin.before or capacities@...
    """
    if not email or '@' not in email or not person_name:
        return False
    local = email.split('@')[0].lower().strip()
    local_clean = re.sub(r'[^a-z0-9]', '', local)

    # Significant name parts (length >= 3)
    name_parts = [re.sub(r'[^a-z]', '', p.lower()) for p in person_name.split()]
    name_parts = [p for p in name_parts if len(p) >= 3]
    if not name_parts:
        return False

    # Check direct occurrence of first name or last name
    if any(part in local for part in name_parts):
        return True

    # Check first initial + last name (e.g. 'stayer' for Saeed Tayer)
    if len(name_parts) >= 2:
        fi_ln = f"{name_parts[0][0]}{name_parts[-1]}"
        if len(fi_ln) >= 4 and (fi_ln in local_clean or local_clean.startswith(fi_ln)):
            return True
        fn_li = f"{name_parts[0]}{name_parts[-1][0]}"
        if len(fn_li) >= 4 and (fn_li in local_clean or local_clean.startswith(fn_li)):
            return True

    return False

def extract_emails_near_name(
    content: str,
    person_name: str,
    company_domain: str = "",
    window: int = 300
) -> List[str]:
    """
    Structured proximity extraction:
    Extracts emails near a person's name ONLY when both the name and email
    co-exist in the same structural HTML block (<p>, <div>, <li>, <td>, <tr>, etc.)
    and satisfy strict personal email & domain ownership verification.
    """
    if not content or not person_name:
        return []

    name_parts = [p.lower() for p in person_name.split() if len(p) >= 3]
    if not name_parts:
        return []

    # Split HTML or text into structural blocks
    blocks = re.split(
        r'</?(?:p|div|li|td|tr|section|article|header|aside|blockquote)[^>]*>|(?:\r?\n){2,}',
        content,
        flags=re.IGNORECASE
    )

    results: List[str] = []
    seen: Set[str] = set()

    for block in blocks:
        if not block or len(block.strip()) < 10:
            continue
        block_lower = block.lower()

        # Check if this block contains any substantial part of the person's name
        name_found = any(part in block_lower for part in name_parts)
        if not name_found:
            continue

        # Extract strict emails from this block
        cand_emails = STRICT_EMAIL.findall(block)
        for em in cand_emails:
            clean_em = em.strip().lower()
            if clean_em in seen:
                continue
            seen.add(clean_em)

            # 1. Strict syntax & valid TLD & MX check
            if not is_valid_email_syntax(clean_em, domain=company_domain, check_mx=True):
                continue
            # 2. Reject generic departmental emails (info@, sales@)
            if is_generic_email(clean_em):
                continue
            # 3. Domain ownership check
            if company_domain and not email_belongs_to_company(clean_em, company_domain):
                continue
            # 4. Strict personal name affiliation
            if not is_personal_email(clean_em, person_name):
                continue

            results.append(clean_em)

    return results

# ── Dual-Tier Departmental / Functional Category Taxonomy ──
DEPARTMENTAL_CATEGORIES: Dict[str, str] = {
    # Front Desk & General Contact
    'info': 'info',
    'information': 'info',
    'contact': 'contact',
    'contactus': 'contact',
    'contacts': 'contact',
    'general': 'info',
    'hello': 'info',
    'office': 'admin',
    'admin': 'admin',
    'administration': 'admin',

    # Sales & Commercial Inquiries
    'sales': 'sales',
    'inquiries': 'sales',
    'inquiry': 'sales',
    'enquiries': 'sales',
    'enquiry': 'sales',
    'business': 'sales',
    'bd': 'sales',

    # Support & Customer Care
    'support': 'support',
    'help': 'support',
    'helpdesk': 'support',
    'service': 'support',
    'services': 'support',
    'customercare': 'support',
    'customer': 'support',

    # HR & Recruitment
    'hr': 'hr',
    'humanresources': 'hr',
    'careers': 'careers',
    'career': 'careers',
    'jobs': 'careers',
    'recruitment': 'careers',
    'recruiting': 'careers',
    'talent': 'careers',

    # Finance, Billing & Invoices
    'billing': 'billing',
    'invoices': 'billing',
    'invoice': 'billing',
    'accounting': 'billing',
    'finance': 'billing',
    'accounts': 'billing',

    # Media, Press & PR
    'press': 'media',
    'media': 'media',
    'pr': 'media',
    'marketing': 'marketing',
    'communications': 'media',

    # Legal & Compliance
    'legal': 'legal',
    'compliance': 'legal',
    'privacy': 'legal',
    'security': 'legal',
}

DEPARTMENTAL_DISPLAY_ORDER = [
    'info', 'contact', 'sales', 'support', 'hr', 'careers', 'billing', 'media', 'marketing', 'legal', 'admin'
]

GENERIC_LOCAL_PARTS: Set[str] = {
    'info', 'sales', 'support', 'contact', 'admin', 'help', 'helpdesk',
    'careers', 'jobs', 'hr', 'billing', 'accounts', 'marketing', 'press',
    'media', 'enquiries', 'inquiries', 'hello', 'team', 'office', 'mail',
    'email', 'general', 'feedback', 'service', 'customerservice',
    'customer.service', 'sales-support', 'sales_support', 'supportus',
    'support-us', 'support_us', 'supportuk', 'support-uk', 'us', 'uk',
    'eu', 'apac', 'emea', 'noreply', 'no-reply', 'donotreply', 'webmaster',
    'postmaster', 'abuse', 'security', 'privacy', 'legal', 'compliance',
    'partners', 'partnerships', 'affiliates', 'wholesale', 'orders',
    'returns', 'shipping', 'techsupport', 'tech-support', 'it', 'devops',
    'engineering', 'product', 'products', 'newsletter', 'subscribe'
}
GENERIC_EMAIL_PREFIXES = GENERIC_LOCAL_PARTS


def is_generic_email(email: str) -> bool:
    """Returns True if the email is a role-based/generic inbox, not a person."""
    if not email or '@' not in email:
        return True
    local = email.split('@')[0].lower().strip()
    
    # Strip HTML entities like u003e (e.g. u003esupport -> support)
    local_clean = re.sub(r'u00[0-9a-f]{2}', '', local)
    normalized = re.sub(r'[^a-z]', '', local_clean)

    # 1. Direct match in generic parts or departmental categories
    if local in GENERIC_LOCAL_PARTS or local_clean in GENERIC_LOCAL_PARTS or normalized in GENERIC_LOCAL_PARTS:
        return True
    if local in DEPARTMENTAL_CATEGORIES or local_clean in DEPARTMENTAL_CATEGORIES or normalized in DEPARTMENTAL_CATEGORIES:
        return True

    # 2. Check if local contains delimiters separating role parts (e.g., sales.support, info-us, it_help)
    parts = re.split(r'[-_.]', local_clean)
    for part in parts:
        part_norm = re.sub(r'[^a-z]', '', part)
        if part in GENERIC_LOCAL_PARTS or part_norm in GENERIC_LOCAL_PARTS:
            return True

    # 3. Prefixes/suffixes with generic roles (minimum length 4 to avoid 2-letter substrings matching names)
    for generic in GENERIC_LOCAL_PARTS:
        generic_norm = re.sub(r'[^a-z]', '', generic)
        if not generic_norm:
            continue
        if len(generic_norm) <= 3:
            # 2-3 letter abbreviations (it, hr, pr, qa) must be exact match or delimited
            if normalized == generic_norm:
                return True
        else:
            # Longer generic words (support, sales, contact, billing, admin, office, general, service)
            # Match if normalized starts with it (e.g. supportus, saleshelp) or ends with it
            if normalized.startswith(generic_norm) or normalized.endswith(generic_norm) or generic_norm in normalized:
                return True

    return False


def classify_email(email: str, known_dm_names: Optional[List[Dict[str, str]]] = None) -> Tuple[str, Optional[str]]:
    """
    Classifies an email into Tier 1 (personal executive/individual) vs Tier 2 (departmental/functional inbox).
    Returns (tier, category) where:
      - tier: 'personal' or 'departmental'
      - category: canonical category string (e.g. 'info', 'sales', 'hr') if departmental, else None.
    """
    if not email or '@' not in email:
        return 'unknown', None

    local = email.split('@')[0].lower().strip()
    local_clean = re.sub(r'[^a-z]', '', local)

    # 0. Strict Generic Email Check (Bug #4 Fix)
    if is_generic_email(email):
        cat = DEPARTMENTAL_CATEGORIES.get(local, DEPARTMENTAL_CATEGORIES.get(local_clean, 'general'))
        return 'departmental', cat

    # 1. Exact or stripped matches in canonical departmental dict
    if local in DEPARTMENTAL_CATEGORIES:
        return 'departmental', DEPARTMENTAL_CATEGORIES[local]
    if local_clean in DEPARTMENTAL_CATEGORIES:
        return 'departmental', DEPARTMENTAL_CATEGORIES[local_clean]

    # 2. Functional prefix patterns (e.g., info-us, sales_team, hr.dept, careers-apac)
    for prefix, cat in DEPARTMENTAL_CATEGORIES.items():
        if local.startswith(f"{prefix}-") or local.startswith(f"{prefix}_") or local.startswith(f"{prefix}."):
            return 'departmental', cat
        if local_clean.startswith(prefix) and len(local_clean) <= len(prefix) + 4:
            return 'departmental', cat

    # 3. Check if local part matches known decision maker names (definitely personal)
    if known_dm_names:
        for dm in known_dm_names:
            fn = re.sub(r'[^a-z]', '', (dm.get("first_name") or "").lower())
            ln = re.sub(r'[^a-z]', '', (dm.get("last_name") or "").lower())
            if (fn and len(fn) >= 3 and fn in local) or (ln and len(ln) >= 3 and ln in local):
                return 'personal', None

    # 4. Standard personal naming conventions (first.last, first_last, first-last, etc.)
    if any(sep in local for sep in ('.', '_', '-')) and not any(p in local for p in ('info', 'contact', 'sales', 'support', 'team', 'service')):
        return 'personal', None

    return 'personal', None


def deduplicate_departmental_emails(emails: List[str], target_domain: str) -> List[str]:
    """
    Deduplicates departmental/functional emails so that each functional category
    (e.g., 'info', 'sales', 'support', 'hr', 'careers', 'billing', 'media')
    appears AT MOST ONCE per company.

    If multiple regional or subdomain variants exist (e.g. info@company.com.sg vs info@company.com),
    the canonical inbox matching target_domain exactly with the cleanest local prefix is retained.
    """
    clean_domain = target_domain.lower().replace("www.", "").strip()
    category_candidates: Dict[str, List[str]] = {}

    for em in emails:
        if not em or '@' not in em:
            continue
        clean_em = em.strip().lower()
        parts = clean_em.split('@', 1)
        if len(parts) != 2:
            continue
        tier, cat = classify_email(clean_em)
        if tier == 'departmental' and cat:
            category_candidates.setdefault(cat, []).append(clean_em)

    def _score_candidate(candidate: str, cat: str) -> int:
        score = 0
        local, em_dom = candidate.split('@', 1)

        # Primary domain exact match is top priority
        if em_dom == clean_domain:
            score += 100
        elif em_dom.endswith('.' + clean_domain):
            score += 50
        else:
            score += 10

        # Exact canonical local part (e.g. 'info' exactly vs 'info-us' or 'information')
        if local == cat:
            score += 40
        elif local.startswith(cat):
            score += 20

        # Penalize extra subdomains / regional dots (.com.sg, .co.uk)
        score -= em_dom.count('.') * 5
        # Prefer shorter emails
        score -= len(candidate)
        return score

    best_inboxes: Dict[str, str] = {}
    for cat, candidates in category_candidates.items():
        candidates_sorted = sorted(candidates, key=lambda c: _score_candidate(c, cat), reverse=True)
        if candidates_sorted:
            best_inboxes[cat] = candidates_sorted[0]

    # Return deduplicated inboxes ordered by canonical display hierarchy
    ordered_results: List[str] = []
    for cat in DEPARTMENTAL_DISPLAY_ORDER:
        if cat in best_inboxes and best_inboxes[cat] not in ordered_results:
            ordered_results.append(best_inboxes[cat])

    # Append any remaining categories
    for cat, em in best_inboxes.items():
        if em not in ordered_results:
            ordered_results.append(em)

    return ordered_results


def is_valid_email_syntax(em: str, domain: Optional[str] = None, check_mx: bool = True) -> bool:
    r"""
    Validates structural regex syntax and filters junk/placeholder emails:
    1. Strict regex match (\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b)
    2. Valid TLD verification (rejects fake TLDs like .before, .he, .la, .png)
    3. Domain dot count check (rejects domains with > 3 dots or bad formatting)
    4. Local part suspicious check (rejects prose words: texas, austin, before, scott, etc.)
    5. Domain ownership check (if domain is provided, ensures matching or subdomain)
    6. Cached MX record check (rejects nonexistent domains in milliseconds)
    """
    if not em or not isinstance(em, str):
        return False
    clean = em.strip().lower()
    if not STRICT_EMAIL.fullmatch(clean):
        return False

    parts = clean.split('@')
    if len(parts) != 2:
        return False
    local, em_domain = parts

    # Suspicious local words & excluded prefixes
    if local in EXCLUDED_EMAIL_PREFIXES or any(sw in local for sw in SUSPICIOUS_LOCAL_WORDS):
        return False

    # Domain structure check
    if em_domain.count('.') > 3 or em_domain.startswith('.') or em_domain.endswith('.'):
        return False

    tld = em_domain.split('.')[-1].lower()
    if tld not in VALID_TLDS or tld in INVALID_EMAIL_EXTENSIONS:
        return False

    # Check if local part is pseudo-junk (length >= 5 without standard vowels)
    if len(local) >= 5 and not any(c in local for c in 'aeiouy0123456789'):
        return False

    # Domain ownership anchor check
    if domain:
        if not email_belongs_to_company(clean, domain):
            return False

    # Cached MX record check
    if check_mx and not has_mx_record(em_domain):
        return False

    return True


async def resolve_mx_records(domain: str) -> List[Tuple[int, str]]:
    """Resolves MX records using Google/Cloudflare DNS with in-memory caching."""
    clean_domain = domain.lower().replace("www.", "").strip()
    if not clean_domain:
        return []

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


_PORT_25_FILTERED: Dict[str, float] = {}

async def smtp_ping_email(
    email: str,
    mx_host: str,
    from_email: str = "verify@leadai.com",
    timeout: float = 3.0
) -> Dict[str, Any]:
    """
    Zero-Send SMTP Handshake with Canary Catch-All Detection and 550 Hard-Bouncing:
    1. Connect on port 25 -> 220 banner check
    2. HELO leadai.com
    3. MAIL FROM:<verify@leadai.com>
    4. RCPT TO:<candidate_email> -> get candidate response code
    5. If code in (550, 551, 552, 553, 554):
         Hard rejection -> 'invalid' (mailbox definitely does not exist).
    6. If code == 250:
         Probe random canary address: xkjhgfdsa9876@{domain}
         RCPT TO:<canary> -> get canary response code2
         If code2 == 250:
             Server accepts EVERYTHING -> 'catch_all' (unreliable, do not confirm deliverable).
         If code2 != 250:
             Target exists, canary rejected -> 'valid' (authentic deliverable mailbox!).
    7. Any timeout or connection error -> 'unknown' / 'smtp_port25_blocked'
    """
    now = time.time()
    if mx_host in _PORT_25_FILTERED and (now - _PORT_25_FILTERED[mx_host]) < 600:
        return {
            "email": email,
            "mx_host": mx_host,
            "deliverable": False,
            "status": "smtp_port25_blocked_or_timed_out",
            "code": None,
            "code2": None,
            "is_catch_all": False,
            "verified": False,
            "error": "Port 25 unreachable/filtered (cached)"
        }

    domain = email.split('@')[1].strip() if '@' in email else ""
    result = {
        "email": email,
        "mx_host": mx_host,
        "deliverable": False,
        "status": "unknown",
        "code": None,
        "code2": None,
        "is_catch_all": False,
        "verified": False,
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
        writer.write(f"MAIL FROM:<{from_email}>\r\n".encode("utf-8"))
        await writer.drain()
        mail_resp = await asyncio.wait_for(reader.readline(), timeout=timeout)
        if not mail_resp.startswith(b"250"):
            result["status"] = "sender_rejected"
            result["error"] = mail_resp.decode("utf-8", errors="replace").strip()
            return result

        # Step 1: Candidate Email RCPT TO
        writer.write(f"RCPT TO:<{email}>\r\n".encode("utf-8"))
        await writer.drain()
        rcpt_resp = await asyncio.wait_for(reader.readline(), timeout=timeout)
        rcpt_str = rcpt_resp.decode("utf-8", errors="replace").strip()

        code_match = re.match(r'^(\d{3})', rcpt_str)
        if not code_match:
            result["status"] = "unknown_response"
            result["error"] = rcpt_str
            return result

        code = int(code_match.group(1))
        result["code"] = code

        # Reliable 550 hard rejection: mailbox does not exist
        if code in (550, 551, 552, 553, 554):
            result["deliverable"] = False
            result["status"] = "invalid"
            result["verified"] = False
            return result

        # If candidate code is 250, run the Canary Catch-All Check!
        if code == 250:
            canary_email = f"xkjhgfdsa9876@{domain}"
            writer.write(f"RCPT TO:<{canary_email}>\r\n".encode("utf-8"))
            await writer.drain()
            rcpt2_resp = await asyncio.wait_for(reader.readline(), timeout=timeout)
            rcpt2_str = rcpt2_resp.decode("utf-8", errors="replace").strip()

            code2_match = re.match(r'^(\d{3})', rcpt2_str)
            code2 = int(code2_match.group(1)) if code2_match else None
            result["code2"] = code2

            if code2 == 250:
                # Catch-all server: accepts any fake string
                result["deliverable"] = False
                result["status"] = "catch_all"
                result["is_catch_all"] = True
                result["verified"] = False
            else:
                # Non-catchall server: candidate exists and canary bounced! Real verified!
                result["deliverable"] = True
                result["status"] = "valid"
                result["is_catch_all"] = False
                result["verified"] = True
            return result

        if code in (450, 451, 452):
            result["deliverable"] = False
            result["status"] = "greylisted_or_busy"
        else:
            result["status"] = f"code_{code}"

        return result

    except (asyncio.TimeoutError, ConnectionRefusedError, socket.gaierror, OSError) as e:
        _PORT_25_FILTERED[mx_host] = time.time()
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
                writer.write(b"QUIT\r\n")
                await writer.drain()
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass


def verify_email_smtp(email: str, from_email: str = 'verify@leadai.com', timeout: float = 8.0) -> str:
    """
    Synchronous SMTP RCPT Verification with Canary Catch-All Check.
    Delegates to standalone smtp_verify module.
    Returns:
      'valid'     -> 250 OK (and canary rejected, email exists)
      'invalid'   -> 550 (mailbox definitely does not exist)
      'catch_all' -> server accepts everything
      'unknown'   -> connection/timeout error
    """
    try:
        res = standalone_verify_email_smtp(email, from_email=from_email, timeout=timeout)
        return res.get("status", "unknown")
    except Exception:
        return "unknown"


MAILBOXLAYER_API_KEY = os.getenv("MAILBOXLAYER_API_KEY", "b9ded5ede23067e9848082c86c8eba6e")

async def verify_via_mailboxlayer(email: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Validates email deliverability via Mailboxlayer (APILayer) API with strict integrity rules:
    - Never approves on format_valid or mx_found alone.
    - Flags and rejects catch-all domains (which accept all addresses, giving false 250s).
    - Requires confirmed positive smtp_check on non-catch-all mailservers.
    """
    key = api_key or MAILBOXLAYER_API_KEY
    if not key or not email:
        return {"deliverable": None, "status": "no_key", "error": "No API key", "verified": False}

    import urllib.request
    import json

    endpoints = [
        (f"https://api.apilayer.com/email_verification/check?email={email}", {"apikey": key}),
        (f"http://apilayer.net/api/check?access_key={key}&email={email}", {})
    ]

    for url, headers in endpoints:
        try:
            def _call():
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    return json.loads(resp.read().decode())
            data = await asyncio.to_thread(_call)
            if data and isinstance(data, dict):
                smtp_ok = data.get("smtp_check") is True
                mx_ok = data.get("mx_found") is True
                format_ok = data.get("format_valid") is True
                is_catch_all = data.get("catch_all") is True
                is_disposable = data.get("disposable") is True
                score = data.get("score", 0.0)

                # 1. Hard rejection: bad format, missing MX, disposable, or explicit non-existence
                if not format_ok or not mx_ok or is_disposable or data.get("smtp_check") is False:
                    return {
                        "deliverable": False,
                        "status": "mailboxlayer_mailbox_not_found",
                        "score": score,
                        "data": data,
                        "verified": False
                    }

                # 2. Catch-all domain detection: mailserver accepts all incoming emails regardless of recipient
                # Individual existence cannot be guaranteed via SMTP on catch-all servers!
                if is_catch_all:
                    return {
                        "deliverable": False,
                        "status": "mailboxlayer_catch_all_unverified",
                        "score": score,
                        "data": data,
                        "is_catch_all": True,
                        "verified": False
                    }

                # 3. Authentic positive verification: explicit SMTP confirmation on dedicated mailbox
                if smtp_ok and not is_catch_all:
                    return {
                        "deliverable": True,
                        "status": "mailboxlayer_smtp_verified",
                        "score": score,
                        "data": data,
                        "verified": True
                    }

                # If smtp_check is None or inconclusive, do not assume deliverable
                return {
                    "deliverable": False,
                    "status": "mailboxlayer_unconfirmed",
                    "score": score,
                    "data": data,
                    "verified": False
                }
        except urllib.error.HTTPError as he:
            logger.debug(f"[Mailboxlayer] HTTP {he.code}: {he.reason}")
            continue
        except Exception as e:
            logger.debug(f"[Mailboxlayer] Check error: {e}")
            continue

    return {"deliverable": None, "status": "api_unavailable", "verified": False}



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
    is_catch_all = bool(ping.get("deliverable"))
    _CATCHALL_CACHE[clean_domain] = (now, is_catch_all)
    return is_catch_all


# ─── Anchor Email Reverse Pattern Strategy ────────────────────────────────────

def extract_email_pattern(email: str, known_names: Optional[List[Dict[str, str]]] = None) -> Optional[str]:
    """
    Reverse-engineers the company's authentic corporate email schema from a known real email.
    Evaluates syntax (dots, underscores, initials) and cross-checks known leadership names.
    Returns standard pattern tokens: 'first.last', 'flast', 'f.last', 'first_last', etc.
    """
    if not email or '@' not in email:
        return None
    if is_generic_email(email):
        return None
    local = email.split('@')[0].lower().strip()
    if len(local) < 2:
        return None

    # 1. Match against known executive/employee names
    if known_names:
        for p in known_names:
            f = re.sub(r'[^a-z0-9]', '', (p.get('first_name') or '').lower())
            l = re.sub(r'[^a-z0-9]', '', (p.get('last_name') or '').lower())
            if not f:
                continue
            if l:
                if local == f"{f}.{l}":
                    return "first.last"
                if local == f"{f}_{l}":
                    return "first_last"
                if local == f"{f}-{l}":
                    return "first-last"
                if local == f"{f[0]}.{l}":
                    return "f.last"
                if local == f"{f[0]}{l}":
                    return "flast"
                if local == f"{f}{l}":
                    return "firstlast"
                if local == f:
                    return "first"
                if local == f"{l}.{f}":
                    return "last.first"
                if local == f"{f}.{l[0]}":
                    return "first.l"
            else:
                if local == f:
                    return "first"

    # 2. Structural punctuation syntax inference
    if '.' in local:
        parts = local.split('.')
        if len(parts) == 2:
            if len(parts[0]) == 1 and len(parts[1]) > 1:
                return "f.last"
            if len(parts[0]) > 1 and len(parts[1]) == 1:
                return "first.l"
            if len(parts[0]) > 1 and len(parts[1]) > 1:
                return "first.last"
    if '_' in local:
        parts = local.split('_')
        if len(parts) == 2:
            if len(parts[0]) == 1 and len(parts[1]) > 1:
                return "f_last"
            if len(parts[0]) > 1 and len(parts[1]) > 1:
                return "first_last"
    if '-' in local:
        parts = local.split('-')
        if len(parts) == 2 and len(parts[0]) > 1 and len(parts[1]) > 1:
            return "first-last"

    # Do not fabricate pattern for arbitrary strings without known names
    return None


def synthesize_by_pattern(first_name: str, last_name: str, domain: str, pattern: str) -> Optional[str]:
    """Synthesizes a corporate email for an individual using a discovered anchor pattern."""
    f = re.sub(r'[^a-zA-Z0-9]', '', (first_name or '').lower())
    l = re.sub(r'[^a-zA-Z0-9]', '', (last_name or '').lower())
    d = domain.lower().replace("www.", "").strip()
    if not d or not f:
        return None

    if pattern == "first.last":
        return f"{f}.{l}@{d}" if l else f"{f}@{d}"
    elif pattern == "first_last":
        return f"{f}_{l}@{d}" if l else f"{f}@{d}"
    elif pattern == "first-last":
        return f"{f}-{l}@{d}" if l else f"{f}@{d}"
    elif pattern == "f.last":
        return f"{f[0]}.{l}@{d}" if l else f"{f}@{d}"
    elif pattern == "flast":
        return f"{f[0]}{l}@{d}" if l else f"{f}@{d}"
    elif pattern == "f_last":
        return f"{f[0]}_{l}@{d}" if l else f"{f}@{d}"
    elif pattern == "last.first":
        return f"{l}.{f}@{d}" if l else f"{f}@{d}"
    elif pattern == "firstlast":
        return f"{f}{l}@{d}" if l else f"{f}@{d}"
    elif pattern == "first":
        return f"{f}@{d}"
    elif pattern == "first.l":
        return f"{f}.{l[0]}@{d}" if l else f"{f}@{d}"
    return f"{f}.{l}@{d}" if l else f"{f}@{d}"


def find_domain_anchor_pattern(
    domain: str,
    candidate_emails: List[str],
    known_names: Optional[List[Dict[str, str]]] = None
) -> Tuple[Optional[str], Optional[str]]:
    """
    Scans candidate emails discovered from web footprints, press releases,
    or website crawls to identify an authentic non-generic employee email and extract
    its institutional corporate pattern.
    Returns (anchor_email, detected_pattern).
    """
    clean_domain = domain.lower().replace("www.", "").strip()
    if not candidate_emails or not clean_domain:
        return None, None

    for em in candidate_emails:
        if not em or '@' not in em:
            continue
        parts = em.lower().strip().split('@', 1)
        if len(parts) != 2:
            continue
        local, em_dom = parts
        if em_dom != clean_domain and not em_dom.endswith('.' + clean_domain):
            continue

        # CRITICAL FIX (Bug #1): Reject generic anchors
        if is_generic_email(em):
            logger.info(f"[AnchorStrategy] SKIP generic anchor: {em}")
            continue

        if not is_valid_email_syntax(em, domain=clean_domain):
            continue

        pat = extract_email_pattern(em, known_names=known_names)
        if pat:
            return em, pat

    return None, None


def generate_email_permutations(
    first_name: str,
    last_name: str,
    domain: str,
    anchor_pattern: Optional[str] = None
) -> List[str]:
    """
    Generates standard corporate B2B email permutations.
    If anchor_pattern is provided (from a discovered real domain email),
    synthesizes that exact pattern first.
    If anchor_pattern is missing/None, falls back to the Standard Enterprise Permutation Matrix:
      1. {first}.{last}@domain.com  (Standard B2B corporate)
      2. {first}@domain.com         (Small/medium business & executive direct)
      3. {f}{last}@domain.com       (Aerospace, defense, engineering & legacy B2B)
      4. {first}_{last}@domain.com  (Technical & enterprise standard)
      5. {first[0]}.{last}@domain.com
      6. {first}{last}@domain.com
      7. {last}.{first}@domain.com
      8. {first}.{last[0]}@{domain}
    """
    first = re.sub(r'[^a-zA-Z0-9]', '', (first_name or '').lower())
    last = re.sub(r'[^a-zA-Z0-9]', '', (last_name or '').lower())
    clean_domain = domain.lower().replace("www.", "").strip()

    if not clean_domain or not first:
        return []

    perms = []

    # Priority 0: Anchor Pattern Synthesis if previously detected
    if anchor_pattern:
        pattern_email = synthesize_by_pattern(first, last, clean_domain, anchor_pattern)
        if pattern_email:
            perms.append(pattern_email)

    # Standard Enterprise Permutation Matrix (High-Probability Ordered Hierarchy)
    if first and last:
        perms.extend([
            f"{first}.{last}@{clean_domain}",      # e.g., mark.lebovitz@l2aviation.com
            f"{first}@{clean_domain}",             # e.g., mark@l2aviation.com
            f"{first[0]}{last}@{clean_domain}",     # e.g., mlebovitz@l2aviation.com (Crucial for aerospace/gov/engineering)
            f"{first}_{last}@{clean_domain}",      # e.g., mark_lebovitz@l2aviation.com
            f"{first[0]}.{last}@{clean_domain}",    # e.g., m.lebovitz@l2aviation.com
            f"{first}{last}@{clean_domain}",       # e.g., marklebovitz@l2aviation.com
            f"{last}.{first}@{clean_domain}",      # e.g., lebovitz.mark@l2aviation.com
            f"{first}.{last[0]}@{clean_domain}",    # e.g., mark.l@l2aviation.com
        ])
    elif first:
        perms.extend([
            f"{first}@{clean_domain}",
            f"{first}.admin@{clean_domain}",
        ])

    return list(dict.fromkeys(perms))


def extract_leadership_from_website_text(text: str, company_name: str = "", company_domain: str = "") -> List[Dict[str, str]]:
    """
    Scans crawled website content (/about, /team, /leadership, homepage)
    for executive leadership names and roles (CEO, Founder, Director, President, Owner).
    Uses 5 complementary patterns to maximize extraction coverage.
    Applies structured HTML/text block proximity extraction to ensure direct personal emails
    are only linked to an executive when authentically co-located in the same section.
    """
    if not text or len(text.strip()) < 20:
        return []

    people: List[Dict[str, str]] = []
    seen: set = set()

    NAME_PAT = r'([A-Z][a-z]{1,25}(?:\s+[A-Z]\.?|\s+[A-Z][a-z]{1,25}){1,3})'

    ROLE = (
        r'(Representative Director|Representative Member|Representative|Contact Person|'
        r'Chief Executive Officer|Chief Operating Officer|Chief Financial Officer|'
        r'Chief Technology Officer|Chief Marketing Officer|Chief Revenue Officer|'
        r'Chief Information Officer|Chief Compliance Officer|Chief Scientist|Chief Engineer|'
        r'Executive Chairman|Managing Principal|Senior Principal|Principal|'
        r'Managing Director|Executive Director|Managing Partner|Senior Partner|Partner|'
        r'Executive Vice President|Senior Vice President|Vice President|'
        r'Director of Operations|Operations Director|Operations Manager|'
        r'General Manager|Head of Operations|Head of Engineering|Head of Sales|'
        r'Founder & CEO|Co-Founder & CEO|President & CEO|'
        r'Co-Founder|Co Founder|Founder|Co-Owner|Owner|President|'
        r'CEO|COO|CFO|CTO|CMO|CRO|CIO|CCO|EVP|SVP|VP|GM)'
    )

    # Pattern 1: "John Smith, CEO" / "John Smith - Founder" / "John Smith | President" / Heading with newline
    pat1 = re.compile(NAME_PAT + r'(?:\s*[,\-\u2013\u2014|:]\s*|\s*[\r\n]+\s*|\s+\()' + ROLE, re.IGNORECASE)

    # Pattern 2: "CEO: John Smith" / "Founder - Jane Doe"
    pat2 = re.compile(r'\b' + ROLE + r'\s*[:\-\u2013\u2014|\r\n]+\s*' + NAME_PAT, re.IGNORECASE)

    # Pattern 3: "John Smith serves as CEO" / "John Smith serves as JBS USA Chief Executive Officer"
    pat3 = re.compile(
        NAME_PAT + r'\s+(?:serves?\s+as|is\s+(?:our\s+|the\s+)?|acts?\s+as|joined\s+as|works?\s+as)\s+(?:(?:[A-Za-z0-9\.\-]+\s+){0,3})' + ROLE,
        re.IGNORECASE
    )

    # Pattern 4: "founded by John Smith" / "led by Robert Miller"
    pat4 = re.compile(
        r'(?:founded|co-founded|started|established|led|headed|run|operated)\s+by\s+([A-Z][a-z]{1,25}(?:\s+[A-Z][a-z]{1,25}){1,3})(?=\s*(?:in\s+\d{4}|,|\.|$|to|and))',
        re.IGNORECASE
    )

    # Pattern 5: "Meet John Smith, our CEO"
    pat5 = re.compile(
        r'(?:Meet|Introducing|Welcome)\s+' + NAME_PAT + r'[,\s]+(?:our\s+)?' + ROLE,
        re.IGNORECASE
    )

    # Pattern 6: Japanese / Asian & International Profile (e.g. "Representative Eric Turner" or "Representative: Taro Tanaka")
    pat6 = re.compile(
        r'\b(Representative\s+Director|Representative|President|CEO|Founder|Managing\s+Director)\s*[:：\-\u2013\u2014|]?\s*' + NAME_PAT,
        re.IGNORECASE
    )

    disallowed_words = {
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
        'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
        'september', 'october', 'november', 'december', 'about us', 'contact us',
        'privacy policy', 'terms conditions', 'all rights', 'reserved', 'read more',
        'learn more', 'our team', 'leadership team', 'board directors', 'copyright',
        'click here', 'view more', 'get started', 'sign in', 'log in', 'home',
        'services', 'products', 'solutions', 'portfolio', 'executive mba', 'the executive team',
        'executive team', 'board members', 'student listing', 'management team'
    }

    def process_candidate(raw_name: str, raw_role: str, source: str = "website_content", match_span: Optional[Tuple[int, int]] = None):
        cleaned_name = re.sub(r'^(?:by|with|and|mr\.?|mrs\.?|ms\.?|dr\.?|prof\.?)\s+', '', raw_name.strip(), flags=re.IGNORECASE).strip()
        cleaned_name = re.sub(r'\s+in\s*\d{4}.*$', '', cleaned_name, flags=re.IGNORECASE).strip()
        cleaned_role_raw = re.sub(r'\s+at\s+.*$', '', raw_role.strip(), flags=re.IGNORECASE).strip()
        def _fix_role_case(r):
            abbrevs = {'Ceo','Coo','Cfo','Cto','Cmo','Cro','Vp','Gm','Hr','Evp','Svp','Cio','Cco'}
            return ' '.join(w.upper() if w in abbrevs or (len(w) <= 3 and w.isupper()) else w for w in r.split())
        cleaned_role = _fix_role_case(cleaned_role_raw.title())

        name_lower = cleaned_name.lower()
        if any(w in name_lower for w in disallowed_words):
            return

        if company_name:
            cn_lower = company_name.lower().strip()
            if name_lower in cn_lower or cn_lower in name_lower:
                return

        parts = cleaned_name.split()
        disallowed_name_abbr = {'PR', 'HR', 'CEO', 'CTO', 'CFO', 'COO', 'IT', 'AI', 'UK', 'US', 'EU', 'NED', 'B2B', 'SAAS', 'LLC', 'INC', 'LTD', 'PTE', 'CO', 'SVP', 'EVP'}
        if 2 <= len(parts) <= 4 and name_lower not in seen:
            if any(p.upper() in disallowed_name_abbr or len(p) <= 1 for p in parts):
                return
            if not all(p[0].isupper() for p in parts if p):
                return
            seen.add(name_lower)

            # 🔧 FIX #3: Proximity extraction using structured HTML/text blocks & personal name verification
            direct_email = ""
            if text and cleaned_name:
                near_emails = extract_emails_near_name(
                    content=text,
                    person_name=cleaned_name,
                    company_domain=company_domain
                )
                if near_emails:
                    direct_email = near_emails[0]

            people.append({
                "name": cleaned_name,
                "first_name": parts[0],
                "last_name": parts[-1],
                "role": cleaned_role,
                "email": direct_email,
                "source": source
            })

    # Apply all patterns with correct group indices and span tracking
    for m in pat1.finditer(text):
        process_candidate(m.group(1), m.group(2), match_span=m.span())

    for m in pat2.finditer(text):
        process_candidate(m.group(2), m.group(1), match_span=m.span())

    for m in pat3.finditer(text):
        process_candidate(m.group(1), m.group(2), match_span=m.span())

    for m in pat4.finditer(text):
        process_candidate(m.group(1), "Founder", match_span=m.span())

    for m in pat5.finditer(text):
        process_candidate(m.group(1), m.group(2), match_span=m.span())

    for m in pat6.finditer(text):
        process_candidate(m.group(2), m.group(1), match_span=m.span())

    return people


async def find_web_footprint_emails(domain: str, company_name: str = "") -> List[str]:
    """
    Web Footprint Dorking:
    Finds authentic corporate email disclosures in press releases, PDFs, and external directories.
    """
    clean_domain = domain.lower().replace("www.", "").strip()
    if not clean_domain:
        return []

    query = f'"{clean_domain}" email OR contact -site:{clean_domain}'
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


# ─── Deep PDF & Press Release Dorking ─────────────────────────────────────────

async def dork_executive_press_and_pdfs(company_name: str, domain: str) -> Dict[str, Any]:
    """
    Deep PDF & Press Release Dorking Engine:
    Executes targeted queries to uncover hidden direct executive contacts from public PDFs,
    wire services (PRNewswire, GlobeNewswire, BusinessWire), and official corporate disclosures.
    1. "{company_name}" filetype:pdf (email OR contact OR CEO OR director OR management)
    2. site:prnewswire.com OR site:globenewswire.com OR site:businesswire.com "{company_name}"
    """
    clean_domain = domain.lower().replace("www.", "").strip()
    clean_company = company_name.strip()
    if not clean_domain and not clean_company:
        return {"discovered_emails": [], "decision_makers": [], "anchor_candidates": []}

    target_name = clean_company or clean_domain.split('.')[0]
    queries = [
        f'"{target_name}" filetype:pdf (email OR contact OR CEO OR director OR management)',
        f'site:prnewswire.com OR site:globenewswire.com OR site:businesswire.com "{target_name}"'
    ]

    discovered_emails: Set[str] = set()
    decision_makers: List[Dict[str, str]] = []
    seen_dm_names: Set[str] = set()

    try:
        from discover import search_searxng_or_ddg
    except Exception:
        search_searxng_or_ddg = None

    if not search_searxng_or_ddg:
        return {"discovered_emails": [], "decision_makers": [], "anchor_candidates": []}

    email_re = re.compile(rf'[a-zA-Z0-9._%+-]+@{re.escape(clean_domain)}', re.IGNORECASE) if clean_domain else None

    role_pattern = (
        r'(Chief Executive Officer|Chief Operating Officer|Chief Financial Officer|'
        r'Chief Technology Officer|Chief Information Officer|Chief Scientist|Chief Engineer|'
        r'Executive Chairman|Managing Principal|Senior Principal|Principal|'
        r'Managing Director|Executive Director|Managing Partner|Senior Partner|Partner|'
        r'Executive Vice President|Senior Vice President|Vice President|'
        r'Director of Operations|Operations Director|Operations Manager|'
        r'CEO|COO|CFO|CTO|CIO|CCO|EVP|SVP|VP|President|Founder|Owner|GM|General Manager|'
        r'Head of Communications|Media Contact|Investor Relations)'
    )
    dm_re1 = re.compile(r'([A-Z][a-z]{1,25}(?:\s+[A-Z]\.?|\s+[A-Z][a-z]{1,25}){1,2})\s*,\s*' + role_pattern, re.IGNORECASE)
    dm_re2 = re.compile(role_pattern + r'\s*[:\-–]\s*([A-Z][a-z]{1,25}(?:\s+[A-Z]\.?|\s+[A-Z][a-z]{1,25}){1,2})', re.IGNORECASE)

    for q in queries:
        try:
            hits = await asyncio.wait_for(search_searxng_or_ddg(q, page=1), timeout=5.0)
        except Exception as e:
            logger.debug(f"[PDF/Press Dork] Search failed for '{q}': {e}")
            hits = []

        for item in (hits or [])[:6]:
            title = item.get("title") or ""
            snippet = item.get("snippet") or item.get("content") or ""
            url = item.get("url") or ""
            blob = f"{title} {snippet} {url}"

            # 1. Extract domain-specific corporate emails
            if email_re:
                for match in email_re.findall(blob):
                    clean_em = match.strip().lower()
                    if is_valid_email_syntax(clean_em, domain=clean_domain):
                        discovered_emails.add(clean_em)

            # 2. Extract decision-maker candidates
            for m in dm_re1.finditer(blob):
                name = m.group(1).strip()
                role = m.group(2).strip()
                n_lower = name.lower()
                parts = name.split()
                if 2 <= len(parts) <= 3 and n_lower not in seen_dm_names:
                    if target_name.lower() not in n_lower and n_lower not in target_name.lower():
                        seen_dm_names.add(n_lower)
                        decision_makers.append({
                            "name": name,
                            "first_name": parts[0],
                            "last_name": parts[-1],
                            "role": role.title(),
                            "source": "press_release_or_pdf",
                            "linkedin_url": ""
                        })

            for m in dm_re2.finditer(blob):
                role = m.group(1).strip()
                name = m.group(2).strip()
                n_lower = name.lower()
                parts = name.split()
                if 2 <= len(parts) <= 3 and n_lower not in seen_dm_names:
                    if target_name.lower() not in n_lower and n_lower not in target_name.lower():
                        seen_dm_names.add(n_lower)
                        decision_makers.append({
                            "name": name,
                            "first_name": parts[0],
                            "last_name": parts[-1],
                            "role": role.title(),
                            "source": "press_release_or_pdf",
                            "linkedin_url": ""
                        })

    return {
        "discovered_emails": list(discovered_emails),
        "decision_makers": decision_makers,
        "anchor_candidates": list(discovered_emails)
    }


async def probe_website_leadership_pages(domain: str) -> str:
    """
    Intelligent Navbar-First Leadership Subpage Prober:
    Discovers authentic leadership & team pages dynamically from the homepage navbar/footer.
    Falls back to standard leadership endpoints if navbar links cannot be read.
    """
    if not domain:
        return ""
    clean_d = domain.lower().replace("www.", "").strip()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    discovered_pages = []
    try:
        from email_outreach import discover_subpage_urls, fetch_raw_html
        homepage_url = f"https://{clean_d}"
        raw_html = await fetch_raw_html(homepage_url)
        if raw_html:
            discovered_pages = discover_subpage_urls(homepage_url, raw_html, max_links=4)
    except Exception:
        discovered_pages = []

    subpages = discovered_pages or [
        f"https://{clean_d}/leadership",
        f"https://{clean_d}/team",
        f"https://{clean_d}/our-team",
        f"https://{clean_d}/about",
        f"https://{clean_d}/about-us",
        f"https://{clean_d}/management",
    ]

    async def _fetch(u: str) -> str:
        try:
            import httpx
            import bs4
            async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=3.5, verify=False) as c:
                resp = await c.get(u)
                if resp.status_code == 200 and len(resp.text) > 400:
                    soup = bs4.BeautifulSoup(resp.text, 'html.parser')
                    for s in soup(["script", "style", "svg"]):
                        s.extract()
                    return soup.get_text(separator=' ')
        except Exception:
            return ""
        return ""

    tasks = [_fetch(u) for u in subpages[:4]]
    texts = await asyncio.gather(*tasks, return_exceptions=True)
    combined = " ".join([t for t in texts if isinstance(t, str) and len(t) > 100])
    return combined


async def find_decision_makers(company_name: str, domain: str, website_text: str = "") -> List[Dict[str, str]]:
    """
    State-of-the-Art Autonomous Decision-Maker & Executive Discovery Engine:
    1. Extracts authentic leadership from crawled website content (with direct emails if present).
    2. Proactively probes dedicated leadership subpages (/about, /team, /leadership, etc.).
    3. Executes clean, high-precision natural search queries on Bing/Yahoo/SearXNG.
    4. Accurately extracts names, executive roles (CEO, Founder, Director, Representative), direct emails, and LinkedIn URLs.
    """
    clean_company = company_name.strip()
    people: List[Dict[str, str]] = []
    seen_names = set()

    # Step 1: Scan provided crawled website content
    if website_text:
        site_people = extract_leadership_from_website_text(website_text, clean_company, company_domain=domain)
        for p in site_people:
            if p["name"].lower() not in seen_names:
                seen_names.add(p["name"].lower())
                people.append({
                    "name": p["name"],
                    "first_name": p["first_name"],
                    "last_name": p["last_name"],
                    "role": p["role"],
                    "email": p.get("email", ""),
                    "linkedin_url": "",
                    "source": "website_leadership"
                })

    # Step 1.5: Proactively probe leadership subpages if under 2 people found
    if len(people) < 2 and domain:
        try:
            probe_text = await asyncio.wait_for(probe_website_leadership_pages(domain), timeout=4.5)
            if probe_text:
                probe_people = extract_leadership_from_website_text(probe_text, clean_company, company_domain=domain)
                for p in probe_people:
                    if p["name"].lower() not in seen_names:
                        seen_names.add(p["name"].lower())
                        people.append({
                            "name": p["name"],
                            "first_name": p["first_name"],
                            "last_name": p["last_name"],
                            "role": p["role"],
                            "email": p.get("email", ""),
                            "linkedin_url": "",
                            "source": "website_leadership"
                        })
        except Exception as probe_err:
            logger.debug(f"[Leadership Probe] Error probing {domain}: {probe_err}")

    if len(people) >= 2:
        return people

    # Step 2: SearXNG Optimized Decision-Maker Queries (5 Templates)
    searxng_dm_templates = [
        f'"{clean_company}" "CEO" OR "Founder" OR "Managing Director" site:linkedin.com/in/',
        f'"{clean_company}" "VP" OR "Director" site:linkedin.com/in/',
        f'"{clean_company}" "Head of" site:linkedin.com/in/',
        f'"{clean_company}" leadership team OR executives',
        f'"{clean_company}" contact email "CEO" OR "Founder"'
    ]

    leadership_hits_found = False

    if clean_company and len(clean_company) >= 2:
        for query in searxng_dm_templates:
            try:
                from discover import search_searxng_or_ddg
                results = await asyncio.wait_for(search_searxng_or_ddg(query, page=1), timeout=8.0)
            except Exception as e:
                logger.debug(f"[SearXNG DM Search] Query failed '{query}': {e}")
                results = []

            for r in (results or [])[:12]:
                url = r.get("url") or ""
                raw_title = r.get("title") or ""
                title = html.unescape(raw_title)
                title = re.sub(r'[\u200e\u200f]', '', title)
                clean_t = re.sub(r'\s*\|\s*LinkedIn.*$', '', title, flags=re.IGNORECASE).strip()

                is_li = "linkedin.com/in/" in url.lower()
                cand_name, cand_role = None, None

                # 1. Parse LinkedIn in/ URLs
                if is_li:
                    leadership_hits_found = True
                    # Parse from title: e.g. "John Doe - Chief Executive Officer - Acme | LinkedIn"
                    segments = re.split(r'\s*[-–—|:]\s*', clean_t)
                    if len(segments) >= 2:
                        cand_name = segments[0].strip()
                        cand_role = segments[1].strip()
                        cand_role = re.sub(rf'\s+(?:at|@|for|in|\|)\s+.*$', '', cand_role, flags=re.IGNORECASE).strip()

                    # Fallback to URL slug: e.g. linkedin.com/in/john-doe-12345
                    if not cand_name or len(cand_name.split()) < 2:
                        m_slug = re.search(r'linkedin\.com/in/([^/?#]+)', url, re.IGNORECASE)
                        if m_slug:
                            slug = m_slug.group(1).strip()
                            slug = re.sub(r'[-_][0-9a-fA-F]{4,}$', '', slug)
                            slug = re.sub(r'[-_]\d+$', '', slug)
                            slug_parts = [w.capitalize() for w in re.split(r'[-_]', slug) if w.isalpha() and len(w) >= 2]
                            if 2 <= len(slug_parts) <= 4:
                                cand_name = " ".join(slug_parts)
                                if not cand_role:
                                    cand_role = "Executive / Leadership"

                # 2. Parse Non-LinkedIn corporate / team pages
                elif any(k in title.lower() for k in ('ceo', 'founder', 'director', 'president', 'owner', 'partner', 'managing', 'vp', 'vice president', 'chairman', 'executive', 'general manager')):
                    leadership_hits_found = True
                    m_meet = re.search(r'Meet the Team:\s*([A-Za-z\s]+),\s*([^-\.]+)', title, re.IGNORECASE)
                    if m_meet:
                        cand_name = m_meet.group(1).strip()
                        cand_role = m_meet.group(2).strip()
                    else:
                        segments = re.split(r'\s*[-–—|:]\s*', clean_t)
                        if len(segments) >= 2:
                            cand_name = segments[0].strip()
                            cand_role = segments[1].strip()
                            cand_role = re.sub(rf'\s+(?:at|@|for|in|\|)\s+.*$', '', cand_role, flags=re.IGNORECASE).strip()

                if cand_name and cand_role:
                    parts = cand_name.split()
                    if 2 <= len(parts) <= 4 and all(p[0].isupper() or p.lower() in ('de', 'van', 'von', 'del', 'filho', 'al', 'bin') for p in parts if p):
                        cn_lower = clean_company.lower()
                        n_lower = cand_name.lower()
                        if n_lower not in seen_names and n_lower not in cn_lower and cn_lower not in n_lower:
                            # Reject generic titles misparsed as names
                            if not any(w in n_lower for w in ('mba', 'team', 'executive', 'student', 'board', 'listing', 'company', 'inc', 'llc', 'solutions', 'post', 'view', 'read', 'overview', 'department')):
                                seen_names.add(n_lower)
                                role_str = cand_role[:60] if cand_role and cand_role.lower() != cn_lower else "Executive / Leadership"
                                people.append({
                                    "name": cand_name,
                                    "first_name": parts[0],
                                    "last_name": parts[-1],
                                    "role": role_str,
                                    "linkedin_url": url if "linkedin.com" in url else "",
                                    "source": "searxng_linkedin" if is_li else "searxng_dork"
                                })

            if len(people) >= 3:
                break

    # Part D: If SearXNG returns 0 leadership/linkedin hits, log clearly
    if not people:
        logger.info(f"[SearXNG] No leadership hits for {clean_company} — decision makers not found via search")

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
    """
    if not mx_records:
        return {"deliverable": False, "status": "rejected_no_mx", "email": email, "tier": "personal", "badge": "Dropped"}

    # Bug #4 Fix: Generic emails must NEVER be treated as personal / executive verified
    if is_generic_email(email):
        return {
            "deliverable": False,
            "status": "generic_departmental",
            "email": email,
            "confidence": "zero",
            "verified": False,
            "tier": "departmental",
            "badge": "General Contact",
            "source": "generic_rejected"
        }

    # Step 1: Mailboxlayer API Verification
    mbl_res = await verify_via_mailboxlayer(email)
    if mbl_res.get("is_catch_all") is True:
        is_catch_all = True

    if mbl_res.get("status") == "mailboxlayer_smtp_verified" and not is_catch_all:
        return {
            "deliverable": True,
            "status": "smtp_verified",
            "email": email,
            "confidence": "high",
            "verified": True,
            "tier": "personal",
            "badge": "Direct Reach / Verified",
            "source": "mailboxlayer_api"
        }
    elif mbl_res.get("status") in ("mailboxlayer_mailbox_not_found", "mailbox_not_found"):
        return {
            "deliverable": False,
            "status": "mailbox_not_found",
            "email": email,
            "confidence": "zero",
            "verified": False,
            "tier": None,
            "badge": "Dropped",
            "source": "mailboxlayer_api"
        }
    elif is_catch_all:
        return {
            "deliverable": False,
            "status": "catch_all_unverified",
            "email": email,
            "confidence": "low",
            "verified": False,
            "tier": "personal",
            "badge": "Likely (unverified)",
            "source": "catch_all_policy"
        }

    # Step 2: Direct Zero-Send SMTP ping on port 25 with Canary Catch-All Check
    best_mx = mx_records[0][1] if mx_records else None
    if is_catch_all:
        return {
            "deliverable": False,
            "status": "catch_all_unverified",
            "email": email,
            "confidence": "low",
            "verified": False,
            "tier": "personal",
            "badge": "Likely (unverified)",
            "mx_host": best_mx
        }

    smtp_res = await async_verify_email_smtp(email, timeout=6.0)
    status = smtp_res.get("status")
    code = smtp_res.get("code")
    detected_mx = smtp_res.get("mx_host") or best_mx

    if status == "valid":
        return {
            "deliverable": True,
            "status": "smtp_verified",
            "email": email,
            "confidence": "high",
            "verified": True,
            "tier": "personal",
            "badge": "Direct Reach / Verified",
            "mx_host": detected_mx,
            "source": "smtp_canary_handshake"
        }
    elif status == "catch_all" or smtp_res.get("is_catch_all") or is_catch_all:
        return {
            "deliverable": False,
            "status": "catch_all_unverified",
            "email": email,
            "confidence": "low",
            "verified": False,
            "tier": "personal",
            "badge": "Likely (unverified)",
            "mx_host": detected_mx
        }
    elif status in ("invalid", "invalid_mx") or code in (550, 551, 552, 553, 554):
        return {
            "deliverable": False,
            "status": "mailbox_not_found",
            "email": email,
            "confidence": "zero",
            "verified": False,
            "tier": None,
            "badge": "Dropped",
            "mx_host": detected_mx
        }
    else:
        return {
            "deliverable": False,
            "status": status or "unreachable_smtp",
            "email": email,
            "confidence": "low",
            "verified": False,
            "tier": "personal",
            "badge": "Unverified",
            "mx_host": detected_mx
        }


async def enrich_company_contacts_advanced(
    domain: str,
    company_name: str,
    existing_emails: Optional[List[str]] = None,
    website_text: str = "",
    timeout: float = 12.0
) -> Dict[str, Any]:
    """
    Unified Contact Intelligence & Direct Decision Maker Extraction Engine:
    1. Extracts leadership (CEO, Founder, Director) from website /about & /team content.
    2. Runs clean targeted external dorks on LinkedIn.
    3. Synthesizes B2B email permutations for identified executives.
    4. Validates deliverability against domain MX records.
    5. Consolidates all authentic corporate emails, prioritizing direct decision makers.
    """
    clean_domain = domain.lower().replace("www.", "").strip()
    existing_emails = existing_emails or []

    footprint_emails: List[str] = []
    decision_makers: List[Dict[str, str]] = []

    # 1. Resolve MX records (~50ms via Google/Cloudflare DNS)
    try:
        mx_records = await asyncio.wait_for(resolve_mx_records(clean_domain), timeout=3.0)
    except Exception as e:
        logger.debug(f"[ContactEnricherPro] MX resolve error for {clean_domain}: {e}")
        mx_records = []

    # 2. Concurrently execute Web Footprint Dork, Decision Maker Search, and Deep PDF/Press Dorking
    footprint_task = asyncio.create_task(find_web_footprint_emails(clean_domain, company_name))
    dm_task = asyncio.create_task(find_decision_makers(company_name, clean_domain, website_text=website_text))
    press_pdf_task = asyncio.create_task(dork_executive_press_and_pdfs(company_name, clean_domain))

    try:
        results = await asyncio.gather(footprint_task, dm_task, press_pdf_task, return_exceptions=True)
        if len(results) == 3:
            r_fp, r_dm, r_pp = results
            if isinstance(r_fp, list):
                footprint_emails.extend(r_fp)
            if isinstance(r_dm, list):
                decision_makers.extend(r_dm)
            if isinstance(r_pp, dict):
                footprint_emails.extend(r_pp.get("discovered_emails", []))
                for new_dm in r_pp.get("decision_makers", []):
                    dm_names = {d.get("name", "").lower() for d in decision_makers}
                    if new_dm.get("name", "").lower() not in dm_names:
                        decision_makers.append(new_dm)
    except Exception as e:
        logger.debug(f"[ContactEnricherPro] Parallel discovery warning: {e}")

    # Deduplicate footprint emails
    footprint_emails = list(dict.fromkeys(footprint_emails))

    # 3. Anchor Email Reverse Pattern Strategy:
    # Reverse-engineer corporate email schema from authentic emails strictly belonging to this company
    candidate_anchor_pool = [
        em for em in (footprint_emails + existing_emails)
        if em and '@' in em
        and is_valid_email_syntax(em, domain=clean_domain, check_mx=True)
        and email_belongs_to_company(em, clean_domain)
        and not is_generic_email(em)
    ]
    anchor_email, detected_pattern = find_domain_anchor_pattern(
        clean_domain,
        candidate_emails=candidate_anchor_pool,
        known_names=decision_makers
    )
    if detected_pattern:
        logger.info(f"[AnchorStrategy] Domain {clean_domain} matched corporate schema '{detected_pattern}' via anchor '{anchor_email}'")

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

    # 4. Process Decision Makers: Permutate + Mailboxlayer & MX Validation (Strict Zero Fake Policy)
    verified_stakeholders: List[Dict[str, Any]] = []

    for dm in decision_makers[:4]:  # Top leadership figures
        f_name = dm.get("first_name", "")
        l_name = dm.get("last_name", "")
        role = dm.get("role", "Executive")
        full_name = dm.get("name", "")
        linkedin = dm.get("linkedin_url", "")
        site_email = (dm.get("email") or "").strip().lower()

        best_dm_email = None
        best_dm_status = "unverified"
        is_strictly_verified = False

        # Priority 1: Authentic personal email extracted directly from website text for this leader
        if (
            site_email 
            and '@' in site_email 
            and email_belongs_to_company(site_email, clean_domain) 
            and not is_generic_email(site_email)
            and is_valid_email_syntax(site_email, domain=clean_domain, check_mx=True)
        ):
            best_dm_email = site_email
            best_dm_status = "website_direct"
            is_strictly_verified = True
        else:
            # Priority 2: Check candidate pool (footprint, PDFs, press releases) for personal email matching this executive
            fn_clean = re.sub(r'[^a-z]', '', f_name.lower())
            ln_clean = re.sub(r'[^a-z]', '', l_name.lower())
            for cand in candidate_anchor_pool:
                cand_clean = cand.strip().lower()
                if not cand_clean or '@' not in cand_clean or is_generic_email(cand_clean):
                    continue
                cand_local = cand_clean.split('@')[0]
                # Check if executive's last name or first name is in this authentic disclosed email
                if (len(ln_clean) >= 3 and ln_clean in cand_local) or (len(fn_clean) >= 3 and fn_clean in cand_local):
                    best_dm_email = cand_clean
                    best_dm_status = "disclosed_verified"
                    is_strictly_verified = True
                    break

            # Priority 3: Synthesize permutations & verify with Canary Catch-All SMTP
            if not best_dm_email and f_name and clean_domain and mx_records and not is_catch_all:
                permutations = generate_email_permutations(f_name, l_name, clean_domain, pattern=detected_pattern)
                for cand_perm in permutations[:3]:
                    v_res = await verify_synthesized_email(cand_perm, clean_domain, mx_records, is_catch_all)
                    if v_res.get("deliverable") and v_res.get("verified"):
                        best_dm_email = cand_perm
                        best_dm_status = "smtp_verified"
                        is_strictly_verified = True
                        break

        # STRICT ZERO-TOLERANCE POLICY: If no authentic personal email found, leave email as None!
        # NEVER invent permuted emails or accept false SMTP 250 codes without canary proof.
        # Bug #4: Ensure decision maker email cannot be generic
        if best_dm_email and is_generic_email(best_dm_email):
            logger.info(f"[DecisionMaker] Rejected generic email for {full_name}: {best_dm_email}")
            best_dm_email = None
            best_dm_status = "unverified"
            is_strictly_verified = False

        dm_tier = "personal" if best_dm_email else "departmental"
        if not best_dm_email:
            dm_badge = "Unverified"
        elif is_strictly_verified:
            dm_badge = "Direct Reach / Verified"
        elif is_catch_all:
            dm_badge = "Likely (unverified)"
        else:
            dm_badge = "Direct Reach"

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
            "mx_host": best_mx,
            "anchor_pattern": detected_pattern,
            "tier": dm_tier,
            "badge": dm_badge
        })

    # 5. Dual-Tier Email Categorization & Direct Reach Priority
    # STRICT: Only include decision-maker emails that are verified deliverable!
    dm_emails = [s["email"] for s in verified_stakeholders if s.get("email") and s.get("strictly_verified") and not is_generic_email(s["email"])]
    # 🔧 FIX #1, #2, #4: Strictly filter all incoming candidate emails
    raw_discovered = [
        em.strip().lower() for em in (footprint_emails + existing_emails)
        if em and '@' in em
        and is_valid_email_syntax(em, domain=clean_domain, check_mx=True)
        and email_belongs_to_company(em, clean_domain)
    ]

    # Separate discovered emails into personal/individual vs departmental candidates
    discovered_personal: List[str] = []
    for em in raw_discovered:
        if not em or '@' not in em:
            continue
        clean_em = em.strip().lower()
        if clean_em in dm_emails or is_generic_email(clean_em):
            continue
        tier, _ = classify_email(clean_em, known_dm_names=decision_makers)
        if tier == 'personal':
            discovered_personal.append(clean_em)

    discovered_personal = list(dict.fromkeys(discovered_personal))

    # Collect authentic departmental candidate inboxes (Tier 2)
    candidate_dept_emails = [
        em for em in raw_discovered
        if em and '@' in em and (is_generic_email(em.strip().lower()) or classify_email(em.strip().lower())[0] == 'departmental')
    ]

    # Deduplicate departmental inboxes strictly to ONE per functional prefix
    deduped_dept_emails = deduplicate_departmental_emails(candidate_dept_emails, clean_domain)

    # Consolidated Clean Email Array for UI:
    # Priority 1: Direct Decision Maker / Executive Personal Emails
    # Priority 2: Discovered Personal Individual Emails
    # Priority 3: Authentic Departmental Inboxes
    all_emails = list(dict.fromkeys(
        dm_emails + 
        discovered_personal + 
        deduped_dept_emails
    ))

    # Build structured metadata with tier & badge for each email
    email_metadata: List[Dict[str, Any]] = []
    for em in all_emails:
        b_info = get_email_tier_and_badge(
            em,
            smtp_status="valid" if em in dm_emails else ("catch_all" if is_catch_all else "unknown"),
            is_catch_all=is_catch_all,
            is_generic=is_generic_email(em)
        )
        if b_info:
            email_metadata.append(b_info)

    # Primary Email: Direct Decision Maker is ALWAYS #1 Priority
    primary_email = None
    if dm_emails:
        primary_email = dm_emails[0]
    elif discovered_personal:
        primary_email = discovered_personal[0]
    elif deduped_dept_emails:
        primary_email = deduped_dept_emails[0]

    return {
        "domain": clean_domain,
        "company_name": company_name,
        "primary_email": primary_email,
        "all_emails": all_emails,
        "departmental_emails": deduped_dept_emails,
        "personal_emails": dm_emails + discovered_personal,
        "footprint_emails": footprint_emails,
        "decision_makers": verified_stakeholders,
        "email_metadata": email_metadata,
        "has_mx": bool(mx_records),
        "is_catch_all": is_catch_all,
        "mx_host": best_mx,
        "anchor_email": anchor_email,
        "anchor_pattern": detected_pattern
    }


# ─────────────────────────────────────────────────────────────────────────────
# Pattern Library — Learning, Inference, and Decision Maker Email Resolution
# ─────────────────────────────────────────────────────────────────────────────

def learn_and_save_pattern(email: str, domain: str, confidence: int = 85) -> Optional[str]:
    """
    PART 2: Pattern Learning.
    Jab bhi ek personal (non-generic) email mile, uska pattern extract
    karke Pattern Library (database) mein save karo.

    Returns detected pattern string, or None.
    """
    if not email or not domain or is_generic_email(email):
        return None
    clean_domain = domain.lower().replace("www.", "").strip()
    email_domain = email.split("@")[-1].lower().strip() if "@" in email else ""
    if email_domain != clean_domain:
        return None  # Email belongs to a different domain; skip

    detected_pattern = extract_email_pattern(email)
    if not detected_pattern:
        return None

    saved = database.save_domain_pattern(
        domain=clean_domain,
        pattern=detected_pattern,
        anchor_email=email,
        confidence=confidence
    )
    if saved:
        logger.info(
            f"[Pattern Library] Learned: {clean_domain} -> '{detected_pattern}' (from {email})"
        )
        print(
            f"[Pattern Library] Learned: {clean_domain} -> '{detected_pattern}' (from {email})",
            flush=True
        )
    return detected_pattern


def apply_pattern_to_name(person_name: str, domain: str, pattern: str) -> List[str]:
    """
    PART 3a: Candidate email generator.
    Person name + known pattern -> list of candidate email addresses.

    Examples:
      person_name="Ahmed Khan", pattern="first"      -> ["ahmed@domain.com"]
      person_name="Ahmed Khan", pattern="first.last" -> ["ahmed.khan@domain.com",
                                                          "a.khan@domain.com",
                                                          "ahmed.k@domain.com"]
      person_name="Ahmed Khan", pattern="flast"      -> ["akhan@domain.com"]
    """
    candidates: List[str] = []
    if not person_name or not domain or not pattern:
        return candidates

    clean_domain = domain.lower().replace("www.", "").strip()
    name_parts = re.sub(r"[^a-zA-Z ]", "", person_name.strip()).split()
    if not name_parts:
        return candidates

    f = name_parts[0].lower()               # first name
    l = name_parts[-1].lower() if len(name_parts) > 1 else ""  # last name

    # Primary candidate from the known pattern
    primary = synthesize_by_pattern(f, l, clean_domain, pattern)
    if primary:
        candidates.append(primary)

    # Secondary candidates: adjacent patterns for better coverage
    SECONDARY_MAP: Dict[str, List[str]] = {
        "first.last":  ["f.last", "flast", "first"],
        "f.last":      ["first.last", "flast"],
        "flast":       ["f.last", "first.last"],
        "first_last":  ["first.last", "flast"],
        "first-last":  ["first.last", "f.last"],
        "firstlast":   ["first.last", "flast"],
        "last.first":  ["first.last", "f.last"],
        "first":       ["first.last", "flast"],
        "first.l":     ["first.last", "f.last"],
    }
    for sec_pattern in SECONDARY_MAP.get(pattern, []):
        sec_email = synthesize_by_pattern(f, l, clean_domain, sec_pattern)
        if sec_email and sec_email not in candidates:
            candidates.append(sec_email)

    return [c for c in candidates if c]  # Filter out None / empty strings


def infer_decision_maker_email(
    person_name: str,
    domain: str
) -> Optional[Dict]:
    """
    PART 3b: Decision Maker Email Inference Engine.

    Steps:
    1. Pattern Library se domain ka pattern lo.
    2. Agar pattern nahi / confidence < 50, return None.
    3. apply_pattern_to_name() se candidates banao.
    4. Har candidate ko SMTP verify karo (standalone_verify_email_smtp).
    5. Pehla 'valid' wala return karo.
    6. Agar koi 'catch_all' mile aur 'valid' nahi, usse return karo (unverified).
    7. Agar koi bhi nahi, return None.

    Returns:
      {
        "email":      "ahmed@bpl-dxb.com",
        "status":     "valid" | "catch_all",
        "badge":      "Direct Reach / Verified" | "Likely (unverified)",
        "pattern":    "first",
        "confidence": 85
      }
    or None
    """
    if not person_name or not domain:
        return None

    pattern_row = database.get_domain_pattern(domain)
    if not pattern_row:
        logger.debug(f"[Pattern Library] No pattern for {domain} — skipping inference")
        return None

    pattern    = pattern_row["pattern"]
    confidence = pattern_row["confidence"]

    # Zero-Fake Policy: only use patterns with confidence >= 50
    if confidence < 50:
        return None

    candidates = apply_pattern_to_name(person_name, domain, pattern)
    if not candidates:
        return None

    best_catch_all: Optional[Dict] = None

    for candidate in candidates:
        try:
            result = standalone_verify_email_smtp(candidate)
            status = result.get("status") if isinstance(result, dict) else str(result)
        except Exception as e:
            logger.debug(f"[Pattern Library] SMTP error for {candidate}: {e}")
            continue

        if status == "valid":
            logger.info(
                f"[Pattern Library] ✅ INFERRED VALID: {candidate} | pattern={pattern} | conf={confidence}"
            )
            return {
                "email":      candidate,
                "status":     "valid",
                "badge":      "Direct Reach / Verified",
                "pattern":    pattern,
                "confidence": confidence,
            }

        if status == "catch_all" and best_catch_all is None:
            best_catch_all = {
                "email":      candidate,
                "status":     "catch_all",
                "badge":      "Likely (unverified)",
                "pattern":    pattern,
                "confidence": confidence,
            }

    # No valid found — return catch_all if available
    if best_catch_all:
        logger.info(
            f"[Pattern Library] ⚠️ INFERRED CATCH-ALL: {best_catch_all['email']} | pattern={pattern}"
        )
        return best_catch_all

    return None
