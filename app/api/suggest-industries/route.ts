import { NextRequest, NextResponse } from 'next/server';

function getBackendUrl(): string {
  const envUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
  if (!envUrl || envUrl.startsWith('/')) return 'http://localhost:8000';
  return envUrl.replace(/\/$/, '');
}

export interface IndustryItem {
  industry: string;
  reason: string;
  score: number;
}

// ─── High-Converting, Easy-to-Contact B2B Industries Knowledge Base ───────────
// Criteria:
// 1. Simple, plain-English names (easy to understand immediately)
// 2. High contactability (public team/about pages, decision-maker emails easily found)
// 3. High commercial intent for software, AI, marketing, and B2B services
const KEYWORD_INDUSTRY_MAP: Record<string, IndustryItem[]> = {
  // ── AI & Automation ──
  'ai': [
    { industry: 'Dental & Orthodontic Clinics', reason: 'Automating patient intake, reminder calls, and imaging diagnostics.', score: 10 },
    { industry: 'Real Estate Brokerages', reason: 'AI property matching, instant buyer inquiry handling, and listing descriptions.', score: 10 },
    { industry: 'Accounting & CPA Firms', reason: 'Automated receipt categorization, tax document extraction, and reconciliation.', score: 10 },
    { industry: 'Law Firms & Legal Consultancies', reason: 'Contract drafting, legal research summaries, and case file discovery.', score: 9 },
    { industry: 'Logistics & Freight Brokers', reason: 'Automated rate quotes, load matching, and dispatch tracking bots.', score: 9 },
    { industry: 'Commercial HVAC & Roofing Contractors', reason: 'Automated job quoting, technician dispatch scheduling, and customer follow-ups.', score: 9 },
    { industry: 'Shopify & D2C E-Commerce Brands', reason: 'Personalized product recommendations, cart recovery, and 24/7 AI chat support.', score: 9 },
    { industry: 'Insurance Agencies & Brokers', reason: 'Automated policy comparison, claims intake, and renewal reminders.', score: 8 },
    { industry: 'Staffing & Recruitment Agencies', reason: 'Automated resume screening, candidate interview scheduling, and skill matching.', score: 8 },
    { industry: 'Gyms & Fitness Center Franchises', reason: 'Member retention tracking, automated lead follow-up, and class booking.', score: 8 },
    { industry: 'Auto Dealerships & Service Centers', reason: 'Virtual test-drive booking, inventory questions, and service maintenance alerts.', score: 8 },
    { industry: 'Hotels & Vacation Rental Managers', reason: 'Guest concierge bots, dynamic pricing, and review response automation.', score: 7 },
  ],
  'automation': [
    { industry: 'Commercial HVAC & Electrical Contractors', reason: 'Automated dispatching, work-order status updates, and digital field billing.', score: 10 },
    { industry: 'Accounting & Bookkeeping Firms', reason: 'Invoice parsing, bank reconciliation, and recurring payroll automation.', score: 10 },
    { industry: 'Logistics & Trucking Fleets', reason: 'Driver dispatch automation, proof-of-delivery processing, and fuel tracking.', score: 10 },
    { industry: 'Property Management Companies', reason: 'Automated rent collection reminders, maintenance ticket routing, and lease renewals.', score: 9 },
    { industry: 'Dental & Specialty Medical Practices', reason: 'Patient appointment reminders, insurance pre-authorization, and check-in workflows.', score: 9 },
    { industry: 'E-Commerce Fulfillment Warehouses', reason: 'Order picking workflows, barcode label generation, and inventory sync.', score: 9 },
    { industry: 'Law & Legal Advisory Practices', reason: 'Client intake automation, retainer agreement generation, and court calendar sync.', score: 8 },
    { industry: 'Wholesale Distributors & Importers', reason: 'Bulk purchase order processing, catalog updates, and warehouse reorder alerts.', score: 8 },
    { industry: 'Commercial Cleaning & Janitorial Services', reason: 'Automated site inspection reporting, crew shift scheduling, and supply ordering.', score: 8 },
    { industry: 'Solar Installation & EPC Contractors', reason: 'Permit application tracking, proposal generation, and installation scheduling.', score: 8 },
  ],
  'machine learning': [
    { industry: 'Fintech & Mortgage Lenders', reason: 'Credit risk assessment, loan eligibility prediction, and automated underwriting.', score: 10 },
    { industry: 'E-Commerce & Online Retailers', reason: 'Predictive inventory replenishment, churn reduction, and customer lifetime value models.', score: 10 },
    { industry: 'Healthcare & Diagnostic Clinics', reason: 'Automated lab result anomaly detection and patient readmission risk scoring.', score: 9 },
    { industry: 'Insurance Agencies & Underwriters', reason: 'Fraudulent claim pattern detection and customized risk tier pricing.', score: 9 },
    { industry: 'Transportation & Fleet Logistics', reason: 'Predictive vehicle maintenance scheduling and fuel efficiency route modeling.', score: 9 },
    { industry: 'Commercial Real Estate Investors', reason: 'Property valuation forecasting, rental yield estimation, and neighborhood trend analysis.', score: 8 },
  ],
  'chatbot': [
    { industry: 'Dental & Cosmetic Clinics', reason: '24/7 patient booking, procedure cost inquiries, and pre-visit instructions.', score: 10 },
    { industry: 'Real Estate Agencies', reason: 'Instant property tour booking, buyer price-range qualification, and agent handover.', score: 10 },
    { industry: 'Shopify & D2C Brands', reason: 'Order tracking, return requests, and high-converting product recommendation flows.', score: 10 },
    { industry: 'Law Firms & Personal Injury Attorneys', reason: '24/7 client intake qualification, case evaluation questions, and urgent consultation booking.', score: 9 },
    { industry: 'Auto Dealerships & Car Rentals', reason: 'Inventory search, test-drive reservations, and financing pre-qualification questions.', score: 9 },
    { industry: 'Home Services (Roofing & Plumbing)', reason: 'Emergency repair inquiries, quote requests, and instant technician scheduling.', score: 9 },
    { industry: 'Hotels & Boutique Resorts', reason: 'Room service requests, amenity booking, local recommendations, and check-out FAQs.', score: 8 },
    { industry: 'Gyms & Wellness Studios', reason: 'Membership pricing queries, trial class bookings, and schedule lookups.', score: 8 },
  ],

  // ── Software & Web/App Development ──
  'software': [
    { industry: 'Logistics & Freight Dispatchers', reason: 'Custom driver apps, real-time cargo telematics, and broker billing portals.', score: 10 },
    { industry: 'Multi-Location Dental & Medical Clinics', reason: 'Custom patient records, appointment scheduling portals, and billing integrations.', score: 10 },
    { industry: 'Commercial Construction & Subcontractors', reason: 'Field change-order tracking, daily job site logs, and subcontractor billing software.', score: 9 },
    { industry: 'Property Management & Real Estate', reason: 'Tenant service portals, rent payment gateways, and maintenance ticketing platforms.', score: 9 },
    { industry: 'Wholesale & B2B Distributors', reason: 'Wholesale customer ordering portals, tiered pricing, and ERP synchronization.', score: 9 },
    { industry: 'Staffing & Executive Search Firms', reason: 'Custom candidate applicant tracking systems and client hiring dashboards.', score: 8 },
    { industry: 'Law Firms & Corporate Legal', reason: 'Secure client document portals, billing time tracking, and matter management.', score: 8 },
    { industry: 'Commercial Cleaning Franchises', reason: 'Mobile crew inspection apps, client satisfaction surveys, and invoicing systems.', score: 8 },
  ],
  'saas': [
    { industry: 'Accounting & Financial Advisors', reason: 'Cloud-based client document portals and automated tax reporting software.', score: 10 },
    { industry: 'Real Estate Brokerages & Teams', reason: 'Agent transaction management, commission tracking, and client CRM software.', score: 9 },
    { industry: 'Healthcare & Wellness Centers', reason: 'Telehealth consultation platforms and HIPAA-compliant patient communication tools.', score: 9 },
    { industry: 'Field Service & HVAC Contractors', reason: 'Mobile dispatching, GPS route tracking, and instant invoice collection.', score: 9 },
    { industry: 'Recruitment & Staffing Agencies', reason: 'Automated video interviewing, candidate pipeline management, and placement billing.', score: 8 },
  ],
  'web development': [
    { industry: 'Dental & Plastic Surgery Clinics', reason: 'High-converting patient booking websites with before-and-after galleries.', score: 10 },
    { industry: 'Law Firms & Attorneys', reason: 'Professional authority websites, practice area landing pages, and lead intake forms.', score: 10 },
    { industry: 'Commercial Construction & Architects', reason: 'Project portfolio showcases, tender bid request portals, and credential displays.', score: 9 },
    { industry: 'Real Estate Developers & Brokerages', reason: 'Interactive property listings with virtual 3D tours and mortgage calculators.', score: 9 },
    { industry: 'Boutique Restaurants & Catering Services', reason: 'Mobile-friendly menu displays, private event booking forms, and reservation links.', score: 9 },
    { industry: 'Accounting & Financial Consulting Firms', reason: 'Client trust websites, service packages, and secure tax file upload portals.', score: 8 },
    { industry: 'Solar & Renewable Energy Installers', reason: 'Rooftop solar savings calculator landing pages and quote request funnels.', score: 8 },
  ],
  'mobile app': [
    { industry: 'Gyms, Fitness Studios & Personal Trainers', reason: 'Custom branded workout tracking, class reservation, and subscription payment apps.', score: 10 },
    { industry: 'Healthcare Clinics & Telehealth', reason: 'Patient symptom logging, doctor chat, and prescription refill mobile apps.', score: 10 },
    { industry: 'Logistics Fleets & Local Delivery Companies', reason: 'Driver navigation, electronic proof-of-delivery, and route tracking apps.', score: 9 },
    { industry: 'Restaurants & Food Chains', reason: 'Loyalty reward apps, mobile pre-ordering, and curb-side pickup tracking.', score: 9 },
    { industry: 'Property Management Companies', reason: 'Resident mobile apps for keyless entry, rent payments, and amenity bookings.', score: 8 },
  ],

  // ── Digital Marketing, SEO & Lead Gen ──
  'digital marketing': [
    { industry: 'Dental & Cosmetic Medical Practices', reason: 'Local Google Maps ranking, patient acquisition ads, and review generation.', score: 10 },
    { industry: 'Roofing, HVAC & Plumbing Contractors', reason: 'High-intent emergency Google search ads and local zip-code targeting.', score: 10 },
    { industry: 'Law Firms & Personal Injury Attorneys', reason: 'High-value client lead generation through Google Ads and localized content.', score: 10 },
    { industry: 'Real Estate Agencies & Realtors', reason: 'Facebook/Instagram property ads, seller lead funnels, and neighborhood guides.', score: 9 },
    { industry: 'Shopify & D2C Apparel Brands', reason: 'TikTok & Meta paid ad creative, influencer partnerships, and email retargeting.', score: 9 },
    { industry: 'Accounting & Wealth Management Firms', reason: 'High-net-worth client lead magnets, LinkedIn thought leadership, and SEO.', score: 8 },
    { industry: 'Solar Energy & Home Improvement Installers', reason: 'Homeowner lead funnels, localized ad campaigns, and landing page optimization.', score: 8 },
    { industry: 'Auto Dealerships & Detailers', reason: 'Local inventory promotion, trade-in campaigns, and Google Business Profile optimization.', score: 8 },
  ],
  'seo': [
    { industry: 'Dental, Orthodontic & Medical Clinics', reason: 'Local 3-Pack Google Maps domination and doctor specialty search rankings.', score: 10 },
    { industry: 'Law Firms & Defense Attorneys', reason: 'Competitive keyword ranking for case types and local practice area searches.', score: 10 },
    { industry: 'Roofing, Electrical & HVAC Services', reason: 'Emergency local search visibility for same-day service queries in target towns.', score: 10 },
    { industry: 'E-Commerce & Online Stores', reason: 'Category page optimization, product rich snippets, and Google Shopping organic traffic.', score: 9 },
    { industry: 'Real Estate Agencies & Brokerages', reason: 'Neighborhood property search ranking and local school district guides.', score: 9 },
    { industry: 'Accounting & Tax Advisory Firms', reason: 'Seasonal tax search traffic and small business accounting service discovery.', score: 8 },
    { industry: 'Hotels & Vacation Resorts', reason: 'Direct organic bookings without paying high commissions to Booking.com/Expedia.', score: 8 },
  ],
  'lead generation': [
    { industry: 'B2B SaaS & Tech Startups', reason: 'High LTV accounts needing automated outbound pipelines to book demos with enterprise buyers.', score: 10 },
    { industry: 'Commercial Real Estate Brokerages', reason: 'Outbound acquisition of corporate tenants and industrial property investors.', score: 10 },
    { industry: 'Commercial Insurance Brokerages', reason: 'High-ticket policy sales requiring continuous outreach to corporate risk officers.', score: 10 },
    { industry: 'IT Support & Managed Service Providers (MSPs)', reason: 'Reaching small business owners needing network security and cloud backups.', score: 10 },
    { industry: 'Commercial Roofing & General Contractors', reason: 'Connecting with commercial property managers and building owners for roof replacements.', score: 9 },
    { industry: 'Staffing & Headhunting Agencies', reason: 'Finding hiring managers and HR directors with open technical or executive positions.', score: 9 },
    { industry: 'Accounting & Outsourced CFO Firms', reason: 'Prospecting fast-growing startups and established SMB owners for advisory services.', score: 9 },
    { industry: 'Solar Commercial Installers', reason: 'Targeting warehouse and factory owners with large roof spaces for commercial solar.', score: 8 },
  ],
  'lead generation automation': [
    { industry: 'B2B SaaS & Tech Companies', reason: 'High-value customer acquisition needing automated outreach to scale demo bookings.', score: 10 },
    { industry: 'Commercial Insurance Agencies', reason: 'Targeting mid-sized business executives for corporate liability and commercial property policies.', score: 10 },
    { industry: 'Staffing & Executive Search Firms', reason: 'Automated outreach to VP of HR and Talent Acquisition heads with active hiring budgets.', score: 10 },
    { industry: 'Commercial Real Estate Brokerages', reason: 'Reaching property investors and corporate tenants looking for commercial lease space.', score: 10 },
    { industry: 'IT Support & Managed Service Providers (MSPs)', reason: 'Outbound prospecting to SMB business owners needing cloud security & tech support.', score: 9 },
    { industry: 'Corporate Law & IP Patent Firms', reason: 'Connecting with corporate legal departments and growing founders needing retainer contracts.', score: 9 },
    { industry: 'Solar EPC & Commercial Renewable Contractors', reason: 'Targeting commercial building owners for rooftop solar installations and energy audits.', score: 9 },
    { industry: 'Wholesale & Industrial Equipment Distributors', reason: 'Outbound B2B lead generation to retail chains and regional contractor accounts.', score: 8 },
  ],

  // ── E-Commerce & Retail ──
  'ecommerce': [
    { industry: 'Clothing & Fashion Boutiques', reason: 'Online shop setup, inventory management, and multi-channel social selling.', score: 10 },
    { industry: 'Health, Vitamins & Supplement Brands', reason: 'Recurring subscription orders, lab-tested badges, and bundle builders.', score: 10 },
    { industry: 'Specialty Food & Coffee Roasters', reason: 'Fresh roast subscriptions, perishable shipping workflows, and wholesale portal.', score: 9 },
    { industry: 'Furniture & Home Decor Retailers', reason: 'Large item freight delivery calculation, room visualizers, and fabric swatches.', score: 9 },
    { industry: 'Beauty & Skincare Brands', reason: 'Skin quiz matchers, auto-replenishment subscriptions, and loyalty points.', score: 9 },
    { industry: 'Pet Supplies & Organic Pet Food', reason: 'Monthly repeat auto-delivery subscriptions and breed-specific bundles.', score: 8 },
  ],
  'shopify': [
    { industry: 'Apparel & Streetwear Brands', reason: 'Shopify Plus setup, drop-shipping integrations, and high-converting checkout apps.', score: 10 },
    { industry: 'Cosmetics & Skincare Brands', reason: 'Custom product bundles, recurring replenishment, and customer review widgets.', score: 10 },
    { industry: 'Gourmet Food & Beverage Producers', reason: 'Gift box builders, recurring delivery subscriptions, and localized shipping.', score: 9 },
    { industry: 'Jewelry & Watch Designers', reason: 'Custom ring sizing tools, high-res zoom imagery, and insured shipping workflows.', score: 9 },
    { industry: 'Fitness Equipment & Accessories', reason: 'Financing options (Klarna/Afterpay), assembly guides, and warranty management.', score: 8 },
  ],

  // ── Logistics, Trucking & Supply Chain ──
  'logistics': [
    { industry: 'E-Commerce Brands & D2C Retailers', reason: 'Fast 2-day regional fulfillment, branded tracking pages, and returns portals.', score: 10 },
    { industry: 'Food & Perishable Goods Distributors', reason: 'Refrigerated cold-chain transport, temperature logs, and delivery route timing.', score: 10 },
    { industry: 'Building Materials & Lumber Suppliers', reason: 'Flatbed delivery to construction job sites, scheduled drop-offs, and crane unloading.', score: 9 },
    { industry: 'Pharmaceutical & Medical Distributors', reason: 'Time-critical delivery, secure chain-of-custody, and climate-controlled vans.', score: 9 },
    { industry: 'Automotive Parts Wholesalers', reason: 'Same-day parts delivery runs to auto repair shops and collision centers.', score: 8 },
    { industry: 'Import & Export Trading Houses', reason: 'Port container drayage, customs clearance coordination, and bonded warehousing.', score: 8 },
  ],

  // ── Real Estate & Property ──
  'real estate': [
    { industry: 'Residential Real Estate Brokerages', reason: 'Agent lead distribution, automated property alert emails, and seller listing ads.', score: 10 },
    { industry: 'Commercial Real Estate Advisors', reason: 'Industrial warehouse leasing campaigns, office tenant rep, and investor pitch decks.', score: 10 },
    { industry: 'Property Management Companies', reason: 'Tenant screening, maintenance coordination, and automated rental payments.', score: 10 },
    { industry: 'Home Builders & Real Estate Developers', reason: 'Pre-construction sales funnels, digital site plans, and VIP buyer lists.', score: 9 },
    { industry: 'Mortgage Brokers & Loan Officers', reason: 'Homebuyer pre-approval funnels, rate drop alerts, and realtor referral tracking.', score: 8 },
  ],

  // ── Healthcare & Clinics ──
  'healthcare': [
    { industry: 'Dental & Orthodontic Practices', reason: 'Patient acquisition, appointment reminder SMS, and hygiene recall automation.', score: 10 },
    { industry: 'Physical Therapy & Chiropractic Clinics', reason: 'Care plan compliance tracking, online rebooking, and insurance intake.', score: 10 },
    { industry: 'Dermatology & Medical Spas', reason: 'High-ticket cosmetic procedure consultations, before/after portfolios, and memberships.', score: 9 },
    { industry: 'Optometry & Eye Care Centers', reason: 'Annual exam reminders, prescription eyeglass reorders, and insurance pre-checks.', score: 9 },
    { industry: 'Veterinary Clinics & Animal Hospitals', reason: 'Vaccination reminder alerts, pet wellness plans, and emergency appointment triage.', score: 8 },
    { industry: 'Mental Health & Therapy Practices', reason: 'Discreet online booking, client intake forms, and telehealth video sessions.', score: 8 },
  ],

  // ── Legal & Accounting ──
  'legal': [
    { industry: 'Personal Injury Law Firms', reason: '24/7 accident lead response, case evaluation intake, and settlement tracking.', score: 10 },
    { industry: 'Corporate & Business Attorneys', reason: 'Contract drafting automation, incorporation packages, and annual compliance alerts.', score: 9 },
    { industry: 'Family & Divorce Law Practices', reason: 'Sensitive client intake questionnaires, document discovery portals, and consultation booking.', score: 9 },
    { industry: 'Immigration Law Offices', reason: 'Visa milestone tracking, multi-language client forms, and USCIS filing deadlines.', score: 8 },
    { industry: 'Estate Planning & Probate Lawyers', reason: 'Will & trust package generators, asset inventory forms, and probate guidance.', score: 8 },
  ],
  'accounting': [
    { industry: 'General Contractors & Builders', reason: 'Job costing accounting, progress draw billing, and lien waiver tracking.', score: 10 },
    { industry: 'Dental & Medical Group Practices', reason: 'Associate doctor payroll, practice profitability analysis, and equipment depreciation.', score: 10 },
    { industry: 'E-Commerce Brands & Amazon Sellers', reason: 'Multi-state sales tax compliance, inventory accounting, and marketplace fee reconciliation.', score: 9 },
    { industry: 'Law Firms & Professional Practices', reason: 'Trust account (IOLTA) compliance, partner distributions, and billable hour audits.', score: 9 },
    { industry: 'Restaurants & Hospitality Groups', reason: 'Food & beverage cost margin tracking, tip reporting compliance, and POS reconciliation.', score: 8 },
  ],

  // ── Construction & Home Trades ──
  'construction': [
    { industry: 'Commercial Roofing Contractors', reason: 'Thermal roof inspection reports, insurance claim packages, and building owner outreach.', score: 10 },
    { industry: 'HVAC & Mechanical Contractors', reason: 'Annual commercial maintenance contracts, emergency dispatch, and equipment warranty logs.', score: 10 },
    { industry: 'Electrical & Solar Contractors', reason: 'Commercial lighting retrofits, panel upgrades, and EV charger installation deals.', score: 9 },
    { industry: 'Plumbing & Drain Cleaning Services', reason: 'Emergency commercial calls, sewer camera inspection reports, and preventive plans.', score: 9 },
    { industry: 'Custom Home Builders & Remodelers', reason: 'Design-build project management, client selection portals, and budget milestones.', score: 8 },
    { industry: 'Commercial Painting Contractors', reason: 'Large square-footage bidding, tenant improvement contracts, and lift rental coordination.', score: 8 },
  ],

  // ── IT, Cybersecurity & Cloud ──
  'cybersecurity': [
    { industry: 'Accounting & CPA Firms', reason: 'Protecting sensitive tax records, meeting IRS cybersecurity mandates, and phishing training.', score: 10 },
    { industry: 'Law Firms & Legal Practices', reason: 'Securing confidential client documents, attorney-client privilege protection, and data encryption.', score: 10 },
    { industry: 'Dental & Healthcare Clinics', reason: 'HIPAA compliance audits, patient record encryption, and ransomware backups.', score: 10 },
    { industry: 'Financial Planning & Wealth Managers', reason: 'FINRA/SEC compliance, multi-factor authentication, and wire fraud prevention.', score: 9 },
    { industry: 'Community Banks & Credit Unions', reason: 'Network vulnerability assessments, compliance reporting, and incident response plans.', score: 9 },
    { industry: 'E-Commerce Merchants & Retailers', reason: 'PCI-DSS compliance, credit card payment tokenization, and anti-fraud monitoring.', score: 8 },
  ],
  'cloud': [
    { industry: 'Accounting & Financial Advisory Firms', reason: 'Secure cloud migration of legacy tax and bookkeeping software with remote access.', score: 10 },
    { industry: 'Law Firms & Legal Consultancies', reason: 'Cloud document storage, searchable case databases, and mobile attorney access.', score: 10 },
    { industry: 'Healthcare Clinics & Diagnostic Labs', reason: 'HIPAA-compliant cloud storage for medical records and imaging scans.', score: 9 },
    { industry: 'Logistics & Dispatch Companies', reason: 'Cloud-hosted dispatch servers with zero downtime and automated daily backups.', score: 9 },
    { industry: 'Architecture & Engineering Firms', reason: 'High-speed cloud rendering and shared access to large CAD/BIM project files.', score: 8 },
  ],
};

