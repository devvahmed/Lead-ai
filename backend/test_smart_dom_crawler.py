"""
Unit Test Suite for Context-Aware Smart DOM Crawler & AI Navigation Engine (Step 6 / Subgraph S2).

Validates:
1. Base Domain & Subdomain Extraction (e.g. ahmed.com, shop.ahmed.com).
2. Multi-Engine Link Harvesting (<nav>, <header>, <footer>, <body>, dropdowns).
3. PDF Document Inclusion (internal PDFs cracked; image/media assets filtered).
4. Dead Generic Filtering (info@, support@, care@ filtered out) vs Commercial Inboxes (sales@, investor@ kept).
5. AI-Powered Optimal Page Selection (Company Overview & Decision Makers).
6. On-Site Executive Names & Raw Emails Extraction.
7. Automatic Pattern Library Registration upon email discovery.
8. Strict Zero-Hallucination Policy (0% fabrication if website has no contacts).
"""

import asyncio
import io
import os
import sys

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(__file__))

from smart_dom_crawler import (
    get_base_domain,
    is_same_domain_or_subdomain,
    normalize_and_validate_url,
    extract_all_site_nav_links,
    extract_pdf_text_from_bytes,
    ai_select_optimal_subpages,
    extract_onsite_contacts_and_decision_makers,
    crawl_smart_dom_target,
    get_cached_crawl_res
)
from database import get_domain_pattern
from pypdf import PdfWriter


def check(desc: str, cond: bool):
    if cond:
        print(f"  PASS  {desc}")
    else:
        print(f"  FAIL  {desc}")
        sys.exit(1)


