import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

const DEFAULT_LMSTUDIO_BASES = [
  'http://localhost:1234/v1',
  'http://127.0.0.1:1234/v1',
  'http://host.docker.internal:1234/v1',
];

const normalizeBaseUrl = (value: string | undefined | null): string | null => {
  const trimmed = (value || '').trim().replace(/[`;'"]+$/g, '');
  if (!trimmed) {
    return null;
  }

  const withProtocol = trimmed.startsWith('http://') || trimmed.startsWith('https://')
    ? trimmed
    : `http://${trimmed}`;
  const withoutTrailingSlash = withProtocol.replace(/\/+$/, '');

  return /\/v1$/i.test(withoutTrailingSlash)
    ? withoutTrailingSlash
    : `${withoutTrailingSlash}/v1`;
};

const buildBaseCandidates = (): string[] => {
  const candidates = [
    normalizeBaseUrl(process.env.QUERY_LMSTUDIO_BASE_URL),
    normalizeBaseUrl(process.env.LMSTUDIO_BASE_URL),
    normalizeBaseUrl(process.env.MLX_BASE_URL),
    normalizeBaseUrl(process.env.NEXT_PUBLIC_LMSTUDIO_URL),
    ...DEFAULT_LMSTUDIO_BASES,
  ].filter((value): value is string => Boolean(value));

  return [...new Set(candidates)];
};

const getApiKey = (): string =>
  (process.env.QUERY_LMSTUDIO_API_KEY
    || process.env.LMSTUDIO_API_KEY
    || process.env.MLX_API_KEY
    || 'lmstudio').trim();

export async function GET() {
  const bases = buildBaseCandidates();
  const errors: string[] = [];
  const apiKey = getApiKey();

  for (const base of bases) {
    try {
      const response = await fetch(`${base}/models`, {
        cache: 'no-store',
        headers: {
          Authorization: `Bearer ${apiKey}`,
        },
        signal: AbortSignal.timeout(1500),
      });
      if (!response.ok) {
        errors.push(`${base}: HTTP ${response.status}`);
        continue;
      }

      const data = await response.json();
      const models = Array.isArray(data?.data) ? data.data : [];
      const names = models
        .map((model: { id?: unknown; name?: unknown }) => String(model?.id || model?.name || '').trim())
        .filter((name: string) => Boolean(name));

      return NextResponse.json({
        models: [...new Set(names)],
        base,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      errors.push(`${base}: ${message}`);
    }
  }

  return NextResponse.json(
    {
      models: [],
      base: null,
      error: errors.join(' | ') || 'Unable to reach LM Studio',
    },
    { status: 502 }
  );
}
