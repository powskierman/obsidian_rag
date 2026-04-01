#!/bin/bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/create-transfer-project.sh <target-drive-path> [project-name] [--force]

Arguments:
  <target-drive-path>   Existing destination drive or directory (example: /Volumes/work)
  [project-name]        Optional transfer project directory name
  --force               Rebuild the specific target project directory if it already exists

Example:
  scripts/create-transfer-project.sh /Volumes/work canmore-obsidian-rag-project --force
EOF
}

die() {
  echo "Error: $*" >&2
  exit 1
}

strip_wrapping_quotes() {
  local value="$1"
  if [ "${value#\"}" != "$value" ] && [ "${value%\"}" != "$value" ]; then
    value="${value#\"}"
    value="${value%\"}"
  fi
  if [ "${value#\'}" != "$value" ] && [ "${value%\'}" != "$value" ]; then
    value="${value#\'}"
    value="${value%\'}"
  fi
  printf '%s' "$value"
}

read_env_value() {
  local env_file="$1"
  local key="$2"
  [ -f "$env_file" ] || return 1

  awk -F= -v lookup_key="$key" '
    $0 ~ /^[[:space:]]*#/ { next }
    {
      raw_key=$1
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", raw_key)
      sub(/^export[[:space:]]+/, "", raw_key)
      if (raw_key == lookup_key) {
        sub(/^[^=]*=/, "", $0)
        print $0
        exit
      }
    }
  ' "$env_file"
}

directory_is_nonempty() {
  local dir="$1"
  [ -d "$dir" ] || return 1
  find "$dir" -mindepth 1 -maxdepth 1 -print -quit | grep -q .
}

resolve_abs_dir() {
  local dir="$1"
  [ -d "$dir" ] || die "Directory not found: $dir"
  (
    cd "$dir"
    pwd -P
  )
}

ensure_executable() {
  chmod 755 "$1"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
ENV_FILE="$REPO_ROOT/.env"
DEFAULT_PROJECT_NAME="obsidian-rag-transfer-project"

FORCE=0
POSITIONAL=()
for arg in "$@"; do
  case "$arg" in
    --force)
      FORCE=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      POSITIONAL+=("$arg")
      ;;
  esac
done

[ "${#POSITIONAL[@]}" -ge 1 ] || {
  usage
  exit 1
}
[ "${#POSITIONAL[@]}" -le 2 ] || die "Too many positional arguments"

TARGET_DRIVE="$(resolve_abs_dir "${POSITIONAL[0]}")"
PROJECT_NAME="${POSITIONAL[1]:-$DEFAULT_PROJECT_NAME}"
PROJECT_DIR="$TARGET_DRIVE/$PROJECT_NAME"

VAULT_SOURCE_RAW="$(read_env_value "$ENV_FILE" "OBSIDIAN_VAULT_PATH" || true)"
DATA_SOURCE_RAW="$(read_env_value "$ENV_FILE" "OBSIDIAN_RAG_DATA_DIR" || true)"

if [ -z "$VAULT_SOURCE_RAW" ] && [ -f "$REPO_ROOT/config/vault_paths.json" ]; then
  VAULT_SOURCE_RAW="$(python3 - "$REPO_ROOT/config/vault_paths.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text())
print(data.get("vault_path", ""))
PY
)"
fi

[ -n "$VAULT_SOURCE_RAW" ] || die "Could not discover OBSIDIAN_VAULT_PATH"
[ -n "$DATA_SOURCE_RAW" ] || die "Could not discover OBSIDIAN_RAG_DATA_DIR"

VAULT_SOURCE="$(resolve_abs_dir "$(strip_wrapping_quotes "$VAULT_SOURCE_RAW")")"
DATA_SOURCE="$(resolve_abs_dir "$(strip_wrapping_quotes "$DATA_SOURCE_RAW")")"
VAULT_NAME="$(basename "$VAULT_SOURCE")"

REPO_DEST="$PROJECT_DIR/repos/obsidian_rag"
VAULT_DEST="$PROJECT_DIR/vaults/$VAULT_NAME"
STATE_DEST="$PROJECT_DIR/state/obsidian-rag"
AI_CONFIG_DIR="$PROJECT_DIR/ai-config"
BUNDLE_SCRIPTS_DIR="$PROJECT_DIR/scripts"

if [ -e "$PROJECT_DIR" ] && directory_is_nonempty "$PROJECT_DIR" && [ "$FORCE" -ne 1 ]; then
  die "Target project already exists and is non-empty: $PROJECT_DIR (rerun with --force to rebuild only this project)"
