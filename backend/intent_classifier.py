"""
Strict Buyer Intent & Non-Job Contract Classifier (Step 5).

Filters out:
1. Seller Agencies: Other dev shops, agencies, or freelancers pitching their own services.
2. Standard 9-to-5 Employment: Salaried corporate jobs with health benefits, W2 forms, 401k, or annual salaries.

Ensures the pipeline only approves:
- Genuine buyers seeking external agency vendors, contractors, or project partners.
- Organizations issuing RFPs/RFQs/SOWs.
- Commercial operating targets (facilities, manufacturing, supply chain) needing external vendor services.

Architecture:
- Tier 1: Deterministic Pattern Classifier (classify_intent_deterministic)
- Tier 2: Contextual LLM Intent Gatekeeper (evaluate_contextual_intent)
- Unified Entry Point: run_intent_classifier
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("intent_classifier")
logger.setLevel(logging.INFO)

# ─── 1. Deterministic Rule Sets ───────────────────────────────────────────────

SELLER_AGENCY_PATTERNS = [
    re.compile(r'(?i)\b(?:we\s+are\s+a(?:n)?\s+(?:web|software|app|mobile|digital|marketing|design|development|dev|seo|it|consulting)\s+agency)\b'),
    re.compile(r'(?i)\b(?:hire\s+our\s+(?:team|developers?|engineers?|agency|programmers?|designers?))\b'),
    re.compile(r'(?i)\b(?:our\s+(?:portfolio|case\s+studies|previous\s+work|client\s+roster))\b'),
    re.compile(r'(?i)\b(?:our\s+clients\s+(?:include|are|range\s+from))\b'),
    re.compile(r'(?i)\b(?:book\s+a\s+(?:discovery|free|strategy|intro|consultation)\s+call(?:\s+with\s+us)?)\b'),
    re.compile(r'(?i)\b(?:we\s+offer\s+(?:custom\s+)?(?:software|web|app|mobile|seo|marketing|consulting)\s+(?:development|services))\b'),
    re.compile(r'(?i)\b(?:leading\s+provider\s+of\s+(?:custom\s+)?(?:software|web|it|marketing|development)\s+services)\b'),
    re.compile(r'(?i)\[\s*for\s+hire\s*\]'),
    re.compile(r'(?i)\b(?:available\s+for\s+hire|hire\s+me\s+for|my\s+portfolio|offering\s+freelance\s+services)\b'),
    re.compile(r'(?i)\b(?:our\s+tech\s+stack\s+includes.*hire\s+us)\b'),
]

EMPLOYMENT_9TO5_PATTERNS = [
    re.compile(r'(?i)\b(?:full[-\s]?time\s+employee)\b'),
    re.compile(r'(?i)\b(?:w[-\s]?2(?:\s+position|\s+only|\s+contract|\s+employee|\s+role)?)\b'),
    re.compile(r'(?i)\b(?:annual\s+salary|base\s+salary\s+of|\$\d{2,3}[,\.]?\d{3}\s*(?:-\s*\$\d{2,3}[,\.]?\d{3})?\s*(?:/yr|/year|per\s+year|annually))\b'),
    re.compile(r'(?i)\b(?:401\s*\(?k\)?\s*(?:match|matching|plan|contribution))\b'),
    re.compile(r'(?i)\b(?:health\s+insurance|medical[,\s]+dental[,\s]+(?:and\s+)?vision)\b'),
    re.compile(r'(?i)\b(?:dental\s+benefits|vision\s+insurance|life\s+insurance\s+policy)\b'),
    re.compile(r'(?i)\b(?:paid\s+time\s+off|\bpto\b|paid\s+vacation|sick\s+leave\s+days)\b'),
    re.compile(r'(?i)\b(?:on[-\s]?site\s+5\s+days\s+(?:a\s+week|per\s+week)|in[-\s]?office\s+mandatory)\b'),
    re.compile(r'(?i)\b(?:we\s+are\s+seeking\s+a\s+full[-\s]?time\s+(?:engineer|developer|designer|manager|architect))\b'),
    re.compile(r'(?i)\b(?:must\s+be\s+eligible\s+to\s+work\s+on\s+w2)\b'),
]

CONTRACT_BUYER_PATTERNS = [
    re.compile(r'(?i)\b(?:looking\s+for\s+(?:an?\s+)?(?:agency|contractor|vendor|consultant|firm|partner|expert|engineering\s+shop))\b'),
    re.compile(r'(?i)\b(?:seeking\s+(?:an?\s+)?(?:vendor|agency|contractor|partner|provider|supplier|team))\b'),
    re.compile(r'(?i)\b(?:request\s+for\s+proposals?|\brfp\b)\b'),
    re.compile(r'(?i)\b(?:request\s+for\s+quotations?|\brfq\b)\b'),
    re.compile(r'(?i)\b(?:statement\s+of\s+work|\bsow\b)\b'),
    re.compile(r'(?i)\b(?:contractor\s+needed|agency\s+needed|developer\s+needed|vendor\s+needed)\b'),
    re.compile(r'(?i)\b(?:outsource\s+(?:this|our|the|development|project|work))\b'),
    re.compile(r'(?i)\b(?:on\s+a\s+project\s+basis|fixed[-\s]?price\s+contract|fixed[-\s]?rate|hourly\s+rate\s+contract)\b'),
    re.compile(r'(?i)\b(?:vendor\s+application|subcontractor\s+agreement|contract\s+opportunity)\b'),
    re.compile(r'(?i)\b(?:budget:\s*\$\d+|\bscope\s+of\s+work\b)\b'),
    re.compile(r'(?i)\[\s*hiring\s*\](?=.*(?:agency|contractor|vendor|project|rfp|contract|freelance))'),
]

COMMERCIAL_TARGET_PATTERNS = [
    # Industrial & Manufacturing
    re.compile(r'(?i)\b(?:our\s+(?:facilities|manufacturing|operations|plant|warehouse|fleet|factory|production\s+lines?|cleanroom))\b'),
    re.compile(r'(?i)\b(?:we\s+manufacture|we\s+produce|industrial\s+solutions|iso\s+9001|turnkey\s+systems)\b'),
    re.compile(r'(?i)\b(?:request\s+a\s+quote|request\s+an\s+rfq|request\s+pricing|contact\s+our\s+sales\s+division)\b'),
    # E-Commerce, Retail & Consumer Brands
    re.compile(r'(?i)\b(?:shop\s+online|add\s+to\s+cart|view\s+cart|checkout|free\s+shipping|buy\s+online|official\s+store|new\s+arrivals|our\s+collection|track\s+order|order\s+online|order\s+today|product\s+catalog|in\s+stock|return\s+policy)\b'),
    # Healthcare & Medical Practices
    re.compile(r'(?i)\b(?:book\s+(?:an?\s+)?appointment|patient\s+care|our\s+clinic|dental\s+practice|medical\s+center|schedule\s+consultation|health\s+services|our\s+physicians|patient\s+portal)\b'),
    # Real Estate & Housing
    re.compile(r'(?i)\b(?:properties\s+for\s+sale|real\s+estate\s+agency|property\s+listings|schedule\s+a\s+viewing|apartments\s+for\s+rent|commercial\s+leasing|property\s+management)\b'),
    # Hospitality, Dining & Travel
    re.compile(r'(?i)\b(?:reserve\s+a\s+table|book\s+a\s+room|hotel\s+reservations|our\s+menu|dining\s+reservations|guest\s+accommodations)\b'),
    # Education & Academies
    re.compile(r'(?i)\b(?:admissions|apply\s+online|tuition\s+fees|academic\s+programs|enroll\s+now|course\s+catalog)\b')
]


# ─── 2. Tier 1: Deterministic Pattern Classifier ──────────────────────────────

def classify_intent_deterministic(
    text_content: str,
    title: str = ""
) -> Tuple[Optional[bool], str, float]:
    """
    Evaluates text for seller agency copy, 9-to-5 employment benefits, and contract buying signals.
    
    Returns:
        (is_buyer: Optional[bool], intent_type: str, confidence: float)
        - (False, "SELLER_AGENCY", 0.95): Competitor agency pitching services.
        - (False, "STANDARD_EMPLOYMENT_JOB", 0.95): 9-to-5 salaried job posting.
        - (True, "CONTRACT_BUYER", 0.85): Clear contract/RFP/vendor buyer.
        - (True, "COMMERCIAL_TARGET", 0.80): Operating commercial business (target customer).
        - (None, "AMBIGUOUS", 0.50): Inconclusive (defer to Tier 2 contextual evaluation).
    """
    corpus = f"{title}\n{text_content}".strip()
    if not corpus:
        return None, "AMBIGUOUS", 0.5

    corpus_lower = corpus.lower()

    # 1. Check for Seller Agency Pitch
    # (Dev shops, marketing agencies, freelancers selling similar services)
    seller_hits = [p.pattern for p in SELLER_AGENCY_PATTERNS if p.search(corpus)]
    if seller_hits:
        # Check if it has an explicit RFP/buying context that overrides (e.g. "We are an agency looking for another agency partner")
        buyer_override = any(bp.search(corpus) for bp in CONTRACT_BUYER_PATTERNS)
        if not buyer_override:
            return False, "SELLER_AGENCY", 0.95

    # 2. Check for Standard 9-to-5 Employment
    # (Salaried positions with health benefits, W2, 401k, etc.)
    employment_hits = [p.pattern for p in EMPLOYMENT_9TO5_PATTERNS if p.search(corpus)]
    if len(employment_hits) >= 1:
        # Check if it's explicitly a 1099 / independent contractor contract
        if "1099" not in corpus_lower and "independent contractor" not in corpus_lower:
            return False, "STANDARD_EMPLOYMENT_JOB", 0.95

    # 3. Check for Contract Buyer / RFP Signals
    contract_hits = [p.pattern for p in CONTRACT_BUYER_PATTERNS if p.search(corpus)]
    if contract_hits:
        return True, "CONTRACT_BUYER", 0.85

    # 4. Check for Commercial Operating Target Business (e.g. factories, retail stores, logistics, healthcare)
    # These are operating companies that can be pitched our services
    commercial_hits = [p.pattern for p in COMMERCIAL_TARGET_PATTERNS if p.search(corpus)]
    if len(commercial_hits) >= 1:
        return True, "COMMERCIAL_TARGET", 0.85

    # 5. Inconclusive deterministic signals
    return None, "AMBIGUOUS", 0.50


# ─── 3. Tier 2: Contextual LLM Intent Gatekeeper ───────────────────────────────

async def evaluate_contextual_intent(
    title: str,
    text_content: str,
    target_service: str = "",
    use_llm: bool = True
) -> Dict[str, Any]:
    """
    Contextual LLM intent classifier for ambiguous postings or company websites.
    Evaluates whether the candidate is:
    - CONTRACT_BUYER: Seeking external vendors, contractors, or project partners.
    - COMMERCIAL_TARGET: A commercial operating business that could procure external services.
    - SELLER_AGENCY: A competing agency/seller pitching their own services.
    - STANDARD_EMPLOYMENT_JOB: A 9-to-5 salaried employee role.
    - INFORMATIONAL: An article, tutorial, news, or non-commercial content.
    """
    text_sample = f"{title}\n{text_content}".strip()[:1800]

    if use_llm and len(text_sample) > 50:
        try:
            from discover import async_call_ollama

            prompt = f"""You are a Strict B2B Buyer Intent & Opportunity Classifier.