async def run_tests():
    print("\n" + "=" * 58)
    print("  Smart DOM Crawler (S2) — Comprehensive Test Suite")
    print("=" * 58)

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
    # PART 2: DOM Navigation & PDF Link Harvesting
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
                <a href="/downloads/company-profile.pdf">Download Company Profile</a>
                <a href="https://linkedin.com/company/ahmed">LinkedIn</a>
            </nav>
        </header>
        <main>
            <h1>Global Freight Leaders</h1>
            <p>Providing seamless freight operations worldwide.</p>
            <a href="/case-studies">View Case Studies</a>
            <img src="/images/banner.jpg" alt="Banner" />
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
    pdf_links = dom_result.get("pdf_links", [])

    check("Harvested internal links found", len(all_links) >= 5)
    check("Nav links properly segmented", any("/about-us" in l["url"] for l in nav_links))
    check("Leadership link captured in nav", any("/leadership" in l["url"] for l in nav_links))
    check("Internal PDF document captured for cracking", len(pdf_links) >= 1 and any("company-profile.pdf" in l["url"] for l in pdf_links))
    check("Non-PDF media image asset filtered out", not any(".jpg" in l["url"] for l in all_links))
    check("External LinkedIn filtered out", not any("linkedin.com" in l["url"] for l in all_links))
    check("Footer link properly segmented", any("/privacy-policy" in l["url"] for l in footer_links))

    # ─────────────────────────────────────────────────────────
    # PART 3: In-Memory PDF Document Cracking
    # ─────────────────────────────────────────────────────────
    print("\nPART 3 — PDF Document Cracking (pypdf Engine):")
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    pdf_buf = io.BytesIO()
    writer.write(pdf_buf)
    pdf_buf.seek(0)
    parsed_pdf_text = extract_pdf_text_from_bytes(pdf_buf.getvalue())
    check("extract_pdf_text_from_bytes executes without crashing", isinstance(parsed_pdf_text, str))

    # ─────────────────────────────────────────────────────────
    # PART 4: Structured Profile Extraction (Name, Position, Bio, Email, Social)
    # ─────────────────────────────────────────────────────────
    print("\nPART 4 — Structured Person Profile & Commercial Inbox Extraction:")
    mock_pages = {
        "homepage": {
            "url": "https://ahmed.com",
            "html": "<p>Welcome to Ahmed Logistics. Call +1 555-234-5678.</p>",
            "text": """Welcome to Ahmed Logistics. Call our office at +1 (555) 234-5678.
            General inquiries: info@ahmed.com
            Customer assistance: support@ahmed.com
            Commercial sales: sales@ahmed.com
            Investor relations: investors@ahmed.com"""
        },
        "leadership": {
            "url": "https://ahmed.com/leadership",
            "html": """
            <div class="team-grid">
                <div class="team-member">
                    <h3>Tariq Ahmed</h3>
                    <span class="role">Founder & Chief Executive Officer</span>
                    <p class="bio">Tariq leads enterprise freight technology and global network strategy with 18+ years in logistics.</p>
                    <a href="mailto:tariq.ahmed@ahmed.com">Email Tariq</a>
                    <a href="https://www.linkedin.com/in/tariq-ahmed">LinkedIn</a>
                </div>
                <div class="team-member">
                    <h3>Sarah Jenkins</h3>
                    <span class="role">Vice President of Operations</span>
                    <p class="bio">Sarah oversees worldwide supply chain execution and multi-modal distribution centers.</p>
                    <a href="mailto:sarah.jenkins@ahmed.com">Email Sarah</a>
                    <a href="https://www.linkedin.com/in/sarah-jenkins">LinkedIn</a>
                </div>
            </div>
            """,
            "text": """Leadership Directory:
            Tariq Ahmed, Founder & Chief Executive Officer
            Tariq leads enterprise freight technology and global network strategy with 18+ years in logistics.
            Direct Email: tariq.ahmed@ahmed.com
            LinkedIn: https://www.linkedin.com/in/tariq-ahmed

            Sarah Jenkins, Vice President of Operations
            Sarah oversees worldwide supply chain execution and multi-modal distribution centers.
            Direct Email: sarah.jenkins@ahmed.com
            LinkedIn: https://www.linkedin.com/in/sarah-jenkins"""
        }
    }
    extracted = extract_onsite_contacts_and_decision_makers(mock_pages, "ahmed.com")
    dms = extracted.get("decision_makers", [])
    emails = extracted.get("emails", [])
    phones = extracted.get("phones", [])

    check("Dead generic info@ahmed.com filtered out", "info@ahmed.com" not in emails)
    check("Dead generic support@ahmed.com filtered out", "support@ahmed.com" not in emails)
    check("Commercial sales@ahmed.com retained from website", "sales@ahmed.com" in emails)
    check("Commercial investors@ahmed.com retained from website", "investors@ahmed.com" in emails)
    check("Direct executive email tariq.ahmed@ahmed.com retained", "tariq.ahmed@ahmed.com" in emails)
    check("Extracted on-site phone", len(phones) >= 1)
    check("Discovered real executive decision makers", len(dms) >= 2)
    ceo = next((d for d in dms if "Tariq Ahmed" in d["name"]), None)
    check("CEO Tariq Ahmed identified", ceo is not None)
    check("CEO position / role captured", "Chief Executive Officer" in (ceo.get("position") or ceo.get("role", "")))
    check("CEO bio captured from DOM card", len(ceo.get("bio", "")) > 15)
    check("CEO direct email bound", ceo.get("email") == "tariq.ahmed@ahmed.com")
    check("CEO social / LinkedIn link captured", "linkedin.com/in/tariq-ahmed" in (ceo.get("linkedin") or ""))
    check("CEO marked strictly verified", ceo.get("strictly_verified") is True)

    # Verify Pattern Library received the pattern
    pat_info = get_domain_pattern("ahmed.com")
    check("Pattern Library saved domain pattern", pat_info is not None)
    check("Pattern identified as first.last", pat_info.get("pattern") == "first.last")

    # ─────────────────────────────────────────────────────────
    # PART 5: Strict Zero-Hallucination Policy (0% Fake Data)
    # ─────────────────────────────────────────────────────────
    print("\nPART 5 — Strict Zero-Hallucination Policy (0% AI Guess):")
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

    print("\n" + "=" * 58)
    print("  Results: All S2 PDF & Commercial Filter Tests Passed!")
    print("=" * 58 + "\n")


if __name__ == "__main__":
    asyncio.run(run_tests())
