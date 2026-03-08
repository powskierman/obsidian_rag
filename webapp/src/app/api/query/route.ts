import { NextResponse } from 'next/server';

import { proxyGatewayJson } from '../_lib/gateway';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export async function POST(request: Request) {
  const body = await request.text();
  const response = await proxyGatewayJson(
    '/api/v1/query',
    {
      method: 'POST',
      headers: {
        'Content-Type': request.headers.get('content-type') || 'application/json',
      },
      body,
    },
    60000,
  );
  const text = await response.text();

  return new NextResponse(text, {
    status: response.status,
    headers: {
      'Content-Type': response.headers.get('content-type') || 'application/json',
    },
  });
}
