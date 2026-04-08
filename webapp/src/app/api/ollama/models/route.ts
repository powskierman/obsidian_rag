import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

interface HostConfig {
  url: string;
  label: string;
}

interface ModelEntry {
  name: string;
  label: string;   // display name shown in selector: "qwen3:30b (MacBook)"
  host: string;    // which host serves this model
}

const normalizeHost = (value: string | undefined | null): string | null => {
  const trimmed = (value || '').trim().replace(/[`;'"]+$/g, '');
  if (!trimmed) return null;
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    return trimmed.replace(/\/+$/, '');
  }
  return `http://${trimmed.replace(/\/+$/, '')}`;
};

function buildHostConfigs(): HostConfig[] {
  const configs: HostConfig[] = [];
  const seen = new Set<string>();

  const add = (urlRaw: string | undefined | null, label: string) => {
    const url = normalizeHost(urlRaw);
    if (!url || seen.has(url)) return;
    seen.add(url);
    configs.push({ url, label });
  };

  // Primary host (e.g. MacBook via Tailscale)
  add(process.env.OLLAMA_HOST, process.env.OLLAMA_HOST_LABEL || 'Primary');
  // Fallback host (e.g. Mac Mini local)
  add(process.env.OLLAMA_FALLBACK_HOST, process.env.OLLAMA_FALLBACK_HOST_LABEL || 'Local');
  // Legacy env var
  add(process.env.NEXT_PUBLIC_OLLAMA_URL, 'Ollama');
  // Container-internal defaults
  add('http://host.docker.internal:11434', 'Local');
  add('http://localhost:11434', 'Local');

  return configs;
}

async function fetchModelsFromHost(
  config: HostConfig,
  timeoutMs = 3000,
): Promise<ModelEntry[]> {
  const response = await fetch(`${config.url}/api/tags`, {
    cache: 'no-store',
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const data = await response.json();
  const models: Array<{ name?: unknown }> = Array.isArray(data?.models) ? data.models : [];
  return models
    .map((m) => String(m?.name || '').trim())
    .filter((name) => name && !name.toLowerCase().includes('embed'))
    .map((name) => ({
      name,
      label: `${name} (${config.label})`,
      host: config.url,
    }));
}

export async function GET() {
  const hosts = buildHostConfigs();

  // Query all hosts concurrently — don't stop at first success
  const results = await Promise.allSettled(
    hosts.map((h) => fetchModelsFromHost(h)),
  );

  // Merge: deduplicate by model name, keep first occurrence (highest-priority host wins)
  const seen = new Set<string>();
  const merged: ModelEntry[] = [];
  const errors: string[] = [];

  for (let i = 0; i < results.length; i++) {
    const result = results[i];
    if (result.status === 'fulfilled') {
      for (const entry of result.value) {
        if (!seen.has(entry.name)) {
          seen.add(entry.name);
          merged.push(entry);
        }
      }
    } else {
      errors.push(`${hosts[i].url}: ${result.reason?.message ?? String(result.reason)}`);
    }
  }

  if (merged.length === 0) {
    return NextResponse.json(
      { models: [], entries: [], error: errors.join(' | ') || 'No Ollama hosts reachable' },
      { status: 502 },
    );
  }

  return NextResponse.json({
    // Simple name list for backwards compatibility with existing selectors
    models: merged.map((e) => e.name),
    // Richer list with labels for new selector components
    entries: merged,
    hosts: hosts.map((h, i) => ({
      url: h.url,
      label: h.label,
      reachable: results[i].status === 'fulfilled',
    })),
  });
}
