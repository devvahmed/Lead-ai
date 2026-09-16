"""
Comprehensive Test Suite for Service-Agnostic Operational Bottleneck Audit Engine (Step 7).

Tests:
1. Tier 1 Deterministic Extraction across all 5 operational categories:
   - MANUAL_QUALITY_CONTROL
   - REPETITIVE_DATA_ENTRY
   - LEGACY_SOFTWARE_DISPATCH
   - HIGH_LABOR_TURNOVER_HIRING
   - UNAUTOMATED_INVENTORY_FLOW
2. Context windowing and verbatim snippet extraction (150-char window with ellipsis).
3. Tier 2 LLM Operational Audit parsing and fallback heuristic synthesis.
4. Unified audit_company_operations for both positive (bottleneck present) and negative (clean automated entity) cases.
5. Integration with discover.py streaming pipeline ensuring operational audit fields are attached to company events.
"""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from operational_audit_engine import (
    OperationalInefficiencyCategory,
    extract_deterministic_bottlenecks,
    run_llm_operational_audit,
    audit_company_operations
)


class TestTier1DeterministicBottlenecks(unittest.TestCase):
    """Verifies regex/keyword pattern extraction of operational bottlenecks."""

    def test_manual_quality_control_detection(self):
        text = (
            "Apex Industrial Machining operates heavy fabrication lines in Chicago. "
            "Our QA supervisors perform manual inspection of each machined valve across three shifts "
            "to ensure zero defect tolerance before palletizing and customer dispatch."
        )
        signals = extract_deterministic_bottlenecks(text)
        self.assertGreaterEqual(len(signals), 1)
        top = signals[0]
        self.assertEqual(top["category"], OperationalInefficiencyCategory.MANUAL_QUALITY_CONTROL.value)
        self.assertIn("manual inspection", top["keyword"].lower())
        self.assertIn("valve", top["evidence_snippet"].lower())
        self.assertGreaterEqual(top["confidence"], 0.85)

    def test_repetitive_data_entry_detection(self):
        text = (
            "Logistics coordination requires fast turnaround. Our warehouse receiving operators "
            "fill out a paper form and log shipping manifests into an excel sheet before cross-docking."
        )
        signals = extract_deterministic_bottlenecks(text)
        self.assertGreaterEqual(len(signals), 1)
        cats = [s["category"] for s in signals]
        self.assertIn(OperationalInefficiencyCategory.REPETITIVE_DATA_ENTRY.value, cats)
        snippet = next(s["evidence_snippet"] for s in signals if s["category"] == OperationalInefficiencyCategory.REPETITIVE_DATA_ENTRY.value)
        self.assertTrue("paper form" in snippet.lower() or "excel sheet" in snippet.lower())

    def test_legacy_software_dispatch_detection(self):
        text = (
            "Our distribution network covers the Midwest. Prospective clients must call for booking "
            "or contact our central phone dispatch desk between 8am and 5pm to arrange freight loading."
        )
        signals = extract_deterministic_bottlenecks(text)
        self.assertGreaterEqual(len(signals), 1)
        cats = [s["category"] for s in signals]
        self.assertIn(OperationalInefficiencyCategory.LEGACY_SOFTWARE_DISPATCH.value, cats)

    def test_high_labor_turnover_detection(self):
        text = (
            "Due to rapid expansion across our fulfillment centers, we are urgently hiring manual laborers "
            "and packaging assistants for immediate start at our central distribution hub."
        )
        signals = extract_deterministic_bottlenecks(text)
        self.assertGreaterEqual(len(signals), 1)
        cats = [s["category"] for s in signals]
        self.assertIn(OperationalInefficiencyCategory.HIGH_LABOR_TURNOVER_HIRING.value, cats)

    def test_unautomated_inventory_flow_detection(self):
        text = (
            "Cold chain operations require constant monitoring. Our facility staff conduct physical inventory count "
            "and record stock tallies in the central stock ledger every morning."
        )
        signals = extract_deterministic_bottlenecks(text)
        self.assertGreaterEqual(len(signals), 1)
        cats = [s["category"] for s in signals]
        self.assertIn(OperationalInefficiencyCategory.UNAUTOMATED_INVENTORY_FLOW.value, cats)

    def test_clean_context_window_snippet_extraction(self):
        long_text = "Intro words. " * 30 + "Our line staff perform manual inspection of metal parts daily. " + "Outro words. " * 30
        signals = extract_deterministic_bottlenecks(long_text, context_window=120)
        self.assertGreaterEqual(len(signals), 1)
        snippet = signals[0]["evidence_snippet"]
        self.assertTrue(snippet.startswith("..."))
        self.assertTrue(snippet.endswith("..."))
        self.assertIn("manual inspection", snippet)
        self.assertLess(len(snippet), 200)


