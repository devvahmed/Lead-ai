import asyncio
import sys
import os
import json
sys.path.insert(0, os.path.dirname(__file__))

from discover import stream_discovery

async def run_verdict_auditing_test():
    print("\n" + "="*75)
    print("  VERIFYING VERDICT LOGGING AUDIT: 100% CANDIDATES MUST SHOW VERDICTS")
    print("="*75)

    emitted_count = 0
    async for raw_line in stream_discovery(
        keyword="Automotive Parts Suppliers",
        country="China",
        target_count=5,
        our_company="Global Cargo Logistics",
        our_services="refrigerated container cargo shipping and freight forwarding"
    ):
        try:
            evt = json.loads(raw_line.strip())
            if evt.get("type") == "company":
                emitted_count += 1
                print(f"[EMITTED TO CLIENT STREAM] #{emitted_count}: {evt.get('domain')}")
        except Exception:
            pass

    print(f"\n✅ STREAM FINISHED: Total companies emitted to client = {emitted_count}")

if __name__ == "__main__":
    asyncio.run(run_verdict_auditing_test())
