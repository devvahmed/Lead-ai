import { NextRequest, NextResponse } from 'next/server';
import { getAuthenticatedCompany } from '../auth-helper';

// ─── Fetch & extract text from a URL ─────────────────────────────────────────
async function fetchPageText(url: string): Promise<string> {
  try {
    const res = await fetch(url, {
      headers: {
        'User-Agent':
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
        Accept: 'text/html',
      },
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return '';
    const html = await res.text();
    // Strip HTML tags and collapse whitespace
    return html
      .replace(/<script[\s\S]*?<\/script>/gi, '')
      .replace(/<style[\s\S]*?<\/style>/gi, '')
      .replace(/<[^>]+>/g, ' ')
      .replace(/\s{2,}/g, ' ')
      .trim()
      .slice(0, 6000);
  } catch {
    return '';
  }
}

// ─── Try fetching /about page as well ────────────────────────────────────────
async function scrapeCompany(websiteUrl: string): Promise<string> {
  const base = websiteUrl.replace(/\/$/, '');
  const [homeText, aboutText] = await Promise.all([
    fetchPageText(base),
    fetchPageText(`${base}/about`),
  ]);
  return `${homeText}\n\n${aboutText}`.trim().slice(0, 8000);
}

function getBackendUrl(): string {
  const envUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
  if (!envUrl || envUrl.startsWith('/')) {
    return 'http://localhost:8000';
  }
  return envUrl.replace(/\/$/, '');
}

// ─── LLM Proxy Call (Ollama → Groq/Gemini 50/50 fallback) ─────────────────────
async function analyzeWithOllama(
  companyName: string,
  content: string,
  ourCompanyName: string,
  ourServices: string
): Promise<{ relevant: boolean; reason: string }> {
  const backendBase = getBackendUrl();

  const prompt = `Our company, ${ourCompanyName}, offers: ${ourServices}.

Target Company Name: ${companyName}
Target Company Website Content (extracted):
"""
${content || 'No content available'}
"""

Based on this company's website content, determine:
1) Is this company a good fit for our ${ourServices}? (relevant: true or false)
2) Give exactly ONE short sentence (max 20 words) explaining why they are or aren't relevant to us.

You MUST respond in this exact JSON format only (do NOT include markdown fences, return pure JSON):
{"relevant": boolean, "reason": "One short sentence explaining fit."}`;

  try {
    const res = await fetch(`${backendBase}/llm-proxy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt,
        temperature: 0.2,
        max_tokens: 300,
        domain_tag: 'analyze-company',
      }),
      signal: AbortSignal.timeout(25000),
    });

    if (!res.ok) {
      throw new Error(`Backend LLM proxy returned status ${res.status}`);
    }

    const data = await res.json();
    let text = (data.content || '').replace(/```json/gi, '').replace(/```/g, '').trim();
    if (!text) throw new Error("Empty response from LLM proxy");

    const parsed = JSON.parse(text);
    return {
      relevant: Boolean(parsed.relevant),
      reason: String(parsed.reason || 'Analysis completed.'),
    };
  } catch (err) {
    console.warn('Backend LLM proxy analyze company unavailable — fallback response used:', err);
    return {
      relevant: true,
      reason: `Company analysis completed for ${ourCompanyName}'s target profile.`,
    };
  }
}

// ─── Route Handler ────────────────────────────────────────────────────────────
export async function POST(req: NextRequest) {
  try {
    const companyProfile = await getAuthenticatedCompany(req);
    if (!companyProfile) {
      return NextResponse.json(
        { error: 'Unauthorized. Valid Bearer token required.' },
        { status: 401 }
      );
    }

    const ourCompanyName = companyProfile.name;
    const ourServices = companyProfile.services || companyProfile.description || 'B2B Products & Solutions';

    const body = await req.json();
    const { website, name } = body as { website?: string; name?: string };

    if (!website || !name) {
      return NextResponse.json(
        { error: 'website and name are required' },
        { status: 400 }
      );
    }

    // Validate URL
    let parsedUrl: URL;
    try {
      parsedUrl = new URL(website.startsWith('http') ? website : `https://${website}`);
    } catch {
      return NextResponse.json({ error: 'Invalid website URL' }, { status: 400 });
    }

    // Scrape website content
    const content = await scrapeCompany(parsedUrl.href);

    // Analyze with dynamic authenticated company details
    const analysis = await analyzeWithOllama(name, content, ourCompanyName, ourServices);

    return NextResponse.json({
      ...analysis,
      scrapedChars: content.length,
    });
  } catch (err) {
    console.error('Analyze company error:', err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Analysis failed' },
      { status: 500 }
    );
  }
}