// ─── Universal Rich Fallback Pool ─────────────────────────────────────────────
// 30+ easy-to-understand, high-lead-density B2B industries with public contacts
const UNIVERSAL_LEAD_RICH_INDUSTRIES: IndustryItem[] = [
  { industry: 'Dental & Orthodontic Clinics', reason: 'High-margin practices with active doctor/owner profiles and public reception emails.', score: 10 },
  { industry: 'Commercial Roofing & HVAC Contractors', reason: 'High-ticket service contracts with published owners, estimators, and direct phone/emails.', score: 10 },
  { industry: 'Real Estate Brokerages & Agencies', reason: 'Every agent and broker principal publishes their direct email, cell phone, and license info.', score: 10 },
  { industry: 'Accounting, Tax & CPA Firms', reason: 'Partners and CPAs listed with direct office emails; steady recurring service budgets.', score: 10 },
  { industry: 'Logistics, Dispatch & Trucking Fleets', reason: 'Dispatchers and fleet owners need urgent tech/operational help; easily reached via site.', score: 9 },
  { industry: 'Law Firms & Corporate Attorneys', reason: 'Managing partners and attorneys listed on team directory with public domain emails.', score: 9 },
  { industry: 'Shopify & D2C E-Commerce Brands', reason: 'Brand founders and marketing leads active online with publicly visible support & press emails.', score: 9 },
  { industry: 'IT Support & Managed Service Providers (MSPs)', reason: 'Tech-savvy business owners seeking new enterprise clients and outsourced partners.', score: 9 },
  { industry: 'Commercial Cleaning & Janitorial Companies', reason: 'Owners and account managers actively bidding on contracts; clear contact pages.', score: 8 },
  { industry: 'Gyms, Fitness Centers & Yoga Studios', reason: 'Owners and general managers easily reachable; keen on lead gen and booking automation.', score: 8 },
  { industry: 'Auto Dealerships & Service Centers', reason: 'General managers and sales directors listed on staff pages with direct work emails.', score: 8 },
  { industry: 'Wholesale Food & Beverage Distributors', reason: 'Procurement and sales managers listed on company catalogs with public business emails.', score: 8 },
  { industry: 'Hotels, Boutique Resorts & Event Venues', reason: 'General managers and event directors actively looking for vendor partnerships.', score: 8 },
  { industry: 'Private Wealth & Financial Advisors', reason: 'Advisors listed on SEC/broker websites with verified corporate email addresses.', score: 8 },
  { industry: 'Plumbing & Electrical Contractors', reason: 'High ticket commercial jobs, owners and dispatch managers prominently listed.', score: 8 },
  { industry: 'Staffing & Executive Recruitment Agencies', reason: 'Recruitment directors and branch heads always open to new corporate relationships.', score: 8 },
  { industry: 'Architecture & Interior Design Studios', reason: 'Principals and lead architects feature their portfolios with direct studio email.', score: 8 },
  { industry: 'Solar & Renewable Energy Installers', reason: 'Fast-growing market with accessible sales directors and commercial project leads.', score: 8 },
  { industry: 'Veterinary Clinics & Animal Hospitals', reason: 'Practice owners and medical directors listed with direct clinic contact forms/emails.', score: 7 },
  { industry: 'Security & Alarm Installation Providers', reason: 'Commercial sales managers and owners readily available for business security bids.', score: 7 },
  { industry: 'Printing & Packaging Manufacturers', reason: 'B2B sales managers and plant directors reachable via company request-for-quote pages.', score: 7 },
  { industry: 'Physical Therapy & Chiropractic Centers', reason: 'Clinic owners and lead doctors listed with direct office email and phone numbers.', score: 7 },
  { industry: 'Car Rental & Commercial Fleet Operators', reason: 'Operations managers and branch directors responsive to operational efficiency tools.', score: 7 },
  { industry: 'Catering & Event Production Companies', reason: 'Executive chefs and event coordinators publish direct booking emails on websites.', score: 7 },
];

