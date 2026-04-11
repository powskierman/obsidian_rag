import { NextResponse } from 'next/server';

import { proxyGatewayJson } from '../_lib/gateway';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

type QueryRouteBody = {
  llm_provider?: string;
  mode?: string;
};

const parseTimeoutMs = (rawValue: string | undefined, fallbackMs: number): number => {
  const parsedValue = Number(rawValue);
  return Number.isFinite(parsedValue) && parsedValue > 0 ? parsedValue : fallbackMs;
};

const resolveGatewayQueryTimeoutMs = (body: QueryRouteBody): number => {
  const defaultTimeoutMs = parseTimeoutMs(process.env.GATEWAY_QUERY_TIMEOUT_MS, 60000);
  const provider = String(body.llm_provider || '').trim().toLowerCase();
  const mode = String(body.mode || '').trim().toLowerCase();
  const isRemoteProvider = provider === 'openrouter' || provider === 'chatgpt' || provider === 'gemini';

  if (mode === 'cascading' || mode === 'vault_review') {
    const cascadingTimeoutMs = parseTimeoutMs(
      process.env.GATEWAY_QUERY_TIMEOUT_MS_CASCADING,
      isRemoteProvider ? 300000 : 120000,
    );

    if (provider === 'lmstudio') {
      return parseTimeoutMs(
        process.env.GATEWAY_QUERY_TIMEOUT_MS_LMSTUDIO_CASCADING,
        Math.max(cascadingTimeoutMs, 180000),
      );
    }

    return cascadingTimeoutMs;
  }

  if (isRemoteProvider) {
    return parseTimeoutMs(
      process.env.GATEWAY_QUERY_TIMEOUT_MS_REMOTE,
      Math.max(defaultTimeoutMs, 180000),
    );
  }

  return defaultTimeoutMs;
};

export async function POST(request: Request) {
  const parsedBody = (await request.json()) as QueryRouteBody;
  const timeoutMs = resolveGatewayQueryTimeoutMs(parsedBody);
  const response = await proxyGatewayJson(
    '/api/v1/query',
    {
      method: 'POST',
      headers: {
        'Content-Type': request.headers.get('content-type') || 'application/json',
      },
      body: JSON.stringify(parsedBody),
    },
    timeoutMs,
  );
  const text = await response.text();

  return new NextResponse(text, {
    status: response.status,
    headers: {
      'Content-Type': response.headers.get('content-type') || 'application/json',
    },
  });
}
