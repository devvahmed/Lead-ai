import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from discover import stream_discovery

async def main():
    print("Testing stream_discovery for 'E-Commerce Fulfillment Centers' in United States, New York...")
    count = 0
    async for line in stream_discovery(
        keyword="E-Commerce Fulfillment Centers",
        country="United States",
        city="New York",
        target_count=10,
        our_company="Global Cargo Logistics",
        our_services="cargo shipment and freight forwarding"
    ):
        print(f"[YIELDED LINE #{count+1}]: {line.strip()[:120]}...")
        count += 1

if __name__ == "__main__":
    asyncio.run(main())
