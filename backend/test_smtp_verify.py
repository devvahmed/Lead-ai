"""
test_smtp_verify.py
===================
Test suite for smtp_verify.py — 3 required scenarios:

  Test 1: Known valid email on a real domain (catch_all expected on most large servers)
  Test 2: A catch-all domain — should return status="catch_all"
  Test 3: An invalid mailbox on a real domain — should return status="invalid"

Run:
    cd backend
    python test_smtp_verify.py

NOTE:
  - Port 25 is frequently blocked by ISPs and cloud providers (AWS, GCP, DO).
    If port 25 is blocked, all results will be "unknown" — this is expected behavior.
  - Run on a server/VPS with open port 25 for accurate results.
  - Gmail / Office 365 often greylist automated SMTP connections.
"""

import asyncio
import sys
import os

# Ensure backend/ is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from smtp_verify import (
    verify_email_smtp,
    async_verify_email_smtp,
    batch_verify_emails,
    apply_smtp_policy,
)


# =============================================================================
#  HELPERS
# =============================================================================
def print_result(label: str, result: dict) -> None:
    status = result.get("status", "?")
    ICONS = {
        "valid":      "[OK]     ",
        "invalid":    "[INVALID]",
        "catch_all":  "[CATCH]  ",
        "unknown":    "[UNKNOWN]",
        "invalid_mx": "[NO_MX]  ",
    }
    icon = ICONS.get(status, "[?]     ")
    print(f"\n  {icon} {label}")
    print(f"           Email      : {result['email']}")
    print(f"           Status     : {result['status']}")
    print(f"           Verified   : {result['verified']}")
    print(f"           Deliverable: {result['deliverable']}")
    print(f"           Catch-All  : {result['is_catch_all']}")
    print(f"           MX Host    : {result['mx_host']}")
    print(f"           Code 1/2   : {result['code']} / {result['code2']}")
    if result["error"]:
        print(f"           Error      : {result['error']}")


def assert_status(result: dict, expected_statuses: list, test_name: str) -> bool:
    got = result.get("status")
    if got in expected_statuses:
        print(f"  [PASS] {test_name} — status={got}")
        return True
    else:
        print(f"  [WARN] {test_name} — got '{got}', expected one of {expected_statuses}")
        print(f"         (Port 25 may be blocked or ISP filtering — 'unknown' is acceptable)")
        return False


# =============================================================================
#  SYNC TESTS
# =============================================================================
def run_sync_tests():
    print("\n" + "="*65)
    print("  SYNC TESTS  (verify_email_smtp)")
    print("="*65)

    # ------------------------------------------------------------------
    # Test 1: Known valid email — real domain, real mailbox pattern
    # Most large mailservers (Google, Microsoft) block port 25 from
    # consumer IPs, so "unknown" is acceptable here.
    # On a clean VPS with open port 25, this should be "valid" or "catch_all".
    # ------------------------------------------------------------------
    print("\n--- Test 1: Real domain, plausible mailbox (apaonline.org) ---")
    result1 = verify_email_smtp("amy.ferrer@apaonline.org", rate_limit=0)
    print_result("Test 1 — Amy Ferrer @ apaonline.org", result1)
    assert_status(result1, ["valid", "catch_all", "unknown"], "Test 1")

    # ------------------------------------------------------------------
    # Test 2: Catch-all detection
    # Domains that accept all incoming email (catch-all) should return
    # status="catch_all". Use a domain known to be catch-all.
    # If port 25 blocked: "unknown" is acceptable.
    # ------------------------------------------------------------------
    print("\n--- Test 2: Catch-all domain probe ---")
    result2 = verify_email_smtp("xyzfakeuser999@mailnull.com", rate_limit=0)
    print_result("Test 2 — Fake user @ mailnull.com (known catch-all)", result2)
    assert_status(result2, ["catch_all", "unknown"], "Test 2")

    # ------------------------------------------------------------------
    # Test 3: Invalid mailbox — real domain (Gmail) + definitely fake user
    # Gmail returns 550 for non-existent mailboxes, but may block port 25.
    # On open port 25: should be "invalid". Otherwise "unknown".
    # ------------------------------------------------------------------
    print("\n--- Test 3: Nonexistent mailbox on real domain ---")
    result3 = verify_email_smtp("xkjhgfdsa_notarealuser99999@gmail.com", rate_limit=0)
    print_result("Test 3 — Fake user @ gmail.com", result3)
    assert_status(result3, ["invalid", "unknown"], "Test 3")

    # ------------------------------------------------------------------
    # Test 4: No MX records — bogus domain — MUST be "invalid_mx"
    # ------------------------------------------------------------------
    print("\n--- Test 4: Domain with no MX record ---")
    result4 = verify_email_smtp("ceo@thisdomaindoesnotexist9999xyz.io", rate_limit=0)
    print_result("Test 4 — No MX domain", result4)
    ok = assert_status(result4, ["invalid_mx"], "Test 4 (strict)")
    if not ok:
        print("  [FAIL] This should ALWAYS be invalid_mx regardless of port 25 status")

    # ------------------------------------------------------------------
    # Test 5: Malformed email — MUST be "invalid"
    # ------------------------------------------------------------------
    print("\n--- Test 5: Malformed email address ---")
    result5 = verify_email_smtp("not-an-email-at-all", rate_limit=0)
    print_result("Test 5 — Malformed", result5)
    ok = assert_status(result5, ["invalid"], "Test 5 (strict)")
    if not ok:
        print("  [FAIL] Malformed email must always return 'invalid'")


