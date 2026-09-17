import { NextRequest, NextResponse } from 'next/server';

function getBackendUrl(): string {
  const envUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
  if (!envUrl || envUrl.startsWith('/')) {
    return 'http://localhost:8000';
  }
  return envUrl.replace(/\/$/, '');
}

export async function POST(req: NextRequest) {
  try {
    let authHeader = req.headers.get('authorization') || req.headers.get('Authorization');
    if (!authHeader) {
      const cookieToken = req.cookies.get('token')?.value;
      if (cookieToken) {
        authHeader = `Bearer ${cookieToken}`;
      }
    }
    const backendUrl = `${getBackendUrl()}/api/automation/stop`;

    const res = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(authHeader ? { Authorization: authHeader } : {}),
      },
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      return NextResponse.json(
        { error: errData.detail || 'Failed to stop automation' },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Backend unreachable' },
      { status: 500 }
    );
  }
}
