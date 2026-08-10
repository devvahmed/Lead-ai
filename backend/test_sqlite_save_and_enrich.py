import sys
import os
import json
sys.path.insert(0, os.path.dirname(__file__))

import database

def test_sqlite_pipeline():
    print("\n" + "="*80)
    print("  TESTING SQLITE CLIENT SAVE & ENRICHMENT PIPELINE")
    print("="*80)

    # 1. Initialize SQLite Database
    database.init_db()
    print(f"[OK] SQLite Database initialized cleanly using file: '{database.DB_FILE}'")

    # 2. Save a Client
    test_client = database.save_client(
        name="Stanford University",
        website="https://www.stanford.edu",
        industry="Universities",
        country="United States",
        trust_score=95,
        relevance_reason="Verified higher education institution suitable for Canvas LMS",
        status="Pending",
        logo_url="https://logo.clearbit.com/stanford.edu",
        company_id=1
    )
    print(f"\n[OK] Saved Client to SQLite (ID={test_client['id']}):")
    print(f"   Name    : {test_client['name']}")
    print(f"   Website : {test_client['website']}")
    print(f"   Status  : {test_client['status']}")

    # 3. Perform Stage 2 Deep Enrichment Update
    client_id = test_client['id']
    updated = database.update_client(
        client_id=client_id,
        company_id=1,
        email="admissions@stanford.edu",
        phone="+1 650-723-2300",
        phones="+1 650-723-2300, +1 650-723-2000",
        linkedin_company="https://linkedin.com/school/stanford-university",
        contact_source_url="https://www.stanford.edu/about/contact",
        contact_source_page="Contact Page",
        contact_source_label="Direct Admissions Contact",
        status="Qualified"
    )
    print(f"\n[OK] Updated Client with Stage 2 Enriched Contacts:")
    print(f"   Email    : {updated['email']}")
    print(f"   Phone    : {updated['phone']}")
    print(f"   LinkedIn : {updated['linkedin_company']}")
    print(f"   Source   : {updated['contact_source_url']}")
    print(f"   Status   : {updated['status']}")

    # 4. Fetch All Clients for Company ID = 1
    all_clients = database.get_clients(company_id=1)
    print(f"\n[OK] Query All Clients for company_id=1 (Total: {len(all_clients)}):")
    for idx, c in enumerate(all_clients, 1):
        print(f"   #{idx:02d} ID={c['id']} | {c['name']} ({c['website']}) | Email: {c['email']} | Phone: {c['phone']}")

    assert len(all_clients) > 0, "No clients returned from SQLite"
    assert updated['email'] == "admissions@stanford.edu", "Email update failed"
    print("\n" + "="*80)
    print("  ALL SQLITE DATABASE TESTS PASSED SUCCESSFULLY!")
    print("="*80)

if __name__ == "__main__":
    test_sqlite_pipeline()
