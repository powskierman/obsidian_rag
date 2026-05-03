import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';

// OBSIDIAN_PROJECT_ROOT is required when the server runs via launchd or Docker
// (stripped environment where process.cwd() may not resolve to the project root).
// Set it in .env.local: OBSIDIAN_PROJECT_ROOT=/Users/michel/dev/obsidian_rag
const PROJECT_ROOT = process.env.OBSIDIAN_PROJECT_ROOT ?? path.resolve(process.cwd(), '..');

// Prefer the project venv python so src.* imports resolve correctly
const VENV_PYTHON = (() => {
  for (const p of [
    path.join(PROJECT_ROOT, 'venv', 'bin', 'python'),
    path.join(PROJECT_ROOT, '.venv', 'bin', 'python'),
  ]) {
    if (fs.existsSync(p)) return p;
  }
  return 'python3';
})();

const MEMPALACE = path.join(process.env.HOME ?? '/root', '.local', 'bin', 'mempalace');

interface JobState {
  running: boolean;
  output: string[];
  exitCode: number | null;
  error: string | null;
  startedAt: number | null;
  databases: string[] | null;
  mode: string | null;
  options: IndexOptions | null;
}

interface IndexOptions {
  lightragIncludeExtensions?: string[];
}

const state: JobState = {
  running: false,
  output: [],
  exitCode: null,
  error: null,
  startedAt: null,
  databases: null,
  mode: null,
  options: null,
};

interface Command {
  cmd: string;
  args: string[];
  env?: Record<string, string>;
  label: string;
  kind?: 'process' | 'lightrag-api';
  payload?: Record<string, unknown>;
  url?: string;
}

const SUPPORTED_LIGHTRAG_EXTENSIONS = ['.md'];

function normalizeExtensions(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return ['.md'];
  }
  const normalized = value
    .map(item => String(item).trim().toLowerCase())
    .filter(Boolean)
    .map(item => item.startsWith('.') ? item : `.${item}`);

  return Array.from(new Set(normalized))
    .filter(ext => SUPPORTED_LIGHTRAG_EXTENSIONS.includes(ext));
}

function buildCommands(databases: string[], mode: string, options: IndexOptions = {}): Command[] {
  const full = mode === 'full';
  const vaultPath = process.env.OBSIDIAN_VAULT_PATH || `${process.env.HOME}/vault`;
  const commands: Command[] = [];

  if (databases.includes('vector')) {
    commands.push({
      cmd: VENV_PYTHON,
      args: full
        ? ['src/indexing/index_vault.py', vaultPath, '--full']
        : ['src/indexing/index_vault.py', vaultPath],
      env: { PYTHONPATH: PROJECT_ROOT },
      label: `Vector DB (${mode})`,
    });
  }

  if (databases.includes('graph')) {
    // Try Docker container first; if not running, build locally
    const containerRunning = (() => {
      try {
        const { execSync } = require('child_process');
        const out = execSync('docker ps --format "{{.Names}}"', { encoding: 'utf8', timeout: 3000 });
        return out.includes('obsidian-graph-service');
      } catch { return false; }
    })();

    if (containerRunning) {
      commands.push({
        cmd: 'docker',
        args: ['exec', '-w', '/app', 'obsidian-graph-service', 'python', '-m', 'src.services.networkx_graph_builder'],
        label: 'NetworkX Graph (docker)',
      });
    } else {
      commands.push({
        cmd: VENV_PYTHON,
        args: ['src/services/build_graph.py', '--force-refresh'],
        env: { PYTHONPATH: PROJECT_ROOT },
        label: 'NetworkX Graph (local)',
      });
    }
  }

  if (databases.includes('lightrag')) {
    const includeExtensions = normalizeExtensions(options.lightragIncludeExtensions);
    const excludeExtensions = SUPPORTED_LIGHTRAG_EXTENSIONS.filter(ext => !includeExtensions.includes(ext));
    commands.push({
      cmd: 'POST',
      args: ['/index-vault'],
      label: `LightRAG (${mode})`,
      kind: 'lightrag-api',
      url: `${process.env.LIGHTRAG_SERVICE_URL ?? 'http://lightrag-service:8001'}/index-vault`,
      payload: {
        vault_path: process.env.LIGHTRAG_VAULT_PATH ?? '/app/vault',
        force: full,
        include_extensions: includeExtensions,
        exclude_extensions: Array.from(new Set([...excludeExtensions, '.pdf'])),
        bypass_reindex_guard: false,
      },
    });
  }

  if (databases.includes('mempalace')) {
    commands.push({
      cmd: MEMPALACE,
      args: ['mine', vaultPath, '--wing', 'vault'],
      label: 'MemPalace mine',
    });
  }

  return commands;
}