class TestTier2LLMOperationalAuditor(unittest.IsolatedAsyncioTestCase):
    """Verifies LLM analysis and heuristic fallback synthesis."""

    async def test_llm_operational_audit_heuristic_fallback(self):
        text = (
            "Our assembly technicians execute visual inspection on all circuit boards. "
            "Any defective units are manually re-routed to rework stations."
        )
        signals = extract_deterministic_bottlenecks(text)
        audit_res = await run_llm_operational_audit(
            domain="circuitcorp.com",
            multi_page_text=text,
            target_service="Computer Vision Quality Inspection",
            deterministic_signals=signals,
            use_llm=False  # Test fallback heuristic
        )
        self.assertTrue(audit_res["has_operational_bottleneck"])
        self.assertEqual(audit_res["bottleneck_category"], OperationalInefficiencyCategory.MANUAL_QUALITY_CONTROL.value)
        self.assertEqual(audit_res["severity"], "HIGH")
        self.assertIn("visual inspection", audit_res["evidence_quote"].lower())
        self.assertTrue(len(audit_res["workflow_gap_summary"]) > 10)
        self.assertTrue(len(audit_res["proposed_solution_angle"]) > 10)

    async def test_llm_operational_audit_no_bottleneck(self):
        clean_text = (
            "CloudFlow is a modern serverless platform. Our microservices scale automatically "
            "with zero maintenance. Everything is monitored continuously via automated telemetry."
        )
        signals = extract_deterministic_bottlenecks(clean_text)
        audit_res = await run_llm_operational_audit(
            domain="cloudflow.io",
            multi_page_text=clean_text,
            target_service="DevOps",
            deterministic_signals=signals,
            use_llm=False
        )
        self.assertFalse(audit_res["has_operational_bottleneck"])
        self.assertIsNone(audit_res["bottleneck_category"])
        self.assertEqual(audit_res["severity"], "LOW")
        self.assertEqual(audit_res["evidence_quote"], "")


class TestUnifiedOperationalAuditEngine(unittest.IsolatedAsyncioTestCase):
    """Verifies end-to-end audit_company_operations."""

    async def test_audit_company_operations_manual_qa_found(self):
        multi_page_text = (
            "[PAGE: Homepage] (/)\n"
            "Welcome to Sterling Textiles. We manufacture export-grade denim and twill fabrics.\n\n"
            "--- [PAGE: Operations] (/facilities) ---\n"
            "Quality Assurance: Our quality controllers manually inspect each fabric roll across 3 shifts, "
            "checking for thread defects and dye inconsistencies before final packing.\n\n"
            "--- [PAGE: Contact] (/contact) ---\n"
            "Mills located in Faisalabad, Pakistan. Phone: +92 41 5550100."
        )
        res = await audit_company_operations(
            domain="sterlingtextiles.pk",
            multi_page_text=multi_page_text,
            target_service="Computer Vision Defect Detection",
            use_llm=False
        )
        self.assertTrue(res["has_operational_bottleneck"])
        self.assertEqual(res["bottleneck_category"], OperationalInefficiencyCategory.MANUAL_QUALITY_CONTROL.value)
        self.assertIn("manually inspect", res["evidence_quote"].lower())
        self.assertIn("defect", res["workflow_gap_summary"].lower())
        self.assertIn("computer vision", res["proposed_solution_angle"].lower())
        self.assertGreaterEqual(res["deterministic_signals_count"], 1)

    async def test_audit_company_operations_paper_entry_found(self):
        multi_page_text = (
            "[PAGE: Operations] (/dispatch)\n"
            "Drivers submit physical paperwork and handwritten manifests at the security gate. "
            "Dispatchers complete manual spreadsheet entry into our central ledger before releases."
        )
        res = await audit_company_operations(
            domain="quickhaul.com",
            multi_page_text=multi_page_text,
            target_service="Custom Warehouse ERP",
            use_llm=False
        )
        self.assertTrue(res["has_operational_bottleneck"])
        self.assertEqual(res["bottleneck_category"], OperationalInefficiencyCategory.REPETITIVE_DATA_ENTRY.value)
        self.assertTrue(
            "handwritten" in res["evidence_quote"].lower() or "manual spreadsheet" in res["evidence_quote"].lower()
        )

    async def test_audit_company_operations_clean_negative(self):
        text = "Fully automated industrial laser cutting with digital CAD/CAM feeds."
        res = await audit_company_operations(
            domain="precisionlasers.com",
            multi_page_text=text,
            target_service="Software Engineering",
            use_llm=False
        )
        self.assertFalse(res["has_operational_bottleneck"])
        self.assertIsNone(res["bottleneck_category"])