// ─── Aliases Mapping ─────────────────────────────────────────────────────────
const KEYWORD_ALIASES: Record<string, string[]> = {
  'artificial intelligence': ['ai'], 'ml': ['machine learning'], 'rpa': ['automation'],
  'robot': ['automation'], 'robotics': ['automation'], 'cv': ['ai'], 'computer vision': ['ai'],
  'natural language processing': ['ai'], 'llm': ['ai'], 'generative ai': ['ai'],
  'gpt': ['ai'], 'deep learning': ['machine learning', 'ai'], 'bot': ['chatbot'],
  'chatbots': ['chatbot'], 'conversational ai': ['chatbot'], 'support': ['chatbot'],
  'customer service': ['chatbot'], 'customer support': ['chatbot'],
  'erp': ['software', 'automation'], 'crm': ['software'], 'saas': ['software', 'saas'],
  'custom software': ['software'], 'web': ['web development', 'software'],
  'web app': ['software', 'web development'], 'website': ['web development'],
  'apps': ['mobile app'], 'app development': ['mobile app', 'software'],
  'ios': ['mobile app'], 'android': ['mobile app'], 'flutter': ['mobile app'],
  'marketing': ['digital marketing', 'lead generation'], 'seo': ['seo', 'digital marketing'],
  'lead gen': ['lead generation', 'lead generation automation'],
  'lead generation': ['lead generation', 'lead generation automation'],
  'lead generation automation': ['lead generation automation'],
  'sales automation': ['lead generation automation', 'automation'],
  'cold outreach': ['lead generation', 'lead generation automation'],
  'cold email': ['lead generation automation', 'lead generation'],
  'b2b sales': ['lead generation', 'lead generation automation'],
  'outbound': ['lead generation', 'lead generation automation'],
  'outbound sales': ['lead generation automation'],
  'prospecting': ['lead generation', 'lead generation automation'],
  'social media': ['digital marketing'],
  'ppc': ['digital marketing'], 'google ads': ['digital marketing'],
  'facebook ads': ['digital marketing'], 'ads': ['digital marketing'],
  'ecommerce': ['ecommerce', 'shopify'], 'e-commerce': ['ecommerce', 'shopify'],
  'online store': ['ecommerce', 'shopify'], 'woocommerce': ['ecommerce', 'shopify'],
  'retail': ['ecommerce'], 'd2c': ['ecommerce', 'shopify'],
  'shipping': ['logistics'], 'freight': ['logistics'], 'trucking': ['logistics'],
  'warehouse': ['logistics', 'automation'], 'supply chain': ['logistics'],
  'dispatch': ['logistics'], 'transport': ['logistics'],
  'property': ['real estate'], 'realtor': ['real estate'], 'realty': ['real estate'],
  'proptech': ['real estate'], 'commercial real estate': ['real estate'],
  'medical': ['healthcare'], 'clinic': ['healthcare'], 'dentist': ['healthcare'],
  'dental': ['healthcare'], 'doctor': ['healthcare'], 'hospital': ['healthcare'],
  'telehealth': ['healthcare'], 'pharma': ['healthcare'],
  'lawyer': ['legal'], 'attorney': ['legal'], 'law': ['legal'],
  'cpa': ['accounting'], 'bookkeeping': ['accounting'], 'tax': ['accounting'],
  'audit': ['accounting'], 'finance': ['accounting'],
  'builder': ['construction'], 'contractor': ['construction'], 'roofing': ['construction'],
  'hvac': ['construction'], 'plumbing': ['construction'], 'electrical': ['construction'],
  'cyber': ['cybersecurity'], 'infosec': ['cybersecurity'], 'security': ['cybersecurity'],
  'network': ['cloud', 'cybersecurity'], 'aws': ['cloud'], 'azure': ['cloud'],
  'devops': ['cloud', 'software'], 'infrastructure': ['cloud'],
};