fi

if [ -e "$PROJECT_DIR" ] && [ "$FORCE" -eq 1 ]; then
  rm -rf "$PROJECT_DIR"
fi

mkdir -p \
  "$PROJECT_DIR/repos" \
  "$PROJECT_DIR/vaults" \
  "$STATE_DEST" \
  "$AI_CONFIG_DIR/claude-desktop" \
  "$BUNDLE_SCRIPTS_DIR"

echo "Building transfer project:"
echo "  Repo:   $REPO_ROOT"
echo "  Vault:  $VAULT_SOURCE"
echo "  State:  $DATA_SOURCE"
echo "  Target: $PROJECT_DIR"

REPO_RSYNC_EXCLUDES=(
  --exclude ".DS_Store"
  --exclude ".pytest_cache/"
  --exclude ".ruff_cache/"
  --exclude ".coverage"
  --exclude "coverage.xml"
  --exclude "htmlcov/"
  --exclude "venv/"
  --exclude ".venv/"
  --exclude "webapp/node_modules/"
  --exclude "webapp/.next/"
  --exclude "webapp/.turbo/"
  --exclude "webapp/dist/"
  --exclude "webapp/.cache/"
  --exclude "Scripts/logs/"
  --exclude "scripts/logs/"
  --exclude "__pycache__/"
  --exclude "*.pyc"
  --exclude "*.pyo"
  --exclude "*.log"
  --exclude "scanner.log"
  --exclude "streamlit.log"
  --exclude "embedding_service.log"
  --exclude "chroma_db/"
  --exclude "lightrag_db/"
  --exclude "graph_data/"
  --exclude "feedback_db/"
  --exclude "memory_db/"
  --exclude "obsidian_rag_sync_bundle_*/"
  --exclude "obsidian_rag_sync_bundle_*.zip"
  --exclude "payload/"
  --exclude "file-list.txt"
  --exclude "sha256sums.txt"
  --exclude "debug_response.json"
  --exclude "graph_test.json"
  --exclude "query_output.json"
  --exclude "query_results.json"
  --exclude "networkx_db_verification_report.json"
  --exclude "vector_db_verification_report.json"
  --exclude "test_*.json"
)

VAULT_RSYNC_EXCLUDES=(
  --exclude ".DS_Store"
  --exclude ".trash/"
  --exclude "__pycache__/"
  --exclude "venv/"
  --exclude ".venv/"
  --exclude "*.pyc"
)

echo "Copying repo..."
rsync -a "${REPO_RSYNC_EXCLUDES[@]}" "$REPO_ROOT/" "$REPO_DEST/"

echo "Copying vault..."
rsync -a "${VAULT_RSYNC_EXCLUDES[@]}" "$VAULT_SOURCE/" "$VAULT_DEST/"

copy_state_dir() {
  local name="$1"
  local src="$DATA_SOURCE/$name"
  local dest="$STATE_DEST/$name"
  [ -d "$src" ] || return 0
  echo "Copying state directory: $name"
  rsync -a "$src/" "$dest/"
}

copy_state_file() {
  local name="$1"
  local src="$DATA_SOURCE/$name"
  local dest="$STATE_DEST/$name"
  [ -f "$src" ] || return 0
  echo "Copying state file: $name"
  mkdir -p "$(dirname "$dest")"
  cp -p "$src" "$dest"
}

copy_state_dir "chroma_db"
copy_state_dir "graph_data"
copy_state_dir "lightrag_db"
copy_state_dir "feedback_db"
copy_state_file "index_vault_cache.json"

echo "Rewriting copied repo for work-drive paths..."
python3 - "$REPO_DEST" "$VAULT_DEST" "$STATE_DEST" "$VAULT_NAME" <<'PY'
import json
import re
import sys
from pathlib import Path

repo = Path(sys.argv[1])
vault_path = Path(sys.argv[2])
state_path = Path(sys.argv[3])
vault_name = sys.argv[4]

