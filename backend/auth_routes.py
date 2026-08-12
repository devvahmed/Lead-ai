import os
import re
import json
import time
import urllib.request
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
from sqlalchemy.orm import Session

from auth_models import Company, get_auth_db
from auth_utils import hash_password, verify_password, create_access_token, decode_access_token
import database

# Load environment from root .env.local if present
env_local_path = os.path.join(os.path.dirname(__file__), "..", ".env.local")
if os.path.exists(env_local_path):
    load_dotenv(env_local_path)
load_dotenv()

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()

# In-memory cache for company-specific suggested industries
_SUGGESTED_INDUSTRIES_CACHE = {}

# ─── Industry suggestions cache: {company_id: (timestamp, [industry_tags])} ─────────────
# Results are cached for 30 min per company so fresh profile changes are reflected
_SUGGEST_INDUSTRIES_CACHE_TTL = 1800  # 30 minutes

# ─── Pydantic Schemas ──────────────────────────────────────────────────────────

class CompanySignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    website: Optional[str] = None
    industry: Optional[str] = None
    services: Optional[str] = None
    target_customers: Optional[str] = None
    description: Optional[str] = None
    smtp_email: Optional[str] = None
    smtp_password: Optional[str] = None

class CompanyLoginRequest(BaseModel):
    email: EmailStr
    password: str

class CompanyResponse(BaseModel):
    id: int
    name: str
    email: str
    website: Optional[str] = None
    industry: Optional[str] = None
    services: Optional[str] = None
    target_customers: Optional[str] = None
    description: Optional[str] = None
    logo_path: Optional[str] = None
    ai_enriched_profile: Optional[str] = None
    smtp_email: Optional[str] = None
    smtp_password: Optional[str] = None

    class Config:
        from_attributes = True

class CompanyUpdateRequest(BaseModel):
    name: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    services: Optional[str] = None
    target_customers: Optional[str] = None
    description: Optional[str] = None
    smtp_email: Optional[str] = None
    smtp_password: Optional[str] = None

class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    company: CompanyResponse

class DashboardStatsResponse(BaseModel):
    company_id: int
    company_name: str
    total_companies_found: int
    qualified_leads: int
    active_outreach: int
    avg_trust_score: float
    total_emails_generated: Optional[int] = 0
    recent_activity: List[Any] = []
    weekly_chart: List[Any] = []

class SuggestedIndustriesResponse(BaseModel):
    company_id: int
    company_name: str
    suggested_industries: List[str]

# ─── AI Company Profile Enrichment Helper ────────────────────────────────────

async def enrich_company_profile(
    company_name: str,
    website: Optional[str] = None,
    services: Optional[str] = None,
    target_customers: Optional[str] = None,
    description: Optional[str] = None,
    industry: Optional[str] = None
) -> str:
    """
    Synthesizes a structured AI-enriched company profile combining raw signup form fields
    and real-time website crawling content. Handles website scrape failures gracefully.
    """
    scraped_content = ""
    evidence_source = "Form fields only"

    clean_url = website.strip() if website else ""
    if clean_url:
        if not clean_url.startswith(("http://", "https://")):
            clean_url = "https://" + clean_url
        try:
            from email_outreach import fetch_url_content_with_subpages
            scraped_text, label = await fetch_url_content_with_subpages(clean_url, timeout=5.0)
            if scraped_text and len(scraped_text.strip()) > 150:
                scraped_content = scraped_text[:3500].strip()
                evidence_source = f"Scraped website ({clean_url}) [{label}]"
                print(f"[Profile Enrichment] Crawled website '{clean_url}' successfully ({len(scraped_content)} chars)")
            else:
                print(f"[Profile Enrichment] Website '{clean_url}' returned thin text — falling back to form inputs")
        except Exception as e:
            print(f"[Profile Enrichment Warning] Failed to crawl '{clean_url}': {e} — continuing with form inputs only")

    form_summary = f"""
Company Name    : {company_name or 'N/A'}
Website         : {clean_url or 'None'}
Industry Sector : {industry or 'Not specified'}
Services/Products: {services or 'Not specified'}
Target Customers: {target_customers or 'Not specified'}
Overview        : {description or 'Not specified'}
"""

    prompt = f"""You are a B2B strategy analyst. Synthesize a structured AI-Enriched Company Profile for '{company_name}'.

=== INPUT SOURCE DATA ===
Form Fields:
{form_summary}

Website Evidence ({evidence_source}):
---
{scraped_content if scraped_content else '(No website content available)'}
---

=== INSTRUCTIONS ===
Generate a comprehensive, structured AI-Enriched Profile in plain text with clear headings:

1. CORE BUSINESS & OFFERINGS: Restate clearly what the company actually manufactures, sells, or provides based on both form input and website evidence.
2. IDEAL CUSTOMER PROFILE (ICP): Identify the specific target industries, business types, company sizes, and buyer personas that buy from this company.
3. KEY VALUE PROPOSITIONS & DIFFERENTIATORS: Highlight main competitive advantages, fleet/service capabilities, or unique selling points.
4. DISCREPANCY & ENHANCEMENT NOTES: Note any additional capabilities found on the website that were missing from the form inputs, or confirm full alignment.

Output a clean, professional profile format. Max 400 words. Do NOT include generic conversational filler."""

    try:
        from discover import call_ollama
        enriched_text = call_ollama(
            prompt=prompt,
            system_prompt="You are an expert B2B company profiler. Output a structured profile.",
            temperature=0.2,
            max_tokens=600,
            timeout=15.0
        )
        if enriched_text and len(enriched_text.strip()) > 50:
            return enriched_text.strip()
    except Exception as e:
        print(f"[Profile Enrichment Ollama Error]: {e}")

    return f"CORE BUSINESS: {services or description or 'B2B Products & Services'}\nIDEAL CUSTOMER PROFILE: {target_customers or 'B2B Clients'}\nVALUE PROPOSITION: High quality solutions in {industry or 'B2B'}."


