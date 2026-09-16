"""
three_way_match_matrix.py — Deep 3-Way Match Matrix Engine (Step 8)
===================================================================
Replaces single-dimensional fit checks with a rigorous, evidence-grounded
3-Way Qualification Matrix evaluating:
1. Solution-to-Pain Alignment (Weight: 45%):
   Does our specific service capability directly solve the prospect's extracted
   operational bottleneck (from Step 7)?
2. ICP & Scale Alignment (Weight: 35%):
   Is the prospect an appropriately scaled commercial entity (revenue, headcount,
   facility size, production volume) in a target industry sub-vertical?
3. Technical & Operational Readiness (Weight: 20%):
   Does the prospect possess the operational maturity, active contact channels,
   or infrastructure required to adopt our solution?

Decision Gates:
- QUALIFIED_LEAD : composite_matrix_score >= 0.70 AND solution_to_pain_score >= 0.60
- MARGINAL_FIT   : composite_matrix_score >= 0.50
- DISQUALIFIED   : composite_matrix_score < 0.50 (dropped before streaming)
"""

import re
import json
import logging
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("three_way_match_matrix")

# ─── 1. Schema & Dataclasses ──────────────────────────────────────────────────

@dataclass
class ThreeWayMatchResult:
    overall_qualification: str  # "QUALIFIED_LEAD", "MARGINAL_FIT", "DISQUALIFIED"
    solution_to_pain_score: float  # 0.0 to 1.0
    icp_scale_score: float  # 0.0 to 1.0
    readiness_score: float  # 0.0 to 1.0
    composite_matrix_score: float  # 0.0 to 1.0
    solution_pain_rationale: str
    icp_scale_rationale: str
    readiness_rationale: str
    key_value_proposition: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── 2. Mapping & Scale Patterns ──────────────────────────────────────────────

CATEGORY_SERVICE_PATTERNS = {
    "MANUAL_QUALITY_CONTROL": [
        r"(?i)\b(?:computer\s*vision|defect\s*detection|visual\s*inspection|quality\s*control|qa\s*automation|inspection\s*system|automated\s*sorting|camera\s*inspection|visual\s*ai|machine\s*vision|image\s*processing|ai|ml|machine\s*learning|deep\s*learning)\b",
        r"(?i)\b(?:defect|inspection|tolerance|quality\s*assurance|surface\s*check|optical\s*sorting)\b"
    ],
    "REPETITIVE_DATA_ENTRY": [
        r"(?i)\b(?:rpa|robotic\s*process\s*automation|data\s*automation|ocr|document\s*processing|workflow\s*automation|custom\s*software|web\s*app|integration|api|form\s*automation|data\s*entry\s*automation|ai\s*agent|scripting)\b",
        r"(?i)\b(?:spreadsheet|excel|transcription|entry|paperwork|clipboard|digitization)\b"
    ],
    "LEGACY_SOFTWARE_DISPATCH": [
        r"(?i)\b(?:dispatch\s*software|logistics\s*software|fleet\s*management|custom\s*software|cloud\s*migration|erp|crm|saas|api\s*integration|modernization|scheduling\s*software|routing\s*system|telematics)\b",
        r"(?i)\b(?:dispatch|freight|legacy|carrier|load\s*board|manifest|schedule)\b"
    ],
    "HIGH_LABOR_TURNOVER_HIRING": [
        r"(?i)\b(?:process\s*automation|robotics|ai\s*agents|self[- ]service|automation|custom\s*software|labor\s*optimization|workforce\s*software|turnover|shift\s*management)\b",
        r"(?i)\b(?:packers|inspectors|laborers|staffing|hiring|turnover|recruiting)\b"
    ],
    "UNAUTOMATED_INVENTORY_FLOW": [
        r"(?i)\b(?:inventory\s*management|wms|warehouse\s*management|warehouse\s*automation|rfid|barcode|tracking\s*system|iot|supply\s*chain\s*software|computer\s*vision|asset\s*tracking)\b",
        r"(?i)\b(?:inventory|stocktaking|pallet|bin|rack|warehouse|manifest)\b"
    ]
}