def quote_shell(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'

env_path = repo / ".env"
if env_path.exists():
    lines = env_path.read_text().splitlines()
    replacements = {
        "OBSIDIAN_RAG_DATA_DIR": str(state_path),
        "OBSIDIAN_VAULT_PATH": str(vault_path),
        "GRAPH_PATH": str(state_path / "graph_data" / "knowledge_graph_full.pkl"),
        "CHROMA_DB_PATH": str(state_path / "chroma_db"),
        "LIGHTRAG_DIR": str(state_path / "lightrag_db"),
    }
    seen = set()
    rewritten = []
    for line in lines:
      stripped = line.strip()
      if not stripped or stripped.startswith("#") or "=" not in line:
        rewritten.append(line)
        continue
      key = line.split("=", 1)[0].strip()
      key = re.sub(r"^export\s+", "", key)
      if key in replacements:
        rewritten.append(f"{key}={quote_shell(replacements[key])}")
        seen.add(key)
      else:
        rewritten.append(line)
    for key, value in replacements.items():
      if key not in seen:
        rewritten.append(f"{key}={quote_shell(value)}")
    env_path.write_text("\n".join(rewritten) + "\n")

vault_paths_json = repo / "config" / "vault_paths.json"
if vault_paths_json.exists():
    data = json.loads(vault_paths_json.read_text())
    data["vault_path"] = str(vault_path)
    templates = data.setdefault("templates", {})
    templates["moc_template"] = str(vault_path / "Templates" / "MoC Template.md")
    templates["new_note_template"] = str(vault_path / "Templates" / "New Note Template.md")
    vault_paths_json.write_text(json.dumps(data, indent=2) + "\n")

compose_path = repo / "docker-compose.yml"
if compose_path.exists():
    text = compose_path.read_text()
    text = text.replace(
        "- ./graph_data:/app/graph_data:ro",
        '- "${OBSIDIAN_RAG_DATA_DIR}/graph_data:/app/graph_data:ro"',
    )
    text = text.replace(
        "- KNOWLEDGE_GRAPH_PATH=/app/data/graph_data/knowledge_graph_full.pkl",
        "- KNOWLEDGE_GRAPH_PATH=/app/graph_data/knowledge_graph_full.pkl",
    )
    compose_path.write_text(text)

sources_display = repo / "webapp" / "src" / "components" / "chat" / "SourcesDisplay.tsx"
if sources_display.exists():
    text = sources_display.read_text()
    text = re.sub(r"const vaultName = '.*?';", f"const vaultName = '{vault_name}';", text)
    text = re.sub(
        r"const vaultRoot = '.*?';",
        f"const vaultRoot = '{str(vault_path).replace('\\\\', '/')}' ;".replace(" ;", ";"),
        text,
    )
    sources_display.write_text(text)

vault_modal = repo / "webapp" / "src" / "components" / "VaultInfoModal.tsx"
if vault_modal.exists():
    text = vault_modal.read_text()
    text = re.sub(r">Michel<", f">{vault_name}<", text, count=1)
    text = re.sub(
        r"/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel",
        str(vault_path),
        text,
    )
    vault_modal.write_text(text)
PY

CLAUDE_CONFIG_PATH="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
CURRENT_STDIO_DEST="$AI_CONFIG_DIR/claude-desktop/obsidian-rag-unified-current-stdio.json"
python3 - "$CLAUDE_CONFIG_PATH" "$CURRENT_STDIO_DEST" <<'PY'
import json
import sys
from pathlib import Path

src = Path(sys.argv[1])
dest = Path(sys.argv[2])
if not src.exists():
    raise SystemExit(0)

config = json.loads(src.read_text())
entry = config.get("mcpServers", {}).get("obsidian-rag-unified")
if not entry:
    raise SystemExit(0)

dest.write_text(json.dumps({"mcpServers": {"obsidian-rag-unified": entry}}, indent=2) + "\n")
PY

python3 - "$AI_CONFIG_DIR" "$VAULT_DEST" "$REPO_DEST" "$VAULT_NAME" "$PROJECT_DIR" <<'PY'
import json
import sys
from pathlib import Path

ai_dir = Path(sys.argv[1])
vault_path = Path(sys.argv[2])
repo_path = Path(sys.argv[3])
vault_name = sys.argv[4]
project_dir = Path(sys.argv[5])

claude_dir = ai_dir / "claude-desktop"
claude_dir.mkdir(parents=True, exist_ok=True)

http_local = {
    "mcpServers": {
        "obsidian-rag-unified": {
            "transport": {
                "type": "http",
                "url": "http://localhost:8811/mcp"
            }
        }
    }
}

http_remote_template = {
    "mcpServers": {
        "obsidian-rag-unified": {
            "transport": {
                "type": "http",
                "url": "http://<canmore-host>:8811/mcp"
            }
        }
    }
}

stdio_template = {
    "mcpServers": {
        "obsidian-rag-unified": {
            "command": "__REPO_PATH__/venv/bin/python",
            "args": [
                "-u",
                "__REPO_PATH__/src/mcp/obsidian_rag_unified_mcp.py",
                "--transport",
                "stdio"
            ],
            "env": {
                "PYTHONPATH": "__REPO_PATH__",
                "OBSIDIAN_VAULT_PATH": "__VAULT_PATH__",
                "EMBEDDING_SERVICE_URL": "http://localhost:8000",
                "GRAPH_SERVICE_URL": "http://localhost:8002",
                "CLAUDE_GRAPH_SERVICE_URL": "http://localhost:8002",
                "LIGHTRAG_SERVICE_URL": "http://localhost:8001",
                "MCP_GATEWAY_URL": "http://localhost:4000",
                "MCP_CAPTURE_TEMPLATE_PATH": "__VAULT_PATH__/Templates/New Note Template.md",
                "OLLAMA_HOST": "http://localhost:11434",
                "LMSTUDIO_BASE_URL": "http://localhost:1234/v1",
                "MLX_BASE_URL": "http://localhost:8090/v1",
                "GPT_OSS_HOST": "http://localhost:12434/engines/llama.cpp",
                "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"
            }
        }
    }
}

(claude_dir / "obsidian-rag-unified-http-local.json").write_text(json.dumps(http_local, indent=2) + "\n")
(claude_dir / "obsidian-rag-unified-http-remote-template.json").write_text(json.dumps(http_remote_template, indent=2) + "\n")
(claude_dir / "obsidian-rag-unified-stdio.restore-template.json").write_text(json.dumps(stdio_template, indent=2) + "\n")

notes = f"""# AI Config Notes

- `claude-desktop/obsidian-rag-unified-http-local.json` uses the Docker MCP HTTP endpoint on the same Mac.
- `claude-desktop/obsidian-rag-unified-http-remote-template.json` is for another machine talking to Canmore over HTTP; replace `<canmore-host>`.
- `claude-desktop/obsidian-rag-unified-stdio.restore-template.json` matches the existing stdio pattern but assumes a recreated repo-local `venv`.
- This transfer bundle is prewired so `{project_dir}/repos/obsidian_rag` can run from the drive with its copied vault and state.
- The current Canmore Claude Desktop entry, when present, is saved as `claude-desktop/obsidian-rag-unified-current-stdio.json`.
"""
(ai_dir / "README.md").write_text(notes)
PY

cat > "$BUNDLE_SCRIPTS_DIR/restore-on-mac.sh" <<EOF
#!/bin/bash

set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/restore-on-mac.sh [--home /path/to/home] [--force] [--install-launch-agents]

Options:
  --home /path    Restore into this home directory instead of the current \$HOME
  --force         Replace the specific destination repo, vault, state, and copied ai-config paths
  --install-launch-agents
                  Run the repo's launch-agent installers after restoring
USAGE
}

