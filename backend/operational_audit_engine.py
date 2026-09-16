"""
Service-Agnostic Operational Bottleneck Audit Engine (Step 7).

Analyzes multi-page scraped content (from Step 6's Smart DOM Crawler) to automatically
detect operational inefficiencies, manual human labor bottlenecks, legacy workflow delays,
and paper-based processes across any industry (manufacturing, logistics, cold storage,
healthcare, services). Extracts exact verbatim quotes from the target site as evidence
and proposes targeted service solution angles.
"""

import json
import logging
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("operational_audit_engine")


# ─── 1. Operational Inefficiency Category Schema ──────────────────────────────

class OperationalInefficiencyCategory(str, Enum):
    MANUAL_QUALITY_CONTROL = "MANUAL_QUALITY_CONTROL"
    REPETITIVE_DATA_ENTRY = "REPETITIVE_DATA_ENTRY"
    LEGACY_SOFTWARE_DISPATCH = "LEGACY_SOFTWARE_DISPATCH"
    HIGH_LABOR_TURNOVER_HIRING = "HIGH_LABOR_TURNOVER_HIRING"
    UNAUTOMATED_INVENTORY_FLOW = "UNAUTOMATED_INVENTORY_FLOW"


# ─── 2. Deterministic Pattern Rule Sets ───────────────────────────────────────

DETERMINISTIC_BOTTLENECK_PATTERNS: Dict[str, List[re.Pattern]] = {
    OperationalInefficiencyCategory.MANUAL_QUALITY_CONTROL.value: [
        re.compile(r"\bmanual(?:ly)?\s+inspect(?:ion|ing|s|ed)?\b", re.IGNORECASE),
        re.compile(r"\bvisual\s+(?:inspection|check(?:s|ing)?|quality\s+control|qa\s+check)\b", re.IGNORECASE),
        re.compile(r"\bmanual\s+(?:defect|sorting|grading|measurement|testing)\b", re.IGNORECASE),
        re.compile(r"\bhuman\s+(?:inspector|inspectors|checker|evaluator)\b", re.IGNORECASE),
        re.compile(r"\bphysical\s+(?:inspection|check|audit)\b", re.IGNORECASE),
        re.compile(r"\b100%\s+manual\s+inspection\b", re.IGNORECASE),
    ],
    OperationalInefficiencyCategory.REPETITIVE_DATA_ENTRY.value: [
        re.compile(r"\bpaper\s+(?:form|forms|ticket|tickets|log|logs|paperwork)\b", re.IGNORECASE),
        re.compile(r"\bmanual(?:ly)?\s+(?:data\s+entry|enter(?:ed|ing)?|spreadsheet|logging)\b", re.IGNORECASE),
        re.compile(r"\bexcel\s+(?:sheet|sheets|spreadsheet|spreadsheets)\b", re.IGNORECASE),
        re.compile(r"\bhandwritten\s+(?:notes|records|manifests|receipts|logs)\b", re.IGNORECASE),
        re.compile(r"\bdouble\s+data\s+entry\b", re.IGNORECASE),
        re.compile(r"\bmanual\s+record\s+keeping\b", re.IGNORECASE),
    ],
    OperationalInefficiencyCategory.LEGACY_SOFTWARE_DISPATCH.value: [
        re.compile(r"\blegacy\s+(?:system|software|platform|erp|database)\b", re.IGNORECASE),
        re.compile(r"\bcall\s+(?:for\s+booking|to\s+schedule|our\s+dispatch|desk\s+to\s+book)\b", re.IGNORECASE),
        re.compile(r"\bpaper-based\s+(?:dispatch|scheduling|workflow|routing)\b", re.IGNORECASE),
        re.compile(r"\bphone(?:-based)?\s+(?:dispatch|ordering|scheduling)\b", re.IGNORECASE),
        re.compile(r"\bmanual\s+(?:dispatch|scheduling|route\s+planning|tracking)\b", re.IGNORECASE),
        re.compile(r"\bfax\s+(?:order|orders|confirmation|manifest)\b", re.IGNORECASE),
    ],
    OperationalInefficiencyCategory.HIGH_LABOR_TURNOVER_HIRING.value: [
        re.compile(r"\burgently\s+hiring\b", re.IGNORECASE),
        re.compile(r"\bhiring\s+(?:\d+\+?|multiple)\s+(?:manual\s+laborers|inspectors|packers|sorters|warehouse\s+associates)\b", re.IGNORECASE),
        re.compile(r"\bhigh\s+(?:labor\s+turnover|staffing\s+cost|turnover\s+rate)\b", re.IGNORECASE),
        re.compile(r"\blabor\s+(?:shortage|constraints|overhead)\b", re.IGNORECASE),
        re.compile(r"\bseeking\s+(?:general\s+laborers|sorting\s+staff|inspectors|qa\s+temps)\b", re.IGNORECASE),
    ],
    OperationalInefficiencyCategory.UNAUTOMATED_INVENTORY_FLOW.value: [
        re.compile(r"\bmanual\s+(?:inventory|stock\s+count(?:ing)?|cycle\s+count(?:ing)?|tally)\b", re.IGNORECASE),
        re.compile(r"\bphysical\s+(?:inventory\s+count|ledger\s+audit|stock\s+check)\b", re.IGNORECASE),
        re.compile(r"\bstock\s+ledger\b", re.IGNORECASE),
        re.compile(r"\bpaper\s+inventory\b", re.IGNORECASE),
        re.compile(r"\bno\s+barcode\b", re.IGNORECASE),
        re.compile(r"\bclipboard\s+inventory\b", re.IGNORECASE),
    ]
}


