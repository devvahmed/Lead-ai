"""
Comprehensive Test Suite for Multi-Tier Deterministic & Semantic Junk Firewall (Step 3).

Tests:
1. Tier 1: Review Directory Blacklist (Clutch, G2, Yelp, Capterra, YellowPages, etc.)
2. Tier 1: Publishing & Social Platform Blacklist (Medium, Wikipedia, GitHub, Reddit, etc.)
3. Tier 1: URL Path Regex Filtering (/blog/, /article/, /top-10-, /press-release/)
4. Tier 1: JSON-LD Schema Guard (Reject Article/BlogPosting vs Pass LocalBusiness/Corporation)
5. Tier 1: Thin Content & Parked Domain Detection (< 80 words, placeholder keywords)
6. Tier 2: Semantic Entity Classification (Commercial business vs Blog/Affiliate)
7. Combined Pipeline: run_junk_firewall end-to-end execution
8. Integration with discover.py: Pre-scrape and post-scrape firewall filtering
"""

import asyncio
import json
import unittest

from junk_firewall import (
    is_deterministic_junk,
    evaluate_semantic_junk,
    run_junk_firewall,
    clean_domain_key,
    extract_jsonld_types
)


class TestTier1DeterministicFilter(unittest.TestCase):
    """Verifies zero-cost deterministic filtering of review directories, blogs, schemas, and parked sites."""

    def test_clean_domain_key(self):
        self.assertEqual(clean_domain_key("https://www.clutch.co:443/agencies"), "clutch.co")
        self.assertEqual(clean_domain_key("http://sub.domain.com/path"), "sub.domain.com")
        self.assertEqual(clean_domain_key("www.yelp.com"), "yelp.com")
        self.assertEqual(clean_domain_key("kuka.com"), "kuka.com")

    def test_review_directory_blacklist(self):
        directories = [
            ("https://clutch.co/agencies/top-developers", "clutch.co"),
            ("https://www.g2.com/products/slack/reviews", "g2.com"),
            ("https://capterra.com/p/123/product", "capterra.com"),
            ("https://www.yelp.com/biz/dentist-lahore", "yelp.com"),
            ("https://www.yellowpages.com/search?q=hvac", "yellowpages.com"),
            ("https://www.trustpilot.com/review/acme.com", "trustpilot.com"),
            ("https://www.goodfirms.co/directory", "goodfirms.co"),
            ("https://thomasnet.com/suppliers/metal-stamping", "thomasnet.com"),
            ("https://kompass.com/c/industrial/123", "kompass.com"),
            ("https://zoominfo.com/c/company/123", "zoominfo.com")
        ]
        for url, dom in directories:
            is_junk, reason = is_deterministic_junk(url=url, domain=dom)
            self.assertTrue(is_junk, f"Failed to reject review directory: {dom}")
            self.assertIn("Review directory", reason)

    def test_publishing_and_social_blacklist(self):
        platforms = [
            ("https://medium.com/@author/how-to-scale-b2b", "medium.com"),
            ("https://en.wikipedia.org/wiki/Robotics", "wikipedia.org"),
            ("https://github.com/torvalds/linux", "github.com"),
            ("https://reddit.com/r/forhire/comments/123", "reddit.com"),
            ("https://techauthor.substack.com/p/future-trends", "substack.com"),
            ("https://quora.com/what-is-computer-vision", "quora.com"),
            ("https://youtube.com/watch?v=123", "youtube.com"),
            ("https://forbes.com/sites/writer/2026/09/growth", "forbes.com")
        ]
        for url, dom in platforms:
            is_junk, reason = is_deterministic_junk(url=url, domain=dom)
            self.assertTrue(is_junk, f"Failed to reject publishing/social platform: {dom}")
            self.assertIn("Publishing / social", reason)

    def test_blog_and_article_path_regex(self):
        blog_urls = [
            ("https://acmecorp.com/blog/top-10-agencies-in-2026", "acmecorp.com"),
            ("https://industrialtech.io/article/future-of-automation", "industrialtech.io"),
            ("https://machinerycorp.org/news/press-release/new-factory-opened", "machinerycorp.org"),
            ("https://logisticsfirm.net/insights/best-5-tools-for-wms", "logisticsfirm.net"),
            ("https://consulting.com/category/case-studies/post/123", "consulting.com"),
            ("https://enterprise.com/reviews/competitor-analysis", "enterprise.com"),
            ("https://www.linkedin.com/pulse/my-thoughts-on-industrial-automation", "linkedin.com"),
            ("https://supplier.com/whitepapers/technical-report.pdf", "supplier.com")
        ]
        for url, dom in blog_urls:
            is_junk, reason = is_deterministic_junk(url=url, domain=dom)
            self.assertTrue(is_junk, f"Failed to reject blog/article URL pattern: {url}")
            self.assertIn("Non-commercial article / blog URL pattern", reason)

    def test_commercial_urls_pass_tier1(self):
        commercial_urls = [
            ("https://kuka.com/en-de/products/robotics-systems", "kuka.com"),
            ("https://fanucamerica.com/solutions/cnc-systems", "fanucamerica.com"),
            ("https://textilelead.com/contact-us", "textilelead.com"),
            ("https://coldstoragefacilities.com/about-us", "coldstoragefacilities.com"),
            ("https://precisionmachining.io/facilities", "precisionmachining.io"),
            ("https://freightlogistics.co.uk/services/fleet", "freightlogistics.co.uk")
        ]
        for url, dom in commercial_urls:
            is_junk, reason = is_deterministic_junk(url=url, domain=dom)
            self.assertFalse(is_junk, f"Falsely rejected commercial URL: {url} (reason: {reason})")

    def test_jsonld_schema_guard(self):
        # 1. Non-commercial schema (BlogPosting / Article)
        html_blog = """
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "BlogPosting",
                "headline": "Top 10 Trends in Automation",
                "author": {"@type": "Person", "name": "Jane Doe"}
            }
            </script>
        </head>
        <body><p>Blog content goes here.</p></body>
        </html>
        """
        is_junk, reason = is_deterministic_junk(url="https://example.com", domain="example.com", html_content=html_blog)
        self.assertTrue(is_junk)
        self.assertIn("Non-commercial JSON-LD schema (@type=BlogPosting)", reason)

        # 2. Commercial schema (LocalBusiness / Corporation)
        html_commercial = """
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "LocalBusiness",
                "name": "Precision CNC Machine Shop",
                "telephone": "+1-800-555-0199",
                "address": {
                    "@type": "PostalAddress",
                    "addressLocality": "Detroit",
                    "addressRegion": "MI"
                }
            }
            </script>
        </head>
        <body>
            <p>Welcome to Precision CNC Machine Shop. We are a certified manufacturing plant with multi-axis milling operations, heavy industrial fabrication, and custom tooling solutions for aerospace and automotive clients. Our facilities encompass over 80,000 square feet of precision manufacturing space. Contact our industrial engineering department at info@precisionmachining.com or call our direct office line to request a formal quote for components, assemblies, and turnkey machining services across North America.</p>
        </body>
        </html>
        """
        is_junk, reason = is_deterministic_junk(url="https://precisionmachining.com", domain="precisionmachining.com", html_content=html_commercial)
        self.assertFalse(is_junk)

    def test_thin_content_and_parked_domain_rejection(self):
        # Parked domain
        parked_text = "This domain is for sale on GoDaddy. Buy this domain today before someone else does!"
        is_junk, reason = is_deterministic_junk(url="https://unusedname.com", domain="unusedname.com", text_content=parked_text)
        self.assertTrue(is_junk)
        self.assertIn("parked domain placeholder", reason)

        # Ultra-thin content (< 40 words)
        ultra_thin = "Hello world welcome to our official website page today. Please check back later."
        is_junk, reason = is_deterministic_junk(url="https://emptyco.com", domain="emptyco.com", text_content=ultra_thin)
        self.assertTrue(is_junk)
        self.assertIn("Thin content: only", reason)

        # Genuine commercial business text (> 100 words with contact and services)
        rich_commercial_text = (
            "Welcome to Precision Industrial Automation Ltd. We are an ISO 9001 certified manufacturing "
            "and robotics integration facility specializing in custom conveyor assembly lines, high-speed vision "
            "sorting systems, and PLC industrial automation for automotive tier 1 suppliers. "
            "Our facilities encompass over 50,000 square feet of precision CNC machining and clean-room assembly space. "
            "Contact our engineering team today at sales@precisionindustrial.com or call our headquarters at +1-800-555-0144. "
            "About us: Founded in 2002, our operations serve clients across North America, Europe, and Asia. "
            "Request a formal quote or RFQ for specialized tooling, plant retrofits, and equipment upgrades."
        )
        is_junk, reason = is_deterministic_junk(url="https://precisionindustrial.com", domain="precisionindustrial.com", text_content=rich_commercial_text)
        self.assertFalse(is_junk)


