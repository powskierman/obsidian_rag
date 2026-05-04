import { NextResponse } from 'next/server';

import { proxyGatewayJson } from '../../_lib/gateway';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const fallbackStatus = () => {
  const provider = process.env.PDF_TREE_PROVIDER || 'ollama';
  return {
    enabled: ['1', 'true', 'yes', 'on'].includes((process.env.PDF_TREE_RETRIEVAL_ENABLED || 'false').toLowerCase()),
    provider,
    configured: Boolean(process.env.PDF_TREE_MODEL || process.env.OLLAMA_MODEL || process.env.LMSTUDIO_MODEL || process.env.OPENROUTER_API_KEY),
    reachable: false,
    hosted: provider === 'openrouter',
    model: process.env.PDF_TREE_MODEL || process.env.OLLAMA_MODEL || process.env.LMSTUDIO_MODEL || process.env.OPENROUTER_MODEL || 'llama3.1:8b',
    baseUrl: process.env.OLLAMA_BASE_URL || process.env.OLLAMA_HOST || process.env.LMSTUDIO_BASE_URL || process.env.OPENROUTER_BASE_URL || '',
    models: [],
    error: 'Gateway provider status is unavailable; showing webapp environment fallback.',
  };
};

export async function GET() {
  const response = await proxyGatewayJson('/api/v1/pdf-tree/provider-status', undefined, 5000);
  if (!response.ok) {
    return NextResponse.json(fallbackStatus(), { status: 200 });
  }
  const text = await response.text();

  return new NextResponse(text, {
    status: response.status,
    headers: {
      'Content-Type': response.headers.get('content-type') || 'application/json',
    },
  });
}
