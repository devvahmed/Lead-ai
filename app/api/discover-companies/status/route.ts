import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

function getBackendUrl(): string {
  const envUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
  if (!envUrl || envUrl.startsWith('/')) return 'http://localhost:8000';
  return envUrl.replace(/\/$/, '');
}

export async function GET(req: NextRequest) {
  const authHeader = req.headers.get('authorization');
  try {
    const resp = await fetch(`${getBackendUrl()}/discover-companies/status`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'ngrok-skip-browser-warning': 'true',
        ...(authHeader ? { Authorization: authHeader } : {}),
      },
      cache: 'no-store',
    });

    if (!resp.ok) {
      return NextResponse.json({ active: false, status: 'idle', companies: [] }, { status: 200 });
    }

    const data = await resp.json();
    return NextResponse.json(data, { status: 200 });
  } catch (err: any) {
    return NextResponse.json({ active: false, status: 'idle', companies: [], error: err.message }, { status: 200 });
  }
}
