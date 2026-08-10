import { NextRequest, NextResponse } from 'next/server';
import { getAuthenticatedCompany } from '../auth-helper';

export async function POST(req: NextRequest) {
  let ourCompanyName = 'WTechX';
  let company_name = 'the prospect company';
  let matched_service = 'AI & Automated Solutions';

  try {
    const companyProfile = await getAuthenticatedCompany(req);
    let ourServices = 'AI, Robotics, and Computer Vision solutions';
    let ourDescription = 'provider of intelligent automated solutions';

    if (companyProfile) {
      ourCompanyName = companyProfile.name;
      ourServices = companyProfile.services || companyProfile.description || ourServices;
      ourDescription = companyProfile.description || `${ourCompanyName} specializes in ${ourServices}.`;
    }

    const body = await req.json();
    company_name = body.company_name || body.companyName || 'the prospect company';
    const industry = body.industry || 'Technology';
    const country = body.country || 'Global';
    matched_service = body.matched_service || body.matchedService || ourServices;
    const client_reply = body.client_reply || body.clientReply || body.reply || '';

    if (!client_reply || client_reply.trim().length < 5) {
      return NextResponse.json({ error: 'Client reply text is required for negotiation analysis.' }, { status: 400 });
    }

    const systemPrompt = `You are an elite B2B Sales & Negotiation Strategist for ${ourCompanyName} (${ourDescription}).

The prospect company is: ${company_name} (${industry}, ${country}).
Our service solution: ${matched_service}.

The prospect replied to our outreach with this email/message:
"""
${client_reply}
"""

Evaluate their reply carefully and provide strategic negotiation guidance for ${ourCompanyName}:
1. Identify objection_type (pick ONE: "Price & Budget", "Technical Feasibility", "Implementation Timeline", "Competitor Comparison", "Scope & Customization", "General Interest")
2. Summarize detected_intent in one line.
3. Write strategy_hint: 1-2 actionable sales strategy tips for ${ourCompanyName} (e.g., offer phased pilot, highlight specific ROI, propose flexible milestones, or schedule a technical deep-dive).
4. Write subject: Professional counter-offer subject line under 60 chars.
5. Write body: Persuasive counter-reply email addressing their exact point (< 150 words, warm executive tone, no placeholder brackets, signed 'The ${ourCompanyName} Team').

Return ONLY pure JSON matching this exact structure:
{
  "objection_type": "Price & Budget",
  "detected_intent": "one line summary of client concern",
  "strategy_hint": "actionable sales strategy advice for ${ourCompanyName}",
  "subject": "counter-offer subject line",
  "body": "full counter-reply email body text"
}`;

    const rawBaseUrl = process.env.OLLAMA_BASE_URL || process.env.OLLAMA_URL || 'http://100.91.220.98:11434/v1';
    const baseUrl = rawBaseUrl.trim().replace(/\/$/, '');
    const ollamaEndpoint = baseUrl.endsWith('/v1') ? `${baseUrl}/chat/completions` : `${baseUrl}/v1/chat/completions`;
    const modelName = process.env.OLLAMA_MODEL || 'llama3:latest';

    console.log(`[Ollama Negotiation Analysis] Analyzing client reply for ${company_name} on behalf of ${ourCompanyName}...`);

    const groqRes = await fetch(ollamaEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: modelName,
        messages: [{ role: 'user', content: systemPrompt }],
        temperature: 0.3,
        max_tokens: 600,
        response_format: { type: 'json_object' },
      }),
      signal: AbortSignal.timeout(25000),
    });

    if (!groqRes.ok) {
      const errText = await groqRes.text().catch(() => '');
      console.warn(`[Groq Negotiation Analysis] HTTP ${groqRes.status}: ${errText}`);
      return NextResponse.json({
        objection_type: 'Technical & Commercial Alignment',
        detected_intent: 'Client replied with questions regarding implementation and terms.',
        strategy_hint: `Offer a technical alignment call with ${ourCompanyName}'s engineering lead and flexible pilot milestones.`,
        subject: `Re: ${ourCompanyName} & ${company_name} Collaboration Options`,
        body: `Hi team at ${company_name},\n\nThank you for sharing your feedback. We would be happy to adapt our implementation schedule to fit your team's exact requirements for ${matched_service}.\n\nWould you be open to a brief 15-minute call with our team next week to explore tailored options?\n\nBest regards,\nThe ${ourCompanyName} Team`
      });
    }

    const data = await groqRes.json();
    const rawContent = data.choices?.[0]?.message?.content?.trim() || '{}';
    let parsed: {
      objection_type?: string;
      detected_intent?: string;
      strategy_hint?: string;
      subject?: string;
      body?: string;
    } = {};

    try {
      parsed = JSON.parse(rawContent);
    } catch {
      parsed = { body: rawContent };
    }

    return NextResponse.json({
      objection_type: parsed.objection_type || 'General Interest',
      detected_intent: parsed.detected_intent || 'Client responded to outreach.',
      strategy_hint: parsed.strategy_hint || `Highlight ${ourCompanyName}'s specialized ${matched_service} capabilities and offer a flexible pilot roadmap.`,
      subject: parsed.subject || `Re: ${ourCompanyName} & ${company_name} Options`,
      body: parsed.body || rawContent,
    });
  } catch (err) {
    console.error('Negotiation analysis error:', err);
    // Return clean fallback response instead of crashing
    return NextResponse.json({
      objection_type: 'Technical & Commercial Alignment',
      detected_intent: 'Client replied with questions regarding implementation and terms.',
      strategy_hint: `Offer a technical alignment call with ${ourCompanyName}'s engineering lead and flexible pilot milestones.`,
      subject: `Re: ${ourCompanyName} & ${company_name} Collaboration Options`,
      body: `Hi team at ${company_name},\n\nThank you for sharing your feedback. We would be happy to adapt our implementation schedule to fit your team's exact requirements for ${matched_service}.\n\nWould you be open to a brief 15-minute call with our team next week to explore tailored options?\n\nBest regards,\nThe ${ourCompanyName} Team`
    });
  }
}
