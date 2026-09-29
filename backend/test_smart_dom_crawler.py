"""
Unit Test Suite for Context-Aware Smart DOM Crawler & AI Navigation Engine (Step 6 / Subgraph S2).

Validates:
1. Base Domain & Subdomain Extraction (e.g. ahmed.com, shop.ahmed.com).
2. Multi-Engine Link Harvesting (<nav>, <header>, <footer>, <body>, dropdowns).
3. Asset & Disallowed Domain Filtering.
4. AI-Powered Optimal Page Selection (Company Overview & Decision Makers).
5. On-Site Executive Names & Raw Emails Extraction.
6. Automatic Pattern Library Registration upon email discovery.
7. Strict Zero-Hallucination Policy (0% fabrication if website has no contacts).
"""

import asyncio
import os
import sys

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(__file__))

from smart_dom_crawler import (
    get_base_domain,
    is_same_domain_or_subdomain,
    normalize_and_validate_url,
    extract_all_site_nav_links,
    ai_select_optimal_subpages,
    extract_onsite_contacts_and_decision_makers,
    crawl_smart_dom_target,
    get_cached_crawl_res
)
from database import get_domain_pattern


def check(desc: str, cond: bool):
    if cond:
        print(f"  PASS  {desc}")
    else:
        print(f"  FAIL  {desc}")
        sys.exit(1)


