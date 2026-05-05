import { execFile } from 'child_process';
import path from 'path';
import { promisify } from 'util';

import { getGatewayBaseCandidates } from '../_lib/gateway';

export const dynamic = 'force-dynamic';
export const revalidate = 0;
export const runtime = 'nodejs';

const execFileAsync = promisify(execFile);

const PROJECT_ROOT = process.env.OBSIDIAN_PROJECT_ROOT ?? path.resolve(process.cwd(), '..');
const CORE_SERVICES = [
  'embedding-service',
  'lightrag-service',
  'graph-service',
  'api-gateway',
  'mcp-unified',
  'streamlit-ui',
  'webapp',
];

const HTTP_HEALTH_SERVICES: Array<{ service: string; url: string }> = [
  { service: 'embedding-service', url: 'http://embedding-service:8000/health' },
  { service: 'lightrag-service', url: 'http://lightrag-service:8001/health' },
  { service: 'graph-service', url: 'http://graph-service:8002/health' },
  { service: 'mcp-unified', url: 'http://mcp-unified:8811/health' },
];

interface ComposeServiceStatus {
  name: string;
  service: string;
  state: string;
  status: string;
  health: string;
  running: boolean;
  healthy: boolean;
}

interface ComposePsEntry {
  Name?: string;
  Service?: string;
  State?: string;
  Status?: string;
  Health?: string;
}

function parseComposeJson(stdout: string): ComposePsEntry[] {
  const text = stdout.trim();
  if (!text) return [];

  try {
    const parsed = JSON.parse(text);
    return Array.isArray(parsed) ? parsed : [parsed];
  } catch {
    return text
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .flatMap((line) => {
        try {
          const parsed = JSON.parse(line);
          return Array.isArray(parsed) ? parsed : [parsed];
        } catch {
          return [];
        }
      });
  }
}

function normalizeStatus(entry: ComposePsEntry): ComposeServiceStatus {
  const state = String(entry.State ?? 'unknown').toLowerCase();
  const status = String(entry.Status ?? '');
  const healthMatch = status.match(/\((healthy|unhealthy|starting)\)/i);
  const explicitHealth = typeof entry.Health === 'string' && entry.Health.trim() ? entry.Health : undefined;
  const health = String(explicitHealth ?? healthMatch?.[1] ?? (state === 'running' ? 'unknown' : 'offline')).toLowerCase();

  return {
    name: String(entry.Name ?? entry.Service ?? 'unknown'),
    service: String(entry.Service ?? entry.Name ?? 'unknown'),
    state,
    status,
    health,
    running: state === 'running',
    healthy: state === 'running' && (health === 'healthy' || health === 'unknown'),
  };
}

async function dockerCompose(args: string[], timeout = 15000) {
  return execFileAsync('docker', ['compose', ...args], {
    cwd: PROJECT_ROOT,
    timeout,
    maxBuffer: 1024 * 1024,
    env: process.env,
  });
}

function isDockerUnavailable(error: unknown): boolean {
  if (!error || typeof error !== 'object' || !('code' in error)) {
    return false;
  }
  return String((error as { code?: unknown }).code) === 'ENOENT';
}

async function fetchHealth(url: string, timeout = 3000): Promise<boolean> {
  try {
    const response = await fetch(url, {
      cache: 'no-store',
      signal: AbortSignal.timeout(timeout),
    });
    return response.ok;
  } catch {
    return false;
  }
}

