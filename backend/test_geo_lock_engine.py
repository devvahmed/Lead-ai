"""
Comprehensive Test Suite for Strict Local Entity & Country Lock Engine (Step 4).

Tests:
1. Local ccTLD Hard Pass (.pk for Pakistan, .co.uk for UK, .de for Germany, etc.)
2. Foreign ccTLD Hard Rejection (.de, .fr, .co.uk rejected when target is Pakistan)
3. Generic TLD Phone Prefix and Major City Detection (+92 and Lahore on .com -> passes)
4. Generic TLD Foreign Conflict Disqualification (Berlin HQ on .com rejected for Pakistan)
5. Global / Empty Country Bypass Behavior
6. Contextual LLM Geo-Gatekeeper (evaluate_contextual_geo)
7. Discover.py End-to-End Streaming Interception (filtering foreign leads while yielding local leads)
"""

import asyncio
import json
import unittest

from geo_lock_engine import (
    clean_domain_key,
    get_country_profile,
    verify_deterministic_geo,
    evaluate_contextual_geo,
    run_geo_lock_engine,
    COUNTRY_GEO_MAP
)


class TestTier1DeterministicGeoVerifier(unittest.TestCase):
    """Verifies zero-cost deterministic country locking via TLDs, phone numbers, and cities."""

    def test_clean_domain_key(self):
        self.assertEqual(clean_domain_key("https://www.service.com.pk:443/about"), "service.com.pk")
        self.assertEqual(clean_domain_key("http://sub.company.co.uk/contact"), "sub.company.co.uk")
        self.assertEqual(clean_domain_key("www.kuka.de"), "kuka.de")
        self.assertEqual(clean_domain_key("acmecorp.com"), "acmecorp.com")

    def test_country_profile_resolution(self):
        self.assertEqual(get_country_profile("Pakistan")["iso_code"], "PK")
        self.assertEqual(get_country_profile("pk")["iso_code"], "PK")
        self.assertEqual(get_country_profile("UK")["iso_code"], "GB")
        self.assertEqual(get_country_profile("Great Britain")["iso_code"], "GB")
        self.assertEqual(get_country_profile("USA")["iso_code"], "US")
        self.assertEqual(get_country_profile("UAE")["iso_code"], "AE")
        self.assertEqual(get_country_profile("Dubai")["iso_code"], "AE")
        self.assertEqual(get_country_profile("Germany")["iso_code"], "DE")
        self.assertEqual(get_country_profile("Saudi Arabia")["iso_code"], "SA")

    def test_local_tld_hard_pass(self):
        local_cases = [
            ("interloop.com.pk", "Pakistan", ".com.pk"),
            ("millat.pk", "Pakistan", ".pk"),
            ("rolls-royce.co.uk", "United Kingdom", ".co.uk"),
            ("bbc.uk", "UK", ".uk"),
            ("bmw.de", "Germany", ".de"),
            ("emirates.ae", "UAE", ".ae"),
            ("aramco.com.sa", "Saudi Arabia", ".com.sa"),
            ("telstra.com.au", "Australia", ".com.au"),
            ("tcs.co.in", "India", ".co.in"),
            ("shopify.ca", "Canada", ".ca"),
        ]
        for domain, country, expected_tld in local_cases:
            is_local, reason, conf = verify_deterministic_geo(domain=domain, target_country=country)
            self.assertTrue(is_local, f"Failed local TLD hard pass for {domain} in {country}")
            self.assertEqual(conf, 1.0)
            self.assertIn(expected_tld, reason)

    def test_foreign_tld_hard_rejection(self):
        foreign_cases = [
            ("siemens.de", "Pakistan", "Germany"),
            ("airbus.fr", "Pakistan", "France"),
            ("dyson.co.uk", "Pakistan", "United Kingdom"),
            ("volkswagen.de", "United Kingdom", "Germany"),
            ("renault.fr", "Germany", "France"),
            ("tata.in", "United States", "India"),
            ("atlassian.com.au", "United States", "Australia"),
            ("samsung.de", "Saudi Arabia", "Germany"),
        ]
        for domain, target_country, foreign_nation in foreign_cases:
            is_local, reason, conf = verify_deterministic_geo(domain=domain, target_country=target_country)
            self.assertFalse(is_local, f"Failed foreign TLD disqualification for {domain} in {target_country}")
            self.assertEqual(conf, 0.0)
            self.assertIn("Foreign ccTLD disqualification", reason)
            self.assertIn(foreign_nation, reason)

    def test_generic_tld_with_local_phone_and_city(self):
        # 1. Pakistan on .com
        pk_text = (
            "Welcome to Master Textile Mills Ltd. Established in 1985 in Lahore, Pakistan, "
            "we are a premier vertically integrated manufacturing unit. "
            "Head office: 12-KM Raiwind Road, Lahore. Telephone: +92 42 35391200 or mobile: 0300-8451234. "
            "Contact our sales department for global export inquiries."
        )
        is_local, reason, conf = verify_deterministic_geo(
            domain="mastertextiles.com",
            text_content=pk_text,
            target_country="Pakistan"
        )
        self.assertTrue(is_local, f"Expected local verification: {reason}")
        self.assertGreaterEqual(conf, 0.7)
        self.assertIn("Lahore", reason)

        # 2. United Kingdom on .io
        uk_text = (
            "Fintech Dynamics Ltd is an authorized electronic money institution registered in England. "
            "Our headquarters are located at 25 Bank Street, Canary Wharf, London, United Kingdom. "
            "Direct line: +44 20 7946 0199. Regulated by the Financial Conduct Authority."
        )
        is_local, reason, conf = verify_deterministic_geo(
            domain="fintechdynamics.io",
            text_content=uk_text,
            target_country="United Kingdom"
        )
        self.assertTrue(is_local, f"Expected UK local verification: {reason}")
        self.assertGreaterEqual(conf, 0.7)
        self.assertIn("London", reason)

        # 3. United States on .net
        us_text = (
            "Midwest Precision Machining is a certified aerospace fabrication shop based in Chicago, Illinois. "
            "Facility: 4400 West Ohio Street, Chicago, United States. Call +1 (312) 555-0144 to request an RFQ."
        )
        is_local, reason, conf = verify_deterministic_geo(
            domain="midwestmachining.net",
            text_content=us_text,
            target_country="United States"
        )
        self.assertTrue(is_local, f"Expected US local verification: {reason}")
        self.assertGreaterEqual(conf, 0.7)
        self.assertIn("Chicago", reason)

    def test_generic_tld_with_foreign_conflict(self):
        # Target is Pakistan, but .com content explicitly says Headquarters in Berlin, Germany with German phone
        german_text = (
            "KUKA Systems is an international automation specialist. "
            "Our corporate headquarters in Germany coordinates all European manufacturing operations. "
            "Visit our central facility in Augsburg or contact our central office."
        )
        is_local, reason, conf = verify_deterministic_geo(
            domain="kuka-robotics.com",
            text_content=german_text,
            target_country="Pakistan"
        )
        self.assertFalse(is_local)
        self.assertEqual(conf, 0.0)
        self.assertIn("foreign headquarters", reason.lower())