die() {
  echo "Error: \$*" >&2
  exit 1
}

directory_is_nonempty() {
  local dir="\$1"
  [ -d "\$dir" ] || return 1
  find "\$dir" -mindepth 1 -maxdepth 1 -print -quit | grep -q .
}

SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd -P)"
BUNDLE_ROOT="\$(cd "\$SCRIPT_DIR/.." && pwd -P)"
PROJECT_NAME="\$(basename "\$BUNDLE_ROOT")"
VAULT_NAME="$VAULT_NAME"

DEST_HOME="\$HOME"
FORCE=0
INSTALL_LAUNCH_AGENTS=0

while [ \$# -gt 0 ]; do
  case "\$1" in
    --home)
      [ \$# -ge 2 ] || die "--home requires a path"
      DEST_HOME="\$2"
      shift 2
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --install-launch-agents)
      INSTALL_LAUNCH_AGENTS=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: \$1"
      ;;
  esac
done

DEST_HOME="\$(cd "\$DEST_HOME" && pwd -P)"
REPO_SOURCE="\$BUNDLE_ROOT/repos/obsidian_rag"
VAULT_SOURCE="\$BUNDLE_ROOT/vaults/\$VAULT_NAME"
STATE_SOURCE="\$BUNDLE_ROOT/state/obsidian-rag"
AI_CONFIG_SOURCE="\$BUNDLE_ROOT/ai-config"

DEST_REPO="\$DEST_HOME/dev/obsidian_rag"
DEST_VAULT="\$DEST_HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/\$VAULT_NAME"
DEST_STATE="\$DEST_HOME/obsidian_rag_local_data"
DEST_AI_CONFIG="\$DEST_HOME/obsidian_rag_transfer_ai_config/\$PROJECT_NAME"

