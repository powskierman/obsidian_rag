#!/usr/bin/env bash
set -euo pipefail

repo_root="${1:-$(pwd)}"

if ! git -C "$repo_root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "not-a-git-repo: $repo_root" >&2
  exit 1
fi

branch="$(git -C "$repo_root" branch --show-current)"
head="$(git -C "$repo_root" rev-parse --short HEAD)"
upstream_ref="$(git -C "$repo_root" rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)"
upstream_head=""
ahead_behind="no-upstream"

if [[ -n "$upstream_ref" ]]; then
  upstream_head="$(git -C "$repo_root" rev-parse --short '@{u}')"
  ahead_behind="$(git -C "$repo_root" rev-list --left-right --count HEAD...@{u} | awk '{print "ahead=" $1 ",behind=" $2}')"
fi

if [[ -n "$(git -C "$repo_root" status --porcelain)" ]]; then
  dirty="dirty"
else
  dirty="clean"
fi

printf 'repo=%s\n' "$repo_root"
printf 'branch=%s\n' "${branch:-detached}"
printf 'head=%s\n' "$head"
if [[ -n "$upstream_ref" ]]; then
  printf 'upstream=%s\n' "$upstream_ref"
  printf 'upstream_head=%s\n' "$upstream_head"
else
  printf 'upstream=none\n'
fi
printf 'sync=%s\n' "$ahead_behind"
printf 'state=%s\n' "$dirty"