POST TITLE: "{title}"
OUR SERVICE OFFERING: "{target_service or 'B2B Solutions & Engineering'}"
POST / PAGE CONTENT:
\"\"\"{text_sample}\"\"\"

TASK:
Determine if this posting or company represents:
1. "CONTRACT_BUYER": An organization actively seeking an external agency, contractor, vendor, RFP, or project partner.
2. "COMMERCIAL_TARGET": An operating commercial business (e.g., e-commerce store, consumer brand selling products/clothing/goods online, medical clinic, logistics warehouse, manufacturer, restaurant, hotel) that buys B2B products and services. (THESE ARE TARGET BUYERS).
3. "SELLER_AGENCY": A competing digital marketing, IT, web design, or software development agency trying to SELL IT/software/marketing services. (NOTE: Retail brands or e-commerce stores selling physical goods to shoppers are COMMERCIAL_TARGET, NOT seller agencies).
4. "STANDARD_EMPLOYMENT_JOB": A standard 9-to-5 salaried corporate job listing offering employee benefits (401k, healthcare, W2, salaried employment).
5. "INFORMATIONAL": A blog article, tutorial, discussion, or news story with no buying intent.

RULES:
- Approve ("is_valid_buyer": true) ONLY if the intent is "CONTRACT_BUYER" or "COMMERCIAL_TARGET".
- Reject ("is_valid_buyer": false) if the intent is "SELLER_AGENCY", "STANDARD_EMPLOYMENT_JOB", or "INFORMATIONAL".

