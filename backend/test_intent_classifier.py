"""
Comprehensive Test Suite for Strict Buyer Intent & Non-Job Contract Classifier (Step 5).

Tests:
1. Rejection of seller agency copy ("We are a web dev agency", "hire our team", "our portfolio")
2. Rejection of 9-to-5 salaried job ads ("$140k salary", "401k match", "health insurance", "W2")
3. Approval of contract buyer requests ("looking for an agency", "seeking vendor", "RFP", "fixed rate")
4. Approval of commercial target entities (factories, manufacturing facilities, warehouses)
5. Tier 2 Contextual Intent Gatekeeper (evaluate_contextual_intent)
6. Discover.py End-to-End Streaming Interception (filtering sellers & 9-to-5 jobs while yielding genuine buyers)
"""

import asyncio
import json
import unittest

from intent_classifier import (
    classify_intent_deterministic,
    evaluate_contextual_intent,
    run_intent_classifier
)


class TestTier1DeterministicIntentClassifier(unittest.TestCase):
    """Verifies zero-cost deterministic pattern filtering of sellers, 9-to-5 jobs, and contract buyers."""

    def test_seller_agency_rejection(self):
        seller_posts = [
            (
                "Top Web & Mobile App Development Agency",
                "We are a web development agency specializing in Next.js, React, and Node.js. "
                "Hire our team of senior full-stack developers. Check out our portfolio and client roster. "
                "Book a discovery call with us today to start your project!"
            ),
            (
                "[FOR HIRE] Full-Stack Developer & UI/UX Designer",
                "Available for hire! I have 8+ years experience building mobile applications. "
                "My portfolio includes fintech and e-commerce platforms. Offering freelance services at competitive rates."
            ),
            (
                "Custom Software Solutions Provider",
                "We are a leading provider of custom software development services. "
                "Hire our engineers to scale your engineering team quickly. Our clients include Fortune 500 brands."
            )
        ]
        for title, text in seller_posts:
            is_buyer, intent_type, conf = classify_intent_deterministic(text_content=text, title=title)
            self.assertFalse(is_buyer, f"Expected seller rejection for: {title}")
            self.assertEqual(intent_type, "SELLER_AGENCY")
            self.assertGreaterEqual(conf, 0.9)

    def test_standard_9to5_job_rejection(self):
        job_posts = [
            (
                "[HIRING] Senior Full-Stack Engineer",
                "Acme Corp is hiring a full-time employee for our backend platform. "
                "Compensation: $140,000 - $160,000 annual salary. Benefits include 401k match, "
                "comprehensive health insurance, dental benefits, and 20 days paid time off (PTO). "
                "This is a W2 position on-site 5 days a week in Boston."
            ),
            (
                "Lead DevOps Engineer (W-2 Only)",
                "We are seeking a full-time engineer to manage our Kubernetes infrastructure. "
                "Base salary of $150,000 per year plus 401(k) matching and medical, dental, and vision insurance. "
                "Must be eligible to work on W2."
            ),
            (
                "Software Architect - Enterprise Platforms",
                "Join our corporate team as a full-time employee. We offer competitive annual salary, "
                "401k plan, life insurance policy, and sick leave days."
            )
        ]
        for title, text in job_posts:
            is_buyer, intent_type, conf = classify_intent_deterministic(text_content=text, title=title)
            self.assertFalse(is_buyer, f"Expected 9-to-5 job rejection for: {title}")
            self.assertEqual(intent_type, "STANDARD_EMPLOYMENT_JOB")
            self.assertGreaterEqual(conf, 0.9)

    def test_contract_buyer_approval(self):
        buyer_posts = [
            (
                "[HIRING] Looking for an agency to build our warehouse ERP",
                "We are looking for an agency or vendor to develop a custom supply chain portal. "
                "This is on a project basis with a fixed rate budget of $45,000. "
                "Request for Proposals (RFP) and detailed statement of work (SOW) available upon request."
            ),
            (
                "Seeking vendor for mobile application redesign",
                "Our retail group is seeking an external vendor or engineering firm for an end-to-end mobile redesign. "
                "Subcontractor agreement on a fixed-price contract. Please submit your vendor application."
            ),
            (
                "Contractor needed for computer vision defect detection line",
                "Contract opportunity: We are seeking an experienced contractor or specialized firm to integrate "
                "automated visual quality control on our factory assembly line. Outsource development on project basis."
            )
        ]
        for title, text in buyer_posts:
            is_buyer, intent_type, conf = classify_intent_deterministic(text_content=text, title=title)
            self.assertTrue(is_buyer, f"Expected contract buyer approval for: {title}")
            self.assertEqual(intent_type, "CONTRACT_BUYER")
            self.assertGreaterEqual(conf, 0.8)

    def test_commercial_target_approval(self):
        commercial_sites = [
            (
                "Precision Valve & Fluid Controls Inc",
                "Welcome to Precision Valve. Our manufacturing facilities encompass over 120,000 square feet "
                "of heavy fabrication and cleanroom space. We manufacture high-pressure industrial solutions and "
                "turnkey systems for chemical processing plants. ISO 9001 certified. Request pricing or quote from our sales division."
            ),
            (
                "Apex Cold Storage & Multimodal Logistics",
                "Apex Logistics operates temperature-controlled warehouse facilities and an automated fleet across North America. "
                "Our operations optimize refrigerated supply chain handling. Request pricing or quote for warehousing services."
            )
        ]
        for title, text in commercial_sites:
            is_buyer, intent_type, conf = classify_intent_deterministic(text_content=text, title=title)
            self.assertTrue(is_buyer, f"Expected commercial target approval for: {title}")
            self.assertEqual(intent_type, "COMMERCIAL_TARGET")
            self.assertGreaterEqual(conf, 0.75)


