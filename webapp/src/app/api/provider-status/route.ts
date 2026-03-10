import { NextResponse } from 'next/server';

import { proxyGatewayJson } from '../_lib/gateway';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export async function GET() {
  const response = await proxyGatewayJson('/api/v1/provider-status');
  const text = await response.text();

  return new NextResponse(text, {
    status: response.status,
    headers: {
      'Content-Type': response.headers.get('content-type') || 'application/json',
    },
  });
}