# ─── Auth Endpoints ────────────────────────────────────────────────────────────

@router.post("/signup", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(company_data: CompanySignupRequest, db: Session = Depends(get_auth_db)):
    """Registers a new Company, generates AI-enriched profile, and returns JWT access token."""
    existing = db.query(Company).filter(Company.email == company_data.email.lower().strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A company with this email address is already registered."
        )

    hashed_pwd = hash_password(company_data.password)

    # Trigger AI profile enrichment at signup time
    ai_profile = await enrich_company_profile(
        company_name=company_data.name.strip(),
        website=company_data.website,
        services=company_data.services,
        target_customers=company_data.target_customers,
        description=company_data.description,
        industry=company_data.industry
    )

    new_company = Company(
        name=company_data.name.strip(),
        email=company_data.email.lower().strip(),
        hashed_password=hashed_pwd,
        website=company_data.website.strip() if company_data.website else None,
        industry=company_data.industry.strip() if company_data.industry else None,
        services=company_data.services.strip() if company_data.services else None,
        target_customers=company_data.target_customers.strip() if company_data.target_customers else None,
        description=company_data.description.strip() if company_data.description else None,
        ai_enriched_profile=ai_profile,
        smtp_email=company_data.smtp_email.strip() if company_data.smtp_email else None,
        smtp_password=company_data.smtp_password.strip() if company_data.smtp_password else None
    )

    db.add(new_company)
    db.commit()
    db.refresh(new_company)

    token = create_access_token(data={"sub": str(new_company.id), "email": new_company.email})

    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        company=CompanyResponse.model_validate(new_company)
    )


@router.post("/login", response_model=AuthTokenResponse)
def login(login_data: CompanyLoginRequest, db: Session = Depends(get_auth_db)):
    """Authenticates an existing Company and returns a JWT access token."""
    company = db.query(Company).filter(Company.email == login_data.email.lower().strip()).first()
    if not company or not verify_password(login_data.password, company.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password credentials."
        )

    token = create_access_token(data={"sub": str(company.id), "email": company.email})

    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        company=CompanyResponse.model_validate(company)
    )


@router.get("/me", response_model=CompanyResponse)
def get_current_company(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_auth_db)):
    """Decodes JWT bearer token and returns the profile of the current authenticated Company."""
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or missing JWT authorization token."
        )

    company_id = int(payload["sub"])
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authenticated company profile no longer exists in system."
        )

    return company


def get_current_company_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_auth_db)
) -> Company:
    """Decodes JWT bearer token if present; falls back to default company (id=1) for dev/guest access."""
    if credentials and credentials.credentials:
        payload = decode_access_token(credentials.credentials)
        if payload and "sub" in payload:
            try:
                cid = int(payload["sub"])
                co = db.query(Company).filter(Company.id == cid).first()
                if co:
                    return co
            except Exception:
                pass
    fallback = db.query(Company).first()
    if fallback:
        return fallback
    return Company(id=1, name="Default Company", email="admin@example.com")


