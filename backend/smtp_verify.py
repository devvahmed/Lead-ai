"""
smtp_verify.py
==============
Standalone SMTP Verification Module — Lead-AI Pipeline

Zero-Send SMTP handshake with Canary Catch-All Detection.
Drop-in compatible with contact_enricher_pro.py and email_outreach.py.

USAGE (sync):
    from smtp_verify import verify_email_smtp
    result = verify_email_smtp("john.doe@company.com")

STATUS MATRIX:
  "valid"       -> 250 for target + canary rejected (550) -> Mailbox confirmed real
  "invalid"     -> 5xx hard reject for target -> Mailbox definitely does not exist -> DROP
  "catch_all"   -> 250 for target AND 250 for canary -> Server accepts all -> Unverifiable
  "unknown"     -> Connection timeout / port 25 blocked / ISP filter
  "invalid_mx"  -> No MX record found for domain -> DROP

ZERO-FAKE POLICY:
  - If "invalid" or "invalid_mx" -> email MUST be dropped from output
  - If "catch_all" -> email MUST NOT be labeled "Verified" or "Direct Reach"
  - 2-second inter-domain rate limit (configurable via SMTP_RATE_LIMIT_SEC env)
  - 10-second SMTP timeout (configurable via SMTP_TIMEOUT env)
"""

import re
import os
import time
import socket
import asyncio
import smtplib
import logging
import random
import string
from typing import Dict, List, Optional, Tuple, Any

import dns.resolver

logger = logging.getLogger("smtp_verify")

# --- Configuration -----------------------------------------------------------
SMTP_HELO_DOMAIN    = os.getenv("SMTP_HELO_DOMAIN",    "leadai.com")
SMTP_FROM_EMAIL     = os.getenv("SMTP_FROM_EMAIL",     "verify@leadai.com")
SMTP_TIMEOUT        = float(os.getenv("SMTP_TIMEOUT",  "10"))
SMTP_RATE_LIMIT_SEC = float(os.getenv("SMTP_RATE_LIMIT_SEC", "2"))

# --- DNS Resolver ------------------------------------------------------------
_DNS_RESOLVER = dns.resolver.Resolver()
_DNS_RESOLVER.nameservers = ["8.8.8.8", "1.1.1.1"]
_DNS_RESOLVER.timeout     = 2.0
_DNS_RESOLVER.lifetime    = 4.0

# --- In-Memory Caches --------------------------------------------------------
_MX_CACHE: Dict[str, Tuple[float, List[Tuple[int, str]]]] = {}
MX_CACHE_TTL = 3600

_PORT_25_FILTERED: Dict[str, float] = {}
PORT_25_BLOCK_TTL = 600

_DOMAIN_RATE: Dict[str, float] = {}


# --- Result Schema -----------------------------------------------------------
def _make_result(
    email: str,
    status: str,
    verified: bool = False,
    deliverable: bool = False,
    code: Optional[int] = None,
    code2: Optional[int] = None,
    is_catch_all: bool = False,
    mx_host: Optional[str] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "email":        email,
        "status":       status,
        "verified":     verified,
        "deliverable":  deliverable,
        "code":         code,
        "code2":        code2,
        "is_catch_all": is_catch_all,
        "mx_host":      mx_host,
        "error":        error,
    }


# --- MX Resolution -----------------------------------------------------------
def resolve_mx_sync(domain: str) -> List[Tuple[int, str]]:
    clean = domain.lower().replace("www.", "").strip()
    if not clean:
        return []
    now = time.time()
    if clean in _MX_CACHE:
        ts, records = _MX_CACHE[clean]
        if now - ts < MX_CACHE_TTL:
            return records
    try:
        answers = _DNS_RESOLVER.resolve(clean, "MX", lifetime=4.0)
        records = sorted(
            [(r.preference, str(r.exchange).rstrip(".")) for r in answers],
            key=lambda x: x[0],
        )
        _MX_CACHE[clean] = (now, records)
        return records
    except Exception as e:
        logger.debug(f"[MX] No records for {clean}: {e}")
        _MX_CACHE[clean] = (now, [])
        return []