async def run_tests():
    print("\n" + "=" * 54)
    print("  Smart DOM Crawler (S2) — Full Unit Test Suite")
    print("=" * 54)

    # ─────────────────────────────────────────────────────────
    # PART 1: Domain & Subdomain Validation
    # ─────────────────────────────────────────────────────────
    print("\nPART 1 — Domain & Subdomain Validation:")
    check("Root domain extraction", get_base_domain("https://ahmed.com/about") == "ahmed.com")
    check("Subdomain extraction", get_base_domain("https://shop.ahmed.com/products") == "shop.ahmed.com")
    check("WWW strip", get_base_domain("https://www.ahmed.bhj.com") == "ahmed.bhj.com")
    check("Port strip", get_base_domain("http://ahmed.com:8080/test") == "ahmed.com")
    check("Same domain match", is_same_domain_or_subdomain("https://ahmed.com/team", "https://ahmed.com"))
    check("Subdomain match", is_same_domain_or_subdomain("https://app.ahmed.com/login", "https://ahmed.com"))
    check("Different domain rejected", not is_same_domain_or_subdomain("https://google.com", "https://ahmed.com"))

    # ─────────────────────────────────────────────────────────
    # PART 2: DOM Navigation & Link Harvesting
    # ─────────────────────────────────────────────────────────
    print("\nPART 2 — DOM Navigation & Link Harvesting:")
    mock_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Ahmed Logistics LLC</title></head>
    <body>
        <header>
            <div class="logo"><a href="/">Ahmed Logistics</a></div>
            <nav class="main-navbar">
                <a href="/about-us">About Company</a>
                <a href="/leadership">Executive Team</a>
                <a href="/services/freight">Freight Solutions</a>
                <a href="/contact">Contact Us</a>
                <a href="/downloads/brochure.pdf">Download Brochure</a>
                <a href="https://linkedin.com/company/ahmed">LinkedIn</a>
            </nav>
        </header>
        <main>
            <h1>Global Freight Leaders</h1>
            <p>Providing seamless freight operations worldwide.</p>
            <a href="/case-studies">View Case Studies</a>
        </main>
        <footer>
            <div class="footer-links">
                <a href="/careers">Join Our Team</a>
                <a href="/privacy-policy">Privacy</a>
            </div>
        </footer>
    </body>
    </html>
    """
    dom_result = extract_all_site_nav_links(mock_html, "https://ahmed.com")
    all_links = dom_result.get("all_links", [])
    nav_links = dom_result.get("nav_links", [])
    footer_links = dom_result.get("footer_links", [])

    check("Harvested internal links found", len(all_links) >= 5)
    check("Nav links properly segmented", any("/about-us" in l["url"] for l in nav_links))
    check("Leadership link captured in nav", any("/leadership" in l["url"] for l in nav_links))
    check("Static PDF asset filtered out", not any("brochure.pdf" in l["url"] for l in all_links))
    check("External LinkedIn filtered out", not any("linkedin.com" in l["url"] for l in all_links))
    check("Footer link properly segmented", any("/privacy-policy" in l["url"] for l in footer_links))

    # ─────────────────────────────────────────────────────────
    # PART 3: AI / Smart Heuristic Page Selection
    # ─────────────────────────────────────────────────────────
    print("\nPART 3 — AI / Smart Heuristic Page Selection:")
    selected_pages = await ai_select_optimal_subpages(
        domain="ahmed.com",
        candidate_links=all_links,
        max_pages=4
    )
    check("Selected 2 to 3 optimal subpages", 1 <= len(selected_pages) <= 3)
    check("Prioritized overview or leadership page", any("about" in p or "leadership" in p or "contact" in p for p in selected_pages))

    # ─────────────────────────────────────────────────────────
    # PART 4: On-Site Contact & Decision-Maker Extraction (With Pattern Learning)
    # ─────────────────────────────────────────────────────────
    print("\nPART 4 — On-Site Decision Maker & Email Extraction:")
    mock_pages = {
        "homepage": {
            "url": "https://ahmed.com",
            "text": "Welcome to Ahmed Logistics. Call our office at +1 (555) 234-5678 or write to info@ahmed.com."
        },
        "leadership": {
            "url": "https://ahmed.com/leadership",
            "text": "Leadership Directory:\nTariq Ahmed, Founder & Chief Executive Officer\nDirect Email: tariq.ahmed@ahmed.com\n\nSarah Jenkins, Vice President of Operations\nDirect Email: sarah.jenkins@ahmed.com"
        }
    }
    extracted = extract_onsite_contacts_and_decision_makers(mock_pages, "ahmed.com")
    dms = extracted.get("decision_makers", [])
    emails = extracted.get("emails", [])
    phones = extracted.get("phones", [])

    check("Extracted on-site emails", len(emails) >= 2)
    check("Found info@ahmed.com", "info@ahmed.com" in emails)
    check("Extracted on-site phone", len(phones) >= 1)
    check("Discovered real executive decision makers", len(dms) >= 2)
    ceo = next((d for d in dms if "Tariq Ahmed" in d["name"]), None)
    check("CEO Tariq Ahmed identified", ceo is not None)
    check("CEO matched role Founder & Chief Executive Officer", "Chief Executive Officer" in ceo.get("role", "") or "Founder" in ceo.get("role", ""))
    check("CEO direct email bound", ceo.get("email") == "tariq.ahmed@ahmed.com")
    check("CEO marked strictly verified", ceo.get("strictly_verified") is True)

    # Verify Pattern Library received the pattern
    pat_info = get_domain_pattern("ahmed.com")
    check("Pattern Library saved domain pattern", pat_info is not None)
    check("Pattern identified as first.last", pat_info.get("pattern") == "first.last")

    # ─────────────────────────────────────────────────────────
    # PART 5: Strict Zero-Hallucination Policy (0% Fake Data)
    # ─────────────────────────────────────────────────────────
    print("\nPART 5 — Strict Zero-Hallucination Policy:")
    mock_empty_pages = {
        "homepage": {
            "url": "https://mystery-firm.com",
            "text": "We provide premium enterprise consulting. All rights reserved 2026."
        },
        "about": {
            "url": "https://mystery-firm.com/about",
            "text": "Our mission is to deliver excellence in cloud consulting worldwide."
        }
    }
    empty_extracted = extract_onsite_contacts_and_decision_makers(mock_empty_pages, "mystery-firm.com")
    check("Zero emails fabricated (empty array)", len(empty_extracted.get("emails", [])) == 0)
    check("Zero decision-makers fabricated (empty array)", len(empty_extracted.get("decision_makers", [])) == 0)
    check("Zero phones fabricated (empty array)", len(empty_extracted.get("phones", [])) == 0)

    # ─────────────────────────────────────────────────────────
    # PART 6: Full Multi-Page Crawl Execution & Cache
    # ─────────────────────────────────────────────────────────
    print("\nPART 6 — Full Crawl Execution & Cache:")
    crawl_output = await crawl_smart_dom_target(
        domain="ahmed.com",
        homepage_url="https://ahmed.com",
        homepage_html=mock_html,
        max_pages=3
    )
    check("Crawl combined text non-empty", len(crawl_output.get("combined_text", "")) > 50)
    check("DOM links included in crawl result", len(crawl_output.get("dom_links", {}).get("all_links", [])) >= 5)

    cached = get_cached_crawl_res("ahmed.com")
    check("Domain crawl result successfully cached", cached is not None)
    check("Cached result contains dom_links", "dom_links" in cached)

    print("\n" + "=" * 54)
    print("  Results: All Subgraph S2 Smart DOM Crawler Tests Passed!")
    print("=" * 54 + "\n")


if __name__ == "__main__":
    asyncio.run(run_tests())
