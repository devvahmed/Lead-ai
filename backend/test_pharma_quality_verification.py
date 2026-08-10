import asyncio
import sys
import os
import json
sys.path.insert(0, os.path.dirname(__file__))

from discover import stream_discovery

async def run_pharma_test():
    print("\n" + "="*80)
    print("  TESTING DISCOVERY FOR: 'Pharmaceutical Manufacturers' in United States")
    print("="*80)

    emitted_companies = []
    rejected_count = 0
    drugs_com_status = "NOT FOUND IN SEARCH RESULTS"

    async for raw_line in stream_discovery(
        keyword="Pharmaceutical Manufacturers",
        country="United States",
        target_count=10,
        our_company="Global Cargo Logistics",
        our_services="refrigerated container cargo shipping and freight forwarding"
    ):
        try:
            evt = json.loads(raw_line.strip())
            if evt.get("type") == "company":
                emitted_companies.append(evt)
                print(f"\n[CARD #{len(emitted_companies)}] ----------------------------------------")
                print(f"  Official Name : {evt.get('name')}")
                print(f"  Domain        : {evt.get('domain')}")
                print(f"  Lead Type     : {evt.get('leadType')}")
                print(f"  Description   : {evt.get('snippet')}")
                print(f"  Match Reason  : {evt.get('matchReason')}")

                if "drugs.com" in evt.get("domain", ""):
                    drugs_com_status = "❌ ERROR: drugs.com WAS EMITTED AS A LEAD!"

        except Exception:
            pass

    print("\n" + "="*80)
    print(f"  VERIFICATION RESULTS (Total Emitted: {len(emitted_companies)})")
    print("="*80)

    generic_names = [c for c in emitted_companies if c.get('name', '').lower() in ('united states', 'us', 'us locations', 'locations', 'overview')]
    bio_descriptions = [c for c in emitted_companies if any(word in c.get('snippet', '') for word in ['Senior Vice President', 'Mohit Manrao', 'CEO', 'Director'])]

    print(f"  1. drugs.com status                  : {drugs_com_status}")
    print(f"  2. Generic names emitted             : {len(generic_names)} (Must be 0)")
    if generic_names:
        print(f"     ❌ Generic names found: {[c.get('name') for c in generic_names]}")
    else:
        print("     ✓ All company names are genuine brand names!")

    print(f"  3. Executive bios in card description: {len(bio_descriptions)} (Must be 0)")
    if bio_descriptions:
        print(f"     ❌ Person bio descriptions found: {[c.get('snippet')[:60] for c in bio_descriptions]}")
    else:
        print("     ✓ All card descriptions describe company business!")

if __name__ == "__main__":
    asyncio.run(run_pharma_test())