class TestTier2ContextualIntentClassifier(unittest.IsolatedAsyncioTestCase):
    """Verifies contextual LLM and heuristic intent gatekeeper."""

    async def test_contextual_contract_buyer(self):
        text = (
            "We are modernizing our internal warehouse operations and need an external engineering shop "
            "to construct our API middleware on a project contract."
        )
        res = await evaluate_contextual_intent(
            title="Warehouse API Modernization",
            text_content=text,
            target_service="Software Engineering",
            use_llm=False
        )
        self.assertIsInstance(res, dict)
        self.assertTrue(res["is_valid_buyer"])
        self.assertEqual(res["intent_type"], "CONTRACT_BUYER")

    async def test_contextual_seller_agency(self):
        text = (
            "We are a web development agency with decades of combined experience building cloud apps. "
            "Hire our team to take your idea to market quickly."
        )
        res = await evaluate_contextual_intent(
            title="Expert Web & Mobile Team",
            text_content=text,
            target_service="Web Development",
            use_llm=False
        )
        self.assertIsInstance(res, dict)
        self.assertFalse(res["is_valid_buyer"])
        self.assertEqual(res["intent_type"], "SELLER_AGENCY")

    async def test_contextual_employment_job(self):
        text = (
            "Seeking a Staff Developer. Annual salary $165,000 with 401k and complete health insurance. "
            "Candidate must work on W2."
        )
        res = await evaluate_contextual_intent(
            title="Staff Developer Opening",
            text_content=text,
            target_service="Engineering",
            use_llm=False
        )
        self.assertIsInstance(res, dict)
        self.assertFalse(res["is_valid_buyer"])
        self.assertEqual(res["intent_type"], "STANDARD_EMPLOYMENT_JOB")


class TestRunIntentClassifierPipeline(unittest.IsolatedAsyncioTestCase):
    """Verifies end-to-end unified intent classifier execution."""

    async def test_pipeline_rejects_seller_agency(self):
        is_valid, intent_type, reason = await run_intent_classifier(
            title="Top Digital Agency",
            text_content="We are a web development agency. Hire our team for your next React app. Our portfolio speaks for itself.",
            use_llm=False
        )
        self.assertFalse(is_valid)
        self.assertEqual(intent_type, "SELLER_AGENCY")
        self.assertIn("Seller Agency", reason)

    async def test_pipeline_rejects_9to5_job(self):
        is_valid, intent_type, reason = await run_intent_classifier(
            title="Senior Engineer",
            text_content="Full-time employee position. $130,000 annual salary with 401k match, health insurance, and 15 days PTO on W2.",
            use_llm=False
        )
        self.assertFalse(is_valid)
        self.assertEqual(intent_type, "STANDARD_EMPLOYMENT_JOB")
        self.assertIn("Standard Employment Job", reason)

    async def test_pipeline_approves_contract_buyer(self):
        is_valid, intent_type, reason = await run_intent_classifier(
            title="ERP Migration RFP",
            text_content="Looking for an agency to execute our cloud ERP migration on a fixed rate project basis. Statement of work attached.",
            use_llm=False
        )
        self.assertTrue(is_valid)
        self.assertEqual(intent_type, "CONTRACT_BUYER")
        self.assertIn("Contract Buyer", reason)