@router.put("/profile", response_model=CompanyResponse)
async def update_company_profile(
    profile_data: CompanyUpdateRequest,
    current_company: Company = Depends(get_current_company),
    db: Session = Depends(get_auth_db)
):
    """Updates company profile and re-triggers AI profile enrichment."""
    if profile_data.name is not None:
        current_company.name = profile_data.name.strip()
    if profile_data.website is not None:
        current_company.website = profile_data.website.strip()
    if profile_data.industry is not None:
        current_company.industry = profile_data.industry.strip()
    if profile_data.services is not None:
        current_company.services = profile_data.services.strip()
    if profile_data.target_customers is not None:
        current_company.target_customers = profile_data.target_customers.strip()
    if profile_data.description is not None:
        current_company.description = profile_data.description.strip()

    # Re-trigger profile enrichment on profile update
    ai_profile = await enrich_company_profile(
        company_name=current_company.name,
        website=current_company.website,
        services=current_company.services,
        target_customers=current_company.target_customers,
        description=current_company.description,
        industry=current_company.industry
    )
    current_company.ai_enriched_profile = ai_profile

    db.commit()
    db.refresh(current_company)
    return CompanyResponse.model_validate(current_company)


@router.get("/dashboard-stats", response_model=DashboardStatsResponse)
def get_dashboard_stats_endpoint(current_company: Company = Depends(get_current_company)):
    """Returns real-time multi-tenant dashboard stats isolated to current_company.id."""
    stats = database.get_dashboard_stats(current_company.id)
    stats["company_name"] = current_company.name
    return stats


@router.get("/suggest-industries", response_model=SuggestedIndustriesResponse)
def get_suggested_industries_endpoint(current_company: Company = Depends(get_current_company)):
    """
    Generates dynamic, company-profile aware target industry recommendations using Groq LLM.
    Caches results per company_id to respect Groq API rate limits.
    """
    company_id = current_company.id
    cached = _SUGGESTED_INDUSTRIES_CACHE.get(company_id)
    if cached:
        cached_time, cached_tags = cached
        if time.time() - cached_time < _SUGGEST_INDUSTRIES_CACHE_TTL:
            return SuggestedIndustriesResponse(
                company_id=company_id,
                company_name=current_company.name,
                suggested_industries=cached_tags
            )
        else:
            del _SUGGESTED_INDUSTRIES_CACHE[company_id]  # Expired; discard and re-generate

    default_tags = ["Fintech", "Healthcare", "E-Commerce & Retail", "Software & SaaS", "Logistics & Supply Chain", "Industrial Manufacturing"]

    prompt = f"""
    We are '{current_company.name}', operating in the '{current_company.industry or 'Technology'}' sector.
    Our products/services: '{current_company.services or current_company.description or 'B2B Products & Services'}'.
    Our ideal target clients: '{current_company.target_customers or 'Enterprise B2B companies'}'.

    Identify 6 high-value target industry verticals or sectors where our solutions provide strong business ROI.
    Return ONLY a JSON object with key "suggested_industries" containing 6 short industry titles (1-3 words each), e.g.:
    {{"suggested_industries": ["Fintech & Banking", "Healthcare Systems", "Cloud Infrastructure", "E-Commerce", "Government", "Logistics"]}}
    """

    try:
        from discover import call_ollama
        raw_content = call_ollama(
            prompt=prompt,
            system_prompt="You are a B2B strategy analyst. Output valid JSON.",
            temperature=0.2,
            max_tokens=300,
            timeout=10.0
        )
        if raw_content:
            raw_content = re.sub(r'^```(?:json)?\s*', '', raw_content)
            raw_content = re.sub(r'\s*```$', '', raw_content)
            parsed = json.loads(raw_content)
            industries = parsed.get("suggested_industries", default_tags)
            if isinstance(industries, list) and len(industries) > 0:
                clean_tags = [str(t).strip() for t in industries if isinstance(t, str) and len(t.strip()) > 0][:6]
                _SUGGESTED_INDUSTRIES_CACHE[company_id] = (time.time(), clean_tags)  # Store with timestamp
                return SuggestedIndustriesResponse(
                    company_id=company_id,
                    company_name=current_company.name,
                    suggested_industries=clean_tags
                )
    except Exception as e:
        print(f"[Suggest Industries Ollama Error]: {e}")

    return SuggestedIndustriesResponse(
        company_id=company_id,
        company_name=current_company.name,
        suggested_industries=default_tags
    )
