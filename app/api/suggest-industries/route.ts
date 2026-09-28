import { NextRequest, NextResponse } from 'next/server';

function getBackendUrl(): string {
  const envUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
  if (!envUrl || envUrl.startsWith('/')) return 'http://localhost:8000';
  return envUrl.replace(/\/$/, '');
}

// ─── Comprehensive Keyword → Industry Mapping ─────────────────────────────────
// Score 10 = perfect fit, 7 = decent fit. Enables instant 0ms suggestions.
const KEYWORD_INDUSTRY_MAP: Record<string, Array<{ industry: string; reason: string; score: number }>> = {
  'ai': [
    { industry: 'Healthcare & MedTech', reason: 'AI-powered diagnostics, imaging analysis, and clinical decision support.', score: 10 },
    { industry: 'Financial Services & Fintech', reason: 'Fraud detection, risk scoring, and algorithmic trading automation.', score: 10 },
    { industry: 'Manufacturing & Industry 4.0', reason: 'Predictive maintenance, defect detection, and process optimization.', score: 9 },
    { industry: 'Retail & E-Commerce', reason: 'Personalization engines, demand forecasting, and visual search.', score: 9 },
    { industry: 'Logistics & Supply Chain', reason: 'Route optimization, demand prediction, and warehouse automation.', score: 8 },
    { industry: 'HR Tech & Recruitment', reason: 'Resume screening, candidate matching, and workforce analytics.', score: 8 },
    { industry: 'Legal Tech', reason: 'Contract analysis, document review, and compliance automation.', score: 7 },
    { industry: 'EdTech & Online Learning', reason: 'Adaptive learning paths, tutoring bots, and student analytics.', score: 7 },
  ],
  'machine learning': [
    { industry: 'Financial Services & Fintech', reason: 'Credit scoring, fraud detection, and real-time risk assessment models.', score: 10 },
    { industry: 'Healthcare & MedTech', reason: 'Drug discovery, patient outcome prediction, and genomics analysis.', score: 10 },
    { industry: 'Manufacturing & Industry 4.0', reason: 'Predictive maintenance and quality control through sensor data analysis.', score: 9 },
    { industry: 'Insurance & InsurTech', reason: 'Claims prediction, underwriting automation, and churn prevention.', score: 9 },
    { industry: 'Retail & E-Commerce', reason: 'Customer lifetime value prediction and inventory optimization.', score: 8 },
    { industry: 'Cybersecurity', reason: 'Anomaly detection and threat intelligence powered by behavioral ML.', score: 8 },
  ],
  'automation': [
    { industry: 'Manufacturing & Industry 4.0', reason: 'Robotic assembly lines, process automation, and smart factory integration.', score: 10 },
    { industry: 'Finance & Accounting', reason: 'Invoice processing, reconciliation, and regulatory reporting automation.', score: 10 },
    { industry: 'HR Tech & Recruitment', reason: 'Onboarding workflows, payroll automation, and compliance tracking.', score: 9 },
    { industry: 'Logistics & Supply Chain', reason: 'Warehouse picking automation, shipping label generation, and tracking.', score: 9 },
    { industry: 'Healthcare & MedTech', reason: 'Prior authorization, claims processing, and patient scheduling automation.', score: 8 },
    { industry: 'Legal Tech', reason: 'Contract lifecycle automation and regulatory document generation.', score: 7 },
    { industry: 'Real Estate & PropTech', reason: 'Lease management, maintenance routing, and tenant onboarding automation.', score: 7 },
  ],
  'robotics': [
    { industry: 'Manufacturing & Industry 4.0', reason: 'Assembly, welding, painting, and quality inspection robots on production lines.', score: 10 },
    { industry: 'Logistics & Warehousing', reason: 'Autonomous mobile robots for picking, sorting, and last-mile delivery.', score: 10 },
    { industry: 'Healthcare & MedTech', reason: 'Surgical robots, rehabilitation devices, and hospital delivery robots.', score: 9 },
    { industry: 'Agriculture & AgriTech', reason: 'Harvesting robots, drone spraying, and soil monitoring automation.', score: 9 },
    { industry: 'Construction & Infrastructure', reason: 'Autonomous site surveying, bricklaying robots, and safety monitoring.', score: 8 },
    { industry: 'Defense & Aerospace', reason: 'Unmanned systems, inspection drones, and explosive disposal robots.', score: 8 },
  ],
  'computer vision': [
    { industry: 'Manufacturing & Industry 4.0', reason: 'Visual quality control, defect detection, and dimensional inspection.', score: 10 },
    { industry: 'Retail & E-Commerce', reason: 'Visual search, planogram compliance, and cashierless checkout systems.', score: 10 },
    { industry: 'Healthcare & MedTech', reason: 'Radiology image analysis, pathology scanning, and surgical assistance.', score: 9 },
    { industry: 'Logistics & Warehousing', reason: 'Barcode/label reading, damage detection, and autonomous vehicle guidance.', score: 9 },
    { industry: 'Security & Surveillance', reason: 'Facial recognition, crowd analysis, and intrusion detection systems.', score: 8 },
    { industry: 'Agriculture & AgriTech', reason: 'Crop disease detection, yield estimation, and precision spraying guidance.', score: 8 },
  ],
  'nlp': [
    { industry: 'Customer Service & CX Platforms', reason: 'AI chatbots, ticket classification, and sentiment-driven routing.', score: 10 },
    { industry: 'Legal Tech', reason: 'Contract clause extraction, legal research, and compliance scanning.', score: 10 },
    { industry: 'Healthcare & MedTech', reason: 'Clinical note extraction, EHR coding, and medical transcription.', score: 9 },
    { industry: 'Financial Services & Fintech', reason: 'Earnings call analysis, news sentiment trading, and document processing.', score: 9 },
    { industry: 'Market Research & Analytics', reason: 'Brand monitoring, survey analysis, and competitive intelligence.', score: 8 },
    { industry: 'HR Tech & Recruitment', reason: 'Resume parsing, job description optimization, and interview analytics.', score: 8 },
  ],
  'chatbot': [
    { industry: 'E-Commerce & Retail', reason: 'Order tracking, product recommendations, and cart abandonment recovery.', score: 10 },
    { industry: 'Banking & Financial Services', reason: '24/7 customer support for account queries and loan applications.', score: 10 },
    { industry: 'Healthcare & Telehealth', reason: 'Patient triage, appointment booking, and medication reminders.', score: 9 },
    { industry: 'Real Estate & PropTech', reason: 'Lead qualification, property inquiry handling, and virtual tours.', score: 9 },
    { industry: 'HR Tech & Recruitment', reason: 'Candidate screening, FAQ automation, and onboarding assistance.', score: 8 },
    { industry: 'Travel & Hospitality', reason: 'Booking assistance, itinerary changes, and concierge automation.', score: 8 },
  ],
  'saas': [
    { industry: 'Financial Services & Fintech', reason: 'Cloud-native tools for payments, banking, and wealth management.', score: 10 },
    { industry: 'Healthcare & MedTech', reason: 'EHR platforms, telemedicine, and practice management software.', score: 9 },
    { industry: 'HR Tech & Recruitment', reason: 'HRIS, applicant tracking, and performance management platforms.', score: 9 },
    { industry: 'Legal Tech', reason: 'Matter management, e-billing, and document automation software.', score: 8 },
    { industry: 'Real Estate & PropTech', reason: 'Property management CRM and lease automation platforms.', score: 8 },
    { industry: 'Construction & Infrastructure', reason: 'Project management, BIM, and field operations software.', score: 8 },
  ],
  'software': [
    { industry: 'Financial Services & Fintech', reason: 'Custom trading platforms, compliance tools, and banking systems.', score: 10 },
    { industry: 'Healthcare & MedTech', reason: 'EHR, medical imaging, and clinical trial management systems.', score: 9 },
    { industry: 'Manufacturing & Industry 4.0', reason: 'ERP, MES, and SCADA systems for factory operations.', score: 9 },
    { industry: 'Logistics & Supply Chain', reason: 'TMS, WMS, and fleet management software.', score: 8 },
    { industry: 'Education & EdTech', reason: 'LMS, student information systems, and assessment platforms.', score: 8 },
  ],
  'mobile app': [
    { industry: 'Healthcare & Telehealth', reason: 'Patient portals, remote monitoring, and telemedicine apps.', score: 10 },
    { industry: 'Retail & E-Commerce', reason: 'Shopping apps, loyalty programs, and mobile-first commerce.', score: 10 },
    { industry: 'Banking & Fintech', reason: 'Mobile banking, digital wallets, and investment apps.', score: 9 },
    { industry: 'Fitness & Wellness', reason: 'Workout tracking, nutrition coaching, and mental health apps.', score: 9 },
    { industry: 'Logistics & Field Services', reason: 'Driver apps, delivery tracking, and field technician tools.', score: 8 },
  ],
  'cybersecurity': [
    { industry: 'Financial Services & Banking', reason: 'Protecting transactions, preventing fraud, and meeting regulatory mandates.', score: 10 },
    { industry: 'Healthcare & MedTech', reason: 'HIPAA compliance, medical device security, and patient data protection.', score: 10 },
    { industry: 'Government & Defense', reason: 'Critical infrastructure protection and classified data security.', score: 9 },
    { industry: 'Retail & E-Commerce', reason: 'PCI-DSS compliance, fraud prevention, and customer data protection.', score: 9 },
    { industry: 'Legal Tech', reason: 'Attorney-client privilege protection and secure document management.', score: 8 },
    { industry: 'Energy & Utilities', reason: 'OT/ICS security for power grids, water systems, and pipelines.', score: 8 },
  ],
  'cloud': [
    { industry: 'Financial Services & Banking', reason: 'Scalable core banking, regulatory compliance, and data lakes.', score: 10 },
    { industry: 'Healthcare & MedTech', reason: 'HIPAA-compliant cloud for EHR, imaging, and genomics data.', score: 9 },
    { industry: 'Retail & E-Commerce', reason: 'Scalable infrastructure for peak traffic and omnichannel ops.', score: 9 },
    { industry: 'Media & Entertainment', reason: 'Content delivery, streaming infrastructure, and production workflows.', score: 8 },
    { industry: 'Manufacturing & Industry 4.0', reason: 'IoT data collection, digital twin modeling, and predictive analytics.', score: 8 },
  ],
  'devops': [
    { industry: 'Software & SaaS Companies', reason: 'CI/CD pipeline optimization and deployment automation.', score: 10 },
    { industry: 'Financial Services & Banking', reason: 'Regulated release management and zero-downtime deployments.', score: 9 },
    { industry: 'E-Commerce & Retail', reason: 'High-availability deployments for peak shopping events.', score: 8 },
    { industry: 'Healthcare IT', reason: 'Compliant deployment pipelines for medical software updates.', score: 8 },
    { industry: 'Telecom & Network Operators', reason: 'Infrastructure automation for large-scale network deployments.', score: 8 },
  ],
  'data analytics': [
    { industry: 'Retail & E-Commerce', reason: 'Customer behavior analysis, basket optimization, and churn prediction.', score: 10 },
    { industry: 'Financial Services & Fintech', reason: 'Portfolio analytics, risk modeling, and market trend forecasting.', score: 10 },
    { industry: 'Healthcare & MedTech', reason: 'Clinical outcomes analysis, population health, and operational efficiency.', score: 9 },
    { industry: 'Logistics & Supply Chain', reason: 'Demand forecasting, route analytics, and supplier performance tracking.', score: 9 },
    { industry: 'Manufacturing & Industry 4.0', reason: 'OEE analysis, yield optimization, and quality trend reporting.', score: 8 },
    { industry: 'Media & Entertainment', reason: 'Audience engagement metrics, content performance, and ad attribution.', score: 8 },
  ],
  'bi': [
    { industry: 'Retail & E-Commerce', reason: 'Sales dashboards, inventory analytics, and product performance reporting.', score: 10 },
    { industry: 'Financial Services', reason: 'P&L analysis, regulatory reporting, and KPI visualization.', score: 9 },
    { industry: 'Manufacturing', reason: 'Production dashboards, OEE reports, and supply chain visibility.', score: 9 },
    { industry: 'Healthcare', reason: 'Patient outcomes dashboards, cost analytics, and compliance reporting.', score: 8 },
  ],
  'ecommerce': [
    { industry: 'Fashion & Apparel Brands', reason: 'Online storefronts, visual merchandising, and returns management.', score: 10 },
    { industry: 'Consumer Electronics D2C', reason: 'Direct-to-consumer sales, warranty management, and comparison tools.', score: 9 },
    { industry: 'Food & Beverage D2C', reason: 'Subscription commerce, perishable inventory, and direct delivery.', score: 9 },
    { industry: 'Health & Wellness Products', reason: 'Supplement subscriptions, regulatory compliance, and personalization.', score: 8 },
    { industry: 'Furniture & Home Decor', reason: 'AR visualization, custom configuration, and white-glove delivery.', score: 8 },
    { industry: 'Industrial B2B Distribution', reason: 'Complex product catalogs, bulk pricing, and procurement integration.', score: 8 },
  ],
  'shopify': [
    { industry: 'Fashion & Apparel Brands', reason: 'D2C store launch, multi-currency selling, and inventory sync.', score: 10 },
    { industry: 'Health & Beauty Brands', reason: 'Subscription boxes, influencer integrations, and review management.', score: 9 },
    { industry: 'Food & Beverage D2C', reason: 'Shopify-native subscription and perishable logistics management.', score: 9 },
    { industry: 'Sports & Outdoor Gear', reason: 'Size/fit guides, bundle builders, and wholesale portals.', score: 8 },
  ],
  'digital marketing': [
    { industry: 'Retail & E-Commerce', reason: 'Performance marketing, ROAS optimization, and omnichannel campaigns.', score: 10 },
    { industry: 'Real Estate & PropTech', reason: 'Lead generation, property listing promotion, and geo-targeted ads.', score: 9 },
    { industry: 'Healthcare & Wellness', reason: 'Patient acquisition, HIPAA-compliant campaigns, and reputation management.', score: 9 },
    { industry: 'Education & EdTech', reason: 'Student enrollment campaigns, content marketing, and social media.', score: 8 },
    { industry: 'Hospitality & Tourism', reason: 'Seasonal campaigns, OTA visibility, and influencer partnerships.', score: 8 },
    { industry: 'Financial Services', reason: 'Regulated advertising, loan lead gen, and wealth management promotion.', score: 8 },
  ],
  'seo': [
    { industry: 'E-Commerce & Retail', reason: 'Product page optimization, category SEO, and structured data for rich results.', score: 10 },
    { industry: 'Healthcare & Medical Practices', reason: 'Local SEO for clinics, medical content optimization, and E-E-A-T compliance.', score: 9 },
    { industry: 'Legal Services & Law Firms', reason: 'Practice area page optimization and local search dominance.', score: 9 },
    { industry: 'Real Estate & Property', reason: 'Neighborhood content, agent profiles, and local search optimization.', score: 9 },
    { industry: 'Travel & Hospitality', reason: 'Destination content, hotel SEO, and experience page ranking.', score: 8 },
    { industry: 'Financial Services', reason: 'Trust-building content and competitive keyword domination.', score: 8 },
  ],
  'fintech': [
    { industry: 'Banking & Neobanks', reason: 'Core banking modernization, payment infrastructure, and digital onboarding.', score: 10 },
    { industry: 'Insurance & InsurTech', reason: 'Premium financing, embedded insurance, and policy management APIs.', score: 9 },
    { industry: 'Retail & E-Commerce', reason: 'Buy-now-pay-later, embedded checkout financing, and merchant services.', score: 9 },
    { industry: 'Real Estate & PropTech', reason: 'Mortgage origination tech, rent payment platforms, and digital closings.', score: 8 },
    { industry: 'Wealth Management', reason: 'Robo-advisory, portfolio analytics, and digital client onboarding.', score: 8 },
  ],
  'payment': [
    { industry: 'E-Commerce & Retail', reason: 'Checkout conversion optimization, fraud reduction, and multi-currency payments.', score: 10 },
    { industry: 'Hospitality & Restaurants', reason: 'Point-of-sale systems, table-side payments, and tip management.', score: 9 },
    { industry: 'Healthcare & Medical Services', reason: 'Patient billing, insurance claims processing, and copay collection.', score: 9 },
    { industry: 'SaaS & Subscription Businesses', reason: 'Recurring billing, dunning management, and revenue recognition.', score: 9 },
    { industry: 'Marketplaces & Platforms', reason: 'Split payments, escrow, and multi-party settlement infrastructure.', score: 8 },
  ],
  'healthcare': [
    { industry: 'Hospital Networks & Health Systems', reason: 'EMR integration, patient flow optimization, and care coordination.', score: 10 },
    { industry: 'Pharmaceutical & Biotech', reason: 'Clinical trial management, drug discovery support, and regulatory filing.', score: 9 },
    { industry: 'Health Insurance & Payers', reason: 'Claims adjudication, prior auth automation, and member engagement.', score: 9 },
    { industry: 'Medical Devices & Diagnostics', reason: 'Device connectivity, data analytics, and FDA compliance support.', score: 9 },
    { industry: 'Mental Health & Teletherapy', reason: 'Virtual care platforms, therapist matching, and HIPAA compliance.', score: 8 },
  ],
  'telemedicine': [
    { industry: 'Primary Care & GP Clinics', reason: 'Virtual consultation platforms for routine care and follow-ups.', score: 10 },
    { industry: 'Mental Health & Psychiatry', reason: 'Remote therapy sessions, prescription management, and crisis support.', score: 10 },
    { industry: 'Dermatology & Aesthetics', reason: 'Asynchronous photo consultations and follow-up care.', score: 9 },
    { industry: 'Chronic Disease Management', reason: 'Remote monitoring, medication adherence, and care plan delivery.', score: 9 },
  ],
  'logistics': [
    { industry: 'E-Commerce & D2C Brands', reason: 'Last-mile delivery optimization, returns management, and fulfillment.', score: 10 },
    { industry: 'Manufacturing & Distribution', reason: 'Inbound freight management, supplier coordination, and inventory tracking.', score: 10 },
    { industry: 'Retail Chains & FMCG', reason: 'Multi-DC network optimization, replenishment automation, and cold chain.', score: 9 },
    { industry: 'Pharmaceutical & MedSupply', reason: 'Temperature-controlled logistics, serialization, and regulatory traceability.', score: 9 },
    { industry: 'Automotive & Aftermarket', reason: 'JIT delivery, parts distribution network, and cross-border logistics.', score: 8 },
  ],
  'supply chain': [
    { industry: 'Manufacturing & Industrial', reason: 'Raw material procurement, supplier diversification, and BOM management.', score: 10 },
    { industry: 'Retail & Consumer Goods', reason: 'Demand sensing, inventory positioning, and supplier collaboration.', score: 10 },
    { industry: 'Pharmaceutical & Healthcare', reason: 'Serialization, cold chain integrity, and shortage risk management.', score: 9 },
    { industry: 'Automotive & Aerospace', reason: 'Tier-1/2 supplier management, JIT scheduling, and component traceability.', score: 9 },
    { industry: 'Food & Beverage', reason: 'Farm-to-shelf traceability, recall management, and seasonal demand planning.', score: 8 },
  ],
  'real estate': [
    { industry: 'Residential Property Developers', reason: 'Sales automation, virtual tours, and buyer journey management.', score: 10 },
    { industry: 'Commercial Real Estate & REITs', reason: 'Asset management, tenant portals, and lease abstraction.', score: 10 },
    { industry: 'Property Management Companies', reason: 'Maintenance workflows, rent collection, and tenant communications.', score: 9 },
    { industry: 'Mortgage & Lending', reason: 'Digital origination, underwriting automation, and borrower portals.', score: 9 },
    { industry: 'Construction & Architecture', reason: 'Project costing, design visualization, and permit management.', score: 8 },
  ],
  'recruitment': [
    { industry: 'Staffing & Recruitment Agencies', reason: 'ATS optimization, candidate sourcing automation, and placement tracking.', score: 10 },
    { industry: 'Technology Companies', reason: 'Technical screening, distributed hiring, and engineering talent pipelines.', score: 9 },
    { industry: 'Healthcare & Medical Staffing', reason: 'Credentialing, compliance screening, and shift-based workforce management.', score: 9 },
    { industry: 'Retail & Hospitality', reason: 'High-volume seasonal hiring, onboarding automation, and shift matching.', score: 8 },
    { industry: 'Financial Services', reason: 'Regulatory background checks, Series licensing verification, and talent analytics.', score: 8 },
  ],
  'edtech': [
    { industry: 'K-12 Schools & Districts', reason: 'Adaptive learning platforms, student progress tracking, and parent engagement.', score: 10 },
    { industry: 'Higher Education & Universities', reason: 'LMS platforms, virtual labs, and student lifecycle management.', score: 9 },
    { industry: 'Corporate Training & L&D', reason: 'Employee upskilling, compliance training, and skills gap analysis.', score: 9 },
    { industry: 'Professional Certification Bodies', reason: 'Exam delivery, credential management, and CPE tracking.', score: 8 },
  ],
  'construction': [
    { industry: 'General Contractors & Builders', reason: 'Project scheduling, subcontractor coordination, and cost control.', score: 10 },
    { industry: 'Real Estate Developers', reason: 'Pre-construction planning, permit management, and budget tracking.', score: 9 },
    { industry: 'Engineering & Architecture Firms', reason: 'BIM coordination, design review workflows, and document control.', score: 9 },
    { industry: 'Infrastructure & Civil Engineering', reason: 'Asset monitoring, inspection management, and lifecycle tracking.', score: 8 },
  ],
  'energy': [
    { industry: 'Renewable Energy & Solar', reason: 'Asset performance monitoring, grid integration, and O&M optimization.', score: 10 },
    { industry: 'Oil & Gas', reason: 'Upstream production monitoring, pipeline inspection, and safety compliance.', score: 10 },
    { industry: 'Utilities & Grid Operators', reason: 'Smart grid management, demand response, and outage prediction.', score: 9 },
    { industry: 'Energy Retail & Trading', reason: 'Price optimization, risk management, and customer billing platforms.', score: 8 },
    { industry: 'Industrial Manufacturing', reason: 'Energy consumption monitoring, carbon footprint tracking, and cost reduction.', score: 8 },
  ],
};

