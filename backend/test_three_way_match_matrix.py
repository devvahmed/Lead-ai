"""
test_three_way_match_matrix.py — Test Suite for Step 8: Deep 3-Way Match Matrix Engine
======================================================================================
Verifies:
1. Deterministic scoring of Pillar 1 (Solution-to-Pain), Pillar 2 (ICP Scale), Pillar 3 (Readiness).
2. Weight math: (P1 * 0.45) + (P2 * 0.35) + (P3 * 0.20).
3. Qualification decision gates (QUALIFIED_LEAD, MARGINAL_FIT, DISQUALIFIED).
4. Fallback resilience when LLM is unavailable.
5. End-to-end integration with discover.py streaming discovery.
"""

import os
import sys
import json
import asyncio
import unittest
from unittest.mock import patch, MagicMock

# Force CPU single thread
os.environ['OPENBLAS_NUM_THREADS'] = '1'

import discover
from three_way_match_matrix import (
    ThreeWayMatchResult,
    evaluate_deterministic_matrix,
    evaluate_contextual_matrix,
    run_three_way_match_matrix
)


class TestThreeWayMatchMatrix(unittest.TestCase):

    def setUp(self):
        self.our_cv_profile = {
            "name": "VisionTech AI",
            "services": "Computer Vision, Automated Defect Detection, Quality Control Systems",
            "target_customers": "Textile, Automotive, and Electronics Manufacturers",
            "description": "We build deep learning visual inspection systems for high-speed production lines."
        }

        self.our_mobile_profile = {
            "name": "AppCraft Studio",
            "services": "iOS and Android Mobile App Development, Consumer Apps",
            "target_customers": "Direct-to-consumer startups and restaurants",
            "description": "Mobile app design and native Swift/Kotlin development."
        }

    def test_deterministic_pillar1_strong_match(self):
        """Pillar 1 should score >= 0.85 when our services directly solve the prospect's bottleneck."""
        candidate_info = {
            "domain": "sterlingtextiles.pk",
            "text_content": "We operate two large weaving mills and spinning facilities in Karachi.",
            "industry": "Textile Manufacturing"
        }
        audit_result = {
            "has_operational_bottleneck": True,
            "bottleneck_category": "MANUAL_QUALITY_CONTROL",
            "severity": "HIGH",
            "evidence_quote": "Our QA supervisors manually inspect every fabric roll across 3 shifts.",
            "workflow_gap_summary": "Manual visual defect inspection causing shipment delays.",
            "proposed_solution_angle": "Automated visual defect detection using AI cameras."
        }

        res = evaluate_deterministic_matrix(self.our_cv_profile, candidate_info, audit_result)
        self.assertGreaterEqual(res["solution_to_pain_score"], 0.85)
        self.assertIn("Direct alignment", res["solution_pain_rationale"])

    def test_deterministic_pillar1_weak_mismatch(self):
        """Pillar 1 should score <= 0.50 when our services are completely unrelated to the bottleneck."""
        candidate_info = {
            "domain": "heavysteelfab.com",
            "text_content": "Heavy industrial steel beam casting and forging plant.",
            "industry": "Steel Manufacturing"
        }
        audit_result = {
            "has_operational_bottleneck": True,
            "bottleneck_category": "UNAUTOMATED_INVENTORY_FLOW",
            "severity": "HIGH",
            "evidence_quote": "Yard workers manually count steel billets with physical chalk marks.",
            "workflow_gap_summary": "Unautomated physical yard stocktaking.",
            "proposed_solution_angle": "RFID and warehouse management automation."
        }

        res = evaluate_deterministic_matrix(self.our_mobile_profile, candidate_info, audit_result)
        self.assertLessEqual(res["solution_to_pain_score"], 0.50)
        self.assertIn("Weak alignment", res["solution_pain_rationale"])

    def test_deterministic_pillar2_enterprise_scale(self):
        """Pillar 2 should score >= 0.85 when enterprise facility, headcount, and certification signals are found."""
        candidate_info = {
            "domain": "apexmanufacturing.com",
            "text_content": (
                "Our 150,000 sq ft production facility operates across 4 plants. "
                "Employing over 450 staff and technicians, we are proud to be ISO 9001 certified "
                "with an annual revenue of $45 million."
            ),
            "industry": "Industrial Manufacturing"
        }
        audit_result = {"has_operational_bottleneck": False}

        res = evaluate_deterministic_matrix(self.our_cv_profile, candidate_info, audit_result)
        self.assertGreaterEqual(res["icp_scale_score"], 0.85)
        self.assertIn("verified physical production", res["icp_scale_rationale"])

    def test_deterministic_pillar2_thin_scale(self):
        """Pillar 2 should score <= 0.40 on thin/minimal text without physical or employee presence."""
        candidate_info = {
            "domain": "quickconsultant.com",
            "text_content": "I offer independent advisory services from home.",
            "industry": "Consulting"
        }
        audit_result = {"has_operational_bottleneck": False}

        res = evaluate_deterministic_matrix(self.our_cv_profile, candidate_info, audit_result)
        self.assertLessEqual(res["icp_scale_score"], 0.40)
        self.assertIn("thin or minimal content", res["icp_scale_rationale"])

    def test_deterministic_pillar3_high_readiness(self):
        """Pillar 3 should score >= 0.80 when active RFQ, phone, email, and multi-shift ops are detected."""
        candidate_info = {
            "domain": "globalfreightexpress.com",
            "text_content": (
                "Call our dispatch desk at +1 (800) 555-0199 or email sales@globalfreightexpress.com. "
                "Request a quote online via our customer portal login. We run 24/7 operations across multiple shifts."
            ),
            "industry": "Freight Logistics"
        }
        audit_result = {"has_operational_bottleneck": False}

        res = evaluate_deterministic_matrix(self.our_cv_profile, candidate_info, audit_result)
        self.assertGreaterEqual(res["readiness_score"], 0.80)
        self.assertIn("active commercial inquiry", res["readiness_rationale"])

    def test_composite_score_calculation_weights(self):
        """Composite score must adhere strictly to (P1 * 0.45) + (P2 * 0.35) + (P3 * 0.20)."""
        candidate_info = {
            "domain": "testcompany.com",
            "text_content": "Manufacturing plant employing 100 workers. Call +1-555-0123 for RFQ inquiries.",
            "industry": "Electronics"
        }
        audit_result = {
            "has_operational_bottleneck": True,
            "bottleneck_category": "MANUAL_QUALITY_CONTROL",
            "evidence_quote": "Workers manually inspect PCB boards.",
            "workflow_gap_summary": "Manual PCB defect inspection.",
            "proposed_solution_angle": "Automated optical inspection."
        }

        res = evaluate_deterministic_matrix(self.our_cv_profile, candidate_info, audit_result)
        expected = round((res["solution_to_pain_score"] * 0.45) + (res["icp_scale_score"] * 0.35) + (res["readiness_score"] * 0.20), 3)
        self.assertAlmostEqual(res["composite_matrix_score"], expected, places=3)

    def test_qualification_decision_gates(self):
        """Tests that decision thresholds correctly categorize QUALIFIED_LEAD, MARGINAL_FIT, and DISQUALIFIED."""
        # 1. Qualified Lead: composite >= 0.70 and pain >= 0.60
        strong_candidate = {
            "domain": "sterlingtextiles.pk",
            "text_content": "Our 100,000 sq ft mill employs over 450 staff. Contact sales@sterlingtextiles.pk for RFQ.",
            "industry": "Textiles"
        }
        strong_audit = {
            "has_operational_bottleneck": True,
            "bottleneck_category": "MANUAL_QUALITY_CONTROL",
            "evidence_quote": "Manual inspection across three shifts."
        }
        res_strong = evaluate_deterministic_matrix(self.our_cv_profile, strong_candidate, strong_audit)
        self.assertEqual(res_strong["overall_qualification"], "QUALIFIED_LEAD")

        # 2. Disqualified Lead: mismatch + thin scale
        weak_candidate = {
            "domain": "tinyshop.org",
            "text_content": "Small hobby blog with personal thoughts.",
            "industry": "Blogging"
        }
        weak_audit = {
            "has_operational_bottleneck": False
        }
        res_weak = evaluate_deterministic_matrix(self.our_mobile_profile, weak_candidate, weak_audit)
        self.assertEqual(res_weak["overall_qualification"], "DISQUALIFIED")
        self.assertLess(res_weak["composite_matrix_score"], 0.50)

    def test_run_three_way_match_matrix_empty_content(self):
        """Empty candidate text should return DISQUALIFIED result without error."""
        res = asyncio.run(run_three_way_match_matrix(
            our_profile=self.our_cv_profile,
            candidate_domain="empty.com",
            candidate_text="",
            audit_result={},
            use_llm=False
        ))
        self.assertEqual(res.overall_qualification, "DISQUALIFIED")
        self.assertEqual(res.composite_matrix_score, 0.20)

    def test_evaluate_contextual_matrix_fallback(self):
        """When LLM is disabled or times out, contextual matrix returns deterministic scores seamlessly."""
        candidate_text = "Operating weaving plant with 250 employees. Call +92-21-3456789 for inquiries."
        audit_result = {
            "has_operational_bottleneck": True,
            "bottleneck_category": "MANUAL_QUALITY_CONTROL",
            "evidence_quote": "Fabric inspection is performed manually."
        }

        res = asyncio.run(evaluate_contextual_matrix(
            our_profile=self.our_cv_profile,
            candidate_domain="textilecorp.com",
            candidate_text=candidate_text,
            audit_result=audit_result,
            use_llm=False
        ))

        self.assertIsInstance(res, ThreeWayMatchResult)
        self.assertIn(res.overall_qualification, ("QUALIFIED_LEAD", "MARGINAL_FIT"))
        self.assertGreater(res.composite_matrix_score, 0.60)
        self.assertIn("solution_to_pain_score", res.to_dict())