for target in "\$DEST_REPO" "\$DEST_VAULT" "\$DEST_STATE" "\$DEST_AI_CONFIG"; do
  if [ -e "\$target" ] && directory_is_nonempty "\$target" && [ "\$FORCE" -ne 1 ]; then
    die "Destination exists and is non-empty: \$target (rerun with --force to replace only these restore targets)"
  fi
done

if [ "\$FORCE" -eq 1 ]; then
  rm -rf "\$DEST_REPO" "\$DEST_VAULT" "\$DEST_STATE" "\$DEST_AI_CONFIG"
fi

mkdir -p "\$(dirname "\$DEST_REPO")" "\$(dirname "\$DEST_VAULT")" "\$(dirname "\$DEST_AI_CONFIG")"

echo "Restoring repo to:  \$DEST_REPO"
rsync -a "\$REPO_SOURCE/" "\$DEST_REPO/"

echo "Restoring vault to: \$DEST_VAULT"
rsync -a "\$VAULT_SOURCE/" "\$DEST_VAULT/"

echo "Restoring state to: \$DEST_STATE"
rsync -a "\$STATE_SOURCE/" "\$DEST_STATE/"

echo "Copying ai-config to: \$DEST_AI_CONFIG"
rsync -a "\$AI_CONFIG_SOURCE/" "\$DEST_AI_CONFIG/"

python3 - "\$DEST_REPO" "\$DEST_VAULT" "\$DEST_STATE" "\$VAULT_NAME" "\$DEST_AI_CONFIG" <<'PY'
import json
import re
import sys
from pathlib import Path

repo = Path(sys.argv[1])
vault_path = Path(sys.argv[2])
state_path = Path(sys.argv[3])
vault_name = sys.argv[4]
ai_dir = Path(sys.argv[5])

def quote_shell(value: str) -> str:
    escaped = value.replace("\\\\", "\\\\\\\\").replace('"', '\\\\"')
    return f'"{escaped}"'

env_path = repo / ".env"
if env_path.exists():
    lines = env_path.read_text().splitlines()
    replacements = {
        "OBSIDIAN_RAG_DATA_DIR": str(state_path),
        "OBSIDIAN_VAULT_PATH": str(vault_path),
        "GRAPH_PATH": str(state_path / "graph_data" / "knowledge_graph_full.pkl"),
        "CHROMA_DB_PATH": str(state_path / "chroma_db"),
        "LIGHTRAG_DIR": str(state_path / "lightrag_db"),
    }
    seen = set()
    rewritten = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            rewritten.append(line)
            continue
        key = re.sub(r"^export\\s+", "", line.split("=", 1)[0].strip())
        if key in replacements:
            rewritten.append(f"{key}={quote_shell(replacements[key])}")
            seen.add(key)
        else:
            rewritten.append(line)
    for key, value in replacements.items():
        if key not in seen:
            rewritten.append(f"{key}={quote_shell(value)}")
    env_path.write_text("\\n".join(rewritten) + "\\n")

vault_paths_json = repo / "config" / "vault_paths.json"
if vault_paths_json.exists():
    data = json.loads(vault_paths_json.read_text())
    data["vault_path"] = str(vault_path)
    templates = data.setdefault("templates", {})
    templates["moc_template"] = str(vault_path / "Templates" / "MoC Template.md")
    templates["new_note_template"] = str(vault_path / "Templates" / "New Note Template.md")
    vault_paths_json.write_text(json.dumps(data, indent=2) + "\\n")

compose_path = repo / "docker-compose.yml"
if compose_path.exists():
    text = compose_path.read_text()
    text = text.replace("- ./graph_data:/app/graph_data:ro", '- "\${OBSIDIAN_RAG_DATA_DIR}/graph_data:/app/graph_data:ro"')
    text = text.replace("- KNOWLEDGE_GRAPH_PATH=/app/data/graph_data/knowledge_graph_full.pkl", "- KNOWLEDGE_GRAPH_PATH=/app/graph_data/knowledge_graph_full.pkl")
    compose_path.write_text(text)

sources_display = repo / "webapp" / "src" / "components" / "chat" / "SourcesDisplay.tsx"
if sources_display.exists():
    text = sources_display.read_text()
    text = re.sub(r"const vaultName = '.*?';", f"const vaultName = '{vault_name}';", text)
    text = re.sub(r"const vaultRoot = '.*?';", f"const vaultRoot = '{str(vault_path).replace('\\\\\\\\', '/')}' ;".replace(" ;", ";"), text)
    sources_display.write_text(text)