class TestTier2ContextualGeoClassifier(unittest.IsolatedAsyncioTestCase):
    """Verifies contextual LLM and heuristic geo-gatekeeper."""

    async def test_contextual_geo_local_entity(self):
        local_text = (
            "Crescent Bahuman Limited is Pakistan's first vertically integrated denim facility. "
            "Operating in Pindi Bhattian and Lahore with administrative offices in Karachi."
        )
        res = await evaluate_contextual_geo(
            domain="crescentbahuman.com",
            page_text=local_text,
            target_country="Pakistan",
            use_llm=False
        )
        self.assertIsInstance(res, dict)
        self.assertTrue(res["is_local_entity"])
        self.assertEqual(res["detected_country"], "Pakistan")

    async def test_contextual_geo_foreign_entity(self):
        foreign_text = (
            "Acme Automation Inc is an Ohio-based provider of robotic packaging lines for North America. "
            "Serving automotive clients across the United States with locations in Cleveland and Detroit."
        )
        res = await evaluate_contextual_geo(
            domain="acmeautomation.com",
            page_text=foreign_text,
            target_country="Pakistan",
            use_llm=False
        )
        self.assertIsInstance(res, dict)
        self.assertFalse(res["is_local_entity"])


class TestRunGeoLockEnginePipeline(unittest.IsolatedAsyncioTestCase):
    """Verifies end-to-end multi-tier geo lock execution."""

    async def test_global_or_empty_country_bypassed(self):
        is_valid, reason = await run_geo_lock_engine(
            domain="randomcompany.com",
            target_country="",
            use_llm=False
        )
        self.assertTrue(is_valid)
        self.assertIn("bypassed", reason)

        is_valid, reason = await run_geo_lock_engine(
            domain="randomcompany.com",
            target_country="Global",
            use_llm=False
        )
        self.assertTrue(is_valid)
        self.assertIn("bypassed", reason)

    async def test_local_cctld_passes_pipeline(self):
        is_valid, reason = await run_geo_lock_engine(
            domain="engro.com.pk",
            target_country="Pakistan",
            use_llm=False
        )
        self.assertTrue(is_valid)
        self.assertIn("[Tier 1 Deterministic Geo]", reason)
        self.assertIn(".com.pk", reason)

    async def test_foreign_cctld_rejected_pipeline(self):
        is_valid, reason = await run_geo_lock_engine(
            domain="daimler.de",
            target_country="Pakistan",
            use_llm=False
        )
        self.assertFalse(is_valid)
        self.assertIn("[Tier 1 Deterministic Geo]", reason)
        self.assertIn("Foreign ccTLD disqualification", reason)

    async def test_generic_tld_local_passes_pipeline(self):
        pk_content = (
            "Lucky Cement Limited is the flagship company of YB Group. "
            "Registered office: Main Clifton, Karachi, Pakistan. Call: +92 21 35878601. "
            "Operating production plants in Pezu and Karachi."
        )
        is_valid, reason = await run_geo_lock_engine(
            domain="lucky-cement.com",
            text_content=pk_content,
            target_country="Pakistan",
            use_llm=False
        )
        self.assertTrue(is_valid)
        self.assertIn("Karachi", reason)


