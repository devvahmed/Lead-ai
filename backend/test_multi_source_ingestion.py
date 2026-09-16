"""
Comprehensive Test Suite for Parallel Multi-Source Ingestion Engine (Step 1).

Tests:
1. Unified Data Schema (RawLeadCandidate)
2. Individual Worker Execution & Fault Tolerance
3. Cross-Platform Deduplication & Priority Boosting
4. Concurrency Bounds & 6-second Timeouts
5. Full Ingestion Pipeline (ingest_all_sources)
6. End-to-End Integration with discover.py
"""

import asyncio
import hashlib
import json
import time
import unittest

from multi_source_ingestion import (
    RawLeadCandidate,
    clean_domain_str,
    clean_text_content,
    extract_company_from_title,
    extract_first_external_url,
    generate_dynamic_search_keywords,
    get_dynamic_subreddits,
    deduplicate_candidates,
    fetch_searxng_async,
    fetch_reddit_async,
    fetch_hacker_news_async,
    fetch_rss_feeds_async,
    fetch_twitter_intent_async,
    ingest_all_sources,
    TIMEOUT_SECONDS
)


class TestDynamicKeywordAndSubredditExpansion(unittest.TestCase):
    """Verifies that dynamic query expansion adapts to any target service and industry."""

    def test_dynamic_keyword_generation_warehouse_automation(self):
        keywords = generate_dynamic_search_keywords("Warehouse Automation", "Logistics")
        self.assertIsInstance(keywords, list)
        self.assertGreaterEqual(len(keywords), 4)
        # Verify targeted buying terms are included
        combined = " ".join(keywords)
        self.assertIn("Warehouse Automation", combined)
        self.assertIn("looking for agency", combined)
        self.assertIn("seeking freelancer", combined)

    def test_dynamic_keyword_generation_computer_vision(self):
        keywords = generate_dynamic_search_keywords("Computer Vision", "AI")
        combined = " ".join(keywords)
        self.assertIn("Computer Vision", combined)
        self.assertIn("need contractor", combined)

    def test_dynamic_keyword_generation_custom_crm(self):
        keywords = generate_dynamic_search_keywords("Custom CRM", "SaaS")
        combined = " ".join(keywords)
        self.assertIn("Custom CRM", combined)
        self.assertIn("seeking agency", combined)

    def test_get_dynamic_subreddits_relevance(self):
        # Vision/AI cluster
        ai_subs = get_dynamic_subreddits("Computer Vision", "AI")
        self.assertGreaterEqual(len(ai_subs), 10)
        self.assertIn("computervision", ai_subs)
        self.assertIn("MachineLearning", ai_subs)

        # Logistics/Automation cluster
        auto_subs = get_dynamic_subreddits("Warehouse Automation", "Supply Chain")
        self.assertGreaterEqual(len(auto_subs), 10)
        self.assertIn("automation", auto_subs)
        self.assertIn("robotics", auto_subs)

        # Web cluster
        web_subs = get_dynamic_subreddits("Web & Mobile App Development", "Tech")
        self.assertGreaterEqual(len(web_subs), 10)
        self.assertIn("webdev", web_subs)


class TestRawLeadCandidateSchema(unittest.TestCase):
    """Verifies Pydantic schema validation, defaults, and serialization."""

    def test_valid_candidate_creation(self):
        candidate = RawLeadCandidate(
            source="searxng",
            title="Acme Corporation - Cloud Solutions",
            text_content="We provide scalable cloud infrastructure.",
            url="https://acmecorp.io/services",
            author_or_company="Acme Corp",
            raw_domain="acmecorp.io",
            published_at="2026-09-01T12:00:00Z",
            priority_rank=1,
            raw_metadata={"engine": "google"}
        )
        self.assertEqual(candidate.source, "searxng")
        self.assertEqual(candidate.title, "Acme Corporation - Cloud Solutions")
        self.assertEqual(candidate.raw_domain, "acmecorp.io")
        self.assertEqual(candidate.priority_rank, 1)
        self.assertEqual(candidate.raw_metadata["engine"], "google")

    def test_schema_defaults(self):
        candidate = RawLeadCandidate(
            source="reddit",
            title="[Hiring] Need Web Developer",
            text_content="Budget $5k, please apply.",
            url="https://reddit.com/r/forhire/comments/12345"
        )
        self.assertIsNone(candidate.author_or_company)
        self.assertIsNone(candidate.raw_domain)
        self.assertIsNone(candidate.published_at)
        self.assertEqual(candidate.priority_rank, 1)
        self.assertEqual(candidate.raw_metadata, {})


