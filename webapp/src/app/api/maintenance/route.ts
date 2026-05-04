import { execFile } from 'child_process';
import path from 'path';
import { promisify } from 'util';

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
      services,
      summary: {
        total: services.length,
        running: services.filter((service) => service.running).length,
        healthy: services.filter((service) => service.healthy).length,
      },
    });
  } catch (error) {
    return Response.json({
      available: false,
      error: error instanceof Error ? error.message : 'Docker Compose status failed',
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
    return Response.json({
      error: error instanceof Error ? error.message : 'Docker Compose start failed',
    }, { status: 500 });
  }
}