Respond ONLY in valid JSON format. No markdown backticks:
{{
  "is_valid_buyer": true or false,
  "intent_type": "CONTRACT_BUYER" | "COMMERCIAL_TARGET" | "SELLER_AGENCY" | "STANDARD_EMPLOYMENT_JOB" | "INFORMATIONAL",
  "confidence": 85,
  "reason": "1-sentence factual explanation"
}}"""

            raw = await async_call_ollama(
                prompt=prompt,
                system_prompt="You are a strict B2B buyer intent classifier. Output JSON only.",
                temperature=0.1,
                max_tokens=200,
                timeout=7.0
            )

            if raw:
                cleaned = re.sub(r"^```json\s*", "", raw.strip(), flags=re.MULTILINE)
                cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE)
                start = cleaned.find("{")
                end = cleaned.rfind("}")
                if start != -1 and end != -1:
                    parsed = json.loads(cleaned[start:end + 1])
                    if isinstance(parsed, dict) and "is_valid_buyer" in parsed:
                        return {
                            "is_valid_buyer": bool(parsed["is_valid_buyer"]),
                            "intent_type": str(parsed.get("intent_type", "CONTRACT_BUYER" if parsed["is_valid_buyer"] else "SELLER_AGENCY")),
                            "confidence": int(parsed.get("confidence", 80)),
                            "reason": str(parsed.get("reason", "Contextual LLM intent evaluation"))
                        }
        except Exception as e:
            logger.debug(f"[IntentClassifier] LLM evaluation error: {e}")

    # Fallback heuristic:
    text_lower = text_sample.lower()
    if any(p in text_lower for p in ("rfp", "rfq", "vendor", "contractor", "contract", "outsource", "looking for agency", "seeking vendor", "project contract", "need an agency", "engineering shop")):
        return {
            "is_valid_buyer": True,
            "intent_type": "CONTRACT_BUYER",
            "confidence": 75,
            "reason": "Heuristic fallback detected buying/contract terms"
        }

    if any(p in text_lower for p in ("we are a web development agency", "hire our team", "our portfolio")):
        return {
            "is_valid_buyer": False,
            "intent_type": "SELLER_AGENCY",
            "confidence": 80,
            "reason": "Heuristic fallback detected competing agency pitch"
        }

    if any(p in text_lower for p in ("401k", "health insurance", "annual salary", "w2", "dental")):
        return {
            "is_valid_buyer": False,
            "intent_type": "STANDARD_EMPLOYMENT_JOB",
            "confidence": 85,
            "reason": "Heuristic fallback detected 9-to-5 salaried employment perks"
        }

    # Default to commercial target if it has commercial operational language
    if any(p in text_lower for p in ("facilities", "manufacturing", "operations", "contact us", "solutions")):
        return {
            "is_valid_buyer": True,
            "intent_type": "COMMERCIAL_TARGET",
            "confidence": 70,
            "reason": "Commercial operating entity"
        }

    return {
        "is_valid_buyer": False,
        "intent_type": "INFORMATIONAL",
        "confidence": 60,
        "reason": "Insufficient buying or commercial footprint detected"
    }


# ─── 4. Unified Intent Classifier Entry Point ─────────────────────────────────

async def run_intent_classifier(
    title: str,
    text_content: str,
    target_service: str = "",
    is_intent_source: bool = False,
    use_llm: bool = True
) -> Tuple[bool, str, str]:
    """
    Main entry point for Step 5: Strict Buyer Intent & Non-Job Contract Classifier.
    
    Returns:
        (is_valid_buyer: bool, intent_type: str, reason: str)
    """
    # ── Tier 1: Deterministic Check ───────────────────────────────────────────
    is_buyer, intent_type, conf = classify_intent_deterministic(
        text_content=text_content,
        title=title
    )

    if is_buyer is False:
        return False, intent_type, f"[Tier 1 Deterministic] Detected {intent_type.replace('_', ' ').title()}"

    if is_buyer is True and conf >= 0.80:
        # Definite approval (CONTRACT_BUYER or strong COMMERCIAL_TARGET)
        return True, intent_type, f"[Tier 1 Deterministic] Approved {intent_type.replace('_', ' ').title()}"

    # ── Tier 2: Contextual LLM Gatekeeper ─────────────────────────────────────
    contextual_res = await evaluate_contextual_intent(
        title=title,
        text_content=text_content,
        target_service=target_service,
        use_llm=use_llm
    )

    is_valid = bool(contextual_res.get("is_valid_buyer", False))
    res_intent = contextual_res.get("intent_type", "CONTRACT_BUYER" if is_valid else "INFORMATIONAL")
    res_reason = contextual_res.get("reason", "Contextual evaluation")

    return is_valid, res_intent, f"[Tier 2 Contextual] {res_reason}"