# Scale & ICP indicators
SCALE_PATTERNS = {
    "FACILITY": [
        r"(?i)\b(?:\d+[\d,]*\s*(?:sq(?:uare)?\s*(?:ft|feet|meters?)|acres?|hectares?))\b",
        r"(?i)\b(?:manufacturing\s*plant|production\s*facility|spinning\s*mill|weaving\s*mill|fabrication\s*plant|distribution\s*center|state[- ]of[- ]the[- ]art\s*facility|cold\s*storage\s*warehouse|multiple\s*facilities|multiple\s*locations|industrial\s*complex|warehouses?)\b",
        r"(?i)\b(?:headquarters|corporate\s*office|branches|subsidiaries|global\s*offices|regional\s*offices)\b"
    ],
    "HEADCOUNT": [
        r"(?i)\b(?:team\s*of|employing|workforce\s*of|staff\s*of|over|\+)\s*(?:\d+[\d,]*)\s*(?:employees|staff|workers|engineers|specialists|professionals|technicians)\b",
        r"(?i)\b(?:\d+[\d,]*)\+?\s*(?:employees|team\s*members|workforce)\b",
        r"(?i)\b(?:5[0-9]|[6-9][0-9]|[1-9]\d{2,})\s*(?:employees|staff|workers)\b"
    ],
    "REVENUE_CERTIFICATION": [
        r"(?i)\b(?:iso\s*9001|iso\s*14001|iso\s*22000|iso\s*27001|haccp|gmp|ce\s*certified|fda\s*approved|osha)\b",
        r"(?i)\b(?:\$\s*\d+[\d,]*\s*(?:million|m|billion|b)|annual\s*turnover|annual\s*revenue|production\s*capacity\s*of)\b",
        r"(?i)\b(?:thousands\s*of\s*tons|units\s*per\s*(?:day|month|year)|containers\s*per\s*month|daily\s*output)\b"
    ]
}

READINESS_PATTERNS = {
    "CONTACT_CHANNELS": [
        r"(?i)\b(?:request\s*(?:a\s*)?quote|rfq|get\s*in\s*touch|contact\s*us|inquir(?:y|ies)|reach\s*out|sales@|info@|contact@)\b",
        r"(?i)\b(?:\+?\d{1,4}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9})\b"
    ],
    "OPERATIONAL_INFRASTRUCTURE": [
        r"(?i)\b(?:customer\s*portal|client\s*portal|tracking\s*portal|order\s*tracking|portal\s*login|client\s*login|rfq\s*portal)\b",
        r"(?i)\b(?:24\/7\s*operations?|three\s*shifts?|multiple\s*shifts?|round[- ]the[- ]clock|continuous\s*production)\b",
        r"(?i)\b(?:erp|crm|edi|api|sap|oracle|cloud|digital\s*management|automated\s*workflow)\b"
    ]
}


# ─── 3. Tier 1: Deterministic Matrix Scorer ────────────────────────────────────

