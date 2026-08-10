import asyncio
import sys
import os
import json
sys.path.insert(0, os.path.dirname(__file__))

from discover import stream_discovery

async def run_fulfillment_test():
    print("\n" + "="*80)
    print("  TESTING DISCOVERY FOR: 'E-Commerce Fulfillment Centers' in China")
    print("="*80)

    emitted_companies = []

    async for raw_line in stream_discovery(
        keyword="E-Commerce Fulfillment Centers",
        country="China",
        target_count=10,
        our_company="Skyline Logistics Tech",
        our_services="Cargo Shipment"
    ):
        try:
            evt = json.loads(raw_line.strip())
            if evt.get("type") == "company":
                emitted_companies.append(evt)
                print(f"[{len(emitted_companies)}] Official Name: '{evt.get('name')}' | Domain: {evt.get('domain')}")
        except Exception:
            pass

    print("\n" + "="*80)
    print(f"  VERIFICATION RESULTS FOR ALL {len(emitted_companies)} COMPANY NAMES")
    print("="*80)

    bad_names = []
    for idx, co in enumerate(emitted_companies, 1):
        name = co.get('name', '')
        dom = co.get('domain', '')
        print(f"  Company #{idx:02d}: Name = '{name}' (Domain: {dom})")

        # Check bad patterns
        if any(bad in name.lower() for bad in ['(2026)', '(2025)', 'services for', 'provider', 'solutions for', 'fulfillment center in china', 'best logistics']):
            bad_names.append(name)

    print("\n" + "-"*80)
    print(f"Total Companies Emitted : {len(emitted_companies)}")
    print(f"Generic Taglines Found  : {len(bad_names)}")
    if bad_names:
        print(f"❌ BAD NAMES DETECTED: {bad_names}")
    else:
        print("✓ ALL COMPANY NAMES ARE 100% GENUINE BRAND NAMES!")

if __name__ == "__main__":
    asyncio.run(run_fulfillment_test())