class TestNormalizationHelpers(unittest.TestCase):
    """Verifies domain cleaning, text sanitization, and URL extraction."""

    def test_clean_domain_str(self):
        self.assertEqual(clean_domain_str("https://www.example.com/path?arg=1"), "example.com")
        self.assertEqual(clean_domain_str("http://sub.domain.co.uk:8080/"), "sub.domain.co.uk")
        self.assertEqual(clean_domain_str("example.io/about"), "example.io")
        self.assertEqual(clean_domain_str(""), "")

    def test_clean_text_content(self):
        raw = "<p>Hello <b>World</b>! &amp; Welcome &quot;Friends&quot;</p>"
        cleaned = clean_text_content(raw)
        self.assertEqual(cleaned, 'Hello World! & Welcome "Friends"')

    def test_extract_company_from_title(self):
        self.assertEqual(extract_company_from_title("Senior Python Engineer at Stripe"), "Stripe")
        self.assertEqual(extract_company_from_title("PostHog is hiring a frontend engineer"), "PostHog")
        self.assertEqual(extract_company_from_title("Linear: Backend Architect"), "Linear")

    def test_extract_first_external_url(self):
        text = "Check out our site at https://mybrand.io or view docs at https://github.com/mybrand"
        self.assertEqual(extract_first_external_url(text), "https://mybrand.io")
        # Should ignore images
        img_text = "See our logo: https://example.com/logo.png and homepage https://acme.org"
        self.assertEqual(extract_first_external_url(img_text), "https://acme.org")


class TestDeduplicationAndBoosting(unittest.TestCase):
    """Verifies cross-platform deduplication, hashing, and priority ranking boosts."""

    def test_domain_deduplication_and_priority_boost(self):
        cand1 = RawLeadCandidate(
            source="searxng",
            title="TechFlow Systems Home",
            text_content="Leading software consultancy.",
            url="https://techflow.io",
            raw_domain="techflow.io",
            author_or_company="TechFlow Systems"
        )
        cand2 = RawLeadCandidate(
            source="reddit",
            title="[Hiring] TechFlow seeking contractors",
            text_content="TechFlow is expanding our contractor base.",
            url="https://reddit.com/r/forhire/comments/999",
            raw_domain="techflow.io",
            author_or_company="TechFlow Systems"
        )
        cand3 = RawLeadCandidate(
            source="rss_feed",
            title="Senior Architect at TechFlow",
            text_content="Remote architect opening at TechFlow.",
            url="https://techflow.io/careers/architect",
            raw_domain="techflow.io"
        )

        deduped = deduplicate_candidates([cand1, cand2, cand3])
        self.assertEqual(len(deduped), 1)
        lead = deduped[0]
        # Candidate appeared across 3 sources, priority_rank should be 1 + 2 = 3
        self.assertEqual(lead.priority_rank, 3)
        self.assertTrue(lead.raw_metadata.get("cross_source_match"))
        self.assertIn("searxng", lead.raw_metadata.get("sources", []))
        self.assertIn("reddit", lead.raw_metadata.get("sources", []))
        self.assertIn("rss_feed", lead.raw_metadata.get("sources", []))

    def test_snippet_hash_deduplication(self):
        text = "We are an innovative agency looking for senior engineers to scale our B2B pipeline."
        cand1 = RawLeadCandidate(
            source="twitter_x",
            title="Looking for engineers",
            text_content=text,
            url="https://x.com/founder1/status/100"
        )
        cand2 = RawLeadCandidate(
            source="reddit",
            title="Seeking engineers",
            text_content=text,
            url="https://reddit.com/r/forhire/comments/200"
        )

        deduped = deduplicate_candidates([cand1, cand2])
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0].priority_rank, 2)


