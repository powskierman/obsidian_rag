const SERVER_GATEWAY_CANDIDATES = [
  process.env.API_GATEWAY_URL,
  process.env.GATEWAY_URL,
  'http://api-gateway:3000',
];

const FALLBACK_GATEWAY_CANDIDATES = [
  process.env.NEXT_PUBLIC_GATEWAY_URL,
  'http://host.docker.internal:4000',
  'http://127.0.0.1:4000',
  'http://localhost:4000',
];

const normalizeBaseUrl = (value: string | undefined | null): string | null => {
  const trimmed = (value || '').trim();
  if (!trimmed) {
    return null;
  }
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    return trimmed.replace(/\/+$/, '');
  }
  return `http://${trimmed.replace(/\/+$/, '')}`;
};

export const getGatewayBaseCandidates = (): string[] =>
  [
    ...new Set(
      [...SERVER_GATEWAY_CANDIDATES, ...FALLBACK_GATEWAY_CANDIDATES]
        .map(normalizeBaseUrl)
        .filter((value): value is string => Boolean(value)),
    ),
  ];

export const proxyGatewayJson = async (
  pathname: string,
  init?: RequestInit,
  timeoutMs = 15000,
): Promise<Response> => {
  const errors: string[] = [];

  const isTimeoutError = (error: unknown): boolean => {
    if (!error) {
      return false;
    }
    const message = error instanceof Error ? error.message : String(error);
    return (
      message.includes('The operation was aborted due to timeout')
      || message.includes('AbortError')
      || message.includes('timed out')
    );
  };

  for (const baseUrl of getGatewayBaseCandidates()) {
    try {
      const response = await fetch(`${baseUrl}${pathname}`, {
        ...init,
        cache: 'no-store',
        signal: AbortSignal.timeout(timeoutMs),
      });
      if (!response.ok) {
        const body = await response.text();
        errors.push(`${baseUrl}${pathname}: HTTP ${response.status} ${body}`.trim());
        continue;
      }
      return response;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      errors.push(`${baseUrl}${pathname}: ${message}`);
      if (isTimeoutError(error)) {
        break;
      }
    }
  }

  return new Response(
    JSON.stringify({
      detail: errors.join(' | ') || `Unable to reach gateway for ${pathname}`,
    }),
    {
      status: 502,
      headers: {
        'Content-Type': 'application/json',
      },
    },
  );
};
