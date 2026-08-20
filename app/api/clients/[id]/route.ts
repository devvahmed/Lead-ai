import { NextRequest, NextResponse } from 'next/server';

function getBackendUrl(): string {
  const envUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
  if (!envUrl || envUrl.startsWith('/')) {
    return 'http://localhost:8000';
  }
  return envUrl.replace(/\/$/, '');
}

export async function GET(
  req: NextRequest,
  context: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await context.params;
    if (!id) {
      return NextResponse.json({ error: 'Client id is required' }, { status: 400 });
    }

    const authHeader = req.headers.get('authorization') || req.headers.get('Authorization');
    const backendUrl = `${getBackendUrl()}/api/clients/${id}`;

    const res = await fetch(backendUrl, {
      headers: {
        ...(authHeader ? { Authorization: authHeader } : {}),
      },
      cache: 'no-store',
    });

    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json({ error: data.detail || 'Client not found' }, { status: res.status });
    }

    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Failed to fetch client' },
      { status: 500 }
    );
  }
}

async function handleUpdate(
  req: NextRequest,
  context: { params: Promise<{ id: string }> },
  method: 'PATCH' | 'PUT'
) {
  try {
    const { id } = await context.params;
    if (!id) return NextResponse.json({ error: 'Client id is required' }, { status: 400 });

    const authHeader = req.headers.get('authorization') || req.headers.get('Authorization');
    const body = await req.json();
    const backendUrl = `${getBackendUrl()}/api/clients/${id}`;

    const res = await fetch(backendUrl, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(authHeader ? { Authorization: authHeader } : {}),
      },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json({ error: data.detail || 'Failed to update client' }, { status: res.status });
    }

    return NextResponse.json(data);
  } catch (err) {
    console.error(`[${method} client] Error:`, err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Failed to update client' },
      { status: 500 }
    );
  }
}

export async function PATCH(
  req: NextRequest,
  context: { params: Promise<{ id: string }> }
) {
  return handleUpdate(req, context, 'PATCH');
}

export async function PUT(
  req: NextRequest,
  context: { params: Promise<{ id: string }> }
) {
  return handleUpdate(req, context, 'PUT');
}