async def resolve_mx_async(domain: str) -> List[Tuple[int, str]]:
    return await asyncio.to_thread(resolve_mx_sync, domain)


# --- Canary Generator --------------------------------------------------------
def _generate_canary(domain: str) -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"xkjhgfdsa_{suffix}@{domain}"


# --- Async SMTP Handshake ----------------------------------------------------
async def _smtp_handshake_async(
    email: str,
    mx_host: str,
    from_email: str = SMTP_FROM_EMAIL,
    helo_domain: str = SMTP_HELO_DOMAIN,
    timeout: float = SMTP_TIMEOUT,
) -> Dict[str, Any]:
    domain = email.split("@")[1] if "@" in email else ""
    now = time.time()
    if mx_host in _PORT_25_FILTERED and (now - _PORT_25_FILTERED[mx_host]) < PORT_25_BLOCK_TTL:
        return _make_result(email, "unknown", mx_host=mx_host,
                            error="Port 25 unreachable/filtered (cached)")
    reader, writer = None, None
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(mx_host, 25), timeout=timeout)
        banner = await asyncio.wait_for(reader.readline(), timeout=timeout)
        if not banner.startswith(b"220"):
            return _make_result(email, "unknown", mx_host=mx_host,
                                error=f"Bad banner: {banner.decode('utf-8','replace').strip()}")
        writer.write(f"HELO {helo_domain}\r\n".encode())
        await writer.drain()
        await asyncio.wait_for(reader.readline(), timeout=timeout)
        writer.write(f"MAIL FROM:<{from_email}>\r\n".encode())
        await writer.drain()
        mail_resp = await asyncio.wait_for(reader.readline(), timeout=timeout)
        if not mail_resp.startswith(b"250"):
            return _make_result(email, "unknown", mx_host=mx_host,
                                error=f"MAIL FROM rejected: {mail_resp.decode('utf-8','replace').strip()}")
        writer.write(f"RCPT TO:<{email}>\r\n".encode())
        await writer.drain()
        r1 = await asyncio.wait_for(reader.readline(), timeout=timeout)
        r1s = r1.decode("utf-8", "replace").strip()
        m1 = re.match(r"^(\d{3})", r1s)
        if not m1:
            return _make_result(email, "unknown", mx_host=mx_host,
                                error=f"Unparseable RCPT1: {r1s}")
        code1 = int(m1.group(1))
        if code1 in (550, 551, 552, 553, 554, 521, 503):
            return _make_result(email, "invalid", code=code1, mx_host=mx_host)
        if code1 in (450, 451, 452):
            return _make_result(email, "unknown", code=code1, mx_host=mx_host,
                                error=f"Greylisted ({code1})")
        if code1 == 250:
            canary = _generate_canary(domain)
            writer.write(f"RCPT TO:<{canary}>\r\n".encode())
            await writer.drain()
            r2 = await asyncio.wait_for(reader.readline(), timeout=timeout)
            r2s = r2.decode("utf-8", "replace").strip()
            m2 = re.match(r"^(\d{3})", r2s)
            code2 = int(m2.group(1)) if m2 else None
            if code2 == 250:
                return _make_result(email, "catch_all", code=code1, code2=code2,
                                    is_catch_all=True, mx_host=mx_host)
            return _make_result(email, "valid", verified=True, deliverable=True,
                                code=code1, code2=code2, mx_host=mx_host)
        return _make_result(email, "unknown", code=code1, mx_host=mx_host,
                            error=f"Non-standard code: {code1}")
    except asyncio.TimeoutError:
        _PORT_25_FILTERED[mx_host] = time.time()
        return _make_result(email, "unknown", mx_host=mx_host, error="SMTP timed out")
    except (ConnectionRefusedError, OSError, socket.gaierror) as e:
        _PORT_25_FILTERED[mx_host] = time.time()
        return _make_result(email, "unknown", mx_host=mx_host, error=f"Connection error: {e}")
    except Exception as e:
        return _make_result(email, "unknown", mx_host=mx_host, error=f"Error: {e}")
    finally:
        if writer:
            try:
                writer.write(b"QUIT\r\n")
                await writer.drain()
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass


