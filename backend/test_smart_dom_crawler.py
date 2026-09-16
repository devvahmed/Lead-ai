"""
Comprehensive Test Suite for Dynamic DOM Header/Footer/Nav Link Parser & Semantic Crawler (Step 6).

Tests:
1. DOM Structural Zone Extraction (<nav>, <header>, <footer>, <body>).
2. URL Normalization, Relative-to-Absolute Resolution, and Fragment Stripping.
3. Filtering of External Domains, Social Networks, Protocols (mailto, tel), and Static Assets.
4. Semantic Link Router & Operational Categorization (about, services_operations, contact, careers_hiring).
5. Link Prioritization & Scoring (Nav vs Footer vs Body, canonical slug vs blog noise).
6. Concurrent Dynamic Multi-Page Crawling (crawl_smart_dom_target).
7. Discover.py Streaming Integration with DOM-crawled Multi-Page Context.
"""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from smart_dom_crawler import (
    extract_internal_dom_links,
    categorize_and_prioritize_links,
    score_link_for_category,
    normalize_and_validate_url,
    get_base_domain,
    is_same_domain_or_subdomain,
    extract_clean_page_text,
    crawl_smart_dom_target
)


SAMPLE_HOMEPAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Apex Industrial Automation & Robotics</title>
</head>
<body>
    <header class="site-header">
        <div class="logo"><a href="/">Apex Automation</a></div>
        <nav class="main-navigation">
            <ul>
                <li><a href="/about-us">Who We Are</a></li>
                <li><a href="/solutions/industrial-robotics">Robotics & Vision Solutions</a></li>
                <li><a href="/manufacturing-facilities">Our Plants & Facilities</a></li>
                <li><a href="/contact">Get in Touch</a></li>
            </ul>
        </nav>
    </header>

    <main class="content-body">
        <section class="hero">
            <h1>Turnkey Automation for Global Warehousing</h1>
            <p>We deploy autonomous sorting systems and high-speed robotic packaging cells across North America.</p>
            <a href="/case-studies/auto-plant" class="btn">View Automotive Case Study</a>
            <a href="https://linkedin.com/company/apex-auto" class="social">Follow on LinkedIn</a>
            <a href="https://twitter.com/apex_auto" class="social">Twitter</a>
            <a href="mailto:info@apexautomation.com">Email Us</a>
            <a href="tel:+13125550199">Call Headquarters</a>
            <a href="/downloads/product-catalog.pdf">Download Brochure (PDF)</a>
            <a href="/assets/hero-banner.jpg">Hero Image</a>
        </section>

        <section class="blog-preview">
            <h2>Latest Insights</h2>
            <a href="/blog/2024/05/about-our-growth">Read Blog: About Our Growth</a>
            <a href="https://techpartner.org/integration">Partner Website</a>
        </section>
    </main>

    <footer class="site-footer">
        <div class="footer-links">
            <a href="/careers">Career Opportunities</a>
            <a href="/locations/chicago-headquarters">Chicago Facility</a>
            <a href="/privacy-policy">Privacy Policy</a>
            <a href="/terms">Terms of Service</a>
        </div>
        <p>&copy; 2026 Apex Industrial Automation Inc.</p>
    </footer>
