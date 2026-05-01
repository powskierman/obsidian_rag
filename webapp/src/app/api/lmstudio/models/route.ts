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

const toServerRoot = (baseUrl: string): string => baseUrl.replace(/\/v1$/i, '');

const getApiKey = (): string =>
  (process.env.QUERY_LMSTUDIO_API_KEY
    || process.env.LMSTUDIO_API_KEY
    || process.env.MLX_API_KEY
    || 'lmstudio').trim();

const unique = (values: string[]): string[] => [...new Set(values.filter(Boolean))];

const readModelId = (model: { id?: unknown; name?: unknown; path?: unknown }): string =>
  String(model?.id || model?.name || model?.path || '').trim();

export async function GET() {
  const bases = buildBaseCandidates();
  const errors: string[] = [];
  const apiKey = getApiKey();

  for (const base of bases) {
    try {
      const serverRoot = toServerRoot(base);
      const nativeResponse = await fetch(`${serverRoot}/api/v0/models`, {
        cache: 'no-store',
        headers: {
          Authorization: `Bearer ${apiKey}`,
        },
        signal: AbortSignal.timeout(1500),
      });

      if (nativeResponse.ok) {
        const data = await nativeResponse.json();
        const models = Array.isArray(data?.data) ? data.data : [];
        const installedModels = models
          .filter((model: { type?: unknown }) => String(model?.type || '').trim().toLowerCase() !== 'embeddings')
          .map(readModelId);
        const loadedModels = models
          .filter((model: { state?: unknown; type?: unknown }) => {
            const state = String(model?.state || '').trim().toLowerCase();
            const type = String(model?.type || '').trim().toLowerCase();
            return type !== 'embeddings' && (state === 'loaded' || state === 'loading');
          })
          .map(readModelId);

        return NextResponse.json({
          models: unique(loadedModels),
          installedModels: unique(installedModels),
          base,
          reachable: true,
          source: 'lmstudio',
          warning: loadedModels.length === 0 && installedModels.length > 0
            ? 'LM Studio is reachable, but no models are currently loaded.'
            : null,
        });
      }

      errors.push(`${base}/api/v0/models: HTTP ${nativeResponse.status}`);

      const openAiResponse = await fetch(`${base}/models`, {
        cache: 'no-store',
        headers: {
          Authorization: `Bearer ${apiKey}`,
        },
        signal: AbortSignal.timeout(1500),
      });

      if (!openAiResponse.ok) {
        errors.push(`${base}/models: HTTP ${openAiResponse.status}`);
        continue;
      }

      const openAiData = await openAiResponse.json();
      const openAiModels = Array.isArray(openAiData?.data) ? openAiData.data : [];
      const modelIds = unique(
        openAiModels
          .filter((model: { object?: unknown; type?: unknown }) => {
            const objectType = String(model?.object || '').trim().toLowerCase();
            const type = String(model?.type || '').trim().toLowerCase();
            return type !== 'embeddings' && objectType !== 'embedding';
          })
          .map(readModelId)
      );

      return NextResponse.json({
        models: modelIds,
        installedModels: modelIds,
        base,
        reachable: true,
        source: 'openai-compatible',
        warning: modelIds.length === 0
          ? 'Server is reachable, but /v1/models returned no chat model IDs.'
          : null,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      errors.push(`${base}: ${message}`);
    }
  }

  return NextResponse.json(
    {
      models: [],
      installedModels: [],
      base: null,
      reachable: false,
      error: errors.join(' | ') || 'Unable to reach LM Studio',
    },
    { status: 502 }
  );
}