// ─── Alias Resolution ──────────────────────────────────────────────────────────
const KEYWORD_ALIASES: Record<string, string[]> = {
  'artificial intelligence': ['ai'], 'ml': ['machine learning'], 'rpa': ['automation'],
  'robot': ['robotics'], 'cv': ['computer vision'], 'natural language processing': ['nlp'],
  'large language model': ['nlp', 'ai'], 'llm': ['nlp', 'ai'], 'generative ai': ['ai', 'nlp'],
  'gpt': ['ai', 'nlp'], 'erp': ['software', 'automation'], 'crm': ['software', 'saas'],
  'data science': ['data analytics', 'machine learning'], 'big data': ['data analytics'],
  'business intelligence': ['bi'], 'e-commerce': ['ecommerce'], 'online store': ['ecommerce', 'shopify'],
  'woocommerce': ['ecommerce', 'shopify'], 'search engine optimization': ['seo'],
  'ppc': ['digital marketing'], 'social media marketing': ['digital marketing'],
  'blockchain': ['fintech', 'cybersecurity'], 'payments': ['payment'], 'medical': ['healthcare'],
  'pharma': ['healthcare'], 'telehealth': ['telemedicine'], 'supply chain management': ['supply chain'],
  'shipping': ['logistics'], 'freight': ['logistics'], 'warehouse': ['logistics'],
  'hr': ['recruitment'], 'human resources': ['recruitment'], 'payroll': ['automation', 'recruitment'],
  'learning management': ['edtech'], 'lms': ['edtech'], 'property': ['real estate'],
  'proptech': ['real estate'], 'solar': ['energy'], 'renewable': ['energy'],
  'iot': ['automation', 'robotics'], 'internet of things': ['automation', 'robotics'],
  'api': ['software', 'saas'], 'web development': ['saas', 'ecommerce'],
  'app development': ['mobile app'], 'information security': ['cybersecurity'],
  'pentest': ['cybersecurity'], 'machine vision': ['computer vision'],
  'deep learning': ['machine learning', 'ai'], 'neural network': ['machine learning', 'ai'],
};

