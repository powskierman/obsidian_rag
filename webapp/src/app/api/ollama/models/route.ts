import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const DEFAULT_OLLAMA_HOSTS = [
  'http://localhost:11434',
  'http://127.0.0.1:11434',
  'http://host.docker.internal:11434',
];

const normalizeHost = (value: string | undefined | null): string | null => {
  const trimmed = (value || '').trim();
  if (!trimmed) {
    return null;
  }
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    return trimmed.replace(/\/+$/, '');
  }
  return `http://${trimmed.replace(/\/+$/, '')}`;
};

const buildHostCandidates = (): string[] => {
  const candidates = [
    normalizeHost(process.env.OLLAMA_HOST),
    normalizeHost(process.env.NEXT_PUBLIC_OLLAMA_URL),
    ...DEFAULT_OLLAMA_HOSTS,
  ].filter((value): value is string => Boolean(value));

  return [...new Set(candidates)];
};

export async function GET() {
  const hosts = buildHostCandidates();
  const errors: string[] = [];

  for (const host of hosts) {
    try {
      const response = await fetch(`${host}/api/tags`, {
        cache: 'no-store',
        signal: AbortSignal.timeout(1500),
      });
      if (!response.ok) {
        errors.push(`${host}: HTTP ${response.status}`);
        continue;
      }

      const data = await response.json();
      const models = Array.isArray(data?.models) ? data.models : [];
      const names = models
        .map((model: { name?: unknown }) => String(model?.name || '').trim())
        .filter((name: string) => name && !name.includes('embed'));

      return NextResponse.json({
        models: names,
        host,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      errors.push(`${host}: ${message}`);
    }
  }

  return NextResponse.json(
    {
      models: [],
      host: null,
      error: errors.join(' | ') || 'Unable to reach Ollama',
    },
    { status: 502 }
  );
}
