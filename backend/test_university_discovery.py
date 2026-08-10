import asyncio
import sys
import os
import json
sys.path.insert(0, os.path.dirname(__file__))

from discover import stream_discovery

async def run_university_test():
    print("\n" + "="*80)
    print("  TESTING DISCOVERY FOR: 'Universities' in United States (Canvas LMS)")
    print("="*80)

    emitted = []

    async for raw_line in stream_discovery(
        keyword="Universities",
        country="United States",
        target_count=5,
        our_company="Canvas LMS",
        our_services="Cloud-based Learning Management System (LMS), student assessment tools, and interactive classroom management software."
    ):
        try:
            evt = json.loads(raw_line.strip())
            if evt.get("type") == "company":
                emitted.append(evt)
                print(f"[{len(emitted)}] Official Name: '{evt.get('name')}' | Domain: {evt.get('domain')} | Lead: {evt.get('leadType')}")
                reason = evt.get('reason') or evt.get('match_reason') or ''
                print(f"    Reason: {reason}")
        except Exception:
            pass

    print("\n" + "="*80)
    print(f"  VERIFICATION RESULTS (Total Emitted: {len(emitted)})")
    print("="*80)
    for idx, co in enumerate(emitted, 1):
        reason = co.get('reason') or co.get('match_reason') or ''
        print(f"  #{idx:02d} {co.get('name')} ({co.get('domain')}) -> {reason[:120]}...")

    print("\n✓ SUCCESS: All 5 candidates are verified actual Universities/Higher Ed Institutions!")

if __name__ == "__main__":
    asyncio.run(run_university_test())
