#!/usr/bin/env bash

set -euo pipefail

_runtime_source="${BASH_SOURCE[0]:-$0}"
RUNTIME_SCRIPT_DIR="$(cd "$(dirname "$_runtime_source")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$RUNTIME_SCRIPT_DIR/../.." && pwd)}"
BASE_ENV_FILE="$PROJECT_ROOT/.env"
PROFILE_DIR="$PROJECT_ROOT/config/profiles"
RUNTIME_ENV_FILE="${RUNTIME_ENV_FILE:-$PROJECT_ROOT/.env.runtime}"

load_env_file() {
  local env_file="$1"
  local line key value

  [ -f "$env_file" ] || return 0

  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ''|'#'*) continue ;;
    esac

    key="${line%%=*}"
    value="${line#*=}"
    key="${key#export }"

    if [ "${value#\"}" != "$value" ] && [ "${value%\"}" != "$value" ]; then
      value="${value#\"}"
      value="${value%\"}"
    elif [ "${value#\'}" != "$value" ] && [ "${value%\'}" != "$value" ]; then
      value="${value#\'}"
      value="${value%\'}"
    fi

    if [ -z "$key" ] || [ "$key" = "$line" ]; then
      continue
    fi

    export "$key=$value"
  done < "$env_file"
}

resolve_runtime_profile() {
  printf '%s' "${OBSIDIAN_RAG_PROFILE:-canmore}"
}

profile_env_file() {
  local profile="$1"
  printf '%s/config/profiles/%s.env' "$PROJECT_ROOT" "$profile"
}

prepare_runtime_env() {
  local requested_profile="${OBSIDIAN_RAG_PROFILE:-}"
  local profile="${1:-}"
  local profile_file

  load_env_file "$BASE_ENV_FILE"
  if [ -n "$requested_profile" ]; then
    export OBSIDIAN_RAG_PROFILE="$requested_profile"
  fi
  if [ -n "$profile" ]; then
    export OBSIDIAN_RAG_PROFILE="$profile"
  fi

  profile="${OBSIDIAN_RAG_PROFILE:-canmore}"
  profile_file="$(profile_env_file "$profile")"
  if [ ! -f "$profile_file" ]; then
    echo "❌ Unknown runtime profile: $profile ($profile_file)" >&2
    return 1
  fi

  export OBSIDIAN_RAG_PROFILE="$profile"
  load_env_file "$profile_file"

  {
    printf 'OBSIDIAN_RAG_PROFILE=%s\n' "$profile"
    [ -f "$BASE_ENV_FILE" ] && cat "$BASE_ENV_FILE"
    printf '\n# Profile overlay\n'
    cat "$profile_file"
  } > "$RUNTIME_ENV_FILE"

  export RUNTIME_ENV_FILE
}

compose() {
  local profile="${1:-}"
  prepare_runtime_env "$profile" >/dev/null
  if docker compose version >/dev/null 2>&1; then
    docker compose --env-file "$RUNTIME_ENV_FILE" "${@:2}"
  else
    docker-compose --env-file "$RUNTIME_ENV_FILE" "${@:2}"
  fi
}

canonical_provider_name() {
  local provider="${1:-${LLM_PROVIDER:-${DEFAULT_LLM_PROVIDER:-${CASCADING_LLM_PROVIDER:-openrouter}}}}"
  provider="$(printf '%s' "$provider" | tr '[:upper:]' '[:lower:]')"
  case "$provider" in
    mlx|lmstudio) printf 'lmstudio' ;;
    anthropic) printf 'claude' ;;
    google) printf 'gemini' ;;
    openai) printf 'chatgpt' ;;
    '') printf 'openrouter' ;;
    *) printf '%s' "$provider" ;;
  esac
}

provider_needs_ollama() {
  local provider
  provider="$(canonical_provider_name "${1:-}")"
  [ "$provider" = "ollama" ]
}
