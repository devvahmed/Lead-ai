"""
test_pattern_library.py — Full Pattern Library Unit Tests
Run: python backend/test_pattern_library.py
Tests: PART 1 (DB), PART 2 (Learning), PART 3a (apply_pattern_to_name),
       PART 3b (infer_decision_maker_email)
"""
import sys
import os
import types
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ─── Patch DATABASE to use an in-memory temp DB ─────────────────────────────
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DATABASE_FILE"] = _tmp_db.name

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

# ─── Stub smtp_verify ────────────────────────────────────────────────────────
_SMTP_RESULTS = {
    "ahmed@bpl-dxb.com":    {"status": "valid"},
    "a.khan@bpl-dxb.com":   {"status": "invalid"},
    "ahmed.khan@bpl-dxb.com": {"status": "catch_all"},
    "john@acme.io":         {"status": "valid"},
    "j.smith@acme.io":      {"status": "invalid"},
    "john.smith@acme.io":   {"status": "valid"},
}

smtp_mod = types.ModuleType("smtp_verify")
smtp_mod.verify_email_smtp              = lambda em, **kw: _SMTP_RESULTS.get(em, {"status": "unknown"})
smtp_mod.async_verify_email_smtp        = None
smtp_mod.apply_smtp_policy              = lambda x: x
smtp_mod.batch_verify_emails            = lambda x: x
smtp_mod.get_email_tier_and_badge       = lambda x: ("T1", "badge")
sys.modules["smtp_verify"] = smtp_mod

# ─── Stub dns.resolver ───────────────────────────────────────────────────────
dns_mod     = types.ModuleType("dns")
resolver_mod = types.ModuleType("dns.resolver")
class _FakeResolver:
    nameservers = []
    timeout = 2
    lifetime = 3
resolver_mod.Resolver = _FakeResolver
dns_mod.resolver = resolver_mod
sys.modules["dns"] = dns_mod
sys.modules["dns.resolver"] = resolver_mod

# ─── Stub discover ───────────────────────────────────────────────────────────
discover_mod = types.ModuleType("discover")
discover_mod.search_searxng_or_ddg = None
discover_mod.generate_industry_search_queries = None
discover_mod.clean_domain = lambda x: x
sys.modules["discover"] = discover_mod

# ─── Now import the real modules ─────────────────────────────────────────────
import database
database.init_db()   # Creates all tables including domain_email_patterns

from contact_enricher_pro import (
    extract_email_pattern,
    synthesize_by_pattern,
    learn_and_save_pattern,
    apply_pattern_to_name,
    infer_decision_maker_email,
    is_generic_email,
)

# ─── Test Harness ─────────────────────────────────────────────────────────────
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

print("\n══════════════════════════════════════════════════════")
print("  Pattern Library — Full Unit Test Suite")
print("══════════════════════════════════════════════════════\n")


# ──────────────────────────────────────────────────────────────────────────────
# PART 1: Database functions
# ──────────────────────────────────────────────────────────────────────────────
print("PART 1 — database.py Functions:")

ok = database.save_domain_pattern("bpl-dxb.com", "first", "ahmed@bpl-dxb.com", confidence=85)
check("save_domain_pattern returns True", ok)

row = database.get_domain_pattern("bpl-dxb.com")
check("get_domain_pattern returns dict",         row is not None)
check("pattern is 'first'",                      row and row["pattern"] == "first")
check("anchor_email correct",                    row and row["anchor_email"] == "ahmed@bpl-dxb.com")
check("confidence is 85",                        row and row["confidence"] == 85)

# Update with lower confidence — should not decrease existing confidence
database.save_domain_pattern("bpl-dxb.com", "first", "ahmed@bpl-dxb.com", confidence=50)
row2 = database.get_domain_pattern("bpl-dxb.com")
check("confidence stays at MAX (85, not 50)",   row2 and row2["confidence"] == 85)

# get_domain_pattern with unknown domain
check("get_domain_pattern(unknown) is None",    database.get_domain_pattern("unknown-xyz.com") is None)

# list_all_patterns
database.save_domain_pattern("acme.io", "first.last", "john.smith@acme.io", confidence=90)
patterns = database.list_all_patterns()
check("list_all_patterns returns 2+ entries",   len(patterns) >= 2)
check("first entry has highest confidence",     patterns[0]["confidence"] >= patterns[-1]["confidence"])


