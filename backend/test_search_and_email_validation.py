"""
Test script for verifying:
1. B2B Marketplace Exclusion (made-in-china.com, alibaba.com, etc.)
2. Strict Email Validation (rejecting garbage like swiper@7.0.5-bundle.min)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from discover import EXCLUDE_DOMAINS, JUNK_KEYWORD_RE, clean_domain
from email_outreach import is_valid_email

def test_marketplace_exclusions():
    print("\n" + "="*70)
    print("  TASK 1 & 2 VERIFICATION: B2B MARKETPLACE EXCLUSION")
    print("="*70)

    test_domains = [
        "made-in-china.com",
        "cn.made-in-china.com",
        "alibaba.com",
        "supplier.alibaba.com",
        "globalsources.com",
        "tradeindia.com",
        "thomasnet.com",
        "ec21.com",
        "indiamart.com"
    ]

    all_blocked = True
    for d in test_domains:
        root = clean_domain(d)
        is_in_exclude = root in EXCLUDE_DOMAINS or any(root.endswith('.' + x) or root == x for x in EXCLUDE_DOMAINS)
        is_in_regex = bool(JUNK_KEYWORD_RE.search(d))
        
        passed = is_in_exclude or is_in_regex
        status = "✅ BLOCKED" if passed else "❌ NOT BLOCKED"
        print(f"  Domain: {d:<25} -> ExcludeSet: {is_in_exclude!s:<5} JunkRegex: {is_in_regex!s:<5} {status}")
        if not passed:
            all_blocked = False

    return all_blocked

def test_email_validation():
    print("\n" + "="*70)
    print("  TASK 3 VERIFICATION: STRICT EMAIL VALIDATION")
    print("="*70)

    test_cases = [
        # Garbage / Asset Fragment Emails (MUST REJECT)
        ("swiper@7.0.5-bundle.min", False),
        ("vendor@1.2.3-chunk.min.js", False),
        ("image@2x.png", False),
        ("style@theme.min.css", False),
        ("font@fontawesome.woff2", False),
        ("jquery@3.6.0.min", False),
        ("bootstrap@4.5.0.bundle", False),
        ("node_modules@npm.cdn", False),

        # Real Valid Emails (MUST ACCEPT)
        ("contact@foodmachinery.com", True),
        ("sales@chinapack.cn", True),
        ("info@biofoodtech.de", True),
        ("support@agrifood.co.uk", True),
        ("export@foodprocessing.com", True),
    ]

    all_passed = True
    for em, expected in test_cases:
        actual = is_valid_email(em)
        ok = actual == expected
        status = "✅ PASS" if ok else "❌ FAIL"
        expected_str = "VALID" if expected else "REJECT"
        actual_str   = "VALID" if actual else "REJECT"
        print(f"  Email: {em:<30} -> Expected: {expected_str:<6} Got: {actual_str:<6} {status}")
        if not ok:
            all_passed = False

    return all_passed

if __name__ == "__main__":
    t1 = test_marketplace_exclusions()
    t2 = test_email_validation()

    print("\n" + "="*70)
    if t1 and t2:
        print("  ALL VERIFICATION TESTS PASSED 100% ✅")
    else:
        print("  SOME TESTS FAILED ❌")
    print("="*70 + "\n")