class TestTier2SemanticClassifier(unittest.IsolatedAsyncioTestCase):
    """Verifies semantic classification of active commercial operating entities vs blogs/affiliates."""

    async def test_semantic_classifier_commercial_entity(self):
        commercial_text = (
            "KUKA is an international automation powerhouse with sales of around 4 billion euro. "
            "As one of the world's leading suppliers of intelligent automation solutions, KUKA offers its "
            "customers everything from a single source: from the robot component to customized cells and fully "
            "automated turnkey industrial plants. Contact our facilities for equipment inquiries and industrial solutions."
        )
        res = await evaluate_semantic_junk(domain="kuka.com", page_text=commercial_text, use_llm=False)
        self.assertIsInstance(res, dict)
        self.assertFalse(res["is_junk"])
        self.assertEqual(res["entity_type"], "COMMERCIAL_BUSINESS")

    async def test_semantic_classifier_affiliate_and_blog(self):
        blog_text = (
            "Welcome to TechTrends Blog! In this article, we review the top 10 best tools. "
            "Disclaimer: this post contains affiliate links for Amazon Associate and other partners. "
            "Leave a reply in the comment section below. Filed under uncategorized, written by admin on September 2026."
        )
        res = await evaluate_semantic_junk(domain="techtrendsblog.com", page_text=blog_text, use_llm=False)
        self.assertIsInstance(res, dict)
        self.assertTrue(res["is_junk"])
        self.assertEqual(res["entity_type"], "BLOG_OR_NEWS")