</body>
</html>
"""


class TestDOMLinkExtraction(unittest.TestCase):
    """Verifies parsing of HTML structural zones and URL hygiene."""

    def test_structural_zone_partitioning(self):
        base_url = "https://apexautomation.com"
        links = extract_internal_dom_links(SAMPLE_HOMEPAGE_HTML, base_url)

        # 1. Check navigation zone links
        nav_paths = [item["path"] for item in links["nav_links"]]
        self.assertIn("/about-us", nav_paths)
        self.assertIn("/solutions/industrial-robotics", nav_paths)
        self.assertIn("/manufacturing-facilities", nav_paths)
        self.assertIn("/contact", nav_paths)
        for item in links["nav_links"]:
            self.assertEqual(item["zone"], "nav")

        # 2. Check footer zone links
        footer_paths = [item["path"] for item in links["footer_links"]]
        self.assertIn("/careers", footer_paths)
        self.assertIn("/locations/chicago-headquarters", footer_paths)
        for item in links["footer_links"]:
            self.assertEqual(item["zone"], "footer")

        # 3. Check body zone links
        body_paths = [item["path"] for item in links["body_links"]]
        self.assertIn("/case-studies/auto-plant", body_paths)
        self.assertIn("/blog/2024/05/about-our-growth", body_paths)
        for item in links["body_links"]:
            self.assertEqual(item["zone"], "body")

    def test_url_normalization_and_resolution(self):
        base_url = "https://apexautomation.com/en/"
        valid = normalize_and_validate_url("/contact-us#form", base_url)
        self.assertEqual(valid, "https://apexautomation.com/contact-us")

        rel_valid = normalize_and_validate_url("services/robotics", "https://apexautomation.com/corp/")
        self.assertEqual(rel_valid, "https://apexautomation.com/corp/services/robotics")

    def test_filtering_external_and_social_domains(self):
        base_url = "https://apexautomation.com"
        self.assertIsNone(normalize_and_validate_url("https://linkedin.com/company/apex", base_url))
        self.assertIsNone(normalize_and_validate_url("https://twitter.com/apex", base_url))
        self.assertIsNone(normalize_and_validate_url("https://techpartner.org/integration", base_url))
        self.assertIsNone(normalize_and_validate_url("https://clutch.co/profile/apex", base_url))

    def test_filtering_assets_and_protocols(self):
        base_url = "https://apexautomation.com"
        self.assertIsNone(normalize_and_validate_url("/downloads/specs.pdf", base_url))
        self.assertIsNone(normalize_and_validate_url("/images/banner.png", base_url))
        self.assertIsNone(normalize_and_validate_url("/styles/main.css", base_url))
        self.assertIsNone(normalize_and_validate_url("mailto:sales@apex.com", base_url))
        self.assertIsNone(normalize_and_validate_url("tel:+13125550199", base_url))
        self.assertIsNone(normalize_and_validate_url("javascript:void(0)", base_url))
        self.assertIsNone(normalize_and_validate_url("#top", base_url))

    def test_homepage_root_filtering(self):
        base_url = "https://apexautomation.com"
        self.assertIsNone(normalize_and_validate_url("/", base_url))
        self.assertIsNone(normalize_and_validate_url("/index.html", base_url))
        self.assertIsNone(normalize_and_validate_url("/en/", base_url))


class TestSemanticLinkRouter(unittest.TestCase):
    """Verifies operational categorization and priority scoring."""

    def test_operational_categorization(self):
        base_url = "https://apexautomation.com"
        extracted = extract_internal_dom_links(SAMPLE_HOMEPAGE_HTML, base_url)
        all_links = extracted["all_links"]

        categorized = categorize_and_prioritize_links(all_links, base_url)

        self.assertIn("about", categorized)
        self.assertIn("contact", categorized)
        self.assertIn("services_operations", categorized)
        self.assertIn("careers_hiring", categorized)

        self.assertEqual(categorized["about"], "https://apexautomation.com/about-us")
        self.assertEqual(categorized["contact"], "https://apexautomation.com/contact")
        self.assertTrue(
            categorized["services_operations"] in (
                "https://apexautomation.com/solutions/industrial-robotics",
                "https://apexautomation.com/manufacturing-facilities"
            )
        )
        self.assertEqual(categorized["careers_hiring"], "https://apexautomation.com/careers")

    def test_nav_priority_over_blog_noise(self):
        """Verifies canonical nav link /about-us beats blog /blog/2024/05/about-our-growth."""
        base_url = "https://apexautomation.com"
        extracted = extract_internal_dom_links(SAMPLE_HOMEPAGE_HTML, base_url)
        categorized = categorize_and_prioritize_links(extracted["all_links"], base_url)

        self.assertEqual(categorized["about"], "https://apexautomation.com/about-us")
        self.assertNotEqual(categorized["about"], "https://apexautomation.com/blog/2024/05/about-our-growth")

    def test_score_link_for_category(self):
        nav_about = {
            "url": "https://company.com/about",
            "path": "/about",
            "text": "About Us",
            "zone": "nav"
        }
        score = score_link_for_category(nav_about, "about")
        self.assertGreaterEqual(score, 70.0)

        blog_about = {
            "url": "https://company.com/blog/news/2023/about-us-in-press",
            "path": "/blog/news/2023/about-us-in-press",
            "text": "Press Release About Us",
            "zone": "body"
        }
        blog_score = score_link_for_category(blog_about, "about")
        self.assertEqual(blog_score, 0.0)  # Penalized by /blog/ path


class TestDynamicMultiPageCrawler(unittest.IsolatedAsyncioTestCase):
    """Verifies concurrent crawling and structured evidence assembly."""

    async def test_crawl_smart_dom_target_mock_http(self):
        subpage_mocks = {
            "https://apexautomation.com": SAMPLE_HOMEPAGE_HTML,
            "https://apexautomation.com/about-us": (
                "<html><body><h1>About Apex Automation</h1>"
                "<p>Apex Automation was established in 1998 in Chicago, Illinois. "
                "We operate 3 regional manufacturing centers and serve tier-1 aerospace suppliers. "
                "Our team of 150 automation engineers specializes in high-speed pick and place robotics.</p></body></html>"
            ),
            "https://apexautomation.com/solutions/industrial-robotics": (
                "<html><body><h1>Industrial Robotics Solutions</h1>"
                "<p>Our robotics division engineers turnkey assembly lines, automated welding cells, "
                "and computer vision quality inspection stations. ISO 9001 certified operations.</p></body></html>"
            ),
            "https://apexautomation.com/manufacturing-facilities": (
                "<html><body><h1>Manufacturing Facilities</h1>"
                "<p>Our heavy fabrication and testing facility encompasses 85,000 square feet with "
                "cleanroom robotics assembly areas and cold chain material testing facilities.</p></body></html>"
            ),
            "https://apexautomation.com/contact": (
                "<html><body><h1>Contact Apex Automation</h1>"
                "<p>Headquarters: 400 N Michigan Ave, Chicago, IL 60611. Phone: +1 312-555-0199. "
                "Email: procurement@apexautomation.com. Request a quote or schedule a plant visit.</p></body></html>"
            ),
            "https://apexautomation.com/careers": (
                "<html><body><h1>Careers at Apex</h1>"
                "<p>Join our engineering team. We are actively hiring senior robotics programmers "
                "and PLC automation specialists in Chicago and Detroit.</p></body></html>"
            )
        }

        async def mock_fetch(url, timeout=4.0):
            return subpage_mocks.get(url, "<html><body>Default content</body></html>")

        with patch("smart_dom_crawler.fetch_page_html", side_effect=mock_fetch):
            res = await crawl_smart_dom_target(
                domain="apexautomation.com",
                homepage_url="https://apexautomation.com",
                homepage_html=SAMPLE_HOMEPAGE_HTML,
                max_pages=4
            )

        self.assertIsInstance(res, dict)
        self.assertIn("combined_text", res)
        self.assertIn("source_label", res)
        self.assertGreaterEqual(res["total_pages_crawled"], 3)

        # Verify structured page sections in combined text
        combined = res["combined_text"]
        self.assertIn("[PAGE: Homepage]", combined)
        self.assertIn("[PAGE: About]", combined)
        self.assertIn("[PAGE: Contact]", combined)

        # Verify source label incorporates discovered subpages
        label = res["source_label"]
        self.assertIn("homepage", label)
        self.assertIn("/about-us", label)
        self.assertIn("/contact", label)


class TestDiscoverIntegrationWithSmartDOMCrawler(unittest.IsolatedAsyncioTestCase):
    """Verifies that discover.py seamlessly streams candidates using smart_dom_crawler."""

    async def test_discover_pipeline_uses_smart_dom_crawler(self):
        import discover

        # Mock search returning a candidate domain
        async def mock_search(query, page=1):
            return [
                {
                    "url": "https://apexautomation.com",
                    "title": "Apex Automation | Industrial Robotics & Assembly",
                    "content": "Turnkey automation and robotics systems provider with heavy manufacturing facilities.",
                    "raw_domain": "apexautomation.com"
                }
            ]

        # Mock crawler returning structured DOM-scraped multi-page content
        async def mock_smart_crawl(**kwargs):
            return {
                "combined_text": (
                    "[PAGE: HOMEPAGE] (/)\n"
                    "Apex Automation provides turnkey robotic cells and automated vision inspection for manufacturing.\n\n"
                    "--- [PAGE: ABOUT] (/about-us) ---\n"
                    "Operating 85,000 square feet of heavy manufacturing facilities in Chicago, IL.\n\n"
                    "--- [PAGE: CONTACT] (/contact) ---\n"
                    "Headquarters: Chicago, IL. Phone: +1 312-555-0199. Contact our sales division for an RFP."
                ),
                "source_label": "homepage + /about-us + /contact",
                "homepage_text": "Apex Automation provides turnkey robotic cells.",
                "pages": {"homepage": {}, "about": {}, "contact": {}},
                "dom_links": {},
                "categorized_targets": {},
                "total_pages_crawled": 3
            }

        async def mock_eval(**kwargs):
            return {
                "is_junk": False,
                "industry_match": True,
                "lead_type": "NEEDS_SERVICE",
                "confidence": 94,
                "reason": "Industrial automation manufacturer with active operations in Chicago.",
                "official_company_name": "Apex Industrial Automation Inc",
                "source": "smart-dom-test",
                "detected_country": "USA"
            }

        orig_search = discover.search_searxng_or_ddg
        orig_crawl = discover.crawl_smart_dom_target
        orig_eval = discover.evaluate_client_fit_dual_engine

        discover.search_searxng_or_ddg = mock_search
        discover.crawl_smart_dom_target = mock_smart_crawl
        discover.evaluate_client_fit_dual_engine = mock_eval

        try:
            received_events = []
            async for line in discover.stream_discovery(
                keyword="Robotics",
                mode="direct_search",
                start_page=1,
                target_count=1,
                max_pages=1
            ):
                data = json.loads(line.strip())
                received_events.append(data)

            companies = [e for e in received_events if e.get("type") == "company"]
            self.assertEqual(len(companies), 1)
            comp = companies[0]
            self.assertEqual(comp["domain"], "apexautomation.com")
            self.assertEqual(comp["name"], "Apex Industrial Automation Inc")
        finally:
            discover.search_searxng_or_ddg = orig_search
            discover.crawl_smart_dom_target = orig_crawl
            discover.evaluate_client_fit_dual_engine = orig_eval


if __name__ == "__main__":
    unittest.main()