// ─── Instant Keyword→Industry Search ─────────────────────────────────────────
function findInstantSuggestions(query: string): Array<{ industry: string; reason: string }> {
  const q = query.toLowerCase().trim();
  if (!q || q.length < 2) return [];

  const collected = new Map<string, { reason: string; score: number }>();

  const resolveAndMerge = (key: string) => {
    const results = KEYWORD_INDUSTRY_MAP[key];
    if (!results) return;
    for (const item of results) {
      const existing = collected.get(item.industry);
      if (!existing || item.score > existing.score) {
        collected.set(item.industry, { reason: item.reason, score: item.score });
      }
    }
  };

  // 1. Direct exact match
  resolveAndMerge(q);

  // 2. Alias resolution — exact alias match
  for (const [alias, keys] of Object.entries(KEYWORD_ALIASES)) {
    if (q === alias || q.includes(alias) || alias.includes(q)) {
      for (const k of keys) resolveAndMerge(k);
    }
  }

  // 3. Partial keyword map key match
  for (const key of Object.keys(KEYWORD_INDUSTRY_MAP)) {
    if (key !== q && (key.includes(q) || q.includes(key) || key.startsWith(q))) {
      resolveAndMerge(key);
    }
  }

  // 4. Word-level token match for multi-word queries
  const tokens = q.split(/\s+/).filter((t) => t.length >= 3);
  for (const token of tokens) {
    for (const key of Object.keys(KEYWORD_INDUSTRY_MAP)) {
      if (key.includes(token)) resolveAndMerge(key);
    }
    for (const [alias, keys] of Object.entries(KEYWORD_ALIASES)) {
      if (alias.includes(token)) {
        for (const k of keys) resolveAndMerge(k);
      }
    }
  }

  return Array.from(collected.entries())
    .map(([industry, { reason, score }]) => ({ industry, reason, score }))
    .sort((a, b) => b.score - a.score)
    .slice(0, 8)
    .map(({ industry, reason }) => ({ industry, reason }));
}

