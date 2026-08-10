"""
Test the three-stage lead classification pipeline.
Run from: backend/ directory using the venv Python.

Tests:
  A) A genuine pharmaceutical manufacturer         -> NEEDS_SERVICE  (should PASS)
  B) A pharma company with in-house logistics      -> HAS_SIMILAR_SERVICE (should PASS)
  C) A listicle / ranking article                  -> JUNK (should be REJECTED)
  D) A supplier directory / marketplace page       -> JUNK (should be REJECTED)
  E) A completely unrelated company (software SaaS) -> INDUSTRY MISMATCH (should be REJECTED)
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from discover import evaluate_lead_classification

TEST_INDUSTRY = "Pharmaceutical Manufacturers"
TEST_SERVICE  = "cargo shipment and freight forwarding logistics"
TEST_COMPANY  = "WTechX Logistics"

CANDIDATES = [
    {
        "label": "A — Genuine pharma manufacturer (no logistics mention)",
        "company_name": "BioSynth Pharma",
        "domain": "biosynthpharma.com",
        "snippet": "BioSynth Pharma is a leading manufacturer of active pharmaceutical ingredients (APIs) and finished dosage forms.",
        "scraped": (
            "BioSynth Pharma Inc. manufactures and supplies active pharmaceutical ingredients (APIs), "
            "intermediates, and finished dosage forms to hospitals, pharmacies, and healthcare systems worldwide. "
            "Our cGMP-compliant facilities produce over 200 API molecules across cardiovascular, oncology, and "
            "anti-infective therapeutic areas. We supply to regulated markets in the US, EU, and Japan."
        ),
        "expect": "NEEDS_SERVICE",
    },
    {
        "label": "B — Pharma distributor with own fleet / logistics arm",
        "company_name": "MedDistri Group",
        "domain": "meddistri.com",
        "snippet": "MedDistri Group distributes pharmaceutical products across Southeast Asia using our own cold-chain fleet.",
        "scraped": (
            "MedDistri Group is a full-service pharmaceutical distribution company operating in Southeast Asia. "
            "We manage end-to-end cold-chain logistics through our own fleet of 150 temperature-controlled trucks "
            "and 8 strategically located warehouses. Our in-house logistics division ensures 99.7% on-time delivery "
            "to hospitals, clinics, and retail pharmacies across 6 countries."
        ),
        "expect": "HAS_SIMILAR_SERVICE",
    },
    {
        "label": "C — Listicle / ranking article (junk)",
        "company_name": "Top 10 Pharma Companies 2024",
        "domain": "pharmainsights.net",
        "snippet": "Top 10 pharmaceutical companies ranked by revenue in 2024. See which firms dominate the global drug market.",
        "scraped": (
            "Top 10 Pharmaceutical Companies 2024\n"
            "1. Pfizer Inc — Revenue $58.5B\n"
            "2. Johnson & Johnson — Revenue $53.7B\n"
            "3. Roche — Revenue $49.1B\n"
            "This list ranks the world's largest pharma companies by total 2024 revenue..."
        ),
        "expect": "JUNK",
    },
    {
        "label": "D — Supplier marketplace / aggregator (junk)",
        "company_name": "PharmaSources Directory",
        "domain": "pharmasources.com",
        "snippet": "Find verified pharmaceutical manufacturers and API suppliers. Browse 5000+ suppliers across 80 countries.",
        "scraped": (
            "PharmaSources.com is the leading B2B marketplace connecting pharmaceutical buyers with verified "
            "API manufacturers, excipient suppliers, and contract manufacturers worldwide. "
            "Browse 5,000+ verified suppliers. Post an RFQ and receive quotes from multiple vendors. "
            "Featured categories: APIs, Excipients, Contract Manufacturing, Drug Delivery Systems."
        ),
        "expect": "JUNK",
    },
    {
        "label": "E — Unrelated industry: SaaS CRM software",
        "company_name": "SalesDrive CRM",
        "domain": "salesdrive.io",
        "snippet": "SalesDrive CRM — the all-in-one sales pipeline software for high-growth startups.",
        "scraped": (
            "SalesDrive CRM is a cloud-based customer relationship management platform designed for B2B SaaS "
            "companies and high-growth startups. Features include AI-powered lead scoring, email sequences, "
            "deal pipeline management, and Slack/Zapier integrations. Trusted by 3,000+ sales teams."
        ),
        "expect": "INDUSTRY_MISMATCH",
    },
]

async def run_tests():
    print("\n" + "="*70)
    print("  THREE-STAGE LEAD CLASSIFICATION — PIPELINE TEST")
    print(f"  Industry : {TEST_INDUSTRY}")
    print(f"  Service  : {TEST_SERVICE}")
    print("="*70 + "\n")

    passed = 0
    failed = 0

    for c in CANDIDATES:
        print(f"\n{'─'*60}")
        print(f"TEST: {c['label']}")
        print(f"  Domain  : {c['domain']}")

        result = await evaluate_lead_classification(
            company_name=c["company_name"],
            domain=c["domain"],
            snippet=c["snippet"],
            scraped_text=c["scraped"],
            our_company=TEST_COMPANY,
            our_services=TEST_SERVICE,
            industry=TEST_INDUSTRY,
            target_country="",  # global
        )

        if not result:
            print("  ⚠️  No result returned (Ollama offline?)")
            failed += 1
            continue

        is_junk       = result.get("is_junk", False)
        ind_match     = result.get("industry_match", False)
        lead_type     = result.get("lead_type", "")
        confidence    = result.get("confidence", 0)
        reason        = result.get("reason", "")

        # Determine actual outcome
        if is_junk:
            actual = "JUNK"
        elif not ind_match:
            actual = "INDUSTRY_MISMATCH"
        elif lead_type == "NEEDS_SERVICE":
            actual = "NEEDS_SERVICE"
        elif lead_type == "HAS_SIMILAR_SERVICE":
            actual = "HAS_SIMILAR_SERVICE"
        else:
            actual = f"UNKNOWN (lead_type='{lead_type}')"

        ok = actual == c["expect"]
        status = "✅ PASS" if ok else "❌ FAIL"
        if ok:
            passed += 1
        else:
            failed += 1

        print(f"  Expected : {c['expect']}")
        print(f"  Got      : {actual}  (confidence={confidence})")
        print(f"  Reason   : {reason[:200]}")
        print(f"  {status}")

    print(f"\n{'='*60}")
    print(f"  RESULTS: {passed}/{len(CANDIDATES)} passed, {failed} failed")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(run_tests())