vault_modal = repo / "webapp" / "src" / "components" / "VaultInfoModal.tsx"
if vault_modal.exists():
    text = vault_modal.read_text()
    text = re.sub(r"/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel", str(vault_path), text)
    vault_modal.write_text(text)

template_path = ai_dir / "claude-desktop" / "obsidian-rag-unified-stdio.restore-template.json"
if template_path.exists():
    rendered = json.loads(template_path.read_text())
    text = json.dumps(rendered)
    text = text.replace("__REPO_PATH__", str(repo))
    text = text.replace("__VAULT_PATH__", str(vault_path))
    (ai_dir / "claude-desktop" / "obsidian-rag-unified-stdio-restored.json").write_text(
        json.dumps(json.loads(text), indent=2) + "\\n"
    )
PY

chmod 755 "\$DEST_REPO/scripts/setup/start_obsidian_rag.sh" \\
  "\$DEST_REPO/scripts/setup/stop_obsidian_rag.sh" \\
  "\$DEST_REPO/scripts/setup/install_launch_agent.sh" \\
  "\$DEST_REPO/scripts/setup/install_recovery_launch_agent.sh" \\
  "\$DEST_REPO/scripts/setup/recover_api_gateway_and_mlx.sh" \\
  "\$DEST_REPO/start_mlx.sh" 2>/dev/null || true

if [ "\$INSTALL_LAUNCH_AGENTS" -eq 1 ]; then
  "\$DEST_REPO/scripts/setup/install_launch_agent.sh"
  "\$DEST_REPO/scripts/setup/install_recovery_launch_agent.sh"
fi

echo "Restore complete."
echo "  Repo:     \$DEST_REPO"
echo "  Vault:    \$DEST_VAULT"
echo "  State:    \$DEST_STATE"
echo "  AI config \$DEST_AI_CONFIG"
EOF

cat > "$BUNDLE_SCRIPTS_DIR/create-transfer-zip.sh" <<'EOF'
#!/bin/bash

set -euo pipefail

die() {
  echo "Error: $*" >&2
  exit 1
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd -P)"
PROJECT_NAME="$(basename "$PROJECT_DIR")"
DEFAULT_ZIP_PATH="$(cd "$PROJECT_DIR/.." && pwd -P)/${PROJECT_NAME}.zip"
OUTPUT_PATH="${1:-$DEFAULT_ZIP_PATH}"