// ─── GET /api/suggest-industries?q=keyword (Instant 0ms suggestions) ──────────
export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const q = searchParams.get('q') || '';

  if (q.trim().length >= 2) {
    const instant = findInstantSuggestions(q.trim());
    return NextResponse.json({ success: true, source: 'instant', query: q, suggestions: instant });
  }

  const defaultFallback = [
    'Fintech & Banking', 'Healthcare & MedTech', 'E-Commerce & Retail',
    'Software & SaaS', 'Logistics & Supply Chain', 'Manufacturing & Industry 4.0',
  ];
  try {
    const authHeader = req.headers.get('Authorization') || req.headers.get('authorization');
    if (!authHeader) return NextResponse.json({ success: true, suggested_industries: defaultFallback });
    const resp = await fetch(`${getBackendUrl()}/auth/suggest-industries`, {
      method: 'GET', headers: { 'Authorization': authHeader, 'Content-Type': 'application/json' }, cache: 'no-store',
    });
    if (!resp.ok) return NextResponse.json({ success: true, suggested_industries: defaultFallback });
    const data = await resp.json();
    return NextResponse.json({ success: true, company_name: data.company_name, suggested_industries: data.suggested_industries || defaultFallback });
  } catch {
    return NextResponse.json({ success: true, suggested_industries: defaultFallback });
  }
}