async function getHttpStatuses(): Promise<ComposeServiceStatus[]> {
  const gatewayCandidates = getGatewayBaseCandidates().map((baseUrl) => `${baseUrl}/api/v1/health`);
  const checks = await Promise.all([
    ...HTTP_HEALTH_SERVICES.map(async ({ service, url }) => ({
      service,
      healthy: await fetchHealth(url),
    })),
    (async () => ({
      service: 'api-gateway',
      healthy: (await Promise.all(gatewayCandidates.map((url) => fetchHealth(url)))).some(Boolean),
    }))(),
  ]);
  const byService = new Map(checks.map((check) => [check.service, check.healthy]));

  return CORE_SERVICES.map((service) => {
    const hasCheck = byService.has(service);
    const healthy = byService.get(service) ?? service === 'webapp';
    return {
      name: service,
      service,
      state: hasCheck || service === 'webapp' ? (healthy ? 'running' : 'offline') : 'unknown',
      status: hasCheck
        ? (healthy ? 'HTTP health check passed' : 'HTTP health check failed')
        : service === 'webapp'
          ? 'Current webapp process is serving this request'
          : 'Docker CLI unavailable; no direct container status',
      health: hasCheck || service === 'webapp' ? (healthy ? 'healthy' : 'offline') : 'unknown',
      running: healthy,
      healthy,
    };
  });
}

async function getStatuses(): Promise<ComposeServiceStatus[]> {
  const { stdout } = await dockerCompose(['ps', '--all', '--format', 'json']);
  const entries = parseComposeJson(stdout);
  const byService = new Map(entries.map((entry) => [String(entry.Service ?? entry.Name), normalizeStatus(entry)]));
  const extraServices = entries
    .map((entry) => String(entry.Service ?? entry.Name))
    .filter((service) => service && !CORE_SERVICES.includes(service));

  return [...CORE_SERVICES, ...extraServices].map((service) => (
    byService.get(service) ?? {
      name: service,
      service,
      state: 'missing',
      status: 'No container found',
      health: 'missing',
      running: false,
      healthy: false,
    }
  ));
}

export async function GET() {
  try {
    const services = await getStatuses();
    return Response.json({
      available: true,
      canStart: true,
      mode: 'docker',
      services,
      summary: {
        total: services.length,
        running: services.filter((service) => service.running).length,
        healthy: services.filter((service) => service.healthy).length,
      },
    });
  } catch (error) {
    if (isDockerUnavailable(error)) {
      const services = await getHttpStatuses();
      return Response.json({
        available: true,
        canStart: false,
        mode: 'http-health',
        notice: 'Docker CLI is unavailable in the webapp runtime; showing service health only.',
        services,
        summary: {
          total: services.length,
          running: services.filter((service) => service.running).length,
          healthy: services.filter((service) => service.healthy).length,
        },
      });
    }
    return Response.json({
      available: false,
      error: error instanceof Error ? error.message : 'Docker Compose status failed',
      canStart: false,
      mode: 'error',
      services: [],
      summary: { total: CORE_SERVICES.length, running: 0, healthy: 0 },
    }, { status: 200 });
  }
}

export async function POST(request: Request) {
  const body = await request.json().catch(() => ({}));
  const action = String(body.action ?? 'start');
  const requestedServices = Array.isArray(body.services)
    ? body.services.map((item: unknown) => String(item)).filter(Boolean)
    : CORE_SERVICES;
  const services = requestedServices.filter((service: string) => CORE_SERVICES.includes(service));

  if (action !== 'start') {
    return Response.json({ error: `Unsupported maintenance action: ${action}` }, { status: 400 });
  }
  if (services.length === 0) {
    return Response.json({ error: 'No valid services selected' }, { status: 400 });
  }

  try {
    const { stdout, stderr } = await dockerCompose(['up', '-d', ...services], 120000);
    const statuses = await getStatuses();
    return Response.json({
      status: 'started',
      services,
      output: [...stdout.split('\n'), ...stderr.split('\n')].map((line) => line.trim()).filter(Boolean).slice(-80),
      statuses,
    });
  } catch (error) {
    if (isDockerUnavailable(error)) {
      return Response.json({
        error: 'Docker CLI is unavailable in the webapp runtime. Service start requires running the webapp on the host or providing Docker CLI/socket access to the container.',
      }, { status: 503 });
    }
    return Response.json({
      error: error instanceof Error ? error.message : 'Docker Compose start failed',
    }, { status: 500 });
  }
}
