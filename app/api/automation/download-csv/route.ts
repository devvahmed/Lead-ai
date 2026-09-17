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
    const backendUrl = `${getBackendUrl()}/api/automation/download-csv`;

    const res = await fetch(backendUrl, {
      headers: {
        ...(authHeader ? { Authorization: authHeader } : {}),
      },
    });

    if (!res.ok) {
      return NextResponse.json(
        { error: 'Failed to download CSV from backend' },
        { status: res.status }
      );
    }

    const csvData = await res.blob();
    const contentDisposition = res.headers.get('content-disposition') || 'attachment; filename="verified_leads_automation.csv"';

    return new NextResponse(csvData, {
      status: 200,
      headers: {
        'Content-Type': 'text/csv',
        'Content-Disposition': contentDisposition,
      },
    });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Backend unreachable' },
      { status: 500 }
    );
  }
}