// ─── POST /api/suggest-industries (AI-powered deep suggestions) ───────────────
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const service = (body.service || body.input || '').toString().trim();
    if (!service) return NextResponse.json({ error: 'Technology or service name is required.' }, { status: 400 });

    // Layer 1: Instant local suggestions
    const instantSuggestions = findInstantSuggestions(service);

    // Layer 2: LLM deep enrichment
    const prompt = `You are a B2B market intelligence expert. A vendor offers this specific technology or service:\n\nSERVICE: "${service}"\n\nYour task: Identify the 6-8 industries that are the MOST GENUINE buyers of this exact service — industries where companies face a clear, direct operational or commercial problem that this service specifically solves.\n\nRULES (follow strictly):\n1. Do NOT list generic catch-alls like "Technology", "Business Services", or "Enterprise".\n2. Each industry must have a UNIQUE, SPECIFIC reason tied to how THIS service solves a real problem in THAT industry.\n3. Think: What does a company in this industry DO daily? What pain does this service relieve specifically?\n4. Prioritize industries where this service creates COMPETITIVE ADVANTAGE or solves REGULATORY/COMPLIANCE/OPERATIONAL problems unique to that sector.\n5. Industry names should be specific (e.g. "Digital Health Platforms" not just "Healthcare"; "D2C E-Commerce Brands" not just "Retail").\n\nReturn ONLY valid JSON (no markdown):\n{"suggestions": [{"industry": "specific industry name", "reason": "One specific sentence about the direct need THIS service fills for THIS industry."}]}`;

    const systemPrompt = 'You are a precise B2B market analyst. Return only valid JSON. Use specific industry names. Reasons must be unique to the service+industry combination.';

    const proxyRes = await fetch(`${getBackendUrl()}/llm-proxy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, system_prompt: systemPrompt, temperature: 0.55, max_tokens: 1000, domain_tag: 'suggest-industries' }),
      signal: AbortSignal.timeout(25_000),
    });

    if (!proxyRes.ok) {
      if (instantSuggestions.length > 0) return NextResponse.json({ success: true, service, suggestions: instantSuggestions, source: 'instant_fallback' });
      const errText = await proxyRes.text().catch(() => '');
      return NextResponse.json({ error: `LLM error (${proxyRes.status}): ${errText || 'Failed to generate suggestions'}` }, { status: proxyRes.status });
    }

    const proxyData = await proxyRes.json();
    let rawContent: string = (proxyData.content || '').replace(/```json/gi, '').replace(/```/g, '').trim();

    let llmSuggestions: Array<{ industry: string; reason: string }> = [];
    try {
      const parsed = JSON.parse(rawContent);
      if (Array.isArray(parsed)) llmSuggestions = parsed;
      else if (typeof parsed === 'object' && parsed !== null) {
        const possibleArray = Object.values(parsed).find((val) => Array.isArray(val));
        if (possibleArray && Array.isArray(possibleArray)) llmSuggestions = possibleArray as Array<{ industry: string; reason: string }>;
      }
    } catch {
      const matches = [...rawContent.matchAll(/\{\s*"industry"\s*:\s*"([^"]+)"\s*,\s*"reason"\s*:\s*"([^"]+)"\s*\}/gi)];
      llmSuggestions = matches.map((m) => ({ industry: m[1], reason: m[2] }));
    }

    // Merge: LLM first, then fill with instant suggestions not already in LLM results
    const llmNames = new Set(llmSuggestions.map((s) => s.industry.toLowerCase()));
    const merged = [
      ...llmSuggestions,
      ...instantSuggestions.filter((s) => !llmNames.has(s.industry.toLowerCase())),
    ].filter((item) => item?.industry?.trim()).map((item) => ({ industry: item.industry.trim(), reason: (item.reason || '').trim() })).slice(0, 10);

    return NextResponse.json({ success: true, service, suggestions: merged, source: 'ai' });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : 'An unexpected server error occurred.' }, { status: 500 });
  }
}

