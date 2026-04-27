import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';

const PROJECT_ROOT = path.resolve(process.cwd(), '..');

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

const MEMPALACE = path.join(process.env.HOME!, '.local', 'bin', 'mempalace');

interface JobState {
  running: boolean;
  output: string[];
  exitCode: number | null;
  error: string | null;
  startedAt: number | null;
  databases: string[] | null;
  mode: string | null;
}

const state: JobState = {
  running: false,
  output: [],
  exitCode: null,
  error: null,
  startedAt: null,
  databases: null,
  mode: null,
};

interface Command {
  cmd: string;
  args: string[];
  env?: Record<string, string>;
  label: string;
}

function buildCommands(databases: string[], mode: string): Command[] {
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
    commands.push({
      cmd: 'bash',
      args: full
        ? ['Scripts/indexing/index_with_lightrag.sh', '--force']
        : ['Scripts/indexing/index_with_lightrag.sh'],
      label: `LightRAG (${mode})`,
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
    push(`\n▶ [${index + 1}/${commands.length}] ${label}`);

    const proc = spawn(cmd, args, {
      cwd: PROJECT_ROOT,
      env: { ...process.env, ...env },
    });

    proc.stdout.on('data', (data: Buffer) => push(...data.toString().split('\n').filter(Boolean)));
    proc.stderr.on('data', (data: Buffer) => push(...data.toString().split('\n').filter(Boolean)));

    proc.on('close', (code: number | null) => {
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
      state.running = false;
      state.error = `"${label}": ${err.message}`;
    });
  };

  runNext(0);
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

  state.running = true;
  state.output = [];
  state.exitCode = null;
  state.error = null;
  state.startedAt = Date.now();
  state.databases = databases;
  state.mode = mode;

  const commands = buildCommands(databases, mode);
  runCommands(commands);

  return Response.json({ status: 'started', databases, mode });
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
  return Response.json({ status: 'reset' });
}
