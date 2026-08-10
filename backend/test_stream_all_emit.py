import asyncio
import sys
import os
import json
sys.path.insert(0, os.path.dirname(__file__))

from discover import stream_discovery

async def run_all_emit_test():
    print("\n" + "="*70)
    print("  VERIFYING STREAMING PIPELINE: ALL 10 EMIT EVENTS LEAVE BACKEND")
    print("="*70)

    emitted_companies = []
    async for raw_line in stream_discovery(
        keyword="Food Processing and Manufacturing",
        country="China",
        target_count=10,
        our_company="Global Cargo Logistics",
        our_services="refrigerated container cargo shipping and freight forwarding"
    ):
        try:
            evt = json.loads(raw_line.strip())
            if evt.get("type") == "company":
                emitted_companies.append(evt)
                print(f"[TEST CLIENT RECV] #{len(emitted_companies)}: {evt.get('domain')} ({evt.get('name')})")
        except Exception as e:
            pass

    print(f"\n✅ TOTAL EMITTED COMPANIES RECEIVED OVER STREAM: {len(emitted_companies)}")
    if len(emitted_companies) >= 10:
        print("🎉 SUCCESS! Streaming loop yields ALL collected companies to client stream without truncation!")
    else:
        print(f"❌ FAIL: Expected 10 emitted companies, received {len(emitted_companies)}")

if __name__ == "__main__":
    asyncio.run(run_all_emit_test())