// ─── Query Normalization with Typo Correction ────────────────────────────────
function normalizeQuery(input: string): string {
  let q = (input || '').toLowerCase().trim();
  // Typo corrections
  q = q.replace(/\bautomtion\b/g, 'automation');
  q = q.replace(/\bautomaion\b/g, 'automation');
  q = q.replace(/\bautometion\b/g, 'automation');
  q = q.replace(/\bsofware\b/g, 'software');
  q = q.replace(/\bsoftwere\b/g, 'software');
  q = q.replace(/\bdevlopment\b/g, 'development');
  q = q.replace(/\bmarkting\b/g, 'marketing');
  q = q.replace(/\bmarketting\b/g, 'marketing');
  q = q.replace(/\bleadgen\b/g, 'lead generation');
  q = q.replace(/\brealstate\b/g, 'real estate');
  q = q.replace(/\becom\b/g, 'ecommerce');
  q = q.replace(/\becomm\b/g, 'ecommerce');
  return q;
}

// ─── Helper: Resilient Fisher-Yates Shuffle ──────────────────────────────────
function shuffleArray<T>(array: T[]): T[] {
  const arr = [...array];
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

// ─── Instant Smart Suggestions with Non-Repeating Rotation ───────────────────
function findInstantSuggestions(
  query: string,
  excludeNames: string[] = [],
  limit: number = 8
): Array<{ industry: string; reason: string }> {
  const q = normalizeQuery(query);
  const excludeSet = new Set(excludeNames.map((e) => e.toLowerCase().trim()));

  const matchedCandidates: IndustryItem[] = [];
  const addedNames = new Set<string>();

  const addIfFresh = (item: IndustryItem) => {
    const nameLower = item.industry.toLowerCase().trim();
    if (!excludeSet.has(nameLower) && !addedNames.has(nameLower)) {
      addedNames.add(nameLower);
      matchedCandidates.push(item);
    }
  };

  if (q.length >= 2) {
    // 1. Direct key match
    if (KEYWORD_INDUSTRY_MAP[q]) {
      for (const item of KEYWORD_INDUSTRY_MAP[q]) addIfFresh(item);
    }

    // 2. Alias resolution
    for (const [alias, keys] of Object.entries(KEYWORD_ALIASES)) {
      if (q === alias || q.includes(alias) || alias.includes(q)) {
        for (const k of keys) {
          if (KEYWORD_INDUSTRY_MAP[k]) {
            for (const item of KEYWORD_INDUSTRY_MAP[k]) addIfFresh(item);
          }
        }
      }
    }

    // 3. Partial keyword matching
    for (const [key, items] of Object.entries(KEYWORD_INDUSTRY_MAP)) {
      if (key !== q && (key.includes(q) || q.includes(key))) {
        for (const item of items) addIfFresh(item);
      }
    }

    // 4. Token-level matching
    const tokens = q.split(/\s+/).filter((t) => t.length >= 3);
    for (const token of tokens) {
      for (const [key, items] of Object.entries(KEYWORD_INDUSTRY_MAP)) {
        if (key.includes(token)) {
          for (const item of items) addIfFresh(item);
        }
      }
      for (const [alias, keys] of Object.entries(KEYWORD_ALIASES)) {
        if (alias.includes(token)) {
          for (const k of keys) {
            if (KEYWORD_INDUSTRY_MAP[k]) {
              for (const item of KEYWORD_INDUSTRY_MAP[k]) addIfFresh(item);
            }
          }
        }
      }
    }
  }

  // Only supplement from universal lead-rich pool if matched candidates are fewer than limit
  if (matchedCandidates.length < limit) {
    const shuffledUniversal = shuffleArray(UNIVERSAL_LEAD_RICH_INDUSTRIES);
    for (const item of shuffledUniversal) {
      addIfFresh(item);
      if (matchedCandidates.length >= limit) break;
    }
  }

  // If user has excluded too many and we still need items, relax exclude on fallback items
  if (matchedCandidates.length < limit) {
    const shuffledUniversal = shuffleArray(UNIVERSAL_LEAD_RICH_INDUSTRIES);
    for (const item of shuffledUniversal) {
      const nameLower = item.industry.toLowerCase().trim();
      if (!addedNames.has(nameLower)) {
        addedNames.add(nameLower);
        matchedCandidates.push(item);
      }
      if (matchedCandidates.length >= limit) break;
    }
  }

  // Shuffle matched candidates with light bias for higher scores to produce fresh results on every call
  // We partition by score tiers and shuffle within each tier
  const tier10 = shuffleArray(matchedCandidates.filter((c) => c.score >= 10));
  const tier9 = shuffleArray(matchedCandidates.filter((c) => c.score === 9));
  const tierOther = shuffleArray(matchedCandidates.filter((c) => c.score < 9));

  const sortedAndShuffled = [...tier10, ...tier9, ...tierOther];

  return sortedAndShuffled
    .slice(0, limit)
    .map(({ industry, reason }) => ({ industry, reason }));
}

// ─── GET /api/suggest-industries ──────────────────────────────────────────────
export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const q = searchParams.get('q') || '';
  const excludeParam = searchParams.get('exclude') || '';
  const excludeList = excludeParam ? excludeParam.split(',').map((s) => s.trim()).filter(Boolean) : [];

  // Instant suggestions with non-repeating rotation
  const instant = findInstantSuggestions(q.trim(), excludeList, 8);
  if (instant.length > 0) {
    return NextResponse.json({
      success: true,
      source: 'instant',
      query: q,
      suggestions: instant,
      suggested_industries: instant.map((i) => i.industry),
    });
  }

  const fallbackShuffled = shuffleArray(UNIVERSAL_LEAD_RICH_INDUSTRIES).slice(0, 8);
  return NextResponse.json({
    success: true,
    source: 'universal',
    suggestions: fallbackShuffled.map(({ industry, reason }) => ({ industry, reason })),
    suggested_industries: fallbackShuffled.map((i) => i.industry),
  });
}