# ─── 3. Tier 1: Deterministic Signal Extractor ────────────────────────────────

def extract_deterministic_bottlenecks(
    text_content: str,
    context_window: int = 150
) -> List[Dict[str, Any]]:
    """
    Scans text_content for deterministic operational bottleneck indicators.
    Extracts exact 150-character context snippets as raw evidence.

    Returns:
        List of dicts:
        [
            {
                "category": "MANUAL_QUALITY_CONTROL",
                "keyword": "manual inspection",
                "confidence": 0.85,
                "evidence_snippet": "...our QA supervisors perform manual inspection of fabric rolls...",
                "start_char": 420,
                "end_char": 437
            },
            ...
        ]
    """
    if not text_content or not isinstance(text_content, str):
        return []

    signals: List[Dict[str, Any]] = []
    seen_spans: List[Tuple[int, int]] = []

    for category, patterns in DETERMINISTIC_BOTTLENECK_PATTERNS.items():
        for pattern in patterns:
            for match in pattern.finditer(text_content):
                m_start, m_end = match.span()

                # Deduplicate overlapping matches
                if any(abs(m_start - prev_s) < 30 for prev_s, _ in seen_spans):
                    continue
                seen_spans.append((m_start, m_end))

                # Window surrounding text context (e.g. 150 chars total)
                half_window = context_window // 2
                w_start = max(0, m_start - half_window)
                w_end = min(len(text_content), m_end + half_window)

                raw_snippet = text_content[w_start:w_end].strip()
                clean_snippet = re.sub(r"\s+", " ", raw_snippet)

                # Add ellipsis if truncated
                if w_start > 0 and not clean_snippet.startswith("..."):
                    clean_snippet = "..." + clean_snippet
                if w_end < len(text_content) and not clean_snippet.endswith("..."):
                    clean_snippet = clean_snippet + "..."

                matched_kw = match.group(0)

                # Score confidence based on pattern specificity
                confidence = 0.85
                if any(strong in matched_kw.lower() for strong in ("100% manual", "paper-based", "urgently hiring", "double data entry", "handwritten")):
                    confidence = 0.95

                signals.append({
                    "category": category,
                    "keyword": matched_kw,
                    "confidence": confidence,
                    "evidence_snippet": clean_snippet,
                    "start_char": m_start,
                    "end_char": m_end
                })

    # Sort by confidence descending
    signals.sort(key=lambda x: x["confidence"], reverse=True)
    return signals


# ─── 4. Tier 2: Deep LLM Operational Auditor ──────────────────────────────────