class TestDiscoverPipelineWithThreeWayMatch(unittest.IsolatedAsyncioTestCase):

    async def test_discover_pipeline_attaches_matrix_and_filters_disqualified(self):
        """
        Verify that discover.stream_discovery:
        1. Evaluates candidates through run_three_way_match_matrix.
        2. Drops DISQUALIFIED candidates.
        3. Enriches yielded qualified companies with threeWayMatch metadata.
        """
        # Candidate 1: Strong enterprise textile mill (Should be QUALIFIED_LEAD)
        # Candidate 2: Thin blog with no operational scale or pain (Should be DISQUALIFIED)
        mock_candidates = [
            {
                "url": "https://sterlingtextiles.pk",
                "title": "Sterling Textiles Mills",
                "content": (
                    "Sterling Textiles operates two large weaving mills and a spinning plant employing over 450 staff in Karachi. "
                    "Our QA supervisors manually inspect each fabric roll across three shifts. "
                    "Contact our commercial sales office at sales@sterlingtextiles.pk or call +92-21-35061234."
                )
            },
            {
                "url": "https://randomtechthoughts.com",
                "title": "Random Tech Thoughts",
                "content": "Personal reflections on technology by an independent hobbyist."
            }
        ]

        async def mock_search(query, page=1):
            if page == 1:
                return mock_candidates
            return []

        async def mock_smart_crawl(domain, homepage_url, max_pages=4):
            if "sterlingtextiles" in domain:
                return {
                    "combined_text": mock_candidates[0]["content"],
                    "source_label": "homepage + /operations + /contact",
                    "pages": {}, "dom_links": {}, "categorized_targets": {}, "total_pages_crawled": 3
                }
            return {
                "combined_text": mock_candidates[1]["content"],
                "source_label": "homepage",
                "pages": {}, "dom_links": {}, "categorized_targets": {}, "total_pages_crawled": 1
            }

        async def mock_eval(**kwargs):
            domain = kwargs.get("domain", "")
            if "sterlingtextiles" in domain:
                return {
                    "is_junk": False,
                    "industry_match": True,
                    "lead_type": "NEEDS_SERVICE",
                    "confidence": 92,
                    "reason": "Textile fabric manufacturing plant in Pakistan.",
                    "official_company_name": "Sterling Textiles Mills",
                    "source": "matrix-test",
                    "detected_country": "Pakistan"
                }
            else:
                return {
                    "is_junk": False,
                    "industry_match": True,
                    "lead_type": "NEEDS_SERVICE",
                    "confidence": 60,
                    "reason": "General blog post about technology.",
                    "official_company_name": "Random Tech Thoughts",
                    "source": "matrix-test",
                    "detected_country": "Global"
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
                max_pages=1,
                our_services="Computer Vision, Defect Detection, Quality Control Systems"
            ):
                data = json.loads(line.strip())
                received_events.append(data)

            companies = [e for e in received_events if e.get("type") == "company"]
            self.assertEqual(len(companies), 1)
            comp = companies[0]

            self.assertEqual(comp["domain"], "sterlingtextiles.pk")
            # Step 8 Matrix Assertions
            self.assertIn("threeWayMatch", comp)
            self.assertIn("overallQualification", comp)
            self.assertIn("compositeMatrixScore", comp)
            self.assertIn("solutionToPainScore", comp)
            self.assertIn("icpScaleScore", comp)
            self.assertIn("readinessScore", comp)
            self.assertIn("keyValueProposition", comp)

            self.assertEqual(comp["overallQualification"], "QUALIFIED_LEAD")
            self.assertGreaterEqual(comp["compositeMatrixScore"], 0.70)
            self.assertGreaterEqual(comp["solutionToPainScore"], 0.60)

        finally:
            discover.search_searxng_or_ddg = orig_search
            discover.crawl_smart_dom_target = orig_crawl
            discover.evaluate_client_fit_dual_engine = orig_eval


if __name__ == '__main__':
    unittest.main()
