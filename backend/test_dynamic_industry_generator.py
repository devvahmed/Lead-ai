"""
Comprehensive Test Suite for Context-Aware Dynamic Industry Generator (Step 2).

Tests:
1. IndustryHistoryTracker persistence, normalization, and deduplication
2. SearXNG dork construction across countries (Pakistan, UK, USA) and TLD mapping
3. Dynamic LLM/Heuristic industry expansion accuracy across service domains
4. Non-repeating guarantee: verifying previously scanned niches are NEVER repeated
5. End-to-end get_next_discovery_batch coordination and automatic progression
6. Integration with discover.py stream_discovery in target_companies / ICP mode
"""

import asyncio
import json
import os
import tempfile
import unittest

from dynamic_industry_generator import (
    COUNTRY_TLD_MAP,
    IndustryHistoryTracker,
    build_searxng_dorks,
    generate_target_industry_niches,
    get_country_tld,
    get_next_discovery_batch,
)


class TestIndustryHistoryTracker(unittest.TestCase):
    """Tests file persistence, normalization, and query methods for IndustryHistoryTracker."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_file = os.path.join(self.temp_dir.name, "test_history.json")
        self.tracker = IndustryHistoryTracker(filepath=self.temp_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_mark_and_is_scanned(self):
        self.assertFalse(self.tracker.is_scanned("Textile Fabric Quality Control"))

        self.tracker.mark_scanned(
            niche="Textile Fabric Quality Control",
            service_context="Computer Vision",
            country="Pakistan",
            metadata={"priority": 1}
        )

        self.assertTrue(self.tracker.is_scanned("Textile Fabric Quality Control"))
        # Verify case-insensitivity and punctuation normalization
        self.assertTrue(self.tracker.is_scanned("textile fabric quality control"))
        self.assertTrue(self.tracker.is_scanned("  Textile Fabric Quality Control!  "))

    def test_persistence_reload_from_disk(self):
        self.tracker.mark_scanned("Cold Storage Warehouses", "Automated Inventory", "USA")
        self.tracker.mark_scanned("Specialty Freight Dispatch", "Web Development", "UK")

        # Create a new tracker instance reading the same physical file
        reloaded_tracker = IndustryHistoryTracker(filepath=self.temp_file)
        self.assertTrue(reloaded_tracker.is_scanned("Cold Storage Warehouses"))
        self.assertTrue(reloaded_tracker.is_scanned("Specialty Freight Dispatch"))
        self.assertFalse(reloaded_tracker.is_scanned("Pharmaceutical Packaging"))

        history = reloaded_tracker.get_scanned_niches()
        self.assertEqual(len(history), 2)
        self.assertIn("Cold Storage Warehouses", history)
        self.assertIn("Specialty Freight Dispatch", history)

    def test_clear_history(self):
        self.tracker.mark_scanned("Automotive Spare Parts Distributors")
        self.assertTrue(self.tracker.is_scanned("Automotive Spare Parts Distributors"))

        self.tracker.clear_history()
        self.assertFalse(self.tracker.is_scanned("Automotive Spare Parts Distributors"))
        self.assertEqual(len(self.tracker.get_scanned_niches()), 0)


class TestDorkAndTLDBuilder(unittest.TestCase):
    """Tests SearXNG operational dork formulas and country TLD resolutions."""

    def test_get_country_tld(self):
        self.assertEqual(get_country_tld("Pakistan"), "pk")
        self.assertEqual(get_country_tld("United Kingdom"), "co.uk")
        self.assertEqual(get_country_tld("UK"), "co.uk")
        self.assertEqual(get_country_tld("USA"), "com")
        self.assertEqual(get_country_tld("United States"), "com")
        self.assertEqual(get_country_tld("Germany"), "de")
        self.assertEqual(get_country_tld("Canada"), "ca")
        self.assertEqual(get_country_tld("Australia"), "com.au")
        self.assertEqual(get_country_tld("India"), "in")
        self.assertEqual(get_country_tld("United Arab Emirates"), "ae")
        self.assertIsNone(get_country_tld(""))

    def test_dork_construction_pakistan(self):
        dorks = build_searxng_dorks("Textile Fabric Quality Control", "Pakistan")
        self.assertIsInstance(dorks, list)
        self.assertGreaterEqual(len(dorks), 3)

        combined = " ".join(dorks)
        # Verify required operators
        self.assertIn('"Textile Fabric Quality Control"', combined)
        self.assertIn('"Pakistan"', combined)
        self.assertIn('("contact us" OR "about us" OR "our operations")', combined)
        self.assertIn('("hiring" OR "careers" OR "manual process")', combined)
        self.assertIn("site:.pk", combined)

    def test_dork_construction_uk(self):
        dorks = build_searxng_dorks("Commercial HVAC Fleet Dispatch", "United Kingdom")
        combined = " ".join(dorks)
        self.assertIn('"Commercial HVAC Fleet Dispatch"', combined)
        self.assertIn('"United Kingdom"', combined)
        self.assertIn("site:.co.uk", combined)

    def test_dork_construction_usa(self):
        dorks = build_searxng_dorks("Cold Storage Warehouses", "USA")
        combined = " ".join(dorks)
        self.assertIn('"Cold Storage Warehouses"', combined)
        self.assertIn('"USA"', combined)
        self.assertIn('("contact us" OR "about us" OR "our operations")', combined)

    def test_dork_construction_no_country(self):
        dorks = build_searxng_dorks("FMCG Defect Detection & Sorting", "")
        combined = " ".join(dorks)
        self.assertIn('"FMCG Defect Detection & Sorting"', combined)
        self.assertIn('("contact us" OR "about us" OR "our operations")', combined)


class TestDynamicIndustryNicheExpansion(unittest.IsolatedAsyncioTestCase):
    """Tests service mapping accuracy and duplicate prevention."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_file = os.path.join(self.temp_dir.name, "test_niches.json")
        self.tracker = IndustryHistoryTracker(filepath=self.temp_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    async def test_mapping_accuracy_computer_vision(self):
        niches = await generate_target_industry_niches(
            our_services="Computer Vision, Visual Inspection Systems",
            country="Pakistan",
            limit=3,
            tracker=self.tracker,
            use_llm=False
        )
        self.assertIsInstance(niches, list)
        self.assertGreaterEqual(len(niches), 2)

        # Check required keys
        for item in niches:
            self.assertIn("niche", item)
            self.assertIn("parent_industry", item)
            self.assertIn("target_service_fit", item)
            self.assertIn("rationale", item)

        niche_names = [n["niche"] for n in niches]
        has_relevant = any(
            any(k in name.lower() for k in ("textile", "fabric", "pharmaceutical", "packaging", "defect", "inspection", "sorting"))
            for name in niche_names
        )
        self.assertTrue(has_relevant, f"No relevant vision niche found in: {niche_names}")

    async def test_mapping_accuracy_automated_inventory(self):
        niches = await generate_target_industry_niches(
            our_services="Automated Inventory Systems, Warehouse WMS",
            country="USA",
            limit=3,
            tracker=self.tracker,
            use_llm=False
        )
        self.assertIsInstance(niches, list)
        self.assertGreaterEqual(len(niches), 2)

        niche_names = [n["niche"] for n in niches]
        has_relevant = any(
            any(k in name.lower() for k in ("cold storage", "spare parts", "fulfillment", "warehouse", "logistics"))
            for name in niche_names
        )
        self.assertTrue(has_relevant, f"No relevant inventory niche found in: {niche_names}")

    async def test_mapping_accuracy_custom_software(self):
        niches = await generate_target_industry_niches(
            our_services="Web & Mobile App Development, Custom Software",
            limit=3,
            tracker=self.tracker,
            use_llm=False
        )
        self.assertIsInstance(niches, list)
        self.assertGreaterEqual(len(niches), 2)

        niche_names = [n["niche"] for n in niches]
        has_relevant = any(
            any(k in name.lower() for k in ("dispatch", "freight", "hvac", "dental", "construction", "billing"))
            for name in niche_names
        )
        self.assertTrue(has_relevant, f"No relevant software niche found in: {niche_names}")

    async def test_never_repeats_scanned_niches(self):
        # Pre-mark primary vision niche as scanned
        self.tracker.mark_scanned("Textile Fabric Quality Control", "Computer Vision")

        niches = await generate_target_industry_niches(
            our_services="Computer Vision",
            limit=3,
            tracker=self.tracker,
            use_llm=False
        )
        niche_names = [n["niche"] for n in niches]
        self.assertNotIn("Textile Fabric Quality Control", niche_names)

    async def test_live_llm_generation_structure(self):
        # Tests live LLM generation with fallback tolerance
        niches = await generate_target_industry_niches(
            our_services="Robotics Process Automation for Electronics",
            country="Germany",
            limit=2,
            tracker=self.tracker,
            use_llm=True
        )
        self.assertIsInstance(niches, list)
        self.assertGreaterEqual(len(niches), 1)
        self.assertIn("niche", niches[0])
        self.assertIn("parent_industry", niches[0])
        self.assertIn("target_service_fit", niches[0])


class TestGetNextDiscoveryBatch(unittest.IsolatedAsyncioTestCase):
    """Tests the discovery batch coordinator and automatic sequential niche advancement."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_file = os.path.join(self.temp_dir.name, "test_batch.json")
        self.tracker = IndustryHistoryTracker(filepath=self.temp_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    async def test_batch_coordination_and_sequential_advancement(self):
        # Batch 1: Computer Vision in Pakistan
        batch_1 = await get_next_discovery_batch(
            our_services="Computer Vision, Visual AI",
            selected_country="Pakistan",
            mode="target_companies",
            tracker=self.tracker,
            use_llm=False
        )
        self.assertIn("niche", batch_1)
        self.assertIn("queries", batch_1)
        self.assertIn("country_tld", batch_1)
        self.assertEqual(batch_1["country"], "Pakistan")
        self.assertEqual(batch_1["country_tld"], "pk")
        self.assertGreaterEqual(len(batch_1["queries"]), 3)

        niche_1 = batch_1["niche"]
        # Verify niche_1 was recorded as scanned
        self.assertTrue(self.tracker.is_scanned(niche_1))

        # Batch 2: Next call for the same service MUST advance to a different niche
        batch_2 = await get_next_discovery_batch(
            our_services="Computer Vision, Visual AI",
            selected_country="Pakistan",
            mode="target_companies",
            tracker=self.tracker,
            use_llm=False
        )
        niche_2 = batch_2["niche"]
        self.assertTrue(self.tracker.is_scanned(niche_2))
        self.assertNotEqual(niche_1, niche_2, f"Batch 2 returned identical niche '{niche_1}' instead of advancing")


class TestDiscoverIntegrationWithDynamicIndustry(unittest.IsolatedAsyncioTestCase):
    """Tests integration between dynamic_industry_generator and discover.stream_discovery."""

    async def test_stream_discovery_icp_mode(self):
        import discover

        # Mock search provider to avoid actual internet calls
        async def mock_search(query, page=1):
            return [
                {
                    "url": "https://textilelead.com",
                    "title": "TextileLead Mills",
                    "content": "Specialized spinning and weaving quality assurance facility in Lahore.",
                    "author_or_company": "TextileLead Mills",
                    "raw_domain": "textilelead.com"
                }
            ]

        # Mock LLM evaluation to accept lead
        async def mock_eval(**kwargs):
            return {
                "is_junk": False,
                "industry_match": True,
                "lead_type": "NEEDS_SERVICE",
                "confidence": 90,
                "reason": "Textile manufacturing facility with manual defect inspection.",
                "official_company_name": "TextileLead Mills",
                "source": "dynamic-industry-test",
                "detected_country": "Pakistan"
            }

        orig_search = discover.search_searxng_or_ddg
        orig_eval = discover.evaluate_client_fit_dual_engine
        discover.search_searxng_or_ddg = mock_search
        discover.evaluate_client_fit_dual_engine = mock_eval

        try:
            received_events = []
            async for line in discover.stream_discovery(
                keyword="",  # Empty keyword triggers dynamic industry generation from our_services
                country="Pakistan",
                our_services="Computer Vision, Defect Detection",
                mode="target_companies",
                start_page=1,
                target_count=1,
                max_pages=1
            ):
                data = json.loads(line.strip())
                received_events.append(data)

            # Check that start event has dynamic niche fields
            start_events = [e for e in received_events if e.get("type") == "start"]
            self.assertEqual(len(start_events), 1)
            start = start_events[0]
            self.assertIn("dynamicNiche", start)
            self.assertIsNotNone(start["dynamicNiche"])
            self.assertIn("parentIndustry", start)
            self.assertIn("targetServiceFit", start)

            # Check that company event was emitted
            companies = [e for e in received_events if e.get("type") == "company"]
            self.assertGreaterEqual(len(companies), 1)
            self.assertEqual(companies[0]["domain"], "textilelead.com")
        finally:
            discover.search_searxng_or_ddg = orig_search
            discover.evaluate_client_fit_dual_engine = orig_eval


if __name__ == "__main__":
    unittest.main()
