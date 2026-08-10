import os
import sys
import asyncio
import json
from dotenv import load_dotenv

env_local_path = os.path.join(os.path.dirname(__file__), "..", ".env.local")
if os.path.exists(env_local_path):
    load_dotenv(env_local_path)
load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))

import discover

async def main():
    print("======================================================================")
    print("               LIVE DISCOVERY & OLLAMA EVALUATION TEST                ")
    print("======================================================================\n")

    keyword = "Cargo shipment"
    target = 10
    country = "United States"

    our_company = "Skyline Logistics Tech"
    our_services = "AI Powered Fleet Routing and Logistics Software"
    target_customers = "Pharmaceutical Distributors, Healthcare Logistics, and Wholesale Medical Suppliers"

    print(f"Keyword          : '{keyword}'")
    print(f"Target Goal      : {target}")
    print(f"Ollama Base URL  : {os.getenv('OLLAMA_BASE_URL', 'http://100.91.220.98:11434/v1')}")
    print(f"Ollama Model     : {os.getenv('OLLAMA_MODEL', 'llama3:latest')}\n")

    received_companies = []

    async for line in discover.stream_discovery(
        keyword=keyword,
        start_page=1,
        target_count=target,
        max_pages=15,
        our_company=our_company,
        our_services=our_services,
        target_customers=target_customers,
        industry="Industrial Automation & Technology"
    ):
        data = json.loads(line.strip())
        if data.get("type") == "company":
            received_companies.append(data)
            print(f"\n[STREAM COMPANY EVENT #{len(received_companies)}]: {data.get('name')} ({data.get('domain')})")
            print(f"   Reason  : {data.get('matchReason')}")
            print(f"   Country : {data.get('country')}")

    print("\n======================================================================")
    print(f"TEST SUMMARY: Total Companies Collected = {len(received_companies)} / {target}")
    print("======================================================================")

if __name__ == '__main__':
    asyncio.run(main())