def evaluate_deterministic_matrix(
    our_profile: Dict[str, Any],
    candidate_info: Dict[str, Any],
    audit_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Evaluates the three qualification pillars deterministically using regex patterns,
    extracted audit metadata, scale indicators, and service-to-pain mapping.

    Returns:
        Dict with scores, rationales, composite score, and overall qualification.
    """
    our_services = str(our_profile.get("services") or our_profile.get("ai_enriched_profile") or "").lower().strip()
    our_desc = str(our_profile.get("description") or "").lower().strip()
    combined_our = f"{our_services} {our_desc}".strip()

    candidate_text = str(candidate_info.get("text_content") or candidate_info.get("snippet") or "")
    candidate_domain = str(candidate_info.get("domain") or "")
    candidate_industry = str(candidate_info.get("industry") or "").lower().strip()

    # ── FIRST: Compute Scale and Readiness Signals ──
    facility_matches = []
    headcount_matches = []
    revenue_cert_matches = []

    for pat in SCALE_PATTERNS["FACILITY"]:
        m = re.findall(pat, candidate_text)
        if m:
            facility_matches.extend(m)

    for pat in SCALE_PATTERNS["HEADCOUNT"]:
        m = re.findall(pat, candidate_text)
        if m:
            headcount_matches.extend(m)

    for pat in SCALE_PATTERNS["REVENUE_CERTIFICATION"]:
        m = re.findall(pat, candidate_text)
        if m:
            revenue_cert_matches.extend(m)

    has_confirmed_scale = bool(facility_matches or headcount_matches or revenue_cert_matches)

    # Scale score calculation
    scale_score_acc = 0.45  # base for operating business
    scale_reasons = []

    if facility_matches:
        scale_score_acc += 0.25
        scale_reasons.append("verified physical production/distribution facilities")

    if headcount_matches:
        scale_score_acc += 0.20
        scale_reasons.append("established workforce")

    if revenue_cert_matches:
        scale_score_acc += 0.15
        scale_reasons.append(f"industry certification/scale ({revenue_cert_matches[0]})")

    # Domain length/TLD heuristic check for thin/parked sites
    if len(candidate_text.split()) < 40 and not facility_matches:
        scale_score_acc = 0.30
        scale_reasons = ["thin or minimal content with unconfirmed scale"]

    icp_scale_score = min(1.0, round(scale_score_acc, 2))
    icp_scale_rationale = (
        f"Scale confirmed: {'; '.join(scale_reasons)}."
        if scale_reasons else "Standard commercial profile in target vertical."
    )

    # Readiness score calculation
    readiness_score_acc = 0.40
    readiness_reasons = []

    contact_found = any(re.search(p, candidate_text) for p in READINESS_PATTERNS["CONTACT_CHANNELS"])
    infra_found = any(re.search(p, candidate_text) for p in READINESS_PATTERNS["OPERATIONAL_INFRASTRUCTURE"])

    if contact_found:
        readiness_score_acc += 0.30
        readiness_reasons.append("active commercial inquiry/RFQ channels")

    if infra_found:
        readiness_score_acc += 0.25
        readiness_reasons.append("multi-shift or digital operational infrastructure")

    if len(candidate_text) > 400:
        readiness_score_acc += 0.10

    readiness_score = min(1.0, round(readiness_score_acc, 2))
    readiness_rationale = (
        f"Operational readiness established: {', '.join(readiness_reasons)}."
        if readiness_reasons else "Standard operational presence."
    )

    # ── SECOND: PILLAR 1: Solution-to-Pain Alignment (Weight: 45%) ──
    has_bottleneck = bool(audit_result.get("has_operational_bottleneck", False))
    bottleneck_cat = str(audit_result.get("bottleneck_category") or "").upper()
    evidence_quote = str(audit_result.get("evidence_quote") or "")
    gap_summary = str(audit_result.get("workflow_gap_summary") or "")
    proposed_angle = str(audit_result.get("proposed_solution_angle") or "")

    is_industry_fallback = bool(candidate_industry and our_services and candidate_industry == our_services)
    is_generic_services = (
        not combined_our
        or is_industry_fallback
        or any(term == combined_our for term in ("b2b products & services", "custom software", "software", "products & services"))
        or any(term in combined_our for term in ("b2b", "software", "automation", "consulting", "technology", "robotics", "engineering", "solutions", "services", "manufacturing", "logistics"))
    )

    if has_bottleneck and bottleneck_cat in CATEGORY_SERVICE_PATTERNS:
        cat_patterns = CATEGORY_SERVICE_PATTERNS[bottleneck_cat]
        matches_our = any(re.search(p, combined_our) for p in cat_patterns)

        if matches_our:
            solution_to_pain_score = 0.90
            solution_pain_rationale = (
                f"Direct alignment: Our capabilities directly resolve candidate's '{bottleneck_cat}' bottleneck "
                f"({evidence_quote[:70]}...)" if evidence_quote else f"resolving {gap_summary or bottleneck_cat}."
            )
        elif is_generic_services:
            solution_to_pain_score = 0.75
            solution_pain_rationale = (
                f"General solution alignment: Identified operational bottleneck '{bottleneck_cat}' can be automated "
                f"via modern software and process improvements."
            )
        else:
            tokens_our = set(re.findall(r"\w{4,}", combined_our))
            tokens_gap = set(re.findall(r"\w{4,}", f"{gap_summary} {proposed_angle}".lower()))
            overlap = tokens_our.intersection(tokens_gap)
            if overlap:
                solution_to_pain_score = 0.70
                solution_pain_rationale = f"Partial pain alignment: Shared operational focus on {', '.join(list(overlap)[:3])}."
            else:
                solution_to_pain_score = 0.45
                solution_pain_rationale = f"Weak alignment: Our services do not directly target their '{bottleneck_cat}' bottleneck."
    elif has_bottleneck:
        solution_to_pain_score = 0.65 if is_generic_services else 0.55
        solution_pain_rationale = "General operational inefficiency detected but specific category alignment is moderate."
    else:
        # No extracted bottleneck
        if is_generic_services or has_confirmed_scale or icp_scale_score >= 0.60:
            solution_to_pain_score = 0.65
            solution_pain_rationale = "Operating commercial entity in target industry; candidate fits general commercial procurement profile."
        else:
            solution_to_pain_score = 0.35
            solution_pain_rationale = "No operational bottleneck or pain point identified on target website."

    # ── THIRD: Composite Calculation & Qualification Gate ──
    composite_score = round(
        (solution_to_pain_score * 0.45) +
        (icp_scale_score * 0.35) +
        (readiness_score * 0.20),
        3
    )

    if composite_score >= 0.70 and solution_to_pain_score >= 0.60:
        qualification = "QUALIFIED_LEAD"
    elif composite_score >= 0.50:
        qualification = "MARGINAL_FIT"
    else:
        qualification = "DISQUALIFIED"

    # Key Value Proposition synthesis
    if proposed_angle:
        key_value_prop = proposed_angle
    elif has_bottleneck and bottleneck_cat:
        key_value_prop = f"Modernize and automate {bottleneck_cat.lower().replace('_', ' ')} with targeted engineering."
    else:
        key_value_prop = f"Scalable technology solutions tailored for operating {candidate_industry or 'commercial'} enterprises."

    return {
        "overall_qualification": qualification,
        "solution_to_pain_score": solution_to_pain_score,
        "icp_scale_score": icp_scale_score,
        "readiness_score": readiness_score,
        "composite_matrix_score": composite_score,
        "solution_pain_rationale": solution_pain_rationale,
        "icp_scale_rationale": icp_scale_rationale,
        "readiness_rationale": readiness_rationale,
        "key_value_proposition": key_value_prop
    }


# ─── 4. Tier 2: Contextual LLM Matrix Evaluator ───────────────────────────────

async def evaluate_contextual_matrix(
    our_profile: Dict[str, Any],
    candidate_domain: str,
    candidate_text: str,
    audit_result: Dict[str, Any],
    use_llm: bool = True
) -> ThreeWayMatchResult:
    """
    Prompts Ollama in JSON mode to evaluate all three pillars with strict evidence demands.
    Falls back to Tier 1 deterministic scoring if LLM is unavailable or times out.
    """
    det_res = evaluate_deterministic_matrix(
        our_profile=our_profile,
        candidate_info={"domain": candidate_domain, "text_content": candidate_text},
        audit_result=audit_result
    )

    text_sample = candidate_text[:3500] if candidate_text else ""
    if not use_llm or len(text_sample) < 60:
        return ThreeWayMatchResult(**det_res)

    our_name = our_profile.get("name", "Our Company")
    our_services = our_profile.get("services") or our_profile.get("ai_enriched_profile") or "B2B Solutions & Engineering"
    target_customers = our_profile.get("target_customers", "Commercial Enterprises")
    our_desc = our_profile.get("description", "")

    bottleneck_cat = audit_result.get("bottleneck_category", "None")
    evidence_quote = audit_result.get("evidence_quote", "")
    gap_summary = audit_result.get("workflow_gap_summary", "")
    severity = audit_result.get("severity", "LOW")

    prompt = f"""You are a Senior Principal Enterprise Solutions Architect and ICP Qualification Auditor.

OUR COMPANY & CAPABILITIES:
- Company: "{our_name}"
- Our Services: "{our_services}"
- Target Customers: "{target_customers}"
- Profile Overview: "{our_desc}"

PROSPECT CANDIDATE:
- Domain: "{candidate_domain}"
- Operational Bottleneck: "{bottleneck_cat}"
- Bottleneck Severity: "{severity}"
- Extracted Inefficiency Quote: \"\"\"{evidence_quote}\"\"\"
- Bottleneck Gap Summary: "{gap_summary}"

PROSPECT WEBSITE EVIDENCE:
\"\"\"{text_sample}\"\"\"

TASK:
Perform a strict 3-Way Qualification Matrix audit across 3 pillars:
1. Solution-to-Pain Alignment (45% weight):
   Does our specific service capability directly solve their extracted operational bottleneck? Score 0.0 to 1.0.
2. ICP & Scale Alignment (35% weight):
   Is the prospect an appropriately scaled commercial entity (facilities, headcount, plants, square footage, ISO certs)? Score 0.0 to 1.0. Cite exact evidence.
3. Technical & Operational Readiness (20% weight):
   Does the prospect possess operational maturity (RFQs, multi-shift production, customer portals, existing infrastructure)? Score 0.0 to 1.0. Cite evidence.

OUTPUT RULES:
- Output JSON only. No markdown fences.
- "solution_to_pain_score": float (0.0 to 1.0)
- "solution_pain_rationale": 1 sentence explaining service capability vs prospect bottleneck
- "icp_scale_score": float (0.0 to 1.0)
- "icp_scale_rationale": 1 sentence citing scale evidence from text
- "readiness_score": float (0.0 to 1.0)
- "readiness_rationale": 1 sentence citing operational readiness evidence
- "key_value_proposition": 1-sentence high-impact value pitch

JSON SCHEMA:
{{
  "solution_to_pain_score": 0.85,
  "solution_pain_rationale": "Explanation",
  "icp_scale_score": 0.80,
  "icp_scale_rationale": "Evidence",
  "readiness_score": 0.75,
  "readiness_rationale": "Evidence",
  "key_value_proposition": "Pitch"
}}"""

    try:
        from discover import async_call_ollama

        raw = await async_call_ollama(
            prompt=prompt,
            system_prompt="You are an expert enterprise sales qualification auditor. Output strict JSON only.",
            temperature=0.1,
            max_tokens=350,
            timeout=7.5
        )

        if raw:
            cleaned = re.sub(r"^```json\s*", "", raw.strip(), flags=re.MULTILINE)
            cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE)
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                parsed = json.loads(cleaned[start:end+1])

                s_pain = max(0.0, min(1.0, float(parsed.get("solution_to_pain_score", det_res["solution_to_pain_score"]))))
                s_scale = max(0.0, min(1.0, float(parsed.get("icp_scale_score", det_res["icp_scale_score"]))))
                s_ready = max(0.0, min(1.0, float(parsed.get("readiness_score", det_res["readiness_score"]))))

                comp_score = round((s_pain * 0.45) + (s_scale * 0.35) + (s_ready * 0.20), 3)

                if comp_score >= 0.70 and s_pain >= 0.60:
                    qual = "QUALIFIED_LEAD"
                elif comp_score >= 0.50:
                    qual = "MARGINAL_FIT"
                else:
                    qual = "DISQUALIFIED"

                return ThreeWayMatchResult(
                    overall_qualification=qual,
                    solution_to_pain_score=s_pain,
                    icp_scale_score=s_scale,
                    readiness_score=s_ready,
                    composite_matrix_score=comp_score,
                    solution_pain_rationale=str(parsed.get("solution_pain_rationale") or det_res["solution_pain_rationale"]).strip(),
                    icp_scale_rationale=str(parsed.get("icp_scale_rationale") or det_res["icp_scale_rationale"]).strip(),
                    readiness_rationale=str(parsed.get("readiness_rationale") or det_res["readiness_rationale"]).strip(),
                    key_value_proposition=str(parsed.get("key_value_proposition") or det_res["key_value_proposition"]).strip()
                )
    except Exception as llm_err:
        logger.debug(f"[3-Way Matrix] LLM evaluation fallback for {candidate_domain}: {llm_err}")

    return ThreeWayMatchResult(**det_res)


# ─── 5. Unified Matrix Entry Point ────────────────────────────────────────────

async def run_three_way_match_matrix(
    our_profile: Dict[str, Any],
    candidate_domain: str,
    candidate_text: str,
    audit_result: Dict[str, Any],
    use_llm: bool = True
) -> ThreeWayMatchResult:
    """
    Unified entry point for Step 8: Deep 3-Way Match Matrix Engine.
    Evaluates Solution-to-Pain, ICP & Scale, and Technical & Operational Readiness.
    """
    if not candidate_text:
        # Disqualify empty content
        return ThreeWayMatchResult(
            overall_qualification="DISQUALIFIED",
            solution_to_pain_score=0.20,
            icp_scale_score=0.20,
            readiness_score=0.20,
            composite_matrix_score=0.20,
            solution_pain_rationale="No content available to evaluate solution alignment.",
            icp_scale_rationale="No content available to evaluate ICP scale.",
            readiness_rationale="No content available to evaluate operational readiness.",
            key_value_proposition=""
        )

    return await evaluate_contextual_matrix(
        our_profile=our_profile,
        candidate_domain=candidate_domain,
        candidate_text=candidate_text,
        audit_result=audit_result,
        use_llm=use_llm
    )