function runCommands(commands: Command[]): void {
  const MAX_OUTPUT_LINES = 300;

  const push = (...lines: string[]) => {
    state.output.push(...lines);
    if (state.output.length > MAX_OUTPUT_LINES) {
      state.output = state.output.slice(-MAX_OUTPUT_LINES);
    }
  };

  const runNext = (index: number) => {
    if (index >= commands.length) {
      state.running = false;
      state.exitCode = 0;
      return;
    }

    const { cmd, args, env, label } = commands[index];
    push(`\n▶ [${index + 1}/${commands.length}] ${label}`, `  cmd: ${cmd} ${args.join(' ')}`);

    if (commands[index].kind === 'lightrag-api') {
      void runLightRagCommand(commands[index], () => runNext(index + 1), push);
      return;
    }

    let spawnError: string | null = null;

    const proc = spawn(cmd, args, {
      cwd: PROJECT_ROOT,
      env: { ...process.env, ...env },
    });

    proc.stdout.on('data', (data: Buffer) => push(...data.toString().split('\n').filter(Boolean)));
    proc.stderr.on('data', (data: Buffer) => push(...data.toString().split('\n').filter(Boolean)));

    proc.on('close', (code: number | null, signal: string | null) => {
      if (spawnError) {
        // error event already handled this — close fires after with code=-2 (ENOENT); ignore it
        return;
      }
      if (signal) {
        state.running = false;
        state.exitCode = null;
        state.error = `"${label}" killed by signal ${signal}`;
        return;
      }
      if (code !== 0) {
        state.running = false;
        state.exitCode = code;
        state.error = `"${label}" exited with code ${code}`;
        return;
      }
      push(`✓ ${label} complete`);
      runNext(index + 1);
    });

    proc.on('error', (err: Error) => {
      spawnError = err.message;
      state.running = false;
      state.error = `"${label}" failed to start: ${err.message} (cmd: ${cmd})`;
    });
  };

  runNext(0);
}

async function runLightRagCommand(
  command: Command,
  onComplete: () => void,
  push: (...lines: string[]) => void,
): Promise<void> {
  const url = command.url;
  if (!url) {
    state.running = false;
    state.exitCode = 1;
    state.error = `"${command.label}" is missing a LightRAG URL`;
    return;
  }

  push(`  url: ${url}`, `  payload: ${JSON.stringify(command.payload)}`);

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 4 * 60 * 60 * 1000);
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(command.payload ?? {}),
      signal: controller.signal,
    });
    const text = await response.text();
    let parsed: Record<string, unknown> | null = null;
    try {
      parsed = text ? JSON.parse(text) : {};
    } catch {
      parsed = null;
    }

    if (!response.ok) {
      state.running = false;
      state.exitCode = response.status;
      state.error = `"${command.label}" failed with HTTP ${response.status}`;
      push(text || state.error);
      return;
    }

    if (parsed) {
      const status = String(parsed.status ?? 'unknown');
      const newlyIndexed = parsed.newly_indexed;
      const scheduled = parsed.scheduled_for_index;
      const failed = parsed.failed_count;
      push(
        `status=${status}`,
        `scheduled_for_index=${scheduled ?? '<unknown>'}`,
        `newly_indexed=${newlyIndexed ?? '<unknown>'}`,
        `failed_count=${failed ?? '<unknown>'}`,
      );

      const failedCount = Number(failed ?? 0);
      if (failedCount > 0) {
        const failedDocs = Array.isArray(parsed.failed_docs) ? parsed.failed_docs.slice(0, 5) : [];
        for (const item of failedDocs) {
          push(`failed: ${JSON.stringify(item)}`);
        }
        state.running = false;
        state.exitCode = 1;
        state.error = `"${command.label}" finished with ${failedCount} failed document${failedCount === 1 ? '' : 's'}`;
        return;
      }
    } else if (text) {
      push(text);
    }

    push(`✓ ${command.label} complete`);
    onComplete();
  } catch (error) {
    state.running = false;
    state.exitCode = 1;
    state.error = `"${command.label}" failed: ${error instanceof Error ? error.message : 'Unknown error'}`;
  } finally {
    clearTimeout(timeout);
  }
}

const VALID_DATABASES = new Set(['vector', 'graph', 'lightrag', 'mempalace']);
const VALID_MODES = new Set(['partial', 'full']);

export async function POST(request: Request) {
  if (state.running) {
    return Response.json({ status: 'already_running' }, { status: 409 });
  }

  const body = await request.json();
  const databases: string[] = Array.isArray(body.databases)
    ? body.databases
    : [body.database ?? 'vector'];
  const mode: string = body.mode ?? 'partial';
  const options: IndexOptions = {
    lightragIncludeExtensions: normalizeExtensions(body.lightragIncludeExtensions),
  };

  const invalidDbs = databases.filter(d => !VALID_DATABASES.has(d));
  if (invalidDbs.length > 0) {
    return Response.json({ error: `Invalid database(s): ${invalidDbs.join(', ')}` }, { status: 400 });
  }
  if (!VALID_MODES.has(mode)) {
    return Response.json({ error: 'Invalid mode' }, { status: 400 });
  }
  if (databases.length === 0) {
    return Response.json({ error: 'No databases selected' }, { status: 400 });
  }
  if (databases.includes('lightrag') && (options.lightragIncludeExtensions ?? []).length === 0) {
    return Response.json({ error: 'Select at least one LightRAG content type' }, { status: 400 });
  }

  state.running = true;
  state.output = [];
  state.exitCode = null;
  state.error = null;
  state.startedAt = Date.now();
  state.databases = databases;
  state.mode = mode;
  state.options = options;

  const commands = buildCommands(databases, mode, options);
  runCommands(commands);

  return Response.json({ status: 'started', databases, mode, options });
}

export async function GET() {
  return Response.json({
    running: state.running,
    output: state.output,
    exitCode: state.exitCode,
    error: state.error,
    startedAt: state.startedAt,
    databases: state.databases,
    mode: state.mode,
    options: state.options,
  });
}

export async function DELETE() {
  state.running = false;
  state.output = [];
  state.exitCode = null;
  state.error = null;
  state.startedAt = null;
  state.databases = null;
  state.mode = null;
  state.options = null;
  return Response.json({ status: 'reset' });
}
