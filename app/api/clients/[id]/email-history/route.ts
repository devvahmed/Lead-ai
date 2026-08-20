import { NextRequest, NextResponse } from 'next/server';

function getBackendUrl(): string {
  const envBackend = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
  if (!envBackend || envBackend.startsWith('/')) {
    return 'http://localhost:8000';
  }
  return envBackend.replace(/\/$/, '');
}

export async function GET(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const authHeader = req.headers.get('authorization');
    const backendUrl = getBackendUrl();

    const res = await fetch(`${backendUrl}/api/clients/${id}/email-history`, {
      headers: authHeader ? { 'Authorization': authHeader } : {},
    });

    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json({ error: data.detail || data.error || 'Failed to fetch email history' }, { status: res.status });
    }

    return NextResponse.json(data);
  } catch (err) {
    console.error('Fetch email history proxy error:', err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Failed to fetch email history' },
      { status: 500 }
    );
  }
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const authHeader = req.headers.get('authorization');
    const body = await req.json();
    const backendUrl = getBackendUrl();

    const res = await fetch(`${backendUrl}/api/clients/${id}/email-history`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(authHeader ? { 'Authorization': authHeader } : {}),
      },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json({ error: data.detail || data.error || 'Failed to save email history' }, { status: res.status });
    }

    return NextResponse.json(data);
  } catch (err) {
    console.error('Save email history proxy error:', err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Failed to save email history' },
      { status: 500 }
    );
  }
}
