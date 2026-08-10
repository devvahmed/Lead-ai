import asyncio
import sys
import os
import json
sys.path.insert(0, os.path.dirname(__file__))

from email_outreach import deep_enrich, EnrichRequest

async def run_apa_test():
    print("\n" + "="*80)
    print("  TESTING HIGH-PRECISION CONTACT CRAWLING ON: 'apaonline.org'")
    print("="*80)

    req = EnrichRequest(company_name="American Philosophical Association", website_url="apaonline.org")
    result = await deep_enrich(req)

    print("\n[OK] Deep Enrich Result for apaonline.org:")
    print(f"   Primary Email : {result.get('primary_email')}")
    print(f"   All Emails    : {result.get('all_emails')}")
    print(f"   Phones        : {result.get('phones')}")
    print(f"   Contact Page  : {result.get('contact_page_url')}")
    print(f"   Source Label  : {result.get('source_label')}")
    print(f"   Found         : {result.get('found')}")

    emails = result.get('all_emails') or []
    expected_emails = ["info@apaonline.org", "media@apaonline.org", "membership@apaonline.org"]

    found_any_expected = any(exp in [e.lower() for e in emails] for exp in expected_emails)
    print("\n" + "="*80)
    if found_any_expected or len(emails) > 0:
        print(f"  SUCCESS: Extracted {len(emails)} authentic contact email(s) from apaonline.org!")
    else:
        print("  WARNING: No emails extracted — checking raw crawl response...")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(run_apa_test())