# ──────────────────────────────────────────────────────────────────────────────
# PART 2: Pattern Learning (learn_and_save_pattern)
# ──────────────────────────────────────────────────────────────────────────────
print("\nPART 2 — learn_and_save_pattern:")

# Structured email — has a dot separator, so extract_email_pattern can detect it
result = learn_and_save_pattern("john.smith@acme.io", "acme.io", confidence=90)
check("learn_and_save_pattern returns pattern string for structured email", result is not None)
check("pattern is 'first.last'",                       result == "first.last")

# Generic email should return None — not learned
result_generic = learn_and_save_pattern("info@freshco.ae", "freshco.ae")
check("Generic email not learned (returns None)",       result_generic is None)

# Cross-domain email should return None
result_cross = learn_and_save_pattern("omar@other-domain.com", "freshco.ae")
check("Cross-domain email not learned (returns None)",  result_cross is None)

# Single-token email (no separator) — extract_email_pattern returns None by design
# This is correct: we cannot detect 'first' vs 'last' without known_names
result_nopattern = learn_and_save_pattern("omar@freshco.ae", "freshco.ae")
check("Single-token email → None (correct: no structural pattern)", result_nopattern is None)


# ──────────────────────────────────────────────────────────────────────────────
# PART 3a: apply_pattern_to_name
# ──────────────────────────────────────────────────────────────────────────────
print("\nPART 3a — apply_pattern_to_name:")

cands_first = apply_pattern_to_name("Ahmed Khan", "bpl-dxb.com", "first")
check("'first' pattern → ahmed@bpl-dxb.com in candidates",    "ahmed@bpl-dxb.com" in cands_first)

cands_flast = apply_pattern_to_name("Ahmed Khan", "bpl-dxb.com", "flast")
check("'flast' pattern → akhan@bpl-dxb.com in candidates",    "akhan@bpl-dxb.com" in cands_flast)

cands_fl = apply_pattern_to_name("Ahmed Khan", "bpl-dxb.com", "first.last")
check("'first.last' → ahmed.khan@bpl-dxb.com in candidates",  "ahmed.khan@bpl-dxb.com" in cands_fl)
check("'first.last' → also generates secondary candidates",    len(cands_fl) > 1)

cands_single = apply_pattern_to_name("Omar", "freshco.ae", "first")
check("Single-part name → omar@freshco.ae",                   "omar@freshco.ae" in cands_single)

cands_empty = apply_pattern_to_name("", "bpl-dxb.com", "first")
check("Empty name → empty list",                               cands_empty == [])


# ──────────────────────────────────────────────────────────────────────────────
# PART 3b: infer_decision_maker_email
# ──────────────────────────────────────────────────────────────────────────────
print("\nPART 3b — infer_decision_maker_email:")

# bpl-dxb.com has pattern='first', anchor='ahmed@bpl-dxb.com'
# SMTP stub: ahmed@bpl-dxb.com -> valid
result_valid = infer_decision_maker_email("Ahmed Khan", "bpl-dxb.com")
check("Inferred valid email returned",               result_valid is not None)
check("email == ahmed@bpl-dxb.com",                 result_valid and result_valid["email"] == "ahmed@bpl-dxb.com")
check("status == 'valid'",                           result_valid and result_valid["status"] == "valid")
check("badge == 'Direct Reach / Verified'",          result_valid and result_valid["badge"] == "Direct Reach / Verified")
check("pattern == 'first'",                          result_valid and result_valid["pattern"] == "first")

# acme.io has pattern='first.last'
# SMTP: john.smith@acme.io -> valid (primary candidate)
result_acme = infer_decision_maker_email("John Smith", "acme.io")
check("Inferred valid from first.last pattern",      result_acme is not None)
check("email == john.smith@acme.io",                 result_acme and result_acme["email"] == "john.smith@acme.io")

# No pattern for unknown domain
result_none = infer_decision_maker_email("Random Person", "no-pattern-domain.xyz")
check("Unknown domain → None",                       result_none is None)

# Empty name → None
result_empty = infer_decision_maker_email("", "bpl-dxb.com")
check("Empty name → None",                           result_empty is None)


# ──────────────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────────────
print(f"\n══════════════════════════════════════════════════════")
print(f"  Results: {passed} passed, {failed} failed")
print(f"══════════════════════════════════════════════════════\n")

# Cleanup temp DB
try:
    os.unlink(_tmp_db.name)
except Exception:
    pass

sys.exit(0 if failed == 0 else 1)