// ─── POST /api/suggest-industries (AI-Powered Deep Suggestions) ───────────────
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const service = (body.service || body.input || '').toString().trim();
    const excludeList: string[] = Array.isArray(body.exclude)
      ? body.exclude.map((e: any) => String(e).trim()).filter(Boolean)
      : [];

    const effectiveService = service || 'B2B Services & Technology';

    // Layer 1: Instant suggestions ready as baseline / fallback
    const instantSuggestions = findInstantSuggestions(effectiveService, excludeList, 8);

    // Layer 2: LLM Deep Enrichment with Strict Lead-Rich & Easy-to-Understand Guidelines
    const excludeSection = excludeList.length > 0
      ? `\nIMPORTANT - DO NOT REPEAT ANY OF THESE PREVIOUSLY SHOWN INDUSTRIES (MUST BE BRAND NEW):\n${excludeList.slice(-25).map((e) => `- ${e}`).join('\n')}\n`
      : '';

    const prompt = `You are a Senior B2B Outbound Lead Generation and Sales Intelligence Expert.

A company provides the following services or products:
"${effectiveService}"

TASK:
Identify 6-8 SPECIFIC, REAL-WORLD B2B INDUSTRIES that are the BEST BUYERS for this service.

STRICT CRITERIA:
1. EASY TO UNDERSTAND: Use plain, universally understood business names (e.g. "Dental Clinics", "Commercial Roofing Contractors", "Real Estate Brokerages", "Logistics & Trucking", "Shopify E-Commerce Brands", "Accounting & CPA Firms", "Law Firms", "Auto Dealerships"). NEVER use convoluted academic jargon like "Industrial 4.0 Cyber-Physical Systems".
2. HIGH LEAD CONTACTABILITY (LEADS MILNA ASAN HO): Focus strictly on industries where businesses have active websites, published team/about pages, and easily reachable decision-makers (Owners, Founders, CEOs, Partners, Managing Directors).
3. TARGETED COMMERCIAL FIT: Explain in ONE punchy, simple sentence why this industry urgently needs this service to make money, save time, or solve an everyday headache.
4. FRESHNESS: Every time you suggest, pick fresh, creative, high-converting angles.${excludeSection}

Return ONLY a valid JSON object in this exact format (no markdown, no other text):
{
  "suggestions": [
    {
      "industry": "Clean Plain-English Industry Name",
      "reason": "One clear sentence explaining why they need this service and why leads are high value."
    }
  ]
}`;

    const systemPrompt = 'You are a practical B2B lead generation strategist. Return strictly valid JSON with clean, easy-to-understand industry names where finding real business leads and decision-maker emails is fast and effective.';

    let llmSuggestions: Array<{ industry: string; reason: string }> = [];

    try {
      const proxyRes = await fetch(`${getBackendUrl()}/llm-proxy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt,
          system_prompt: systemPrompt,
          temperature: 0.72, // Higher temperature for fresh, diverse suggestions on repeated queries
          max_tokens: 900,
          domain_tag: 'suggest-industries',
        }),
        signal: AbortSignal.timeout(18_000),
      });

      if (proxyRes.ok) {
        const proxyData = await proxyRes.json();
        let rawContent: string = (proxyData.content || '').replace(/```json/gi, '').replace(/```/g, '').trim();

        try {
          const parsed = JSON.parse(rawContent);
          if (Array.isArray(parsed)) {
            llmSuggestions = parsed;
          } else if (typeof parsed === 'object' && parsed !== null) {
            const possibleArray = Object.values(parsed).find((val) => Array.isArray(val));
            if (possibleArray && Array.isArray(possibleArray)) {
              llmSuggestions = possibleArray as Array<{ industry: string; reason: string }>;
            }
          }
        } catch {
          const matches = [...rawContent.matchAll(/\{\s*"industry"\s*:\s*"([^"]+)"\s*,\s*"reason"\s*:\s*"([^"]+)"\s*\}/gi)];
          llmSuggestions = matches.map((m) => ({ industry: m[1], reason: m[2] }));
        }
      }
    } catch {
      // LLM call failed or timed out — will seamlessly use instantSuggestions
    }

    // Filter out any LLM suggestions that match excludeList
    const excludeSet = new Set(excludeList.map((e) => e.toLowerCase().trim()));
    const validLlm = llmSuggestions.filter((item) => {
      const name = (item?.industry || '').trim();
      return name.length > 2 && !excludeSet.has(name.toLowerCase());
    });

    // Merge: LLM fresh suggestions first, then supplement from fresh instantSuggestions
    const seenNames = new Set<string>();
    const finalSuggestions: Array<{ industry: string; reason: string }> = [];

    for (const item of validLlm) {
      const name = item.industry.trim();
      const nameLower = name.toLowerCase();
      if (!seenNames.has(nameLower) && !excludeSet.has(nameLower)) {
        seenNames.add(nameLower);
        finalSuggestions.push({ industry: name, reason: (item.reason || '').trim() });
      }
      if (finalSuggestions.length >= 8) break;
    }

    // If LLM returned fewer than 6, fill from instantSuggestions
    for (const item of instantSuggestions) {
      const name = item.industry.trim();
      const nameLower = name.toLowerCase();
      if (!seenNames.has(nameLower) && !excludeSet.has(nameLower)) {
        seenNames.add(nameLower);
        finalSuggestions.push({ industry: name, reason: item.reason.trim() });
      }
      if (finalSuggestions.length >= 8) break;
    }

    return NextResponse.json({
      success: true,
      service: effectiveService,
      suggestions: finalSuggestions,
      source: validLlm.length > 0 ? 'ai' : 'instant_fresh',
    });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'An unexpected error occurred.' },
      { status: 500 }
    );
  }
}