class TestAsyncWorkersAndPipeline(unittest.IsolatedAsyncioTestCase):
    """Verifies non-blocking execution, timeouts, and live API responses."""

    async def test_searxng_offline_tolerance(self):
        # Should gracefully return empty list without raising ConnectError
        res = await fetch_searxng_async("Software Engineering", page=1)
        self.assertIsInstance(res, list)

    async def test_reddit_dynamic_global_and_sub_search(self):
        # Queries Reddit using dynamic search and subreddits for Computer Vision / AI
        res = await fetch_reddit_async(query="AI", target_service="Computer Vision")
        self.assertIsInstance(res, list)
        if res:
            self.assertEqual(res[0].source, "reddit")
            self.assertTrue(len(res[0].title) > 0)
            self.assertIn("subreddit", res[0].raw_metadata)

    async def test_hacker_news_live_api(self):
        # Hacker News Algolia REST Search API with dynamic keywords
        res = await fetch_hacker_news_async(query="Logistics", target_service="Warehouse Automation")
        self.assertIsInstance(res, list)
        if res:
            self.assertEqual(res[0].source, "hacker_news")
            self.assertTrue(len(res[0].title) > 0)
            self.assertTrue("hn_id" in res[0].raw_metadata or "author" in res[0].raw_metadata)

    async def test_rss_feeds_live_api(self):
        # RemoteOK / WeWorkRemotely public XML
        res = await fetch_rss_feeds_async(query="Developer")
        self.assertIsInstance(res, list)
        if res:
            self.assertEqual(res[0].source, "rss_feed")

    async def test_twitter_intent_engine(self):
        res = await fetch_twitter_intent_async(query="SaaS", target_service="Mobile App Development")
        self.assertIsInstance(res, list)
        self.assertGreater(len(res), 0)
        self.assertEqual(res[0].source, "twitter_x")
        self.assertIn("Mobile App Development", res[0].text_content)

    async def test_ingest_all_sources_concurrency_and_timeout(self):
        start = time.time()
        leads = await ingest_all_sources(query="Fintech", target_service="Custom Software")
        elapsed = time.time() - start

        # Must strictly adhere to the 6.0-second timeout ceiling (allowing minor buffer for dedup)
        self.assertLess(elapsed, TIMEOUT_SECONDS + 1.5, f"Ingestion took {elapsed}s, exceeded timeout budget")
        self.assertIsInstance(leads, list)
        self.assertGreater(len(leads), 0)

        # Check that candidates have source, title, and valid priority_rank
        for lead in leads:
            self.assertIn(lead.source, ("searxng", "reddit", "hacker_news", "rss_feed", "twitter_x"))
            self.assertGreaterEqual(lead.priority_rank, 1)

    async def test_ingest_all_sources_with_custom_services(self):
        leads = await ingest_all_sources(query="Supply Chain", target_service="Warehouse Automation")
        self.assertIsInstance(leads, list)
        self.assertGreater(len(leads), 0)
        # Verify deduplication maintained
        urls = [lead.url for lead in leads if lead.url]
        self.assertEqual(len(urls), len(set(urls)))

    async def test_ingest_all_sources_discovery_modes(self):
        from unittest.mock import patch, AsyncMock
        with patch("multi_source_ingestion.fetch_searxng_async", new_callable=AsyncMock) as mock_searx, \
             patch("multi_source_ingestion.fetch_reddit_async", new_callable=AsyncMock) as mock_reddit, \
             patch("multi_source_ingestion.fetch_hacker_news_async", new_callable=AsyncMock) as mock_hn, \
             patch("multi_source_ingestion.fetch_rss_feeds_async", new_callable=AsyncMock) as mock_rss, \
             patch("multi_source_ingestion.fetch_twitter_intent_async", new_callable=AsyncMock) as mock_tw:

            mock_searx.return_value = [RawLeadCandidate(source="searxng", title="Test Inc", text_content="Site", url="https://testinc.com")]
            mock_reddit.return_value = []
            mock_hn.return_value = []
            mock_rss.return_value = []
            mock_tw.return_value = []

            # Mode 1: companies -> SearXNG ONLY
            leads = await ingest_all_sources(query="Enterprise AI", discovery_mode="companies")
            self.assertEqual(len(leads), 1)
            self.assertTrue(mock_searx.called)
            self.assertFalse(mock_reddit.called)
            self.assertFalse(mock_hn.called)
            self.assertFalse(mock_rss.called)
            self.assertFalse(mock_tw.called)

            mock_searx.reset_mock()
            mock_reddit.reset_mock()
            mock_hn.reset_mock()
            mock_rss.reset_mock()
            mock_tw.reset_mock()

            # Mode 2: social_intent -> Twitter, Reddit, RSS, HN (NO SearXNG)
            mock_reddit.return_value = [RawLeadCandidate(source="reddit", title="Need Dev", text_content="Seeking agency", url="https://reddit.com/r/forhire/999")]
            leads = await ingest_all_sources(query="Enterprise AI", discovery_mode="social_intent")
            self.assertEqual(len(leads), 1)
            self.assertFalse(mock_searx.called)
            self.assertTrue(mock_reddit.called)
            self.assertTrue(mock_hn.called)
            self.assertTrue(mock_rss.called)
            self.assertTrue(mock_tw.called)

            mock_searx.reset_mock()
            mock_reddit.reset_mock()
            mock_hn.reset_mock()
            mock_rss.reset_mock()
            mock_tw.reset_mock()

            # Mode 3: hybrid -> All 5 channels
            leads = await ingest_all_sources(query="Enterprise AI", discovery_mode="hybrid")
            self.assertTrue(mock_searx.called)
            self.assertTrue(mock_reddit.called)
            self.assertTrue(mock_hn.called)
            self.assertTrue(mock_rss.called)
            self.assertTrue(mock_tw.called)