# --- Public Async API --------------------------------------------------------
async def async_verify_email_smtp(
    email: str,
    from_email: str = SMTP_FROM_EMAIL,
    timeout: float = SMTP_TIMEOUT,
    rate_limit: float = SMTP_RATE_LIMIT_SEC,
) -> Dict[str, Any]:
    """
    Async email SMTP verification. Use inside FastAPI/asyncio contexts.
    Returns dict: {email, status, verified, deliverable, code, code2, is_catch_all, mx_host, error}
    """
    if not email or "@" not in email:
        return _make_result(email or "", "invalid", error="Malformed email address")
    domain = email.split("@")[1].strip().lower()
    mx_records = await resolve_mx_async(domain)
    if not mx_records:
        return _make_result(email, "invalid_mx", error=f"No MX records for {domain}")
    mx_host = mx_records[0][1]
    now = time.time()
    last = _DOMAIN_RATE.get(domain, 0)
    wait = rate_limit - (now - last)
    if wait > 0:
        await asyncio.sleep(wait)
    _DOMAIN_RATE[domain] = time.time()
    return await _smtp_handshake_async(email, mx_host, from_email=from_email, timeout=timeout)


# --- Public Sync API ---------------------------------------------------------
def verify_email_smtp(
    email: str,
    from_email: str = SMTP_FROM_EMAIL,
    timeout: float = SMTP_TIMEOUT,
    rate_limit: float = SMTP_RATE_LIMIT_SEC,
) -> Dict[str, Any]:
    """
    Synchronous email SMTP verification. Use in non-async contexts or for direct calls.

    Status values:
        "valid"      -> Verified real mailbox
        "invalid"    -> Hard bounce — DROP this email
        "catch_all"  -> Cannot verify — do NOT label as "Direct Reach"
        "unknown"    -> Port 25 blocked or timeout — leave as unverified
        "invalid_mx" -> No MX records — DROP this email
    """
    if not email or "@" not in email:
        return _make_result(email or "", "invalid", error="Malformed email address")
    domain = email.split("@")[1].strip().lower()
    mx_records = resolve_mx_sync(domain)
    if not mx_records:
        return _make_result(email, "invalid_mx", error=f"No MX records for {domain}")
    mx_host = mx_records[0][1]
    now = time.time()
    last = _DOMAIN_RATE.get(domain, 0)
    wait = rate_limit - (now - last)
    if wait > 0:
        time.sleep(wait)
    _DOMAIN_RATE[domain] = time.time()
    if mx_host in _PORT_25_FILTERED and (time.time() - _PORT_25_FILTERED[mx_host]) < PORT_25_BLOCK_TTL:
        return _make_result(email, "unknown", mx_host=mx_host, error="Port 25 blocked (cached)")
    canary = _generate_canary(domain)
    try:
        server = smtplib.SMTP(timeout=timeout)
        server.connect(mx_host, 25)
        server.helo(SMTP_HELO_DOMAIN)
        server.mail(from_email)
        code1, _ = server.rcpt(email)
        if code1 in (550, 551, 552, 553, 554, 521, 503):
            _safe_quit(server)
            return _make_result(email, "invalid", code=code1, mx_host=mx_host)
        if code1 in (450, 451, 452):
            _safe_quit(server)
            return _make_result(email, "unknown", code=code1, mx_host=mx_host,
                                error=f"Greylisted ({code1})")
        if code1 == 250:
            code2, _ = server.rcpt(canary)
            _safe_quit(server)
            if code2 == 250:
                return _make_result(email, "catch_all", code=code1, code2=code2,
                                    is_catch_all=True, mx_host=mx_host)
            return _make_result(email, "valid", verified=True, deliverable=True,
                                code=code1, code2=code2, mx_host=mx_host)
        _safe_quit(server)
        return _make_result(email, "unknown", code=code1, mx_host=mx_host,
                            error=f"Non-standard code: {code1}")
    except smtplib.SMTPConnectError as e:
        _PORT_25_FILTERED[mx_host] = time.time()
        return _make_result(email, "unknown", mx_host=mx_host, error=f"SMTPConnectError: {e}")
    except (socket.timeout, TimeoutError) as e:
        _PORT_25_FILTERED[mx_host] = time.time()
        return _make_result(email, "unknown", mx_host=mx_host, error=f"Timeout: {e}")
    except (ConnectionRefusedError, OSError, socket.gaierror) as e:
        _PORT_25_FILTERED[mx_host] = time.time()
        return _make_result(email, "unknown", mx_host=mx_host, error=f"Connection error: {e}")
    except Exception as e:
        return _make_result(email, "unknown", mx_host=mx_host, error=f"Unexpected: {e}")


