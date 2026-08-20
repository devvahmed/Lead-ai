import { NextRequest, NextResponse } from 'next/server';

function getBackendUrl(): string {
  const envBackend = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
  if (!envBackend || envBackend.startsWith('/')) {
    return 'http://localhost:8000';
  }
  return envBackend.replace(/\/$/, '');
}

function extractDomain(input: string): string | null {
  try {
    const normalized = input.startsWith('http') ? input : `https://${input}`;
    return new URL(normalized).hostname.replace(/^www\./, '');
  } catch {
    return null;
  }
}

async function enrichWithHunter(website?: string) {
  const key = process.env.HUNTER_API_KEY;
  if (!key || !website) return { email: null as string | null, phone: null as string | null };

  const domain = extractDomain(website);
  if (!domain) return { email: null as string | null, phone: null as string | null };

  try {
    const url = `https://api.hunter.io/v2/domain-search?domain=${encodeURIComponent(domain)}&limit=10&type=personal&api_key=${encodeURIComponent(key)}`;
    const res = await fetch(url, {
      headers: { Accept: 'application/json' },
      signal: AbortSignal.timeout(6000),
    });

    if (!res.ok) {
      return { email: null as string | null, phone: null as string | null };
    }

    const data = await res.json();
    const emails = (data?.data?.emails as Array<{ value?: string; confidence?: number; position?: string }> | undefined) ?? [];

    const best = [...emails].sort((a, b) => {
      const aScore = (a.confidence ?? 0) + (a.position ? 10 : 0);
      const bScore = (b.confidence ?? 0) + (b.position ? 10 : 0);
      return bScore - aScore;
    })[0];

    return {
      email: best?.value ?? null,
      phone: (data?.data?.phone_number as string | undefined) ?? null,
    };
  } catch {
    return { email: null as string | null, phone: null as string | null };
  }
}

export async function POST(req: NextRequest) {
  try {
    const authHeader = req.headers.get('authorization');
    const body = await req.json();
    const { name, website, email, phone } = body;

    if (!name) {
      return NextResponse.json({ error: 'Company name is required' }, { status: 400 });
    }

    // Priority 2: Hunter.io API Fallback ONLY if email is missing
    let finalEmail = email || null;
    let finalPhone = phone || null;

    if (!finalEmail && website && process.env.HUNTER_API_KEY) {
      const hunter = await enrichWithHunter(website);
      if (hunter.email) finalEmail = hunter.email;
      if (hunter.phone && !finalPhone) finalPhone = hunter.phone;
    }

    const payload = {
      ...body,
      email: finalEmail,
      phone: finalPhone,
    };

    const backendUrl = getBackendUrl();
    const res = await fetch(`${backendUrl}/api/save-client`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(authHeader ? { Authorization: authHeader } : {}),
      },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json({ error: data.detail || data.error || 'Failed to save client' }, { status: res.status });
    }

    return NextResponse.json(data);
  } catch (err) {
    console.error('Save client route error:', err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Failed to save client' },
      { status: 500 }
    );
  }
}