case "$OUTPUT_PATH" in
  /*) ;;
  *) OUTPUT_PATH="$(cd "$(pwd)" && pwd -P)/$OUTPUT_PATH" ;;
esac

PROJECT_PREFIX="${PROJECT_DIR%/}/"
case "$OUTPUT_PATH" in
  "$PROJECT_PREFIX"*) die "Refusing to write the zip inside the transfer project: $OUTPUT_PATH" ;;
  "$PROJECT_DIR") die "Refusing to overwrite the transfer project directory with a zip" ;;
esac

mkdir -p "$(dirname "$OUTPUT_PATH")"
rm -f "$OUTPUT_PATH"

/usr/bin/ditto -c -k --keepParent --norsrc "$PROJECT_DIR" "$OUTPUT_PATH"

echo "Created zip archive:"
echo "  $OUTPUT_PATH"
EOF

ensure_executable "$BUNDLE_SCRIPTS_DIR/restore-on-mac.sh"
ensure_executable "$BUNDLE_SCRIPTS_DIR/create-transfer-zip.sh"

cat > "$PROJECT_DIR/README.md" <<EOF
# Canmore Obsidian RAG Transfer Project

This transfer project captures the live Canmore-side \`obsidian_rag\` setup that is currently running from:

- Repo: \`$REPO_ROOT\`
- Vault: \`$VAULT_SOURCE\`
- State: \`$DATA_SOURCE\`

## Included

- \`repos/obsidian_rag\`
  A working copy of the live development repo, including dotfiles and git metadata, but excluding rebuildable bulk such as local virtualenvs, node modules, logs, repo-local databases, caches, and old sync bundles.
- \`vaults/$VAULT_NAME\`
  The active Obsidian vault used by the running services. The vault structure is preserved.
- \`state/obsidian-rag\`
  The active external runtime state used by the live Docker stack:
  - \`chroma_db/\`
  - \`graph_data/\`
  - \`lightrag_db/\`
  - \`feedback_db/\`
  - \`index_vault_cache.json\`
- \`ai-config/\`
  Minimal MCP/Claude Desktop snippets for the current workflow, including HTTP transport config that does not depend on a repo-local Python virtualenv.
- \`scripts/restore-on-mac.sh\`
  Restores the repo, vault, state, and ai-config into a destination Mac home.
- \`scripts/create-transfer-zip.sh\`
  Creates a zip archive of this transfer project next to the project directory.
- \`manifest.txt\`
  Source-to-destination inventory plus major exclusions and caveats.

## Intentionally Excluded

- Local virtualenvs: \`venv/\`, \`.venv/\`, vault \`venv/\`
- Frontend build/runtime bulk: \`webapp/node_modules/\`, \`webapp/.next/\`, \`webapp/.turbo/\`, \`webapp/dist/\`
- Logs and transient output: \`*.log\`, \`scripts/logs/\`, \`Scripts/logs/\`, coverage output, cache directories, \`__pycache__/\`
- Repo-local duplicate databases: \`chroma_db/\`, \`graph_data/\`, \`lightrag_db/\`, \`feedback_db/\`, \`memory_db/\`
- Archived or backup state under \`$DATA_SOURCE\`: \`backups_*\`, \`chroma_db_*\`, \`graph_data_*\`, old indexing logs
- Old sync bundle artifacts such as \`obsidian_rag_sync_bundle_*\` and \`payload/\`

## Work-Drive Operation

This bundle is prewired so the copy under \`$PROJECT_DIR\` can run directly from the drive:

- \`repos/obsidian_rag/.env\` was rewritten to point at:
  - vault: \`$VAULT_DEST\`
  - data: \`$STATE_DEST\`
- \`repos/obsidian_rag/config/vault_paths.json\` was rewritten to the bundled vault path.
- \`repos/obsidian_rag/docker-compose.yml\` was adjusted so the MCP container reads the bundled graph state from \`state/obsidian-rag/graph_data\` instead of depending on a repo-local graph copy.
- Webapp source files that display or open the vault path were rewritten to the bundled vault path.

Typical local startup from the drive:

\`\`\`bash
cd "$REPO_DEST"
./scripts/setup/start_obsidian_rag.sh
\`\`\`

## Restore On Another Mac

Default restore target paths are:

- repo: \`<home>/dev/obsidian_rag\`
- vault: \`<home>/Library/Mobile Documents/iCloud~md~obsidian/Documents/$VAULT_NAME\`
- state: \`<home>/obsidian_rag_local_data\`
- ai-config copy: \`<home>/obsidian_rag_transfer_ai_config/$PROJECT_NAME\`

Run:

\`\`\`bash
cd "$PROJECT_DIR"
./scripts/restore-on-mac.sh
\`\`\`

Optional flags:

- \`--home /path/to/home\`
- \`--force\`
- \`--install-launch-agents\`

If you use \`--install-launch-agents\`, the restored repo's launch-agent installers are run so future login startups point at the restored repo instead of the stale Canmore iCloud mirror that was still present in existing LaunchAgents.

## Create A Zip

From inside this project:

\`\`\`bash
./scripts/create-transfer-zip.sh
\`\`\`

Default output:

- \`$(cd "$PROJECT_DIR/.." && pwd -P)/${PROJECT_NAME}.zip\`

## Operational Caveats

- Docker Desktop and the usual container prerequisites still need to exist on the destination Mac.
- The repo-local Python virtualenv was not copied. Use the included HTTP MCP config snippets under \`ai-config/claude-desktop/\` for the cleanest portable workflow, or recreate a repo-local \`venv\` if you want the prior stdio MCP pattern.
- \`start_mlx.sh\` still depends on an installed or otherwise reachable MLX runtime (\`mlx_lm.server\` or a compatible MLX Python environment). That machine-specific runtime was not bundled.
- The active vault itself lives entirely under \`vaults/$VAULT_NAME\`; the sibling \`/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Media\` directory was inspected and is empty on Canmore, so it was not copied.
EOF

cat > "$PROJECT_DIR/manifest.txt" <<EOF
Transfer Project: $PROJECT_DIR
Built From Repo:  $REPO_ROOT
Built On:         $(date '+%Y-%m-%d %H:%M:%S %Z')

[Copied]
$REPO_ROOT
  -> $REPO_DEST
  Notes: working tree copy of the live dev repo used by the running Docker containers; includes git metadata; copied with rebuildable bulk excluded.

$VAULT_SOURCE
  -> $VAULT_DEST
  Notes: active Obsidian vault used by the live Canmore stack; copied with vault trash, local venvs, and trivial cache junk excluded.

$DATA_SOURCE/chroma_db
  -> $STATE_DEST/chroma_db
  Notes: active Chroma vector index.

$DATA_SOURCE/graph_data
  -> $STATE_DEST/graph_data
  Notes: active NetworkX graph state.

$DATA_SOURCE/lightrag_db
  -> $STATE_DEST/lightrag_db
  Notes: active LightRAG state, indexed file tracking, entity/relation stores, and job state.

$DATA_SOURCE/feedback_db
  -> $STATE_DEST/feedback_db
  Notes: query feedback database used by the repo.

$DATA_SOURCE/index_vault_cache.json
  -> $STATE_DEST/index_vault_cache.json
  Notes: indexing cache/state carried over for practicality.

$AI_CONFIG_DIR/claude-desktop/obsidian-rag-unified-http-local.json
$AI_CONFIG_DIR/claude-desktop/obsidian-rag-unified-http-remote-template.json
$AI_CONFIG_DIR/claude-desktop/obsidian-rag-unified-stdio.restore-template.json
$CURRENT_STDIO_DEST
  Notes: minimal MCP/Claude Desktop configuration artifacts relevant to the Canmore workflow.

$BUNDLE_SCRIPTS_DIR/restore-on-mac.sh
$BUNDLE_SCRIPTS_DIR/create-transfer-zip.sh
$PROJECT_DIR/README.md
$PROJECT_DIR/manifest.txt
  Notes: generated helper and documentation files.

[Bundle-Specific Rewrites]
$REPO_DEST/.env
  Rewritten to use:
  - OBSIDIAN_RAG_DATA_DIR=$STATE_DEST
  - OBSIDIAN_VAULT_PATH=$VAULT_DEST
  - GRAPH_PATH=$STATE_DEST/graph_data/knowledge_graph_full.pkl
  - CHROMA_DB_PATH=$STATE_DEST/chroma_db
  - LIGHTRAG_DIR=$STATE_DEST/lightrag_db

$REPO_DEST/config/vault_paths.json
  Rewritten to point at $VAULT_DEST

$REPO_DEST/docker-compose.yml
  Rewritten so mcp-unified reads graph state from \${OBSIDIAN_RAG_DATA_DIR}/graph_data and uses /app/graph_data/knowledge_graph_full.pkl

$REPO_DEST/webapp/src/components/chat/SourcesDisplay.tsx
$REPO_DEST/webapp/src/components/VaultInfoModal.tsx
  Rewritten so displayed/opened vault paths match the bundled vault.

[Important Autonomy Notes]
- The live Docker containers were verified to mount source code from $REPO_ROOT, not the stale iCloud mirror repo.
- Existing LaunchAgents on Canmore still referenced /Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag; this bundle does not preserve those stale paths.
- This project is intended to operate directly from $PROJECT_DIR and restore cleanly to <home>/dev/obsidian_rag on another Mac.

[Major Exclusions]
- $REPO_ROOT/venv
- $REPO_ROOT/.venv
- $REPO_ROOT/webapp/node_modules
- $REPO_ROOT/webapp/.next
- $REPO_ROOT/Scripts/logs
- $REPO_ROOT/scripts/logs
- $REPO_ROOT/chroma_db
- $REPO_ROOT/graph_data
- $REPO_ROOT/lightrag_db
- $REPO_ROOT/feedback_db
- $REPO_ROOT/memory_db
- $REPO_ROOT/obsidian_rag_sync_bundle_*
- $REPO_ROOT/payload
  Why: duplicate, rebuildable, or transient local repo artifacts.

- $VAULT_SOURCE/.trash
- $VAULT_SOURCE/venv
  Why: trash and unrelated local virtualenv content, not required for vault function.

- $DATA_SOURCE/backups_*
- $DATA_SOURCE/chroma_db_*
- $DATA_SOURCE/graph_data_*
- $DATA_SOURCE/*.log
  Why: archived/backup state or logs, not required for the active working environment.

[Machine-Specific Constraints]
- Repo-local stdio MCP requires a recreated venv if you want the same Claude Desktop pattern as current Canmore.
- MLX runtime is not bundled; start_mlx.sh still depends on a reachable MLX installation or environment on the destination Mac.
- Docker Desktop remains an external prerequisite.
EOF

echo "Transfer project created:"
echo "  $PROJECT_DIR"
