"""
Test script to:
1. Fetch multi-page content and output full evaluation verdicts (ACCEPTED/REJECTED, leadType, confidence, reason)
   for the 5 requested candidates (hormelfoods.com, foodmachinerychina.com, tnasolutions.com, sftmachinery.com, byfoodmachinery.com).
2. Test LLM-level directory/marketplace detection on a marketplace candidate without relying on EXCLUDE_DOMAINS.
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from email_outreach import fetch_url_content_with_subpages
from discover import evaluate_lead_classification

TEST_CANDIDATES = [
    {"name": "Hormel Foods", "domain": "hormelfoods.com", "url": "https://www.hormelfoods.com"},
    {"name": "Food Machinery China", "domain": "foodmachinerychina.com", "url": "https://www.foodmachinerychina.com"},
    {"name": "TNA Solutions", "domain": "tnasolutions.com", "url": "https://www.tnasolutions.com"},
    {"name": "Swift Machinery", "domain": "sftmachinery.com", "url": "https://www.sftmachinery.com"},
    {"name": "BY Food Machinery", "domain": "byfoodmachinery.com", "url": "https://www.byfoodmachinery.com"},
]

UNLISTED_MARKETPLACE_CANDIDATE = {
    "name": "Global B2B Exporters Directory",
    "domain": "unlisted-suppliers-hub.org", # Not in EXCLUDE_DOMAINS
    "snippet": "Global B2B Exporters Directory — Browse 10,000+ verified machinery suppliers, post RFQs, and request quotes.",
    "scraped": (
        "Welcome to Global B2B Exporters Directory! We are an international supplier directory and RFQ platform "
        "connecting international buyers with verified food processing machinery manufacturers, ingredient suppliers, "
        "and packaging vendors across Asia and Europe. Browse categories: Food Machinery, Beverage Processing, "
        "Packaging Equipment, Cold Storage. Post your Request for Quotation (RFQ) today to receive quotes from 50+ vendors."
    )
}

async def run_verdict_tests():
    print("\n" + "="*75)
    print("  PART 1: FULL EVALUATION VERDICTS FOR THE 5 CANDIDATES (MULTI-PAGE EVIDENCE)")
    print("  Industry: Food Processing and Manufacturing")
    print("  Service : refrigerated container cargo shipping and freight forwarding")
    print("="*75)

    for c in TEST_CANDIDATES:
        url = c["url"]
        domain = c["domain"]
        name = c["name"]

        scraped_text, ev_label = await fetch_url_content_with_subpages(url, timeout=4.0)

        result = await evaluate_lead_classification(
            company_name=name,
            domain=domain,
            snippet=f"{name} operates in Food Processing and Manufacturing.",
            scraped_text=scraped_text,
            our_company="Global Cargo Logistics",
            our_services="refrigerated container cargo shipping and freight forwarding",
            industry="Food Processing and Manufacturing",
            target_country="China",
            evidence_source_label=ev_label
        )

        if not result:
            print(f"\n❌ {domain} -> Evaluation Timed Out")
            continue

        is_junk = result.get("is_junk", False)
        ind_match = result.get("industry_match", False)
        lead_type = result.get("lead_type", "")
        conf = result.get("confidence", 0)
        reason = result.get("reason", "")

        if not is_junk and ind_match:
            lead_tag = "NEEDS_SERVICE ✦" if lead_type == "NEEDS_SERVICE" else "HAS_SIMILAR_SERVICE ↑"
            print(f"\n✓ ACCEPTED [{lead_tag}] {domain}")
            print(f"   Official Name   : {name}")
            print(f"   Evidence Source : {ev_label}")
            print(f"   Confidence      : {conf}%")
            print(f"   Verdict Reason  : {reason}")
        else:
            status = "JUNK" if is_junk else "INDUSTRY MISMATCH"
            print(f"\n✗ REJECTED [{status}] {domain}")
            print(f"   Official Name   : {name}")
            print(f"   Evidence Source : {ev_label}")
            print(f"   Verdict Reason  : {reason}")

    print("\n" + "="*75)
    print("  PART 2: UNLISTED MARKETPLACE CANDIDATE (PURE LLM & CONTENT DETECTION)")
    print("="*75)

    c_unk = UNLISTED_MARKETPLACE_CANDIDATE
    res_unk = await evaluate_lead_classification(
        company_name=c_unk["name"],
        domain=c_unk["domain"],
        snippet=c_unk["snippet"],
        scraped_text=c_unk["scraped"],
        our_company="Global Cargo Logistics",
        our_services="refrigerated container cargo shipping and freight forwarding",
        industry="Food Processing and Manufacturing",
        target_country="China",
        evidence_source_label="homepage + /categories + /rfq"
    )

    if res_unk:
        is_j = res_unk.get("is_junk", False)
        reason_j = res_unk.get("reason", "")
        print(f"\nCandidate: {c_unk['domain']}")
        print(f"Is Junk Detected : {is_j}")
        print(f"LLM/Rule Reason  : {reason_j}")
        if is_j:
            print("✅ SUCCESS: Unlisted marketplace correctly caught and rejected as JUNK from content alone!")
        else:
            print("❌ FAIL: Marketplace was not detected as junk.")

if __name__ == "__main__":
    asyncio.run(run_verdict_tests())
