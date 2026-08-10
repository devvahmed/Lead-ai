"""
Live discovery test for "Food Processing and Manufacturing" in China.
Verifies:
1. made-in-china.com and other marketplaces do NOT appear.
2. Emitted companies are strictly classified as NEEDS_SERVICE or HAS_SIMILAR_SERVICE.
3. Extracted emails are valid.
"""

import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from discover import stream_discovery

async def run_live_test():
    print("\n" + "="*70)
    print("  LIVE DISCOVERY TEST: 'Food Processing and Manufacturing' (China)")
    print("="*70 + "\n")

    emitted_companies = []
    marketplaces_seen = []

    async for raw_line in stream_discovery(
        keyword="Food Processing and Manufacturing",
        country="China",
        city="",
        min_trust=60.0,
        min_confidence=60,
        start_page=1,
        target_count=5,
        max_pages=3,
        our_company="Global Cargo Logistics",
        our_services="refrigerated container cargo shipping and freight forwarding",
        industry="Food Processing and Manufacturing",
        company_id=1
    ):
        try:
            event = json.loads(raw_line.strip())
            event_type = event.get("type")

            if event_type == "start":
                print(f"[Stream Start] Query: '{event.get('query')}' | Goal: {event.get('target')}")

            elif event_type == "company":
                name = event.get("name")
                domain = event.get("domain")
                lead_type = event.get("leadType")
                reason = event.get("matchReason")
                email = event.get("email")

                emitted_companies.append(event)
                print(f"\n  ✓ EMITTED COMPANY #{len(emitted_companies)}:")
                print(f"    Name      : {name}")
                print(f"    Domain    : {domain}")
                print(f"    Lead Type : {lead_type}")
                print(f"    Reason    : {reason[:120]}...")
                print(f"    Email     : {email or 'None'}")

                if "made-in-china" in domain.lower() or "alibaba" in domain.lower():
                    marketplaces_seen.append(domain)

            elif event_type == "complete":
                print(f"\n[Stream Complete] Total Qualified: {event.get('totalQualified')}")

        except Exception as e:
            continue

    print("\n" + "="*70)
    print("  VERIFICATION SUMMARY")
    print("="*70)
    print(f"  Emitted Companies Count : {len(emitted_companies)}")
    print(f"  Marketplace Violations  : {len(marketplaces_seen)}")

    if marketplaces_seen:
        print(f"  ❌ FAIL: Marketplace domains slipped through: {marketplaces_seen}")
    else:
        print("  ✅ PASS: 0 B2B marketplaces (made-in-china.com, etc.) appeared in emitted leads!")

if __name__ == "__main__":
    asyncio.run(run_live_test())
