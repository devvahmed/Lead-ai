import { NextRequest, NextResponse } from 'next/server';

function getBackendUrl(): string {
  const envUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
  if (!envUrl || envUrl.startsWith('/')) {
    return 'http://localhost:8000';
  }
  return envUrl.replace(/\/$/, '');
}

export async function GET(req: NextRequest) {
  try {
    const authHeader = req.headers.get('authorization') || req.headers.get('Authorization');
    const backendUrl = `${getBackendUrl()}/api/clients`;

    const res = await fetch(backendUrl, {
      headers: {
        ...(authHeader ? { Authorization: authHeader } : {}),
      },
      cache: 'no-store',
    });

    if (!res.ok) {
      return NextResponse.json({ clients: [] });
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (err) {
    console.error('Fetch clients error:', err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Failed to fetch clients' },
      { status: 500 }
    );
  }
}