class TestDiscoverIntegrationWithIntentClassifier(unittest.IsolatedAsyncioTestCase):
    """Verifies that discover.py drops competing seller agencies and 9-to-5 jobs while yielding genuine buyers."""

    async def test_discover_intent_interception(self):
        import discover

        # Mock search provider returning:
        # Mock search provider returning:
        # 1. Competing Seller Agency (devshop.com) -> should be blocked by intent classifier
        # 2. 9-to-5 Salaried Job Posting (corpstaff.com) -> should be blocked by intent classifier
        # 3. Genuine Commercial Buyer (logisticsflow.com) -> should pass and get emitted
        async def mock_search(query, page=1):
            return [
                {
                    "url": "https://devshop.com",
                    "title": "DevShop Global Software Agency",
                    "content": "We are a web development agency. Hire our team for React, Node, and Python engineering. View our portfolio.",
                    "raw_domain": "devshop.com"
                },
                {
                    "url": "https://corpstaff.com/open-roles/lead-eng",
                    "title": "Lead Software Engineer ($150k + 401k)",
                    "content": "Full-time employee role offering $150,000 annual salary, 401k match, health insurance, and PTO on a W2.",
                    "raw_domain": "corpstaff.com"
                },
                {
                    "url": "https://logisticsflow.com",
                    "title": "LogisticsFlow Supply Chain Systems",
                    "content": "Looking for an agency or vendor to upgrade our automated distribution sorting lines on a project basis. SOW available.",
                    "raw_domain": "logisticsflow.com"
                }
            ]

        async def mock_scrape(url, timeout=4.0):
            if "devshop.com" in url:
                return (
                    "Welcome to DevShop Global Software Agency. We are a web development agency and mobile engineering firm "
                    "specializing in full-cycle enterprise software development, modern UI/UX design, and cloud migrations. "
                    "Hire our team of expert developers for custom software, React Native mobile apps, Node.js backend systems, "
                    "and scalable cloud infrastructure. Our portfolio includes over 100 enterprise projects across North America and Europe. "
                    "We provide dedicated engineering squads, staff augmentation, and offshore development services to fast-growing technology startups. "
                    "Check out our case studies to see how our engineering team has helped clients achieve scale. "
                    "Book a discovery call with our technical directors today to get started on your upcoming software initiative.",
                    "homepage + /about"
                )
            elif "corpstaff.com" in url:
                return (
                    "Career Opportunity: Lead Software Engineer. We are seeking a full-time employee for our backend platform team. "
                    "Compensation: $150,000 annual salary, 401k match, comprehensive health insurance, dental benefits, vision care, and paid time off (PTO). "
                    "Candidates must be eligible for W2 employment and work on-site 5 days a week at our corporate headquarters in Chicago. "
                    "We offer exceptional company perks including 401(k) matching up to 6 percent, generous annual bonuses, and continuous medical coverage. "
                    "Submit your resume and cover letter directly to our human resources talent acquisition team.",
                    "homepage + /open-roles"
                )
            elif "logisticsflow.com" in url:
                return (
                    "LogisticsFlow is a commercial freight distribution and warehouse operating firm. "
                    "Our facilities manage cross-docking and cold chain fulfillment across twenty regional hubs. "
                    "Procurement notice: We are looking for an agency or engineering contractor to build an automated dispatch tracking system. "
                    "Statement of work and RFP documentation available. Contract will be awarded on a project basis with a fixed rate budget. "
                    "Contact our procurement division at vendors@logisticsflow.com.",
                    "homepage + /rfp"
                )
            return ("Empty content", "homepage")

        async def mock_eval(**kwargs):
            return {
                "is_junk": False,
                "industry_match": True,
                "lead_type": "NEEDS_SERVICE",
                "confidence": 92,
                "reason": "Commercial logistics operator with active RFP for automated software.",
                "official_company_name": "LogisticsFlow Supply Chain Systems",
                "source": "intent-classifier-test",
                "detected_country": "Global"
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
                keyword="Logistics",
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
            # The only yielded company MUST be logisticsflow.com; devshop.com and jobboard.com must be dropped
            self.assertEqual(companies[0]["domain"], "logisticsflow.com")
            domains_emitted = [c["domain"] for c in companies]
            self.assertNotIn("devshop.com", domains_emitted)
            self.assertNotIn("corpstaff.com", domains_emitted)
        finally:
            discover.search_searxng_or_ddg = orig_search
            discover.fetch_url_content_with_subpages = orig_scrape
            discover.evaluate_client_fit_dual_engine = orig_eval


if __name__ == "__main__":
    unittest.main()