class TestRunJunkFirewallPipeline(unittest.IsolatedAsyncioTestCase):
    """Verifies end-to-end multi-tier firewall execution."""

    async def test_clutch_directory_rejected_tier1(self):
        is_junk, reason = await run_junk_firewall(
            url="https://clutch.co/profile/some-tech-firm",
            domain="clutch.co",
            use_llm=False
        )
        self.assertTrue(is_junk)
        self.assertIn("[Tier 1 Deterministic]", reason)
        self.assertIn("Review directory", reason)

    async def test_blog_url_rejected_tier1(self):
        is_junk, reason = await run_junk_firewall(
            url="https://company.com/blog/top-10-software-contractors",
            domain="company.com",
            use_llm=False
        )
        self.assertTrue(is_junk)
        self.assertIn("[Tier 1 Deterministic]", reason)
        self.assertIn("Non-commercial article / blog URL pattern", reason)

    async def test_commercial_company_passed_both_tiers(self):
        commercial_text = (
            "FANUC Corporation is a global market leader in CNC systems, robotics, and ROBOMACHINEs. "
            "We provide industrial automation solutions, factory equipment maintenance, and spare parts supply. "
            "Our automated manufacturing systems optimize productivity, reduce operating costs, and deliver superior precision. "
            "Contact our facility headquarters or request a quote from our certified engineering division to explore custom machinery, "
            "robotic arms, and intelligent cell integrations tailored to your industrial facility requirements."
        )
        is_junk, reason = await run_junk_firewall(
            url="https://fanucamerica.com/solutions",
            domain="fanucamerica.com",
            text_content=commercial_text,
            use_llm=False
        )
        self.assertFalse(is_junk)
        self.assertIn("Passed firewall", reason)


class TestDiscoverIntegrationWithFirewall(unittest.IsolatedAsyncioTestCase):
    """Verifies that discover.py pre-scrape and post-scrape gates intercept junk leads before LLM scoring."""

    async def test_discover_firewall_interception(self):
        import discover

        # Mock search provider returning a review directory, a blog, and a genuine company
        async def mock_search(query, page=1):
            return [
                {
                    "url": "https://clutch.co/agencies/top-developers",
                    "title": "Top Developers Directory | Clutch.co",
                    "content": "Directory of top software agencies and reviews."
                },
                {
                    "url": "https://techmedia.com/blog/top-10-robotics-firms",
                    "title": "Top 10 Robotics Firms to Watch in 2026",
                    "content": "Our editorial blog team reviews the best 10 robotics firms."
                },
                {
                    "url": "https://kuka.com",
                    "title": "KUKA Robotics Systems",
                    "content": "KUKA is a global automation powerhouse providing industrial robot cells and automated factory solutions."
                }
            ]

        # Mock LLM evaluation
        async def mock_eval(**kwargs):
            return {
                "is_junk": False,
                "industry_match": True,
                "lead_type": "NEEDS_SERVICE",
                "confidence": 85,
                "reason": "Operating industrial robotics company.",
                "official_company_name": "KUKA Robotics Systems",
                "source": "firewall-test",
                "detected_country": "Global"
            }

        async def mock_intent(*args, **kwargs):
            return True, "BUYER_CONTRACT", "Firewall test mock buyer intent approved"

        orig_search = discover.search_searxng_or_ddg
        orig_eval = discover.evaluate_client_fit_dual_engine
        orig_intent = getattr(discover, "run_intent_classifier", None)
        discover.search_searxng_or_ddg = mock_search
        discover.evaluate_client_fit_dual_engine = mock_eval
        if orig_intent:
            discover.run_intent_classifier = mock_intent

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

            # Check emitted company events
            companies = [e for e in received_events if e.get("type") == "company"]
            self.assertEqual(len(companies), 1)
            # The only yielded company MUST be kuka.com; clutch and blog must be blocked
            self.assertEqual(companies[0]["domain"], "kuka.com")
            domains_emitted = [c["domain"] for c in companies]
            self.assertNotIn("clutch.co", domains_emitted)
            self.assertNotIn("techmedia.com", domains_emitted)
        finally:
            discover.search_searxng_or_ddg = orig_search
            discover.evaluate_client_fit_dual_engine = orig_eval
            if orig_intent:
                discover.run_intent_classifier = orig_intent


if __name__ == "__main__":
    unittest.main()
