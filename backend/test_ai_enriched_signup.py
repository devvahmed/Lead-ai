import asyncio
import sys
import os
import time
sys.path.insert(0, os.path.dirname(__file__))

from database import init_db
from auth_models import init_auth_db, SessionLocal, Company
from auth_routes import enrich_company_profile

async def run_test_signup():
    print("\n" + "="*80)
    print("  TESTING AI-ENRICHED COMPANY PROFILE GENERATION AT SIGNUP")
    print("="*80)

    # Initialize DB schema including migration columns
    init_db()
    init_auth_db()

    test_company_name = "Flexport Supply Chain Services"
    test_website = "https://www.flexport.com"
    test_industry = "Global Freight & Supply Chain"
    test_services = "Ocean freight, air freight, customs brokerage, supply chain software"
    test_target_customers = "Global brands, e-commerce retailers, international importers"
    test_overview = "Modern freight forwarder and logistics platform helping businesses manage global trade."

    print(f"\n[Signup Form Submitted]")
    print(f"  Company Name     : {test_company_name}")
    print(f"  Website URL      : {test_website}")
    print(f"  Industry Sector  : {test_industry}")
    print(f"  Services/Products: {test_services}")
    print(f"  Target Customers : {test_target_customers}")
    print("\n[Triggering Website Crawl & Ollama Synthesis...]")

    start_t = time.time()
    ai_profile = await enrich_company_profile(
        company_name=test_company_name,
        website=test_website,
        services=test_services,
        target_customers=test_target_customers,
        description=test_overview,
        industry=test_industry
    )
    elapsed = time.time() - start_t

    print(f"\n✓ AI Profile Synthesis Completed in {elapsed:.2f}s!")
    print("="*80)
    print("  STORED AI_ENRICHED_PROFILE RESULT")
    print("="*80)
    print(ai_profile)
    print("="*80)

    # Verify DB persistence
    db = SessionLocal()
    try:
        test_email = f"test-{int(time.time())}@flexport.com"
        new_co = Company(
            name=test_company_name,
            email=test_email,
            hashed_password="hashedpassword123",
            website=test_website,
            industry=test_industry,
            services=test_services,
            target_customers=test_target_customers,
            description=test_overview,
            ai_enriched_profile=ai_profile
        )
        db.add(new_co)
        db.commit()
        db.refresh(new_co)

        fetched = db.query(Company).filter(Company.id == new_co.id).first()
        print(f"\n[Database Persistence Verification]")
        print(f"  Stored Company ID : {fetched.id}")
        print(f"  Stored Email      : {fetched.email}")
        print(f"  Has Enriched Profile : {bool(fetched.ai_enriched_profile)}")
        print(f"  Enriched Profile Length : {len(fetched.ai_enriched_profile or '')} chars")
        print("\n✓ SUCCESS: AI-Enriched Company Profile successfully stored in SQLite DB!")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_test_signup())
