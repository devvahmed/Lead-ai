import { NextRequest, NextResponse } from 'next/server';
import { getAuthenticatedCompany } from '../auth-helper';

function getBackendUrl(): string {
  const envUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
  if (!envUrl || envUrl.startsWith('/')) {
    return 'http://localhost:8000';
  }
  return envUrl.replace(/\/$/, '');
}

export async function POST(req: NextRequest) {
  let isFollowup = false;
  let company_name = 'the target company';
  let industry = 'Technology';
  let matched_service = 'AI & Automated Solutions';
  let match_reason = 'optimizing operations';
  let ourCompanyName = 'WTechX';

  try {
    const companyProfile = await getAuthenticatedCompany(req);
    let ourServices = 'AI, Robotics, and Computer Vision solutions';
    let ourDescription = 'provider of intelligent automated solutions';

    if (companyProfile) {
      ourCompanyName = companyProfile.name;
      ourServices = companyProfile.services || companyProfile.description || ourServices;
      ourDescription = companyProfile.description || `${ourCompanyName} provides ${ourServices}.`;
    }

    const body = await req.json();
    company_name = body.company_name || body.companyName || 'the target company';
    industry = body.industry || 'Technology';
    const country = body.country || 'Global';
    const company_summary = body.company_summary || body.description || body.relevance_reason || `${company_name} is a leading provider in the ${industry} industry.`;
    matched_service = body.matched_service || body.matchedService || ourServices;
    match_reason = body.match_reason || body.matchReason || `optimizing operations for ${company_name}`;
    isFollowup = Boolean(body.is_followup || body.isFollowup);

    const systemPrompt = isFollowup
      ? `Write a short, polite 2-3 sentence cold follow-up nudge email to ${company_name}, a company in the ${industry} industry (${country}). 

About them: ${company_summary}
Our service offered: ${matched_service}

Write a follow-up nudge email that:
1. Briefly references our initial email regarding ${ourCompanyName}'s ${matched_service} solutions
2. Asks politely if they had a chance to review it or if there is a better person on their team to connect with
3. Suggests a brief, low-friction 15-minute intro call
4. Keep it under 75 words, professional, warm, and zero fluff
5. Signed simply as 'The ${ourCompanyName} Team'

Return ONLY pure JSON matching this exact structure:
{
  "subject": "Following up: ${matched_service} for ${company_name}",
  "body": "full follow-up email body text ready to send"
}`
      : `Write a short, compelling cold outreach email to ${company_name}, a company in the ${industry} industry (${country}). 

About them: ${company_summary}

We believe they need: ${matched_service} because ${match_reason}

About us: We are ${ourCompanyName}, ${ourDescription}

Write an email that:
1. Opens with a specific, genuine hook referencing their actual business/product (not generic greetings like 'Dear Sir/Madam')
2. Identifies their specific pain point/need in one line
3. Positions our ${matched_service} service as the solution, briefly and confidently
4. Ends with a clear, low-friction call-to-action (e.g. suggesting a short 15-minute call)
5. Keep it under 150 words, professional but warm tone, no corporate jargon or generic filler phrases
6. Do not use placeholder brackets like [Your Name] — write it ready to send, signed simply as 'The ${ourCompanyName} Team'

Return ONLY pure JSON matching this exact structure:
{
  "subject": "short, specific subject line under 60 characters",
  "body": "full email body text ready to send"
}`;

    const backendBase = getBackendUrl();
    console.log(`[LLM Email Gen] Generating ${isFollowup ? 'follow-up' : 'initial'} email for ${company_name} via backend LLM proxy...`);

    const proxyRes = await fetch(`${backendBase}/llm-proxy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: systemPrompt,
        temperature: 0.3,
        max_tokens: 500,
        domain_tag: 'email-gen',
      }),
      signal: AbortSignal.timeout(30000),
    });

    if (!proxyRes.ok) {
      const errText = await proxyRes.text().catch(() => '');
      console.warn(`[LLM Email Gen] Backend proxy HTTP ${proxyRes.status}: ${errText}`);
      return NextResponse.json({
        subject: isFollowup ? `Following up: ${matched_service} for ${company_name}` : `${matched_service} for ${company_name}`,
        body: isFollowup
          ? `Hi team at ${company_name},\n\nFollowing up on my previous email regarding ${ourCompanyName}'s ${matched_service} capabilities.\n\nWould you be open to a quick 15-minute call next week to see if there is alignment for your roadmap?\n\nBest regards,\nThe ${ourCompanyName} Team`
          : `Hi team at ${company_name},\n\nI was reviewing ${company_name}'s operations in ${industry} and was impressed by your team's work. Teams expanding in this domain often look for specialized support when ${match_reason}.\n\nAt ${ourCompanyName}, we provide ${matched_service} to help accelerate production and operational pipelines.\n\nWould you be available for a short 15-minute call next week to see if there is an alignment?\n\nBest regards,\nThe ${ourCompanyName} Team`
      });
    }

    const data = await proxyRes.json();
    let rawContent = (data.content || '').replace(/```json/gi, '').replace(/```/g, '').trim();
    let parsed: { subject?: string; body?: string } = {};
    try {
      parsed = JSON.parse(rawContent);
    } catch {
      parsed = { body: rawContent };
    }

    return NextResponse.json({
      subject: parsed.subject || `Outreach to ${company_name}`,
      body: parsed.body || rawContent,
    });
  } catch (err) {
    console.error('Email generation error:', err);
    // Return clean fallback email instead of 500 red alert UI crash
    return NextResponse.json({
      subject: isFollowup ? `Following up: ${matched_service} for ${company_name}` : `${matched_service} for ${company_name}`,
      body: isFollowup
        ? `Hi team at ${company_name},\n\nFollowing up on my previous email regarding ${ourCompanyName}'s ${matched_service} capabilities.\n\nWould you be open to a quick 15-minute call next week to see if there is alignment for your roadmap?\n\nBest regards,\nThe ${ourCompanyName} Team`
        : `Hi team at ${company_name},\n\nI was reviewing ${company_name}'s operations in ${industry} and was impressed by your team's work. Teams expanding in this domain often look for specialized support when ${match_reason}.\n\nAt ${ourCompanyName}, we provide ${matched_service} to help accelerate production and operational pipelines.\n\nWould you be available for a short 15-minute call next week to see if there is an alignment?\n\nBest regards,\nThe ${ourCompanyName} Team`
    });
  }
}