async def run_llm_operational_audit(
    domain: str,
    multi_page_text: str,
    target_service: str = "",
    deterministic_signals: Optional[List[Dict[str, Any]]] = None,
    use_llm: bool = True
) -> Dict[str, Any]:
    """
    Calls Ollama to deeply analyze multi-page evidence, extract verbatim quotes proving
    the operational bottleneck, determine severity, and propose an aligned service solution.
    """
    # Truncate text sample for LLM window (e.g. 4000 chars)
    text_sample = multi_page_text[:4000] if multi_page_text else ""
    signals = deterministic_signals or []

    if use_llm and len(text_sample) > 80:
        try:
            from discover import async_call_ollama

            prompt = f"""You are a Principal Operational Efficiency & Workflow Auditor for B2B enterprises.

COMPANY DOMAIN: "{domain}"
OUR SERVICE CAPABILITY: "{target_service or 'AI, Automation, Computer Vision, and Custom B2B Software'}"

WEBSITE EVIDENCE:
\"\"\"{text_sample}\"\"\"

TASK:
Analyze the company's workflows, operational descriptions, and stated procedures.
Identify their single biggest OPERATIONAL BOTTLENECK, manual labor inefficiency, paper-based delay, or legacy software gap.

CATEGORIES:
1. "MANUAL_QUALITY_CONTROL": Manual visual checks, human defect inspection, physical grading.
2. "REPETITIVE_DATA_ENTRY": Paper forms, manual spreadsheets, double data entry, physical logging.
3. "LEGACY_SOFTWARE_DISPATCH": Paper/phone-based dispatching, manual tracking, legacy scheduling.
4. "HIGH_LABOR_TURNOVER_HIRING": Urgent manual worker recruitment, high turnover bottlenecks.
5. "UNAUTOMATED_INVENTORY_FLOW": Manual physical stock counting, paper ledgers, barcode-less inventory.

RULES:
- "has_operational_bottleneck": true if an inefficiency or manual workflow exists, false only if the company is 100% automated or no operational info exists.
- "evidence_quote": MUST be an exact or near-exact verbatim quote from the text above proving the manual bottleneck.
- "severity": "CRITICAL" | "HIGH" | "MEDIUM".
- "workflow_gap_summary": Concise 1-sentence explanation of the bottleneck.
- "proposed_solution_angle": How our service capability directly solves their bottleneck.

Respond ONLY in valid JSON format. No markdown fences:
{{
  "has_operational_bottleneck": true,
  "bottleneck_category": "MANUAL_QUALITY_CONTROL",
  "severity": "HIGH",
  "evidence_quote": "Exact verbatim quote from text",
  "workflow_gap_summary": "1-sentence summary of the workflow gap",
  "proposed_solution_angle": "How our service solves this bottleneck"
}}"""

            raw = await async_call_ollama(
                prompt=prompt,
                system_prompt="You are an expert enterprise operations auditor. Output JSON only.",
                temperature=0.1,
                max_tokens=300,
                timeout=7.5
            )

            if raw:
                cleaned = re.sub(r"^```json\s*", "", raw.strip(), flags=re.MULTILINE)
                cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE)
                start = cleaned.find("{")
                end = cleaned.rfind("}")
                if start != -1 and end != -1:
                    parsed = json.loads(cleaned[start:end + 1])
                    if isinstance(parsed, dict) and "has_operational_bottleneck" in parsed:
                        has_b = bool(parsed.get("has_operational_bottleneck", False))
                        b_cat = str(parsed.get("bottleneck_category", "")).upper()
                        # Validate category
                        valid_cats = {c.value for c in OperationalInefficiencyCategory}
                        if b_cat not in valid_cats:
                            b_cat = signals[0]["category"] if signals else OperationalInefficiencyCategory.MANUAL_QUALITY_CONTROL.value

                        return {
                            "has_operational_bottleneck": has_b,
                            "bottleneck_category": b_cat if has_b else None,
                            "severity": str(parsed.get("severity", "HIGH" if has_b else "LOW")).upper(),
                            "evidence_quote": str(parsed.get("evidence_quote", "")).strip(),
                            "workflow_gap_summary": str(parsed.get("workflow_gap_summary", "")).strip(),
                            "proposed_solution_angle": str(parsed.get("proposed_solution_angle", "")).strip()
                        }
        except Exception as e:
            logger.debug(f"[OperationalAuditEngine] LLM audit failed: {e}")

    # Fallback heuristic: synthesize audit from strongest deterministic signal
    if signals:
        top = signals[0]
        cat = top["category"]
        snippet = top["evidence_snippet"]

        gap_summaries = {
            OperationalInefficiencyCategory.MANUAL_QUALITY_CONTROL.value: (
                f"Manual inspection processes detected ('{top['keyword']}'), causing human error, defect oversight, and inspection bottlenecks."
            ),
            OperationalInefficiencyCategory.REPETITIVE_DATA_ENTRY.value: (
                f"Paper forms or manual spreadsheet logging detected ('{top['keyword']}'), leading to double data entry and administrative delays."
            ),
            OperationalInefficiencyCategory.LEGACY_SOFTWARE_DISPATCH.value: (
                f"Legacy phone or paper-based dispatching workflow detected ('{top['keyword']}'), slowing fulfillment scheduling."
            ),
            OperationalInefficiencyCategory.HIGH_LABOR_TURNOVER_HIRING.value: (
                f"Active manual staffing recruitment detected ('{top['keyword']}'), creating operational friction and labor overhead."
            ),
            OperationalInefficiencyCategory.UNAUTOMATED_INVENTORY_FLOW.value: (
                f"Manual stock counting or physical ledgers detected ('{top['keyword']}'), preventing real-time inventory visibility."
            )
        }

        solution_angles = {
            OperationalInefficiencyCategory.MANUAL_QUALITY_CONTROL.value: (
                f"Automated Computer Vision & AI Quality Control to replace manual inspection and achieve zero-defect throughput."
            ),
            OperationalInefficiencyCategory.REPETITIVE_DATA_ENTRY.value: (
                f"Automated OCR and Digital Workflow Integration to eliminate paper paperwork and manual spreadsheets."
            ),
            OperationalInefficiencyCategory.LEGACY_SOFTWARE_DISPATCH.value: (
                f"Modern Cloud-Based Automated Dispatch & Real-Time Tracking Portal to eliminate phone-based coordination."
            ),
            OperationalInefficiencyCategory.HIGH_LABOR_TURNOVER_HIRING.value: (
                f"Autonomous Process Automation to reduce headcount dependency and insulate operations from labor turnover."
            ),
            OperationalInefficiencyCategory.UNAUTOMATED_INVENTORY_FLOW.value: (
                f"Barcode/RFID-Integrated Real-Time Warehouse Management System (WMS) to automate inventory tracking."
            )
        }

        return {
            "has_operational_bottleneck": True,
            "bottleneck_category": cat,
            "severity": "HIGH",
            "evidence_quote": snippet,
            "workflow_gap_summary": gap_summaries.get(cat, f"Operational workflow bottleneck detected: {top['keyword']}."),
            "proposed_solution_angle": solution_angles.get(cat, f"Deploy automated digital systems tailored to {target_service or 'operations'}.")
        }

    # No bottlenecks detected
    return {
        "has_operational_bottleneck": False,
        "bottleneck_category": None,
        "severity": "LOW",
        "evidence_quote": "",
        "workflow_gap_summary": "No critical manual bottlenecks or legacy workflow gaps detected.",
        "proposed_solution_angle": ""
    }


# ─── 5. Unified Audit Engine Entry Point ─────────────────────────────────────

async def audit_company_operations(
    domain: str,
    multi_page_text: str,
    target_service: str = "",
    use_llm: bool = True
) -> Dict[str, Any]:
    """
    Main entry point for Step 7: Service-Agnostic Operational Bottleneck Audit Engine.

    1. Executes Tier 1 deterministic keyword/regex extraction.
    2. Executes Tier 2 LLM operational analysis.
    3. Guarantees clean structured payload with evidence quotes and solution angles.
    """
    # ── Tier 1: Deterministic Extraction ──────────────────────────────────────
    deterministic_signals = extract_deterministic_bottlenecks(multi_page_text)

    # ── Tier 2: Deep LLM Operational Auditor ──────────────────────────────────
    audit_res = await run_llm_operational_audit(
        domain=domain,
        multi_page_text=multi_page_text,
        target_service=target_service,
        deterministic_signals=deterministic_signals,
        use_llm=use_llm
    )

    # Attach diagnostic metadata
    audit_res["deterministic_signals_count"] = len(deterministic_signals)
    audit_res["top_deterministic_signal"] = deterministic_signals[0] if deterministic_signals else None

    return audit_res