class TestDiscoverIntegration(unittest.IsolatedAsyncioTestCase):
    """Verifies that discover.py seamlessly consumes candidates from multi_source_ingestion."""

    async def test_stream_discovery_with_multi_source_mock(self):
        import discover

        # Mock multi_source_ingestion to return controlled candidates
        async def mock_ingest(query, target_service="", page=1, discovery_mode="hybrid", **kwargs):
            return [
                RawLeadCandidate(
                    source="rss_feed",
                    title="LeadCorp: Enterprise Cloud Solutions",
                    text_content="LeadCorp builds scalable infrastructure for global logistics.",
                    url="https://leadcorp.com",
                    author_or_company="LeadCorp",
                    raw_domain="leadcorp.com",
                    priority_rank=2
                )
            ]

        # Mock evaluate_client_fit_dual_engine to return an accepted evaluation verdict
        async def mock_eval(**kwargs):
            return {
                "is_junk": False,
                "industry_match": True,
                "lead_type": "NEEDS_SERVICE",
                "confidence": 90,
                "reason": "Enterprise logistics infrastructure client.",
                "official_company_name": "LeadCorp",
                "source": "multi-source-test",
                "detected_country": "US"
            }

        async def mock_scrape(url, timeout=4.0):
            return (
                "Welcome to LeadCorp Logistics. We provide enterprise cloud infrastructure, warehouse automation software, "
                "and end-to-end freight forwarding dispatch systems for international supply chain operators. "
                "Our scalable platforms optimize cross-docking facilities, real-time inventory tracking, and multimodal shipping routes across North America and Europe. "
                "With over fifteen years of industrial logistics experience, we help enterprise distributors automate order fulfillment and minimize transit delays. "
                "Contact our operations team today at sales@leadcorp.com or visit our corporate facility headquarters to request a demo or customized quote for our supply chain management solutions.",
                "homepage + /services"
            )

        orig_ingest = discover.ingest_all_sources
        orig_eval = discover.evaluate_client_fit_dual_engine
        orig_scrape = discover.fetch_url_content_with_subpages
        discover.ingest_all_sources = mock_ingest
        discover.evaluate_client_fit_dual_engine = mock_eval
        discover.fetch_url_content_with_subpages = mock_scrape

        try:
            received_events = []
            async for line in discover.stream_discovery(
                keyword="Logistics",
                start_page=1,
                target_count=1,
                max_pages=1
            ):
                data = json.loads(line.strip())
                received_events.append(data)

            # Check that company event was emitted
            companies = [e for e in received_events if e.get("type") == "company"]
            self.assertGreaterEqual(len(companies), 1)
            company = companies[0]
            self.assertEqual(company.get("domain"), "leadcorp.com")
            self.assertEqual(company.get("name"), "LeadCorp")
            self.assertEqual(company.get("dataSource"), "rss_feed")
            self.assertEqual(company.get("priorityRank"), 2)
        finally:
            discover.ingest_all_sources = orig_ingest
            discover.evaluate_client_fit_dual_engine = orig_eval
            discover.fetch_url_content_with_subpages = orig_scrape


if __name__ == "__main__":
    unittest.main()