def _safe_quit(server: smtplib.SMTP) -> None:
    try:
        server.quit()
    except Exception:
        try:
            server.close()
        except Exception:
            pass


# --- Batch Helper ------------------------------------------------------------
async def batch_verify_emails(
    emails: List[str],
    from_email: str = SMTP_FROM_EMAIL,
    timeout: float = SMTP_TIMEOUT,
    rate_limit: float = SMTP_RATE_LIMIT_SEC,
    max_concurrent: int = 5,
) -> List[Dict[str, Any]]:
    """
    Async batch verification with concurrency control.
    Respects per-domain rate limits. Returns results in input order.
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _verify_with_sem(em: str) -> Dict[str, Any]:
        async with semaphore:
            return await async_verify_email_smtp(
                em, from_email=from_email, timeout=timeout, rate_limit=rate_limit)

    return await asyncio.gather(*[_verify_with_sem(em) for em in emails])


# --- Pipeline Policy Helper --------------------------------------------------
def apply_smtp_policy(result: Dict[str, Any]) -> Optional[str]:
    """
    Enforces Zero-Fake Policy:
      - Returns email string if it should be kept (valid / catch_all / unknown)
      - Returns None if it must be dropped (invalid / invalid_mx)

    Caller is responsible for labeling:
      result["verified"] == True  -> "Verified"
      result["is_catch_all"]      -> "Unverified (Catch-All)"
      status == "unknown"         -> "Unverified"
    """
    status = result.get("status", "unknown")
    email  = result.get("email", "")
    if status in ("invalid", "invalid_mx"):
        logger.info(f"[SMTP Policy] Dropping {email!r} — {status}")
        return None
    return email or None


# --- CLI Quick-Test ----------------------------------------------------------
if __name__ == "__main__":
    import sys
    test_emails = sys.argv[1:] if len(sys.argv) > 1 else [
        "info@google.com",
        "ceo@nonexistent-xyz.io",
        "nobody@gmail.com",
    ]
    print("\n" + "="*60)
    print("  smtp_verify.py — Quick Test")
    print("="*60)
    for email in test_emails:
        print(f"\nTesting: {email}")
        result = verify_email_smtp(email)
        icon = {"valid": "OK", "invalid": "INVALID", "catch_all": "CATCH_ALL",
                "unknown": "UNKNOWN", "invalid_mx": "NO_MX"}.get(result["status"], "?")
        print(f"  [{icon}] status={result['status']} verified={result['verified']}")
        print(f"  mx={result['mx_host']} code={result['code']}/{result['code2']}")
        if result["error"]:
            print(f"  error={result['error']}")
    print("\n" + "="*60 + "\n")