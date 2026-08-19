import { NextRequest, NextResponse } from 'next/server';

function getBackendUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
  if (!envUrl || envUrl.startsWith('/')) {
    return 'http://localhost:8000';
  }
  return envUrl.replace(/\/$/, '');
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    // Signup includes Ollama AI profile enrichment which can take 30-60s
    const resp = await fetch(`${getBackendUrl()}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(90_000), // 90 seconds for Ollama AI enrichment
    });

    const data = await resp.json();
    return NextResponse.json(data, { status: resp.status });
  } catch (err: any) {
    console.error('[API Proxy Signup Error]:', err);
    const isTimeout = err?.name === 'TimeoutError' || err?.name === 'AbortError';
    return NextResponse.json(
      {
        detail: isTimeout
          ? 'Signup is taking longer than expected. Please try again.'
          : 'Failed to process signup request.',
      },
      { status: 500 }
    );
  }
}
