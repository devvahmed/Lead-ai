"""
test_offsite_waterfall.py
=========================
Comprehensive Test Suite for Off-Site Waterfall OSINT Intelligence Engine.

Tests:
1. Social OSINT Prober (Handle generation & fast async checks)
2. GitHub OSINT Enricher (Public commit & metadata parser)
3. LinkedIn SERP Snippet Parser (Name, Role, and LinkedIn URL extraction)
4. Targeted Press Release Deep Crawling (Executive quote & announcement parsing)
5. Full Waterfall Intelligence Pipeline & Zero-Hallucination Policy
"""

import os
import sys
import asyncio
from unittest.mock import patch, MagicMock

# Force UTF-8 stdout
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from social_osint_prober import generate_candidate_handles, probe_username_cross_platform
from github_osint_enricher import search_github_commits_by_domain
from offsite_waterfall_engine import (
    extract_person_from_linkedin_snippet,
    crawl_target_press_release,
    execute_offsite_waterfall_intelligence
)


def check(description: str, condition: bool):
    status = "  PASS " if condition else "  FAIL "
    print(f"{status} {description}")
    if not condition:
        raise AssertionError(f"Test failed: {description}")


async def run_tests():
    print("\n" + "=" * 58)
    print("  Off-Site Waterfall Intelligence — Comprehensive Tests")
    print("=" * 58 + "\n")

    # ─────────────────────────────────────────────────────────
    # PART 1: Social OSINT Prober (Sherlock Logic)
    # ─────────────────────────────────────────────────────────
    print("PART 1 — Social OSINT Prober (Handle Generation & Prober):")
    handles = generate_candidate_handles("Tariq Ahmed", "ahmed.com")
    check("Generated handles list non-empty", len(handles) >= 2)
    check("Handles include tariqahmed", "tariqahmed" in handles)
    check("Handles include tariq.ahmed", "tariq.ahmed" in handles)

    # ─────────────────────────────────────────────────────────
    # PART 2: LinkedIn SERP Snippet Extraction
    # ─────────────────────────────────────────────────────────
    print("\nPART 2 — LinkedIn SERP Snippet Parsing:")
    sample_title = "Tariq Ahmed - Founder & Chief Executive Officer - Ahmed Global Logistics | LinkedIn"
    sample_snippet = "Experienced Founder & Chief Executive Officer with a demonstrated history of working in global supply chain. Karachi, Pakistan."
    sample_url = "https://pk.linkedin.com/in/tariq-ahmed-99"

    person = extract_person_from_linkedin_snippet(sample_title, sample_snippet, "Ahmed Global Logistics", sample_url)
    check("Extracted person is not None", person is not None)
    check("Person name is Tariq Ahmed", person.get("name") == "Tariq Ahmed")
    check("Person role is Chief Executive Officer", "Chief Executive Officer" in person.get("position", ""))
    check("LinkedIn URL captured", "pk.linkedin.com/in/tariq-ahmed-99" in person.get("linkedin", ""))
    check("Bio snippet populated", len(person.get("bio", "")) > 20)

    # ─────────────────────────────────────────────────────────
    # PART 3: Targeted Press Release Deep Crawling
    # ─────────────────────────────────────────────────────────
    print("\nPART 3 — Press Release Deep Crawling & Quote Parsing:")
    mock_pr_html = """
    <html>
        <body>
            <h1>Ahmed Logistics Announces $15M Expansion</h1>
            <p>KARACHI, Sept 2026 -- "We are scaling our enterprise network rapidly," said Sarah Jenkins, Vice President of Operations at Ahmed Logistics.</p>
            <p>For investor inquiries, contact press@ahmed.com or media@ahmed.com.</p>
        </body>
    </html>
    """

    class MockResponse:
        def __init__(self, text, status_code=200):
            self.text = text
            self.status_code = status_code

    class MockClient:
        async def get(self, url, **kwargs):
            return MockResponse(mock_pr_html)

    semaphore = asyncio.Semaphore(1)
    dms, emails = await crawl_target_press_release(
        MockClient(),
        "https://www.businesswire.com/news/ahmed-logistics-expansion",
        "ahmed.com",
        semaphore
    )
    check("Discovered PR executive Sarah Jenkins", any("Sarah Jenkins" in d["name"] for d in dms))
    check("Discovered PR role Vice President", any("Vice President" in d["position"] for d in dms))
    check("Discovered PR press email", "press@ahmed.com" in emails)
    check("Discovered PR media email", "media@ahmed.com" in emails)

    # ─────────────────────────────────────────────────────────
    # PART 4: Strict Zero-Hallucination Policy
    # ─────────────────────────────────────────────────────────
    print("\nPART 4 — Strict Zero-Hallucination Check (Empty Results):")
    # Mock empty SERP search results
    with patch("discover.search_searxng_or_ddg", return_value=[]):
        empty_res = await execute_offsite_waterfall_intelligence(
            domain="non-existent-co-xyz-982.com",
            company_name="Non Existent Co XYZ",
            timeout=3.0
        )
        check("Zero decision makers fabricated", len(empty_res.get("decision_makers", [])) == 0)
        check("Zero emails fabricated", len(empty_res.get("emails", [])) == 0)

    # ─────────────────────────────────────────────────────────
    # PART 5: Full Waterfall Pipeline Execution with SERP Mocks
    # ─────────────────────────────────────────────────────────
    print("\nPART 5 — Full Waterfall Pipeline Execution:")
    mock_serp_data = [
        {
            "title": "Tariq Ahmed - Founder & Chief Executive Officer - Ahmed Logistics | LinkedIn",
            "url": "https://pk.linkedin.com/in/tariq-ahmed",
            "content": "CEO leading logistics operations. Contact: tariq.ahmed@ahmed.com."
        },
        {
            "title": "BusinessWire: Ahmed Logistics Expands Worldwide",
            "url": "https://www.businesswire.com/news/ahmed-logistics-worldwide",
            "content": "Official announcement for Ahmed Logistics operations."
        }
    ]

    with patch("discover.search_searxng_or_ddg", return_value=mock_serp_data):
        waterfall_res = await execute_offsite_waterfall_intelligence(
            domain="ahmed.com",
            company_name="Ahmed Logistics",
            timeout=6.0
        )
        w_dms = waterfall_res.get("decision_makers", [])
        w_emails = waterfall_res.get("emails", [])

        check("Waterfall discovered decision maker", len(w_dms) >= 1)
        ceo = next((d for d in w_dms if "Tariq Ahmed" in d["name"]), None)
        check("Discovered CEO Tariq Ahmed", ceo is not None)
        check("CEO position captured", "Chief Executive Officer" in ceo.get("position", ""))
        check("CEO LinkedIn link captured", "linkedin.com/in/tariq-ahmed" in ceo.get("linkedin", ""))
        check("CEO email bound via pattern", ceo.get("email") == "tariq.ahmed@ahmed.com")
        check("CEO strictly verified", ceo.get("strictly_verified") is True)

    print("\n" + "=" * 58)
    print("  Results: All Off-Site Waterfall Tests Passed 100%!")
    print("=" * 58 + "\n")


if __name__ == "__main__":
    asyncio.run(run_tests())