class TestDiscoverIntegrationWithOperationalAudit(unittest.IsolatedAsyncioTestCase):
    """Verifies that discover.py attaches operational audit fields to emitted company events."""

    async def test_discover_pipeline_attaches_operational_audit(self):
        import discover

        # Mock search returning a candidate
        async def mock_search(query, page=1):
            return [
                {
                    "url": "https://sterlingtextiles.pk",
                    "title": "Sterling Textiles Mill | Export Quality Fabrics",
                    "content": "Leading textile production facility with manual fabric inspection procedures.",
                    "raw_domain": "sterlingtextiles.pk"
                }
            ]

        # Mock crawler returning multi-page text containing operational bottleneck
        async def mock_smart_crawl(**kwargs):
            return {
                "combined_text": (
                    "[PAGE: Homepage] (/)\n"
                    "Welcome to Sterling Textiles Mills. We are a premier commercial textile manufacturer producing export-grade denim and twill in Pakistan. "
                    "Our modern weaving mills operate high-speed rapier looms and air-jet spinning equipment to fulfill wholesale fabric orders worldwide.\n\n"
                    "--- [PAGE: Operations] (/operations) ---\n"
                    "Production Line Quality Control: Our QA supervisors perform manual inspection on all fabric bolts across three daily shifts. "
                    "Manual visual checks are conducted on rolling inspection tables to identify thread defects and dye variations prior to container loading.\n\n"
                    "--- [PAGE: Contact] (/contact) ---\n"
                    "Headquarters and manufacturing plants located on Jhang Road, Faisalabad, Pakistan. Contact our export sales division at info@sterlingtextiles.pk."
                ),
                "source_label": "homepage + /operations + /contact",
                "homepage_text": "Sterling Textiles produces export-grade fabrics.",
                "pages": {"homepage": {}, "operations": {}, "contact": {}},
                "dom_links": {},
                "categorized_targets": {},
                "total_pages_crawled": 3
            }

        async def mock_eval(**kwargs):
            return {
                "is_junk": False,
                "industry_match": True,
                "lead_type": "NEEDS_SERVICE",
                "confidence": 92,
                "reason": "Textile fabric manufacturing plant in Pakistan.",
                "official_company_name": "Sterling Textiles Mills",
                "source": "operational-audit-test",
                "detected_country": "Pakistan"
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
                keyword="Textile",
                mode="direct_search",
                country="Pakistan",
                start_page=1,
                target_count=1,
                max_pages=1
            ):
                data = json.loads(line.strip())
                received_events.append(data)

            companies = [e for e in received_events if e.get("type") == "company"]
            self.assertEqual(len(companies), 1)
            comp = companies[0]

            # Verify presence of Step 7 operational audit fields
            self.assertIn("operationalAudit", comp)
            self.assertIn("hasOperationalBottleneck", comp)
            self.assertIn("bottleneckCategory", comp)
            self.assertIn("evidenceQuote", comp)
            self.assertIn("workflowGapSummary", comp)
            self.assertIn("proposedSolutionAngle", comp)

            # Check that bottleneck was detected
            self.assertTrue(comp["hasOperationalBottleneck"])
            self.assertEqual(comp["bottleneckCategory"], "MANUAL_QUALITY_CONTROL")
            self.assertIn("manual inspection", comp["evidenceQuote"].lower())
            self.assertTrue(len(comp["workflowGapSummary"]) > 0)
            self.assertTrue(len(comp["proposedSolutionAngle"]) > 0)
        finally:
            discover.search_searxng_or_ddg = orig_search
            discover.crawl_smart_dom_target = orig_crawl
            discover.evaluate_client_fit_dual_engine = orig_eval


if __name__ == "__main__":
    unittest.main()