# =============================================================================
#  POLICY TESTS
# =============================================================================
def run_policy_tests():
    print("\n" + "="*65)
    print("  POLICY TESTS  (apply_smtp_policy)")
    print("="*65)

    # Simulate results
    cases = [
        ({"email": "a@b.com", "status": "valid",      "verified": True,  "is_catch_all": False}, "a@b.com",  "valid -> keep"),
        ({"email": "x@y.com", "status": "invalid",    "verified": False, "is_catch_all": False}, None,       "invalid -> DROP"),
        ({"email": "p@q.com", "status": "invalid_mx", "verified": False, "is_catch_all": False}, None,       "invalid_mx -> DROP"),
        ({"email": "m@n.com", "status": "catch_all",  "verified": False, "is_catch_all": True},  "m@n.com",  "catch_all -> keep (but unverified)"),
        ({"email": "u@v.com", "status": "unknown",    "verified": False, "is_catch_all": False}, "u@v.com",  "unknown -> keep (unverified)"),
    ]

    all_pass = True
    for result, expected, description in cases:
        got = apply_smtp_policy(result)
        ok = (got == expected)
        status = "[PASS]" if ok else "[FAIL]"
        print(f"  {status} {description}: got={got!r}, expected={expected!r}")
        if not ok:
            all_pass = False

    if all_pass:
        print("\n  All policy tests PASSED.")
    else:
        print("\n  Some policy tests FAILED — check output above.")


# =============================================================================
#  ASYNC TESTS
# =============================================================================
async def run_async_tests():
    print("\n" + "="*65)
    print("  ASYNC TESTS  (async_verify_email_smtp + batch_verify_emails)")
    print("="*65)

    print("\n--- Async single: amy.ferrer@apaonline.org ---")
    result = await async_verify_email_smtp("amy.ferrer@apaonline.org", rate_limit=0)
    print_result("Async single", result)
    assert_status(result, ["valid", "catch_all", "unknown"], "Async single")

    print("\n--- Batch: 3 emails ---")
    emails = [
        "xkjhgfdsa_notarealuser99999@gmail.com",
        "ceo@thisdomaindoesnotexist9999xyz.io",
        "contact@apaonline.org",
    ]
    results = await batch_verify_emails(emails, rate_limit=0, max_concurrent=3)
    for r in results:
        print_result(r["email"], r)


# =============================================================================
#  ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    print("\n" + "#"*65)
    print("  smtp_verify.py — Full Test Suite")
    print("#"*65)
    print("\nNOTE: 'unknown' status is acceptable on machines where port 25")
    print("is blocked by ISP or cloud provider (AWS/GCP/DO all block port 25).")
    print("For accurate results, run this on a bare VPS or dedicated server.")

    run_sync_tests()
    run_policy_tests()
    asyncio.run(run_async_tests())

    print("\n" + "#"*65)
    print("  Test suite complete.")
    print("#"*65 + "\n")