import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

function getBackendUrl(): string {
  const envUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
  if (!envUrl || envUrl.startsWith('/')) return 'http://localhost:8000';
  return envUrl.replace(/\/$/, '');
}

export async function POST(req: NextRequest) {
  const authHeader = req.headers.get('authorization');
  try {
    const resp = await fetch(`${getBackendUrl()}/discover-companies/cancel`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'ngrok-skip-browser-warning': 'true',
        ...(authHeader ? { Authorization: authHeader } : {}),
      },
    });

    const data = await resp.json().catch(() => ({ success: true }));
    return NextResponse.json(data, { status: resp.status });
  } catch (err: any) {
    return NextResponse.json({ success: false, error: err.message }, { status: 500 });
  }
}
