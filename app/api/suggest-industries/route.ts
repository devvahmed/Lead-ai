import { NextRequest, NextResponse } from 'next/server';

function getBackendUrl(): string {
  const envUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
  if (!envUrl || envUrl.startsWith('/')) {
    return 'http://localhost:8000';
  }
  return envUrl.replace(/\/$/, '');
}

// ─── GET /api/suggest-industries (Profile-Aware Quick Tags for Authenticated Company) ───
export async function GET(req: NextRequest) {
  const defaultFallback = ["Fintech", "Healthcare", "E-Commerce & Retail", "Software & SaaS", "Logistics & Supply Chain", "Industrial Manufacturing"];

  try {
    const authHeader = req.headers.get('Authorization') || req.headers.get('authorization');
    if (!authHeader) {
      return NextResponse.json({
        success: true,
        suggested_industries: defaultFallback,
      });
    }

    const backendUrl = `${getBackendUrl()}/auth/suggest-industries`;
    const resp = await fetch(backendUrl, {
      method: 'GET',
      headers: {
        'Authorization': authHeader,
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    });

    if (!resp.ok) {
      console.warn(`[Suggest Industries GET Proxy] Backend returned status ${resp.status}`);
      return NextResponse.json({
        success: true,
        suggested_industries: defaultFallback,
      });
    }

    const data = await resp.json();
    return NextResponse.json({
      success: true,
      company_name: data.company_name,
      suggested_industries: data.suggested_industries || defaultFallback,
    });
  } catch (err) {
    console.error('[Suggest Industries GET Proxy Error]:', err);
    return NextResponse.json({
      success: true,
      suggested_industries: defaultFallback,
    });
  }
}

// ─── POST /api/suggest-industries (Typed Keyword / Service Target Industry Suggestions) ───
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const service = (body.service || body.input || '').toString().trim();

    if (!service) {
      return NextResponse.json(
        { error: 'Technology or service name is required.' },
        { status: 400 }
      );
    }

    const prompt = `You are a B2B market intelligence expert. A vendor offers this specific technology or service:

SERVICE: "${service}"

Your task: Identify the 6-8 industries that are the MOST GENUINE buyers of this exact service — industries where companies face a clear, direct operational or commercial problem that this service specifically solves.

RULES (follow strictly):
1. Do NOT list generic catch-alls like "Technology", "Business Services", or "Enterprise" unless the service is clearly fundamental to those exact verticals.
2. Each industry must have a UNIQUE, SPECIFIC reason that is directly tied to how THIS service solves a real problem in THAT industry — not a generic boilerplate reason.
3. Think about: What does a typical company in this industry DO every day? What pain does this service relieve for them specifically?
4. Prioritize industries where this service creates COMPETITIVE ADVANTAGE or solves a REGULATORY/COMPLIANCE/OPERATIONAL problem unique to that sector.
5. Industry names should be specific (e.g. "Digital Health Platforms" not just "Healthcare"; "D2C E-Commerce Brands" not just "Retail").

Return ONLY valid JSON with this exact structure (no markdown):
{"suggestions": [{"industry": "specific industry name", "reason": "One specific sentence explaining the direct operational need THIS service fills for companies in THIS industry."}]}`;

    const systemPrompt = 'You are a precise B2B market analyst. You only return valid JSON. You never use generic industry names when specific ones are more accurate. Your reasons are always unique to the specific service and industry combination.';

    // ── Route through Python backend LLM proxy (Ollama → Groq/Gemini fallback) ──
    const backendBase = getBackendUrl();
    const proxyRes = await fetch(`${backendBase}/llm-proxy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt,
        system_prompt: systemPrompt,
        temperature: 0.55,
        max_tokens: 1000,
        domain_tag: 'suggest-industries',
      }),
      signal: AbortSignal.timeout(30_000),
    });

    if (!proxyRes.ok) {
      const errText = await proxyRes.text().catch(() => '');
      console.error(`[Suggest Industries] LLM proxy error HTTP ${proxyRes.status}: ${errText}`);
      return NextResponse.json(
        { error: `LLM error (${proxyRes.status}): ${errText || 'Failed to generate suggestions'}` },
        { status: proxyRes.status }
      );
    }

    const proxyData = await proxyRes.json();
    let rawContent: string = proxyData.content || '';
    rawContent = rawContent.replace(/```json/gi, '').replace(/```/g, '').trim();

    let suggestions: Array<{ industry: string; reason: string }> = [];

    try {
      const parsed = JSON.parse(rawContent);
      if (Array.isArray(parsed)) {
        suggestions = parsed;
      } else if (typeof parsed === 'object' && parsed !== null) {
        const possibleArray = Object.values(parsed).find((val) => Array.isArray(val));
        if (possibleArray && Array.isArray(possibleArray)) {
          suggestions = possibleArray as Array<{ industry: string; reason: string }>;
        }
      }
    } catch {
      const matches = [...rawContent.matchAll(/\{\s*"industry"\s*:\s*"([^"]+)"\s*,\s*"reason"\s*:\s*"([^"]+)"\s*\}/gi)];
      suggestions = matches.map((m) => ({ industry: m[1], reason: m[2] }));
    }

    const cleanedSuggestions = suggestions
      .filter((item) => item && typeof item.industry === 'string' && item.industry.trim().length > 0)
      .map((item) => ({
        industry: item.industry.trim(),
        reason: (item.reason || '').trim(),
      }));

    return NextResponse.json({
      success: true,
      service,
      suggestions: cleanedSuggestions,
    });
  } catch (error) {
    console.error('[Suggest Industries POST Error]:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'An unexpected server error occurred.' },
      { status: 500 }
    );
  }
}
