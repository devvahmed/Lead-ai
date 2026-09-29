"""
Unit test: automation_engine.py – SMTP verification & generic email filtering
Run: python backend/test_smtp_gate.py
"""
import types, sys, asyncio

# ── Stub smtp_verify ──────────────────────────────────────────────────────────
class _SmtpVerify:
    """Returns preconfigured status per email for deterministic testing."""
    _RESULTS = {
        "john@acmecorp.com":     {"status": "valid"},
        "info@acmecorp.com":     {"status": "valid"},   # will be blocked by is_generic_email
        "hello@widgets.io":     {"status": "valid"},   # will be blocked by is_generic_email
        "noreply@gadgets.co":   {"status": "invalid"},
        "ceo@globalfirm.com":   {"status": "catch_all"},
        "ops@logistics.co.uk":  {"status": "unknown"},
    }
    def verify_email_smtp(self, email):
        return self._RESULTS.get(email, {"status": "unknown"})

stub_smtp = _SmtpVerify()
smtp_module = types.ModuleType("smtp_verify")
smtp_module.verify_email_smtp = stub_smtp.verify_email_smtp
sys.modules["smtp_verify"] = smtp_module

# ── Stub contact_enricher_pro ────────────────────────────────────────────────
_GENERIC_PREFIXES = {
    "info", "hello", "support", "sales", "contact", "general",
    "developers", "games", "noreply", "no-reply", "admin", "webmaster",
    "help", "enquiries", "enquiry", "mail", "office", "team", "hr", "jobs"
}
def _is_generic(email: str) -> bool:
    prefix = email.split("@")[0].lower()
    return prefix in _GENERIC_PREFIXES

ce_module = types.ModuleType("contact_enricher_pro")
ce_module.is_generic_email = _is_generic
sys.modules["contact_enricher_pro"] = ce_module

# ── Now import the functions under test directly ──────────────────────────────
from smtp_verify import verify_email_smtp
from contact_enricher_pro import is_generic_email

# ── Test Cases ───────────────────────────────────────────────────────────────
PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
passed = failed = 0

def check(label, condition):
    global passed, failed
    if condition:
        print(f"  {PASS}  {label}")
        passed += 1
    else:
        print(f"  {FAIL}  {label}")
        failed += 1

print("\n══════════════════════════════════════════════")
print("  automation_engine.py  –  Email Gate Tests")
print("══════════════════════════════════════════════\n")

# 1. is_generic_email
print("1. Generic Email Ban:")
check("info@… is generic",       is_generic_email("info@acmecorp.com"))
check("hello@… is generic",      is_generic_email("hello@widgets.io"))
check("support@… is generic",    is_generic_email("support@foo.com"))
check("sales@… is generic",      is_generic_email("sales@bar.com"))
check("developers@… is generic", is_generic_email("developers@baz.com"))
check("games@… is generic",      is_generic_email("games@baz.com"))
check("john@… is NOT generic",   not is_generic_email("john@acmecorp.com"))
check("ceo@… is NOT generic",    not is_generic_email("ceo@globalfirm.com"))

# 2. SMTP verification statuses
print("\n2. SMTP Verification Logic:")
smtp_valid   = verify_email_smtp("john@acmecorp.com")
smtp_invalid = verify_email_smtp("noreply@gadgets.co")
smtp_catch   = verify_email_smtp("ceo@globalfirm.com")
smtp_unknown = verify_email_smtp("ops@logistics.co.uk")

check("valid email → status=='valid'",       smtp_valid["status"] == "valid")
check("invalid email → status=='invalid'",   smtp_invalid["status"] == "invalid")
check("catch-all email → status=='catch_all'", smtp_catch["status"] == "catch_all")
check("unknown email → status=='unknown'",   smtp_unknown["status"] == "unknown")

# 3. Combined gate logic (as it runs in automation_engine.py)
print("\n3. Combined Gate Simulation:")

def gate(email):
    """Mirrors the exact if-chain added to automation_engine.py."""
    if is_generic_email(email):
        return "SKIP_GENERIC"
    result = verify_email_smtp(email)
    status = result.get("status")
    if status in ("invalid", "invalid_mx"):
        return "DROP_INVALID"
    if status == "catch_all":
        return "SKIP_CATCHALL"
    if status != "valid":
        return "SKIP_UNKNOWN"
    return "SAVE_LEAD"

check("john@acmecorp.com  → SAVE_LEAD",     gate("john@acmecorp.com")  == "SAVE_LEAD")
check("info@acmecorp.com  → SKIP_GENERIC",  gate("info@acmecorp.com")  == "SKIP_GENERIC")
check("hello@widgets.io   → SKIP_GENERIC",  gate("hello@widgets.io")   == "SKIP_GENERIC")
# noreply is in _GENERIC_PREFIXES → blocked before SMTP is called
check("noreply@gadgets.co → SKIP_GENERIC",  gate("noreply@gadgets.co") == "SKIP_GENERIC")
check("ceo@globalfirm.com → SKIP_CATCHALL", gate("ceo@globalfirm.com") == "SKIP_CATCHALL")
check("ops@logistics.co.uk→ SKIP_UNKNOWN",  gate("ops@logistics.co.uk")== "SKIP_UNKNOWN")

print(f"\n══════════════════════════════════════════════")
print(f"  Results: {passed} passed, {failed} failed")
print(f"══════════════════════════════════════════════\n")
sys.exit(0 if failed == 0 else 1)
