import { NextRequest, NextResponse } from 'next/server';
import { getAuthenticatedCompany } from '../auth-helper';

function getBackendUrl(): string {
  const envUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
  if (!envUrl || envUrl.startsWith('/')) {
    return 'http://localhost:8000';
  }
  return envUrl.replace(/\/$/, '');
}

/**
 * Strips HTML tags, markdown fences, JSON brackets, and leaked code/syntax
 * ensuring only pure human email text is returned.
 */
function cleanText(str: string): string {
  if (!str) return '';
  return str
    .replace(/^["'\[]+|["'\]]+$/g, '')
    .replace(/<[^>]*>/g, '')
    .trim();
}

function cleanEmailBody(str: string): string {
  if (!str) return '';
  let cleaned = str;

  // Remove common LLM section headers if leaked into body
  cleaned = cleaned.replace(/^(?:Cold Outreach Email|Email Body|Body|STEP 2 OUTPUT|Output):\s*/im, '');
  cleaned = cleaned.replace(/^Subject:\s*[^\n\r]+[\r\n]*/im, '');
  cleaned = cleaned.replace(/(?:Internal angle rationale|Internal rationale|Rationale)[^\n:]*:[\s\S]*$/im, '');

  // Strip code fences (e.g. ```json ... ``` or ``` ...)
  cleaned = cleaned.replace(/```[a-z]*\s*/gi, '').replace(/\s*```/g, '');

  // Strip raw JSON artifacts if any leaked through (e.g. "body": "...", "subject": "...")
  cleaned = cleaned.replace(/^\{?\s*"(?:subject|body)":\s*"/g, '').replace(/"\s*,?\s*\}?$/g, '');

  // Convert HTML tags to natural clean line breaks
  cleaned = cleaned.replace(/<br\s*\/?>/gi, '\n');
  cleaned = cleaned.replace(/<\/p>/gi, '\n\n');
  cleaned = cleaned.replace(/<p>/gi, '');
  cleaned = cleaned.replace(/<[^>]*>/g, ''); // strip all other HTML tags like <strong>, <span>

  // Normalize excessive newlines to double newlines maximum
  cleaned = cleaned.replace(/\r\n/g, '\n');
  cleaned = cleaned.replace(/\n{3,}/g, '\n\n');

  return cleaned.trim();
}

function parseAndSanitizeEmailResponse(
  rawContent: string,
  defaultSubject: string,
  fallbackCompany: string,
  fallbackService: string,
  ourCompanyName: string
): { subject: string; body: string; internal_rationale?: string } {
  if (!rawContent || !rawContent.trim()) {
    return {
      subject: defaultSubject,
      body: `Hi team at ${fallbackCompany},\n\nI was reviewing your initiatives and wanted to explore how we can support your roadmap with customized ${fallbackService}.\n\nWould you be open to a brief 15-minute technical discussion next week to see if there is alignment?\n\nBest regards,\nThe ${ourCompanyName} Team`,
    };
  }

  let text = rawContent.trim();

  // 1. Strip markdown fences if wrapping entire response
  text = text.replace(/^```[a-z]*\s*/i, '').replace(/\s*```$/i, '').trim();

  // 2. Try JSON parse first if output is JSON formatted
  try {
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      const parsed = JSON.parse(jsonMatch[0]);
      if (parsed.subject || parsed.body) {
        return {
          subject: cleanText(parsed.subject || defaultSubject),
          body: cleanEmailBody(parsed.body || ''),
          internal_rationale: cleanText(parsed.internal_angle_rationale || parsed.internal_rationale || parsed.rationale || '')
        };
      }
    }
  } catch {
    // Not valid JSON, continue with text regex extraction
  }

  // 3. Extract Subject Line
  let subject = defaultSubject;
  const subjectMatch = text.match(/^(?:Subject|SUBJECT):\s*([^\n\r]+)/im);
  if (subjectMatch) {
    subject = cleanText(subjectMatch[1]);
    text = text.replace(/^(?:Subject|SUBJECT):\s*[^\n\r]+[\r\n]*/im, '');
  }

  // 4. Extract Internal Angle Rationale (and prevent it from polluting the body)
  let rationale = '';
  const rationaleMatch = text.match(/(?:Internal angle rationale|Internal rationale|Rationale)[^\n:]*:\s*([\s\S]+)$/i);
  if (rationaleMatch) {
    rationale = cleanText(rationaleMatch[1]);
    text = text.substring(0, rationaleMatch.index).trim();
  }

  // 5. Clean and sanitize the remaining body text
  let body = cleanEmailBody(text);

  if (!body || body.length < 20) {
    body = `Hi team at ${fallbackCompany},\n\nI was reviewing your initiatives and wanted to explore how we can support your roadmap with customized ${fallbackService}.\n\nWould you be open to a brief 15-minute technical discussion next week to see if there is alignment?\n\nBest regards,\nThe ${ourCompanyName} Team`;
  }

  return {
    subject: subject || defaultSubject,
    body,
    internal_rationale: rationale || undefined
  };
}

export async function POST(req: NextRequest) {
  let isFollowup = false;
  let company_name = 'the target company';
  let industry = 'Technology';
  let matched_service = 'AI & Automated Solutions';
  let ourCompanyName = 'WTechX';
  let ourCompanyWebsite = 'https://wtechx.com';

  try {
    const companyProfile = await getAuthenticatedCompany(req);
    let ourServices = 'AI Lead Generation, Custom Robotics, LiDAR SLAM, Computer Vision, and AI Workflow Automation';
    let ourDescription = 'PhD-led engineering company developing production-focused AI automation and advanced robotics systems';
    let ourTargetCustomers = 'Industrial automation, robotics, inspection, logistics, and enterprise software companies';

    if (companyProfile) {
      ourCompanyName = companyProfile.name || ourCompanyName;
      ourCompanyWebsite = companyProfile.website || (ourCompanyName.toLowerCase().includes('wtech') ? 'https://wtechx.com' : 'https://company.com');
      ourServices = companyProfile.services || companyProfile.description || ourServices;
      ourDescription = companyProfile.description || ourDescription;
      ourTargetCustomers = companyProfile.target_customers || ourTargetCustomers;
    }

    const body = await req.json();
    company_name = body.company_name || body.companyName || 'the target company';
    industry = body.industry || 'Technology';
    const country = body.country || 'Global';
    const targetWebsite = body.website || body.company_website || body.target_website || '';
    const fallbackContext = body.fallback_context || body.company_summary || body.description || body.relevance_reason || `${company_name} operates in the ${industry} sector (${country}).`;
    matched_service = body.matched_service || body.matchedService || ourServices;
    const match_reason = body.match_reason || body.matchReason || `optimizing operational pipelines and automation for ${company_name}`;
    isFollowup = Boolean(body.is_followup || body.isFollowup);

    // Build Dynamic Company Profile section
    const isWTechX = ourCompanyName.toLowerCase().includes('wtech') || ourCompanyName.toLowerCase().includes('lead-ai');
    let senderProfilePrompt = '';
    if (isWTechX) {
      senderProfilePrompt = `
ABOUT ${ourCompanyName.toUpperCase()}
${ourCompanyName} is a PhD-led engineering company that develops production-focused AI automation and advanced robotics systems for real business and operational environments.

AI Services:
- AI lead-generation systems: Prospect discovery, personalized outreach, meeting booking, and CRM integration.
- AI chatbots for business: Custom conversational agents that qualify leads, support multi-languages, and book meetings.
- AI workflow automation: Automation of repetitive tasks, data processing, internal workflows, CRM operations, and AI-assisted decisions.
- AI implementation consulting: Opportunity audits, prioritized implementation roadmaps, ROI analysis, and deployment planning.
Delivery model: Customized, production-ready AI systems commonly delivered within 1–4 weeks, depending on scope.

Robotics Services:
- Custom robotics development from concept and simulation through integration, validation, and real-world deployment.
- AGVs, logistics robots, inspection robots, delivery robots, warehouse automation, and industrial automation.
- LiDAR–inertial SLAM, visual-inertial navigation, real-time 2D/3D mapping, and localization in dynamic or GPS-denied environments.
- Multi-sensor fusion and calibration using LiDAR, cameras, IMUs, GPS, and INS.
- Object detection, segmentation, tracking, scene understanding, depth estimation, and pose estimation.
- Path planning, obstacle avoidance, and Extended Kalman Filter-based pose estimation.
- Camera calibration, multi-view geometry, stereo vision, HDR imaging, feature extraction, inspection, and monitoring.
- Embedded and real-time AI deployment, sensor processing, hardware integration, and model optimization.
- Robotics simulation and validation using ROS/ROS2, Gazebo, RViz, and real-world scenarios.

Target Applications:
Construction and infrastructure, Inspection and monitoring, Warehousing and logistics, Industrial automation, Smart mobility, Autonomous and field robotics, Business lead generation, Customer-support automation, Workflow and process automation, AI implementation and consulting.
`;
    } else {
      senderProfilePrompt = `
ABOUT ${ourCompanyName.toUpperCase()}
${ourCompanyName} is a specialized provider of ${ourServices}.
${ourDescription ? `Company Overview: ${ourDescription}` : ''}
${ourTargetCustomers ? `Target Customers & Industries: ${ourTargetCustomers}` : ''}
Delivery model: Customized, production-ready solutions commonly delivered within 1–4 weeks depending on scope.
`;
    }

    // Build the Prompt according to the specification
    const systemPrompt = isFollowup
      ? `TARGET COMPANY: ${company_name}
TARGET COMPANY WEBSITE: ${targetWebsite || 'Provided in fallback'}
MY COMPANY NAME: ${ourCompanyName}
MY COMPANY WEBSITE: ${ourCompanyWebsite}

FALLBACK CONTEXT:
${fallbackContext}

ROLE:
You are a senior technical specialist for ${ourCompanyName}.

OBJECTIVE:
Write a short, professional, polite cold follow-up nudge email to ${company_name}.

RULES:
- Briefly reference our initial email regarding ${ourCompanyName}'s ${matched_service} capabilities.
- Ask politely if they had a chance to review it or if there is a better person on their team to connect with.
- Suggest a brief, low-friction 15-minute intro discussion.
- Keep it strictly under 75 words, professional, peer-to-peer tone, and zero fluff.
- No buzzwords ("synergy", "cutting-edge", "revolutionize").
- Signed simply as "The ${ourCompanyName} Team".

OUTPUT FORMAT:
Subject: <short follow-up subject under 60 chars>

<email body under 75 words ready to send>

Internal angle rationale:
<one sentence rationale>`
      : `TARGET COMPANY: ${company_name}
TARGET COMPANY WEBSITE: ${targetWebsite || 'Provided in fallback'}
MY COMPANY NAME: ${ourCompanyName}
MY COMPANY WEBSITE: ${ourCompanyWebsite}

FALLBACK CONTEXT:
${fallbackContext}

ROLE:
You are a senior solutions engineer, technical business-development specialist, and cold-email writer for ${ourCompanyName}.

OBJECTIVE:
Complete two tasks in order:
1. Determine whether the target company is a genuine potential client, outsourcing customer, or strategic partner for ${ourCompanyName}.
2. Write a personalized cold email for every evidence-supported company scoring 5/10 or higher.

RULES:
- Analyze only the company identified by TARGET COMPANY.
- Select only the single ${ourCompanyName} service most directly connected to the target company's need. Do not mention multiple services in the email.
- Base every claim on the provided TARGET COMPANY details and FALLBACK CONTEXT.
- If the opportunity is inferred, frame it as a question or possibility—not a confirmed problem.
- Never present an inferred problem as a confirmed problem.

${senderProfilePrompt}

COLD EMAIL REQUIREMENTS:
- Provide one subject line and one email body.
- Keep the email body strictly UNDER 100 WORDS, including the greeting, excluding the subject.
- Use a direct, natural, peer-to-peer tone.
- The first sentence must reference one specific company product, project, initiative, service, sensor configuration, or claim supported by the research.
- Focus on exactly one technical or business opportunity.
- Match it with exactly one ${ourCompanyName} capability.
- Suggest one concrete outsourced work package or practical outcome.
- End with only one low-friction call to action: one specific peer-level question OR a request for a brief 15-minute discussion.
- Make the subject short, natural, specific, and non-promotional (under 60 characters).
- Do not include source links in the email.
- Do not use placeholder brackets like [Your Name] or [Company Name]. Sign off simply as "The ${ourCompanyName} Team".
- CRITICAL PROHIBITED PHRASES (NEVER USE):
  "I hope this email finds you well"
  "I wanted to reach out"
  "We are impressed by your innovative work"
  "Cutting-edge"
  "Revolutionize"
  "Synergy"
  "Explore synergies"
  "We would love to collaborate"
  "Let's connect"
  Generic compliments or sales-heavy/exaggerated language.

OUTPUT FORMAT:
Subject: <short, specific subject line>

<email body text under 100 words ready to send>

Internal angle rationale:
<one sentence explaining why the selected company detail, opportunity, and capability are likely to earn a response>`;

    const backendBase = getBackendUrl();
    console.log(`[LLM Email Gen] Generating ${isFollowup ? 'follow-up' : 'initial'} email for ${company_name} (${ourCompanyName})...`);

    const proxyRes = await fetch(`${backendBase}/llm-proxy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: systemPrompt,
        temperature: 0.25,
        max_tokens: 500,
        domain_tag: 'email-gen',
      }),
      signal: AbortSignal.timeout(30000),
    });

    const defaultSubj = isFollowup
      ? `Following up: ${matched_service} for ${company_name}`
      : `${matched_service} for ${company_name}`;

    if (!proxyRes.ok) {
      const errText = await proxyRes.text().catch(() => '');
      console.warn(`[LLM Email Gen] Backend proxy HTTP ${proxyRes.status}: ${errText}`);
      const fallbackResult = parseAndSanitizeEmailResponse('', defaultSubj, company_name, matched_service, ourCompanyName);
      return NextResponse.json(fallbackResult);
    }

    const data = await proxyRes.json();
    const rawContent = data.content || '';
    const sanitized = parseAndSanitizeEmailResponse(rawContent, defaultSubj, company_name, matched_service, ourCompanyName);

    return NextResponse.json(sanitized);
  } catch (err) {
    console.error('Email generation error:', err);
    const defaultSubj = isFollowup
      ? `Following up: ${matched_service} for ${company_name}`
      : `${matched_service} for ${company_name}`;
    const fallbackResult = parseAndSanitizeEmailResponse('', defaultSubj, company_name, matched_service, ourCompanyName);
    return NextResponse.json(fallbackResult);
  }
}