class TestDiscoverIntegrationWithGeoLock(unittest.IsolatedAsyncioTestCase):
    """Verifies that discover.py pre-scrape and post-scrape gates drop foreign leads when country is locked."""

    async def test_discover_geo_lock_interception(self):
        import discover

        # Mock search provider returning:
        # 1. Foreign ccTLD (siemens.de) -> should be blocked by pre-scrape or post-scrape geo gate
        # 2. Foreign generic .com (detroitmachining.com) -> should be blocked by post-scrape geo gate
        # 3. Genuine local entity (interloop-pk.com) -> should pass and get emitted
        async def mock_search(query, page=1):
            return [
                {
                    "url": "https://siemens.de/automation",
                    "title": "Siemens Germany Automation",
                    "content": "German industrial engineering and automation manufacturer.",
                    "raw_domain": "siemens.de"
                },
                {
                    "url": "https://detroitmachining.com",
                    "title": "Detroit Machining Corp",
                    "content": "Specializing in automotive CNC tooling in Detroit, United States.",
                    "raw_domain": "detroitmachining.com"
                },
                {
                    "url": "https://interloop-pk.com",
                    "title": "Interloop Limited",
                    "content": "Premier multi-category manufacturing plant based in Faisalabad, Pakistan. Operations in Lahore and Karachi.",
                    "raw_domain": "interloop-pk.com"
                }
            ]

        async def mock_scrape(url, timeout=4.0):
            if "detroitmachining.com" in url:
                return (
                    "Welcome to Detroit Machining Corporation. We are an ISO 9001 certified CNC tooling and machining facility "
                    "specializing in heavy metal stamping, multi-axis milling, and rapid prototyping for Tier 1 automotive suppliers. "
                    "Our corporate headquarters and production facilities are based in Detroit, United States, coordinating supply operations across North America. "
                    "Contact our engineering division at sales@detroitmachining.com or call +1 313 555 0199 for customized quotes, equipment tooling, and industrial fabrication solutions.",
                    "homepage + /about"
                )
            elif "interloop-pk.com" in url:
                return (
                    "Welcome to Interloop Limited. We are one of the world's largest vertically integrated textile and hosiery manufacturing powerhouses. "
                    "Headquartered in Faisalabad, Pakistan, with expansive operational plants, spinning mills, and research facilities located across Lahore and Karachi. "
                    "Our operations employ over twenty-five thousand personnel, producing high-performance garments for leading global athletic brands. "
                    "Contact our commercial team at info@interloop-pk.com or call +92 41 4567890 to request quotes and explore our industrial manufacturing capabilities.",
                    "homepage + /about"
                )
            return ("Empty content", "homepage")

        async def mock_eval(**kwargs):
            return {
                "is_junk": False,
                "industry_match": True,
                "lead_type": "NEEDS_SERVICE",
                "confidence": 90,
                "reason": "Qualified industrial manufacturing client.",
                "official_company_name": "Interloop Limited",
                "source": "geo-lock-test",
                "detected_country": "Pakistan"
            }

        orig_search = discover.search_searxng_or_ddg
        orig_scrape = discover.fetch_url_content_with_subpages
        orig_eval = discover.evaluate_client_fit_dual_engine

        discover.search_searxng_or_ddg = mock_search
        discover.fetch_url_content_with_subpages = mock_scrape
        discover.evaluate_client_fit_dual_engine = mock_eval

        try:
            received_events = []
            async for line in discover.stream_discovery(
                keyword="Textile",
                country="Pakistan",
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
            # The only yielded company MUST be interloop-pk.com; siemens.de and detroitmachining.com must be dropped
            self.assertEqual(companies[0]["domain"], "interloop-pk.com")
            domains_emitted = [c["domain"] for c in companies]
            self.assertNotIn("siemens.de", domains_emitted)
            self.assertNotIn("detroitmachining.com", domains_emitted)
        finally:
            discover.search_searxng_or_ddg = orig_search
            discover.fetch_url_content_with_subpages = orig_scrape
            discover.evaluate_client_fit_dual_engine = orig_eval


if __name__ == "__main__":
    unittest.main()
