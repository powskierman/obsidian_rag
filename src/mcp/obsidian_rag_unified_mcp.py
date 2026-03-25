#!/usr/bin/env python3
"""
Unified Obsidian RAG MCP Server for ChatGPT Desktop
Combines enhanced vault search with knowledge graph queries.
"""

import argparse
import asyncio
import importlib.util
import json
import logging
import os
import pickle
import re
import secrets
import sys
import time
from datetime import datetime
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, urlparse, urlunparse

import requests

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    YT_TRANSCRIPT_AVAILABLE = True
except ImportError:
    YT_TRANSCRIPT_AVAILABLE = False

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(_env_path, override=False)
except Exception:
    pass

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError as e:
    print(f"MCP import error: {e}", file=sys.stderr)
    sys.exit(1)

# Graph availability
GRAPH_AVAILABLE = NETWORKX_AVAILABLE
logger = logging.getLogger(__name__)

# Service URLs
EMBEDDING_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8000")
GRAPH_SERVICE_URL = os.getenv("CLAUDE_GRAPH_SERVICE_URL") or os.getenv("GRAPH_SERVICE_URL", "http://localhost:8002")
GATEWAY_URL = os.getenv("MCP_GATEWAY_URL") or os.getenv("API_GATEWAY_URL", "http://localhost:4000")
GATEWAY_QUERY_TIMEOUT = float(os.getenv("MCP_GATEWAY_QUERY_TIMEOUT", "120"))
DEEP_RESEARCH_TIMEOUT = float(os.getenv("MCP_DEEP_RESEARCH_TIMEOUT", "240"))
MAX_NOTE_CHARS = int(os.getenv("MCP_MAX_NOTE_CHARS", "200000"))
PDF_MAX_PAGES = int(os.getenv("MCP_PDF_MAX_PAGES", "25"))
MAX_ATTACHMENTS_PER_NOTE = int(os.getenv("MCP_MAX_ATTACHMENTS_PER_NOTE", "3"))

MODE_TOOL_SUPPORTED_MODES = {
    "vector",
    "cascading",
    "deep-research",
}
MODE_PASSTHROUGH_FIELDS = [
    "max_results",
    "llm_provider",
    "model",
    "temperature",
    "entities_mode",
    "force_mode",
    "require_llm",
    "relevance_threshold",
    "web_search",
    "llm_knowledge",
    "system_prompt",
]
CAPTURE_SUBDIR = os.getenv("MCP_CAPTURE_SUBDIR", "00_Inbox/_capture")
CAPTURE_TEMPLATE_PATH = os.getenv(
    "MCP_CAPTURE_TEMPLATE_PATH",
    "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel/Templates/New Note Template.md",
)
TAG_SCAN_MAX_FILES = int(os.getenv("MCP_TAG_SCAN_MAX_FILES", "5000"))
TAG_CACHE_TTL_SECONDS = int(os.getenv("MCP_TAG_CACHE_TTL_SECONDS", "300"))
_TAG_CACHE = {"loaded_at": 0.0, "tags": set()}

FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
INLINE_TAG_PATTERN = re.compile(r"(?:^|\s)#([a-zA-Z0-9_/-]+)")
SUMMARY_NOISE_PATTERN = re.compile(
    r"(♪|♫|\[(?:music|applause)\]|\b(music|applause|laughter|intro|outro|subscribe|lyrics?)\b)",
    flags=re.IGNORECASE,
)
MIN_MEANINGFUL_SENTENCE_CHARS = 40
MAX_SUMMARY_BULLET_CHARS = 140
MIN_SUMMARY_BULLETS = 2
MEDICAL_QUERY_KEYWORDS = {
    "medical",
    "scan",
    "pet",
    "ct",
    "mri",
    "lymphoma",
    "dlbcl",
    "cancer",
    "treatment",
    "therapy",
    "chemo",
    "radiation",
    "yescarta",
    "symptom",
    "diagnosis",
}
TIMELINE_QUERY_KEYWORDS = {
    "timeline",
    "history",
    "when",
    "date",
    "dated",
    "sequence",
    "chronology",
    "progression",
    "before",
    "after",
    "month",
    "year",
    "first",
    "latest",
}
TAG_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "do",
    "each",
    "for",
    "from",
    "if",
    "in",
    "into",
    "is",
    "it",
    "make",
    "new",
    "not",
    "of",
    "on",
    "or",
    "out",
    "that",
    "the",
    "this",
    "to",
    "with",
}


def _slugify(text: str, fallback: str = "capture") -> str:
    lowered = (text or "").strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return lowered or fallback


def _load_gemini_sdk():
    try:
        import google.generativeai as genai
        return genai
    except ImportError:
        return None


GENAI_AVAILABLE = importlib.util.find_spec("google.generativeai") is not None


def _vault_relative_path(path: Path) -> str:
    vault_root = _get_vault_root()
    if vault_root is None:
        return str(path)
    try:
        rel = path.resolve().relative_to(vault_root)
        return str(rel).replace(os.sep, "/")
    except Exception:
        return str(path)


def _get_capture_root() -> tuple[Path | None, str | None]:
    vault_root = _get_vault_root()
    if vault_root is None:
        return None, "❌ OBSIDIAN_VAULT_PATH is not set"

    capture_root = (vault_root / CAPTURE_SUBDIR).resolve()
    try:
        capture_root.relative_to(vault_root)
    except ValueError:
        return None, "❌ Capture directory must be inside OBSIDIAN_VAULT_PATH"
    return capture_root, None


def _ensure_capture_root() -> tuple[Path | None, str | None]:
    capture_root, error = _get_capture_root()
    if error:
        return None, error
    try:
        capture_root.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return None, f"❌ Failed to create capture directory: {str(e)}"
    return capture_root, None


def _is_path_within(base: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(base.resolve())
        return True
    except Exception:
        return False


def _resolve_capture_note_path(raw_path: str) -> tuple[Path | None, str | None]:
    resolved, error = _resolve_vault_path(raw_path)
    if error or resolved is None:
        return None, error
    capture_root, cap_error = _get_capture_root()
    if cap_error or capture_root is None:
        return None, cap_error
    if not _is_path_within(capture_root, resolved):
        return None, f"❌ Writes are restricted to '{CAPTURE_SUBDIR}'"
    return resolved, None


def _split_frontmatter(markdown: str) -> tuple[dict, str, bool]:
    if not markdown:
        return {}, "", False
    match = FRONTMATTER_PATTERN.match(markdown)
    if not match:
        return {}, markdown, False
    if not YAML_AVAILABLE:
        return {}, markdown[match.end():], True
    try:
        parsed = yaml.safe_load(match.group(1)) or {}
        if not isinstance(parsed, dict):
            parsed = {}
    except Exception:
        parsed = {}
    body = markdown[match.end():]
    return parsed, body, True


def _render_frontmatter(frontmatter: dict, body: str) -> str:
    if not YAML_AVAILABLE:
        return body
    dumped = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=False).strip()
    clean_body = body.lstrip("\n")
    if clean_body:
        return f"---\n{dumped}\n---\n\n{clean_body}\n"
    return f"---\n{dumped}\n---\n"


def _normalize_tag(raw_tag: str) -> str | None:
    tag = str(raw_tag or "").strip().lower()
    if not tag:
        return None
    if tag.startswith("#"):
        tag = tag[1:]
    tag = re.sub(r"\s+", "-", tag)
    tag = re.sub(r"[^a-z0-9_/-]", "", tag)
    if not tag:
        return None
    return f"#{tag}"


def _extract_tags_from_frontmatter(frontmatter: dict) -> set[str]:
    if not isinstance(frontmatter, dict):
        return set()
    raw_tags = frontmatter.get("tags")
    tags = set()
    if isinstance(raw_tags, str):
        raw_values = [item.strip() for item in raw_tags.split(",")]
    elif isinstance(raw_tags, list):
        raw_values = raw_tags
    else:
        raw_values = []
    for item in raw_values:
        normalized = _normalize_tag(str(item))
        if normalized:
            tags.add(normalized)
    return tags


def _extract_inline_tags(text: str) -> set[str]:
    found = set()
    for match in INLINE_TAG_PATTERN.findall(text or ""):
        normalized = _normalize_tag(match)
        if normalized:
            found.add(normalized)
    return found


def _collect_existing_tags() -> set[str]:
    now = time.time()
    cached_at = float(_TAG_CACHE.get("loaded_at", 0.0))
    cached_tags = _TAG_CACHE.get("tags", set())
    if now - cached_at < TAG_CACHE_TTL_SECONDS and isinstance(cached_tags, set):
        return set(cached_tags)

    vault_root = _get_vault_root()
    if vault_root is None:
        return set()

    tags: set[str] = set()
    processed = 0
    for note_path in vault_root.rglob("*.md"):
        processed += 1
        if processed > TAG_SCAN_MAX_FILES:
            break
        try:
            text = note_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        frontmatter, body, _ = _split_frontmatter(text)
        tags.update(_extract_tags_from_frontmatter(frontmatter))
        tags.update(_extract_inline_tags(body))

    tags = {tag for tag in tags if _is_valid_existing_tag(tag)}
    _TAG_CACHE["loaded_at"] = now
    _TAG_CACHE["tags"] = set(tags)
    return tags


def _score_tags_for_note(note_text: str, existing_tags: set[str], max_tags: int) -> list[str]:
    valid_existing_tags = {tag for tag in existing_tags if _is_valid_existing_tag(tag)}
    if not valid_existing_tags:
        return []

    text_lower = (note_text or "").lower()
    words = re.findall(r"[a-z0-9][a-z0-9_-]{1,}", text_lower)
    word_counts: dict[str, int] = {}
    for word in words:
        word_counts[word] = word_counts.get(word, 0) + 1

    scored: list[tuple[int, str]] = []
    for tag in sorted(valid_existing_tags):
        bare = tag.lstrip("#")
        score = 0
        if bare and bare in text_lower:
            score += 3
        for token in [p for p in re.split(r"[/_-]+", bare) if len(p) >= 2]:
            score += word_counts.get(token, 0)
        if score > 0:
            scored.append((score, bare))

    scored.sort(key=lambda item: (-item[0], len(item[1]), item[1]))
    return [item[1] for item in scored[:max(1, max_tags)]]


def _load_capture_template() -> str:
    template_path = Path(CAPTURE_TEMPLATE_PATH).expanduser()
    if template_path.exists():
        try:
            return template_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass
    return (
        "# {{title}}\n\n"
        "- Date: {{date}}\n"
        "- Source: {{source}}\n\n"
        "## Summary\n{{summary}}\n\n"
        "## Details\n{{content}}\n\n"
        "## Tags\n{{tags}}\n"
    )


def _render_capture_note(template: str, values: dict[str, str]) -> str:
    rendered = template
    replaced_any = False
    for key, value in values.items():
        token = "{{" + key + "}}"
        if token in rendered:
            rendered = rendered.replace(token, value)
            replaced_any = True

    if replaced_any:
        return rendered.rstrip() + "\n"

    return (
        f"{template.rstrip()}\n\n"
        f"# {values.get('title', 'Capture')}\n\n"
        f"- Date: {values.get('date', '')}\n"
        f"- Source: {values.get('source', 'capture')}\n\n"
        f"## Summary\n{values.get('summary', '')}\n\n"
        f"## Details\n{values.get('content', '')}\n\n"
        f"## Tags\n{values.get('tags', '')}\n"
    )


def _write_capture_note(title: str, content: str) -> tuple[Path | None, str | None]:
    capture_root, error = _ensure_capture_root()
    if error:
        return None, error

    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d_%H-%M-%S")
    slug = _slugify(title)
    candidate = capture_root / f"{timestamp}_{slug}.md"
    if candidate.exists():
        candidate = capture_root / f"{timestamp}_{slug}_{secrets.token_hex(2)}.md"

    resolved = candidate.resolve()
    if not _is_path_within(capture_root, resolved):
        return None, f"❌ Writes are restricted to '{CAPTURE_SUBDIR}'"

    try:
        resolved.write_text(content, encoding="utf-8")
    except Exception as e:
        return None, f"❌ Failed to write capture note: {str(e)}"
    return resolved, None


def _extract_text_from_html(html_text: str) -> str:
    cleaned = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", html_text or "")
    cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
    cleaned = unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _summarize_to_points(raw_text: str, max_points: int = 8) -> list[str]:
    text = re.sub(r"\s+", " ", raw_text or "").strip()
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    points = []
    for sentence in sentences:
        trimmed = sentence.strip()
        if len(trimmed) < 30:
            continue
        points.append(trimmed)
        if len(points) >= max(1, max_points):
            break
    if not points:
        points = [text[:220] + ("..." if len(text) > 220 else "")]
    return points


def _is_valid_existing_tag(tag: str) -> bool:
    normalized = _normalize_tag(tag)
    if not normalized:
        return False
    bare = normalized.lstrip("#")
    if len(bare) < 3:
        return False
    if bare.isdigit():
        return False
    if bare in TAG_STOPWORDS:
        return False
    if not re.search(r"[a-z]", bare):
        return False
    return True


def _sanitize_transcript_fragment(fragment: str) -> str:
    text = fragment or ""
    text = re.sub(r"\[[^\]]+\]", " ", text)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -")
    return text


def _looks_like_transcript_noise(text: str) -> bool:
    if not text:
        return True
    if SUMMARY_NOISE_PATTERN.search(text):
        return True

    lowered = text.lower()
    tokens = re.findall(r"[a-z0-9']+", lowered)
    if len(tokens) < 5:
        return True
    if len(tokens) >= 10:
        unique_ratio = len(set(tokens)) / float(len(tokens))
        if unique_ratio < 0.6:
            return True
    if len(tokens) >= 16:
        window = min(4, max(2, len(tokens) // 8))
        if window >= 2:
            first_chunk = " ".join(tokens[:window])
            repeats = sum(
                1
                for idx in range(0, len(tokens) - window + 1)
                if " ".join(tokens[idx:idx + window]) == first_chunk
            )
            if repeats >= 3:
                return True
    if re.search(r"\b(\w+)(?:\s+\1){3,}\b", lowered):
        return True
    return False


def _compress_summary_point(text: str, max_chars: int = 180) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    shortened = cleaned[:max_chars].rsplit(" ", 1)[0].strip()
    if not shortened:
        shortened = cleaned[:max_chars].strip()
    return shortened + "..."


def _summarize_youtube_transcript_to_points(raw_text: str, max_points: int = 8) -> list[str]:
    if not raw_text:
        return []

    fragments = re.split(r"[\r\n]+|(?<=[.!?])\s+", raw_text)
    points: list[str] = []
    seen: set[str] = set()

    for fragment in fragments:
        raw_fragment = (fragment or "").strip()
        if _looks_like_transcript_noise(raw_fragment):
            continue

        cleaned = _sanitize_transcript_fragment(raw_fragment)
        if len(cleaned) < MIN_MEANINGFUL_SENTENCE_CHARS:
            continue
        if _looks_like_transcript_noise(cleaned):
            continue
        compressed = _compress_summary_point(cleaned, max_chars=180)
        signature = re.sub(r"[^a-z0-9]+", " ", compressed.lower()).strip()
        if not signature or signature in seen:
            continue
        seen.add(signature)
        points.append(compressed)
        if len(points) >= max(1, max_points):
            break

    return points


def _normalize_for_match(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _truncate_without_ellipsis(text: str, max_chars: int) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    shortened = cleaned[:max_chars].rsplit(" ", 1)[0].strip()
    if not shortened:
        shortened = cleaned[:max_chars].strip()
    return shortened


def _looks_like_run_on_fragment(text: str) -> bool:
    tokens = re.findall(r"[a-z0-9']+", (text or "").lower())
    if len(tokens) > 24:
        return True
    comma_count = (text or "").count(",")
    if comma_count >= 3 and not re.search(r"[.!?]\s*$", text or ""):
        return True
    clause_breaks = len(re.findall(r"\b(and|then|because|so|which)\b", (text or "").lower()))
    if clause_breaks >= 4:
        return True
    return False


def _extract_json_object(text: str) -> dict | None:
    candidate = (text or "").strip()
    if not candidate:
        return None
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(candidate[start:end + 1])
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return None
    return None


def _health_status_icon(status: str) -> str:
    lowered = (status or "").strip().lower()
    if lowered in {"healthy", "ok", "up", "ready", "available"}:
        return "✅"
    if lowered in {"degraded", "warning", "warn", "partial"}:
        return "⚠️"
    if lowered in {"unhealthy", "down", "error", "failed", "offline"}:
        return "❌"
    return "ℹ️"


def _format_health_metric_value(value: object) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        if value.is_integer():
            return f"{int(value):,}"
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return None


def _humanize_health_service_name(service_key: str) -> str:
    lowered = (service_key or "").strip().lower()
    aliases = {
        "networkx": "NetworkX",
        "lightrag": "LightRAG",
        "embedding": "Embedding",
        "graph": "Graph",
    }
    base = aliases.get(lowered)
    if not base:
        base = re.sub(r"[_-]+", " ", service_key or "").strip().title() or "Service"
    if base.lower().endswith("service"):
        return base
    return f"{base} service"


def _summarize_health_payload_to_points(payload: dict, max_points: int = 8) -> list[str]:
    if not isinstance(payload, dict):
        return []

    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        return []

    points: list[str] = []

    gateway_status = data.get("gateway")
    if isinstance(gateway_status, str) and gateway_status.strip():
        cleaned_status = gateway_status.strip()
        points.append(f"Gateway: {_health_status_icon(cleaned_status)} {cleaned_status.capitalize()}")

    services = data.get("services")
    if isinstance(services, dict):
        metric_labels = [
            ("count", "items"),
            ("nodes", "nodes"),
            ("edges", "edges"),
            ("indexed_notes", "indexed notes"),
        ]
        for service_key, service_payload in services.items():
            if not isinstance(service_payload, dict):
                continue
            status_value = str(service_payload.get("status") or "unknown").strip() or "unknown"
            icon = _health_status_icon(status_value)
            metrics: list[str] = []
            for metric_key, metric_label in metric_labels:
                formatted_metric = _format_health_metric_value(service_payload.get(metric_key))
                if formatted_metric:
                    metrics.append(f"{formatted_metric} {metric_label}")
            metrics_suffix = f" ({'; '.join(metrics)})" if metrics else ""
            points.append(
                f"{_humanize_health_service_name(str(service_key))}: "
                f"{icon} {status_value.capitalize()}{metrics_suffix}"
            )

    return points[:max(1, max_points)]


def _rewrite_points_with_openai(points: list[str], max_points: int) -> tuple[list[str], str] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    model = os.getenv("MCP_YOUTUBE_SUMMARY_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    prompt = (
        "Rewrite these transcript-derived notes into concise summary bullets.\n"
        "Constraints:\n"
        "- Rewrite into plain-language tutorial steps.\n"
        "- No direct quotes.\n"
        "- No verbatim transcript fragments.\n"
        "- One idea per bullet.\n"
        f"- Return 2 to {max(2, max_points)} bullets.\n"
        "- Each bullet <= 140 chars.\n"
        "- Avoid filler, lyric, and stage-direction text.\n"
        "Also provide a 2-4 sentence synthesized details paragraph.\n\n"
        "Return strict JSON:\n"
        '{"bullets":["..."],"details":"..."}\n\n'
        "Input points:\n"
        + "\n".join([f"- {point}" for point in points])
    )

    payload = {
        "model": model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "You rewrite noisy transcripts into clean tutorial summaries."
            },
            {"role": "user", "content": prompt},
        ],
    }
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=45,
        )
        if response.status_code != 200:
            return None
        content = (
            response.json()
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        parsed = _extract_json_object(content)
        if not parsed:
            return None
        bullets = parsed.get("bullets")
        details = str(parsed.get("details") or "").strip()
        if not isinstance(bullets, list):
            return None
        clean_bullets = [str(item).strip() for item in bullets if str(item).strip()]
        if not clean_bullets:
            return None
        return clean_bullets[:max(1, max_points)], details
    except Exception:
        return None


def _rewrite_points_with_gemini(points: list[str], max_points: int) -> tuple[list[str], str] | None:
    if not GENAI_AVAILABLE:
        return None
    genai = _load_gemini_sdk()
    if genai is None:
        return None
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        return None

    model_name = os.getenv("MCP_YOUTUBE_SUMMARY_GEMINI_MODEL", os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))
    prompt = (
        "Rewrite these transcript-derived notes into concise summary bullets.\n"
        "Constraints:\n"
        "- Rewrite into plain-language tutorial steps.\n"
        "- No direct quotes.\n"
        "- No verbatim transcript fragments.\n"
        "- One idea per bullet.\n"
        f"- Return 2 to {max(2, max_points)} bullets.\n"
        "- Each bullet <= 140 chars.\n"
        "- Avoid filler, lyric, and stage-direction text.\n"
        "Also provide a 2-4 sentence synthesized details paragraph.\n\n"
        "Return strict JSON:\n"
        '{"bullets":["..."],"details":"..."}\n\n'
        "Input points:\n"
        + "\n".join([f"- {point}" for point in points])
    )

    try:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        text = str(getattr(response, "text", "") or "")
        parsed = _extract_json_object(text)
        if not parsed:
            return None
        bullets = parsed.get("bullets")
        details = str(parsed.get("details") or "").strip()
        if not isinstance(bullets, list):
            return None
        clean_bullets = [str(item).strip() for item in bullets if str(item).strip()]
        if not clean_bullets:
            return None
        return clean_bullets[:max(1, max_points)], details
    except Exception:
        return None


def _heuristic_rewrite_points(points: list[str], max_points: int) -> tuple[list[str], str]:
    rewritten: list[str] = []
    for point in points[:max(1, max_points)]:
        sentence = re.sub(r"\s+", " ", point or "").strip()
        sentence = re.sub(r'["“”]', "", sentence)
        sentence = re.sub(r"^\W+", "", sentence)
        sentence = sentence[0].upper() + sentence[1:] if sentence else sentence
        sentence = _truncate_without_ellipsis(sentence, MAX_SUMMARY_BULLET_CHARS)
        if sentence:
            rewritten.append(sentence)

    details = _synthesize_details_paragraph(rewritten)
    return rewritten, details


def _rewrite_points_abstractive(points: list[str], max_points: int) -> tuple[list[str], str]:
    llm_result = _rewrite_points_with_openai(points, max_points=max_points)
    if llm_result is None:
        llm_result = _rewrite_points_with_gemini(points, max_points=max_points)
    if llm_result is not None:
        return llm_result
    return _heuristic_rewrite_points(points, max_points=max_points)


def _is_valid_summary_bullet(bullet: str, source_points: list[str]) -> bool:
    cleaned = (bullet or "").strip()
    if not cleaned:
        return False
    if len(cleaned) > MAX_SUMMARY_BULLET_CHARS:
        return False
    if "..." in cleaned:
        return False
    if "♪" in cleaned or "♫" in cleaned:
        return False
    if _looks_like_transcript_noise(cleaned):
        return False
    if _looks_like_run_on_fragment(cleaned):
        return False

    normalized_bullet = _normalize_for_match(cleaned)
    if not normalized_bullet:
        return False
    for source in source_points:
        normalized_source = _normalize_for_match(source)
        if normalized_source and (
            normalized_bullet == normalized_source
            or normalized_bullet in normalized_source
        ):
            return False
    return True


def _quality_gate_summary_bullets(bullets: list[str], source_points: list[str], max_points: int) -> list[str]:
    kept: list[str] = []
    seen: set[str] = set()
    for bullet in bullets:
        cleaned = re.sub(r"^\s*[-*•]\s*", "", str(bullet or "")).strip()
        cleaned = _truncate_without_ellipsis(cleaned, MAX_SUMMARY_BULLET_CHARS)
        signature = _normalize_for_match(cleaned)
        if not signature or signature in seen:
            continue
        if not _is_valid_summary_bullet(cleaned, source_points=source_points):
            continue
        seen.add(signature)
        kept.append(cleaned)
        if len(kept) >= max(1, max_points):
            break
    return kept


def _synthesize_details_paragraph(bullets: list[str]) -> str:
    if not bullets:
        return ""
    use = bullets[:4]
    phrases = [re.sub(r"[.!?]\s*$", "", item).strip() for item in use if item.strip()]
    if not phrases:
        return ""

    sentences: list[str] = []
    if len(phrases) >= 1:
        sentences.append(f"The walkthrough starts by {phrases[0][0].lower() + phrases[0][1:]}.")
    if len(phrases) >= 2:
        sentences.append(f"It then explains how to {phrases[1][0].lower() + phrases[1][1:]}.")
    if len(phrases) >= 3:
        sentences.append(f"Next, it highlights {phrases[2][0].lower() + phrases[2][1:]}.")
    if len(phrases) >= 4:
        sentences.append(f"Finally, it reinforces {phrases[3][0].lower() + phrases[3][1:]}.")

    # Ensure 2-4 sentences.
    if len(sentences) < 2 and len(phrases) >= 1:
        sentences.append("These steps together provide a practical sequence to apply immediately.")
    return " ".join(sentences[:4]).strip()


def _quality_gate_details_paragraph(details: str, bullets: list[str]) -> str:
    cleaned = re.sub(r"\s+", " ", (details or "").strip())
    if not cleaned:
        return ""
    if "♪" in cleaned or "♫" in cleaned:
        return ""
    if "..." in cleaned:
        return ""

    sentences = [
        segment.strip()
        for segment in re.split(r"(?<=[.!?])\s+", cleaned)
        if segment.strip()
    ]
    if len(sentences) < 2 or len(sentences) > 4:
        return ""

    bullet_block = " ".join([f"- {bullet}" for bullet in bullets]).strip()
    if bullet_block and _normalize_for_match(cleaned) == _normalize_for_match(bullet_block):
        return ""
    return " ".join(sentences)


def _extract_youtube_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]

    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
        return video_id or None

    if host in {"youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
            return video_id
        if parsed.path.startswith("/shorts/") or parsed.path.startswith("/embed/"):
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) >= 2:
                return parts[1]
    return None


def _fetch_youtube_title(url: str) -> str:
    try:
        response = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": url, "format": "json"},
            timeout=15,
        )
        if response.status_code == 200:
            payload = response.json()
            title = payload.get("title")
            if isinstance(title, str) and title.strip():
                return title.strip()
    except Exception:
        pass
    return "YouTube Capture"


def _fetch_youtube_transcript(video_id: str) -> str:
    if not YT_TRANSCRIPT_AVAILABLE:
        raise RuntimeError("youtube_transcript_api is not installed")
    chunks: list[str] = []
    if hasattr(YouTubeTranscriptApi, "get_transcript"):
        # Backward compatibility with older youtube_transcript_api releases.
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
        for item in transcript:
            if isinstance(item, dict):
                text = str(item.get("text", "")).strip()
            else:
                text = str(getattr(item, "text", "")).strip()
            if text:
                chunks.append(text)
    else:
        # Newer releases expose an instance method `fetch`.
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=["en"])
        for item in fetched:
            if isinstance(item, dict):
                text = str(item.get("text", "")).strip()
            else:
                text = str(getattr(item, "text", "")).strip()
            if text:
                chunks.append(text)
    text = " ".join(chunks).strip()
    if not text:
        raise RuntimeError("Transcript is empty")
    return text

def _service_headers() -> dict:
    api_key = os.getenv("OBSIDIAN_RAG_API_KEY")
    if not api_key:
        return {}
    return {"X-API-Key": api_key}


def _gateway_base_url() -> str:
    return GATEWAY_URL.rstrip("/")


def _gateway_query_url() -> str:
    base = _gateway_base_url()
    if base.endswith("/api/v1"):
        return f"{base}/query"
    return f"{base}/api/v1/query"


def _gateway_deep_research_ws_url() -> str:
    parsed = urlparse(_gateway_base_url())
    scheme = "wss" if parsed.scheme in {"https", "wss"} else "ws"
    path = parsed.path.rstrip("/")
    if path.endswith("/api/v1"):
        path = path[:-7]
    ws_path = f"{path}/api/v1/deep-research"
    return urlunparse((scheme, parsed.netloc, ws_path, "", "", ""))


def _get_vault_root() -> Path | None:
    vault_root = os.getenv("OBSIDIAN_VAULT_PATH")
    if not vault_root:
        return None
    return Path(vault_root).expanduser().resolve()


def _normalize_for_matching(text: str) -> str:
    """Normalize text for fuzzy matching by removing special chars and extra spaces."""
    # Replace hyphens, underscores with spaces
    normalized = re.sub(r'[-_]+', ' ', text.lower())
    # Remove multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized.strip()


def _find_similar_files(vault_root: Path, target_name: str, search_dir: Path | None = None) -> list[str]:
    """Find files with similar names (case-insensitive, partial match)."""
    if search_dir is None:
        search_dir = vault_root

    target_lower = target_name.lower()
    target_base = Path(target_name).stem.lower()
    target_ext = Path(target_name).suffix.lower()
    target_normalized = _normalize_for_matching(target_base)
    matches = []

    try:
        # First check the immediate directory for case-insensitive matches
        if search_dir.exists() and search_dir.is_dir():
            for item in search_dir.iterdir():
                if item.is_file() and item.name.lower() == target_lower:
                    matches.append(str(item.relative_to(vault_root)))
                    return matches  # Exact match found, return immediately

        # If no exact match, do a broader search with partial matching
        search_limit = 0
        for item in search_dir.rglob("*"):
            if search_limit >= 200:  # Increased limit for better coverage
                break
            search_limit += 1

            if item.is_file():
                item_name_lower = item.name.lower()
                item_base_lower = item.stem.lower()
                item_ext_lower = item.suffix.lower()
                item_normalized = _normalize_for_matching(item_base_lower)

                # Match same extension only
                if item_ext_lower != target_ext:
                    continue

                # Scoring system for better matches
                score = 0

                # Exact normalized match (e.g., "1st PET-CT" matches "1st PET CT")
                if target_normalized == item_normalized:
                    score = 100
                # One contains the other (normalized)
                elif target_normalized in item_normalized or item_normalized in target_normalized:
                    score = 50
                # Original partial match
                elif target_base in item_base_lower or item_base_lower in target_base:
                    score = 30
                # Word overlap (split on spaces and check common words)
                else:
                    target_words = set(target_normalized.split())
                    item_words = set(item_normalized.split())
                    common_words = target_words & item_words
                    if len(common_words) >= 2:  # At least 2 words in common
                        score = 20

                if score > 0:
                    matches.append((score, str(item.relative_to(vault_root))))

                if len(matches) >= 10:  # Collect more candidates for sorting
                    break
    except Exception:
        pass

    # Sort by score (highest first) and return top 5
    matches.sort(reverse=True, key=lambda x: x[0])
    return [path for _, path in matches[:5]]


def _resolve_vault_path(raw_path: str) -> tuple[Path | None, str | None]:
    if not raw_path:
        return None, "❌ Path is required"

    vault_root = _get_vault_root()
    if vault_root is None:
        return None, "❌ OBSIDIAN_VAULT_PATH is not set"

    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = vault_root / candidate

    try:
        resolved = candidate.resolve()
    except Exception:
        return None, "❌ Invalid path"

    try:
        resolved.relative_to(vault_root)
    except ValueError:
        return None, "❌ Path is outside the vault root"

    if not resolved.exists():
        # Try to find similar files
        # If the parent directory exists, search there first; otherwise search from vault root
        search_dir = vault_root
        if candidate.parent.exists() and candidate.parent != vault_root:
            try:
                candidate.parent.relative_to(vault_root)
                search_dir = candidate.parent
            except ValueError:
                search_dir = vault_root

        similar = _find_similar_files(vault_root, candidate.name, search_dir)

        # If no matches in the specific directory, try vault-wide search
        if not similar and search_dir != vault_root:
            similar = _find_similar_files(vault_root, candidate.name, vault_root)

        error_msg = f"❌ File not found: {raw_path}"
        if similar:
            error_msg += f"\n\nDid you mean one of these?\n" + "\n".join(f"  • {s}" for s in similar)
        return None, error_msg

    return resolved, None


def _read_text_file(resolved: Path, max_chars: int) -> str:
    with open(resolved, "r", encoding="utf-8", errors="replace") as handle:
        content = handle.read(max_chars + 1)
    if len(content) > max_chars:
        content = content[:max_chars] + "\n\n[TRUNCATED]"
    return content


def _extract_pdf_text(resolved: Path, max_pages: int, max_chars: int) -> tuple[str, bool]:
    try:
        from pypdf import PdfReader
    except Exception as e:
        raise RuntimeError("pypdf is not installed in this environment") from e

    reader = PdfReader(str(resolved))
    pages_to_read = min(len(reader.pages), max_pages)
    parts = []
    total_chars = 0
    truncated = False

    for idx in range(pages_to_read):
        page_text = reader.pages[idx].extract_text() or ""
        if not page_text:
            continue
        remaining = max_chars - total_chars
        if remaining <= 0:
            truncated = True
            break
        if len(page_text) > remaining:
            parts.append(page_text[:remaining])
            truncated = True
            break
        parts.append(page_text)
        total_chars += len(page_text)

    content = "\n\n".join(parts)
    if truncated:
        content = content + "\n\n[TRUNCATED]"
    return content, truncated


def _extract_pdf_refs(note_text: str) -> list[str]:
    refs = re.findall(r"!\[\[([^\]]+)\]\]", note_text)
    cleaned = []
    for ref in refs:
        part = ref.split("|", 1)[0]
        part = part.split("#", 1)[0]
        part = part.strip()
        if part.lower().endswith(".pdf"):
            cleaned.append(part)
    return cleaned


def _resolve_attachment_path(note_path: Path, attachment_ref: str) -> tuple[Path | None, str | None]:
    vault_root = _get_vault_root()
    if vault_root is None:
        return None, "❌ OBSIDIAN_VAULT_PATH is not set"

    attachment_path = Path(attachment_ref)
    candidates = []
    if attachment_path.is_absolute():
        candidates.append(attachment_path)
    else:
        candidates.append(note_path.parent / attachment_ref)
        candidates.append(vault_root / attachment_ref)

    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve()
        except Exception:
            continue
        try:
            resolved.relative_to(vault_root)
        except ValueError:
            continue
        if resolved.exists():
            return resolved, None

    # Fallback: search vault for exact case-insensitive match
    target_name = attachment_path.name
    target_name_lower = target_name.lower()
    try:
        for root, _, files in os.walk(vault_root):
            for file in files:
                if file.lower() == target_name_lower:
                    found = Path(root) / file
                    return found.resolve(), None
    except Exception:
        pass

    # Final fallback: try fuzzy matching
    similar = _find_similar_files(vault_root, target_name, vault_root)
    error_msg = f"❌ Attachment not found: {attachment_ref}"
    if similar:
        error_msg += f"\n\nDid you mean one of these?\n" + "\n".join(f"  • {s}" for s in similar)

    return None, error_msg

# Initialize server
app = Server("obsidian-rag-unified")

class GraphQuerier:
    """Query the knowledge graph using OpenAI or Gemini for synthesis."""

    def __init__(self, graph):
        self.graph = graph
        
        self.gemini_key = os.environ.get("GEMINI_API_KEY")
        self.openai_key = os.environ.get("OPENAI_API_KEY")
        
        # 1. Check for explicit provider configuration
        preferred_provider = os.environ.get("MCP_GRAPH_PROVIDER", "").lower()
        
        if preferred_provider == "gemini":
            if not self.gemini_key:
                raise ValueError("MCP_GRAPH_PROVIDER is 'gemini' but GEMINI_API_KEY is missing.")
            if not GENAI_AVAILABLE:
                raise ValueError("MCP_GRAPH_PROVIDER is 'gemini' but google-generativeai is not installed.")
            self.provider = "gemini"
            
        elif preferred_provider == "openai":
            if not self.openai_key:
                raise ValueError("MCP_GRAPH_PROVIDER is 'openai' but OPENAI_API_KEY is missing.")
            self.provider = "openai"
            
        else:
            # 2. Auto-detect if no preference set
            if self.gemini_key and GENAI_AVAILABLE:
                self.provider = "gemini"
            elif self.openai_key:
                self.provider = "openai"
            else:
                self.provider = "none"
        
        # Configure the selected provider
        if self.provider == "gemini":
            genai = _load_gemini_sdk()
            if genai is None:
                raise ValueError("MCP_GRAPH_PROVIDER is 'gemini' but google-generativeai could not be imported.")
            genai.configure(api_key=self.gemini_key)
            self._gemini_sdk = genai
            self.model = os.environ.get("GEMINI_MODEL", "gemini-1.5-pro-latest")
        else:
            # Default to OpenAI logic (or fallback)
            self._gemini_sdk = None
            self.model = os.environ.get("OPENAI_MODEL", "gpt-4o")

        self.timeout = float(os.environ.get("OPENAI_TIMEOUT", "60"))

    def _node_label(self, node) -> str:
        if isinstance(node, str):
            return node
        if isinstance(node, tuple):
            if self.graph.has_node(node):
                props = self.graph.nodes[node]
                for key in ("title", "name", "path"):
                    value = props.get(key)
                    if isinstance(value, str) and value.strip():
                        return value
            if len(node) > 1:
                return str(node[1])
        return str(node)

    def _resolve_entity_node(self, raw_name: str):
        name = (raw_name or "").strip().strip('"\'')
        if not name:
            return None

        if self.graph.has_node(name):
            return name

        name_lower = name.lower()
        exact_matches = []
        partial_matches = []
        for node in self.graph.nodes():
            node_lower = self._node_label(node).lower()
            if node_lower == name_lower:
                exact_matches.append(node)
            elif name_lower in node_lower or node_lower in name_lower:
                partial_matches.append(node)

        matches = exact_matches or partial_matches
        if not matches:
            return None
        return max(matches, key=lambda n: self.graph.degree(n))

    def find_paths(self, source: str, target: str, max_depth: int = 3):
        s_ent = self._resolve_entity_node(source)
        t_ent = self._resolve_entity_node(target)
        if not s_ent or not t_ent:
            return []
        try:
            paths = list(nx.all_simple_paths(self.graph.to_undirected(), s_ent, t_ent, cutoff=max_depth))
            return [[self._node_label(node) for node in path] for path in paths[:10]]
        except Exception:
            return []

    def get_entity_neighborhood(self, entity: str, depth: int = 1):
        entity = (entity or "").strip().strip('"\'')
        entity_node = self._resolve_entity_node(entity)
        if entity_node is None:
            return {"entity": entity, "found": False}

        neighbors = {
            "entity": self._node_label(entity_node),
            "found": True,
            "properties": dict(self.graph.nodes[entity_node]),
            "outgoing": [],
            "incoming": []
        }

        for _, t, d in self.graph.out_edges(entity_node, data=True):
            neighbors["outgoing"].append({
                "target": self._node_label(t),
                "relationship": d.get("relationship_type") or d.get("kind") or "related_to",
                "properties": d
            })
        for s, _, d in self.graph.in_edges(entity_node, data=True):
            neighbors["incoming"].append({
                "source": self._node_label(s),
                "relationship": d.get("relationship_type") or d.get("kind") or "related_to",
                "properties": d
            })
        return neighbors

    def _extract_entities(self, user_query: str, max_entities: int = 20):
        query_lower = user_query.lower()
        entities_in_query = []
        stopwords = {
            "and", "or", "the", "a", "an", "in", "on", "with", "for", "to", "of",
            "from", "by", "is", "are", "was", "were", "be", "been", "it", "this",
            "that", "these", "those", "as", "at", "via", "etc"
        }

        def is_noise_entity(name: str) -> bool:
            name_lower = name.lower().strip()
            if len(name_lower) <= 2 or name_lower.isdigit():
                return True
            if name_lower in stopwords:
                return True
            tokens = [t for t in re.split(r"\W+", name_lower) if t]
            return bool(tokens) and all(t in stopwords for t in tokens)

        all_nodes = sorted(list(self.graph.nodes()), key=lambda n: len(self._node_label(n)), reverse=True)
        seen_entities = set()
        for node in all_nodes:
            node_label = self._node_label(node)
            node_lower = node_label.lower()
            if len(node_lower) <= 2 or is_noise_entity(node_lower):
                continue
            if re.search(r"\b" + re.escape(node_lower) + r"\b", query_lower):
                if node_label not in seen_entities:
                    entities_in_query.append(node_label)
                    seen_entities.add(node_label)
                continue
            if len(node_lower) > 3 and node_lower in query_lower:
                if node_label not in seen_entities:
                    entities_in_query.append(node_label)
                    seen_entities.add(node_label)

        return entities_in_query[:max_entities]

    def _build_context(self, user_query: str, max_entities: int = 20):
        entities_in_query = self._extract_entities(user_query, max_entities)
        graph_context = [self.get_entity_neighborhood(e) for e in entities_in_query]

        if not graph_context:
            return "I couldn't find specific entities in the knowledge graph. Relying on document search.", []

        blocks = []
        for context in graph_context:
            outgoing = ", ".join([
                f"{context['entity']} --[{r['relationship']}]--> {r['target']}"
                for r in context.get("outgoing", [])
            ])
            incoming = ", ".join([
                f"{r['source']} --[{r['relationship']}]--> {context['entity']}"
                for r in context.get("incoming", [])
            ])
            blocks.append(
                f"Entity: {context['entity']}\n"
                f"Outgoing: {outgoing}\n"
                f"Incoming: {incoming}"
            )

        context_text = "\n---\n".join(blocks)
        return context_text, graph_context

    def _call_llm(self, prompt: str):
        if self.provider == "gemini":
            try:
                if self._gemini_sdk is None:
                    raise ValueError("Gemini SDK is not available")
                model = self._gemini_sdk.GenerativeModel(self.model)
                response = model.generate_content(prompt)
                return response.text
            except Exception as e:
                 raise ValueError(f"Gemini API Error: {str(e)}")

        # Fallback to OpenAI
        if not self.openai_key:
            raise ValueError("OPENAI_API_KEY not configured and Gemini not available")

        model_lower = (self.model or "").lower()
        token_param = "max_tokens"
        restrict_temperature = False
        if model_lower.startswith(("gpt-5", "o1", "o3")):
            token_param = "max_completion_tokens"
            restrict_temperature = True

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are analyzing a personal knowledge graph. "
                        "Answer the user's question using only the provided graph context. "
                        "If the graph context is thin, say so briefly."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            token_param: 1200
        }
        if not restrict_temperature:
            payload["temperature"] = 0.4

        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        # Ensure base_url doesn't end with slash if we append path, but here we append /chat/completions
        # Handle full URL vs base URL provided
        if "/chat/completions" not in base_url:
            url = f"{base_url.rstrip('/')}/chat/completions"
        else:
            url = base_url

        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self.openai_key}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=self.timeout
        )

        if response.status_code != 200:
            raise ValueError(f"OpenAI API Error {response.status_code}: {response.text}")

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("No choices returned from OpenAI")
        message = choices[0].get("message", {})
        return message.get("content", "")

    def query_graph(self, user_query: str, max_entities: int = 20):
        context_text, graph_context = self._build_context(user_query, max_entities)
        if not graph_context:
            return context_text
        prompt = (
            f"Knowledge Graph Context:\n<graph>\n{context_text}\n</graph>\n\n"
            f"User Question: {user_query}\n"
            "Provide a concise, evidence-based answer citing specific entities when relevant."
        )
        return self._call_llm(prompt)

    # Alias for compatibility
    query_with_openai = query_graph

    def get_graph_stats(self):
        graph = self.graph
        try:
            is_connected = nx.is_connected(graph.to_undirected())
        except Exception:
            is_connected = False

        top_entities = [
            {"entity": self._node_label(node), "connections": degree}
            for node, degree in graph.degree()
        ]
        top_entities.sort(key=lambda item: item["connections"], reverse=True)

        return {
            "total_nodes": graph.number_of_nodes(),
            "total_edges": graph.number_of_edges(),
            "density": nx.density(graph),
            "is_connected": is_connected,
            "top_entities": top_entities
        }


# Global graph querier (lazy-loaded)
querier = None
graph_loaded = False

def _resolve_graph_path():
    graph_path = os.environ.get("KNOWLEDGE_GRAPH_PATH")
    if graph_path:
        return Path(graph_path)
    data_dir = os.environ.get("OBSIDIAN_RAG_DATA_DIR", "").strip()
    if data_dir:
        data_path = Path(data_dir) / "graph_data" / "knowledge_graph_full.pkl"
        if data_path.exists():
            return data_path

    script_dir = Path(__file__).parent.absolute()
    default_paths = [
        script_dir / "graph_data" / "knowledge_graph_full.pkl",
        script_dir / "graph_data" / "knowledge_graph_test.pkl",
        script_dir / "graph_data" / "knowledge_graph.pkl",
        script_dir / "knowledge_graph_full.pkl",
        script_dir / "knowledge_graph_test.pkl",
        script_dir / "knowledge_graph.pkl",
        Path("graph_data/knowledge_graph_full.pkl"),
        Path("graph_data/knowledge_graph_test.pkl"),
        Path("graph_data/knowledge_graph.pkl"),
        Path("knowledge_graph_full.pkl"),
        Path("knowledge_graph_test.pkl"),
        Path("knowledge_graph.pkl")
    ]
    for path in default_paths:
        if path.exists():
            return path.absolute()
    return None

def load_graph():
    """Load the knowledge graph"""
    global querier, graph_loaded

    if graph_loaded:
        return True

    if not GRAPH_AVAILABLE:
        return False

    try:
        graph_path = _resolve_graph_path()
        if not graph_path or not graph_path.exists():
            print("Graph file not found. Set KNOWLEDGE_GRAPH_PATH to a valid .pkl file.", file=sys.stderr)
            return False

        with open(graph_path, "rb") as handle:
            loaded = pickle.load(handle)

        # Support both raw NetworkX pickles and wrapped payloads {"graph": <NetworkX graph>, ...}
        graph = loaded.get("graph") if isinstance(loaded, dict) and "graph" in loaded else loaded

        if not isinstance(graph, nx.Graph):
            print("Graph file did not contain a valid NetworkX graph.", file=sys.stderr)
            return False

        querier = GraphQuerier(graph)
        graph_loaded = True
        return True

    except Exception as e:
        print(f"Error loading graph: {e}", file=sys.stderr)
        return False

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools"""
    
    tools = [
        # Enhanced Vault Search (unique name to distinguish from Docker toolkit)
        Tool(
            name="obsidian_semantic_search",
            description="Search your Obsidian vault using SEMANTIC SEARCH (not text search). Returns top matching notes with content snippets and relevance scores (5-10 results). This uses ChromaDB embeddings for intelligent search. Use this for finding information by meaning, not just keywords. IMPORTANT: When summarizing or referring to a note, you MUST cite it using Obsidian markdown links (e.g., [[Note Name]] or [[Folder/Note Name.md]]).",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query for your vault (e.g., 'CAR-T therapy', 'Home Assistant setup', 'ESP32 projects')"
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of results to return (1-10, default: 5)",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 10
                    },
                    "include_content": {
                        "type": "boolean",
                        "description": "Include content snippets in results (default: true)",
                        "default": True
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="search_vault_full",
            description="Search your vault and return full note text for the top results. Can also extract PDF text for embedded attachments to avoid separate calls. IMPORTANT: When summarizing or referring to a note, you MUST cite it using Obsidian markdown links (e.g., [[Note Name]] or [[Folder/Note Name.md]]).",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query for your vault"
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of notes to return (1-5, default: 3)",
                        "default": 3,
                        "minimum": 1,
                        "maximum": 5
                    },
                    "include_attachments": {
                        "type": "boolean",
                        "description": "Extract PDF text for embedded attachments (default: true)",
                        "default": True
                    },
                    "max_attachments_per_note": {
                        "type": "integer",
                        "description": "Max PDFs to extract per note (default: 3)",
                        "default": 3,
                        "minimum": 0,
                        "maximum": 10
                    },
                    "max_pdf_pages": {
                        "type": "integer",
                        "description": "Max PDF pages to extract per attachment (default: 25)",
                        "default": 25,
                        "minimum": 1,
                        "maximum": 100
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="obsidian_vault_stats",
            description="Get statistics about your vault including total documents, entities, and relationships.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="read_vault_note",
            description="Read the full text of a vault note. Provide a path relative to OBSIDIAN_VAULT_PATH.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to a note in the vault (e.g., 'Medical/Lymphoma/Scan.md')"
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="read_attachment_text",
            description="Extract text from a PDF attachment inside the vault. Provide a relative path to a .pdf.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to a PDF in the vault (e.g., 'Medical/Attachments/Scan.pdf')"
                    },
                    "max_pages": {
                        "type": "integer",
                        "description": "Max PDF pages to extract (default: 25)",
                        "default": 25,
                        "minimum": 1,
                        "maximum": 100
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="obsidian_search_mode",
            description=(
                "Run supported gateway search modes: vector, cascading, and deep-research. IMPORTANT: When summarizing or referring to a note, you MUST cite it using Obsidian markdown links (e.g., [[Note Name]] or [[Folder/Note Name.md]])."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The user question/query to run."
                    },
                    "mode": {
                        "type": "string",
                        "description": (
                            "Search mode. For deep thinking, use 'deep-research'."
                        ),
                        "enum": [
                            "vector",
                            "cascading",
                            "deep-research"
                        ],
                        "default": "cascading"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max results for non-deep-research modes (default: 10)",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    },
                    "llm_provider": {
                        "type": "string",
                        "description": "LLM provider override (for gateway modes)."
                    },
                    "provider": {
                        "type": "string",
                        "description": "Deep-research provider override (claude/gemini/openrouter/chatgpt/ollama/perplexity)."
                    },
                    "model": {
                        "type": "string",
                        "description": "Optional model override."
                    },
                    "temperature": {
                        "type": "number",
                        "description": "Optional temperature override."
                    },
                    "entities_mode": {
                        "type": "string",
                        "description": "Legacy LightRAG override. Ignored by current gateway REST modes."
                    },
                    "force_mode": {
                        "type": "boolean",
                        "description": "Legacy LightRAG override. Ignored by current gateway REST modes."
                    },
                    "require_llm": {
                        "type": "boolean",
                        "description": "Require LLM synthesis where supported."
                    },
                    "relevance_threshold": {
                        "type": "number",
                        "description": "Relevance threshold 0-100 for vector-backed retrieval."
                    },
                    "web_search": {
                        "type": "boolean",
                        "description": "Enable web search augmentation where supported."
                    },
                    "llm_knowledge": {
                        "type": "boolean",
                        "description": "Enable LLM knowledge augmentation where supported."
                    },
                    "system_prompt": {
                        "type": "string",
                        "description": "Optional custom system prompt for gateway modes."
                    }
                },
                "required": ["query", "mode"]
            }
        ),
        Tool(
            name="obsidian_unified_query",
            description="Run unified API query with optional mode override. Defaults to cascading mode. IMPORTANT: When summarizing or referring to a note, you MUST cite it using Obsidian markdown links (e.g., [[Note Name]] or [[Folder/Note Name.md]]).",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "User query."
                    },
                    "mode": {
                        "type": "string",
                        "description": "Optional mode override (default: cascading).",
                        "enum": [
                            "vector",
                            "cascading",
                            "deep-research"
                        ],
                        "default": "cascading"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max results for non-deep-research modes (default: 10).",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    },
                    "concise": {
                        "type": "boolean",
                        "description": "Return concise response text (default: true).",
                        "default": True
                    },
                    "llm_provider": {
                        "type": "string",
                        "description": "Optional LLM provider override."
                    },
                    "provider": {
                        "type": "string",
                        "description": "Optional provider alias."
                    },
                    "model": {
                        "type": "string",
                        "description": "Optional model override."
                    },
                    "temperature": {
                        "type": "number",
                        "description": "Optional temperature override."
                    },
                    "entities_mode": {
                        "type": "string",
                        "description": "Legacy LightRAG override. Ignored by current gateway REST modes."
                    },
                    "force_mode": {
                        "type": "boolean",
                        "description": "Legacy LightRAG override. Ignored by current gateway REST modes."
                    },
                    "require_llm": {
                        "type": "boolean",
                        "description": "Require LLM synthesis."
                    },
                    "relevance_threshold": {
                        "type": "number",
                        "description": "Relevance threshold 0-100."
                    },
                    "web_search": {
                        "type": "boolean",
                        "description": "Enable web search when supported."
                    },
                    "llm_knowledge": {
                        "type": "boolean",
                        "description": "Enable LLM-knowledge augmentation."
                    },
                    "system_prompt": {
                        "type": "string",
                        "description": "Optional custom system prompt."
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="capture_note",
            description=f"Create a capture note. Writes are restricted to '{CAPTURE_SUBDIR}'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Main capture content."
                    },
                    "title": {
                        "type": "string",
                        "description": "Optional note title."
                    },
                    "source": {
                        "type": "string",
                        "description": "Optional source descriptor."
                    },
                    "tags": {
                        "type": "array",
                        "description": "Optional initial tags.",
                        "items": {"type": "string"}
                    }
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="summarize_url_to_capture",
            description=f"Fetch a webpage, summarize it into points, and save to '{CAPTURE_SUBDIR}'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "HTTP(S) URL to summarize."
                    },
                    "title": {
                        "type": "string",
                        "description": "Optional capture title override."
                    },
                    "max_points": {
                        "type": "integer",
                        "description": "Maximum summary points (default: 8).",
                        "default": 8,
                        "minimum": 1,
                        "maximum": 20
                    }
                },
                "required": ["url"]
            }
        ),
        Tool(
            name="summarize_youtube_to_capture",
            description=f"Summarize a YouTube video transcript and save to '{CAPTURE_SUBDIR}'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "YouTube URL (youtube.com or youtu.be)."
                    },
                    "title": {
                        "type": "string",
                        "description": "Optional capture title override."
                    },
                    "max_points": {
                        "type": "integer",
                        "description": "Maximum summary points (default: 8).",
                        "default": 8,
                        "minimum": 1,
                        "maximum": 20
                    }
                },
                "required": ["url"]
            }
        ),
        Tool(
            name="apply_existing_tags_frontmatter_only",
            description=f"Apply existing vault tags to a note frontmatter. Writes are restricted to '{CAPTURE_SUBDIR}'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Vault-relative markdown path inside capture folder."
                    },
                    "max_tags": {
                        "type": "integer",
                        "description": "Maximum tags to apply (default: 5).",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20
                    }
                },
                "required": ["path"]
            }
        )
    ]
    
    # Always expose graph query. It can use remote graph service even if local graph is unavailable.
    tools.append(
        Tool(
            name="obsidian_graph_query",
            description="Query your knowledge graph using LLM synthesis. Uses graph service first and falls back to local graph when available.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Your question about the knowledge graph (e.g., 'What treatments are mentioned?', 'How does CAR-T relate to lymphoma?')"
                    },
                    "max_entities": {
                        "type": "integer",
                        "description": "Maximum number of entities to consider for local graph fallback (default: 20)",
                        "default": 20
                    }
                },
                "required": ["query"]
            }
        )
    )

    # Add local graph-only tools when local graph is available
    if GRAPH_AVAILABLE:
        # Try to load graph (but don't fail if it can't load)
        try:
            load_graph()  # Try to load graph
        except Exception:
            pass  # Graph tools won't be added if load fails
        
        if graph_loaded:
            tools.extend([
                Tool(
                    name="get_entity_info",
                    description="Get detailed information about a specific entity in the knowledge graph, including its type, properties, and all relationships.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "entity_name": {
                                "type": "string",
                                "description": "Name of the entity to explore (e.g., 'CAR-T Therapy', 'Home Assistant')"
                            }
                        },
                        "required": ["entity_name"]
                    }
                ),
                Tool(
                    name="find_entity_path",
                    description="Find connection paths between two entities in the knowledge graph. Shows how entities relate to each other.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "source": {
                                "type": "string",
                                "description": "Source entity name"
                            },
                            "target": {
                                "type": "string",
                                "description": "Target entity name"
                            },
                            "max_depth": {
                                "type": "integer",
                                "description": "Maximum path depth to search (default: 3)",
                                "default": 3
                            }
                        },
                        "required": ["source", "target"]
                    }
                ),
                Tool(
                    name="search_entities",
                    description="Search for entities in the knowledge graph by name. Returns matching entities with their types and connection counts.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "search_term": {
                                "type": "string",
                                "description": "Search term to find entities (e.g., 'treatment', 'CAR-T', '3D printing')"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results (default: 10)",
                                "default": 10
                            }
                        },
                        "required": ["search_term"]
                    }
                ),
                Tool(
                    name="get_graph_stats",
                    description="Get statistics about the knowledge graph including total entities, relationships, density, and top connected entities.",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                )
            ])
    
    return tools

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""
    
    try:
        if name == "obsidian_semantic_search" or name == "obsidian_simple_search" or name == "search_vault":
            # Support multiple names for compatibility
            return await search_vault(arguments)
        elif name == "search_vault_full":
            return await search_vault_full(arguments)
        elif name == "get_vault_stats" or name == "obsidian_vault_stats":
            # Support both names for compatibility
            return await get_vault_statistics(arguments)
        elif name == "obsidian_graph_query" or name == "query_knowledge_graph":
            # Support both names for compatibility
            return await query_knowledge_graph(arguments)
        elif name == "read_vault_note":
            return await read_vault_note(arguments)
        elif name == "read_attachment_text":
            return await read_attachment_text(arguments)
        elif name == "obsidian_search_mode" or name == "search_mode":
            return await search_with_mode(arguments)
        elif name == "obsidian_unified_query":
            return await obsidian_unified_query(arguments)
        elif name == "capture_note":
            return await capture_note(arguments)
        elif name == "summarize_url_to_capture":
            return await summarize_url_to_capture(arguments)
        elif name == "summarize_youtube_to_capture":
            return await summarize_youtube_to_capture(arguments)
        elif name == "apply_existing_tags_frontmatter_only":
            return await apply_existing_tags_frontmatter_only(arguments)
        elif name == "get_entity_info":
            return await get_entity_info(arguments)
        elif name == "find_entity_path":
            return await find_entity_path(arguments)
        elif name == "search_entities":
            return await search_entities(arguments)
        elif name == "get_graph_stats":
            return await get_graph_stats(arguments)
        else:
            return [TextContent(type="text", text=f"❌ Unknown tool: {name}")]
    
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Error: {str(e)}")]

async def search_vault(arguments: dict) -> list[TextContent]:
    """Enhanced vault search with better results"""
    query = arguments.get("query", "")
    n_results = min(max(arguments.get("n_results", 5), 1), 10)  # Clamp between 1-10
    include_content = arguments.get("include_content", True)
    
    if not query:
        return [TextContent(type="text", text="❌ Query is required")]
    
    try:
        response = requests.post(
            f"{EMBEDDING_URL}/query",
            json={
                "query": query,
                "n_results": n_results,
                "reranking": True,
                "deduplicate": True
            },
            headers=_service_headers(),
            timeout=15
        )

        status_code = getattr(response, "status_code", None)
        if not isinstance(status_code, int):
            raise requests.exceptions.ConnectionError("Invalid response from embedding service")

        if status_code != 200:
            return [TextContent(
                type="text",
                text=f"❌ Search failed: {response.status_code}\n"
                     f"Make sure the embedding service is running at {EMBEDDING_URL}"
            )]
        
        results = response.json()
        documents = results.get('documents', [[]])[0]
        metadatas = results.get('metadatas', [[]])[0]
        distances = results.get('distances', [[]])[0]
        
        if not documents:
            return [TextContent(
                type="text",
                text=f"🔍 No notes found matching '{query}'"
            )]
        
        # Build enhanced output
        output = f"🔍 **Found {len(documents)} note(s) for '{query}':**\n\n"
        
        for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
            relevance = (1 - dist) * 100 if dist < 1 else abs(dist) * 100
            relevance = min(100, max(0, relevance))
            filename = meta.get('filename', 'unknown')
            filepath = meta.get('filepath', 'unknown')
            
            output += f"**{i}. {filename}** ({relevance:.0f}% relevant)\n"
            output += f"   📁 {filepath}\n"
            
            if include_content:
                # Show first 300 chars of content
                snippet = doc[:300] + "..." if len(doc) > 300 else doc
                output += f"   📄 {snippet}\n"
            
            output += "\n"
        
        return [TextContent(type="text", text=output)]
    
    except requests.exceptions.ConnectionError:
        return [TextContent(
            type="text",
            text=f"❌ Cannot connect to embedding service at {EMBEDDING_URL}\n"
                 f"Make sure the service is running: docker-compose up embedding-service"
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Search error: {str(e)}")]


async def search_vault_full(arguments: dict) -> list[TextContent]:
    """Search the vault and return full note text + optional PDF text."""
    query = (arguments or {}).get("query", "")
    n_results = min(max((arguments or {}).get("n_results", 3), 1), 5)
    include_attachments = (arguments or {}).get("include_attachments", True)
    max_attachments = min(
        max((arguments or {}).get("max_attachments_per_note", MAX_ATTACHMENTS_PER_NOTE), 0),
        10
    )
    max_pdf_pages = min(
        max((arguments or {}).get("max_pdf_pages", PDF_MAX_PAGES), 1),
        100
    )

    if not query:
        return [TextContent(type="text", text="❌ Query is required")]

    try:
        response = requests.post(
            f"{EMBEDDING_URL}/query",
            json={
                "query": query,
                "n_results": n_results,
                "reranking": True,
                "deduplicate": True
            },
            headers=_service_headers(),
            timeout=15
        )

        status_code = getattr(response, "status_code", None)
        if not isinstance(status_code, int):
            raise requests.exceptions.ConnectionError("Invalid response from embedding service")

        if status_code != 200:
            return [TextContent(
                type="text",
                text=f"❌ Search failed: {response.status_code}\n"
                     f"Make sure the embedding service is running at {EMBEDDING_URL}"
            )]

        results = response.json()
        documents = results.get('documents', [[]])[0]
        metadatas = results.get('metadatas', [[]])[0]
        distances = results.get('distances', [[]])[0]

        if not documents:
            return [TextContent(
                type="text",
                text=f"🔍 No notes found matching '{query}'"
            )]

        output = [f"🔍 **Found {len(documents)} note(s) for '{query}':**\n"]

        for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
            relevance = (1 - dist) * 100 if dist < 1 else abs(dist) * 100
            relevance = min(100, max(0, relevance))
            filename = meta.get('filename', 'unknown')
            filepath = meta.get('filepath', 'unknown')

            output.append(f"--- Result {i}: {filename} ({relevance:.0f}% relevant)")
            output.append(f"Path: {filepath}")

            note_path = None
            note_text = None
            if filepath and filepath != "unknown":
                resolved, error = _resolve_vault_path(filepath)
                if error:
                    output.append(error)
                else:
                    note_path = resolved
                    try:
                        note_text = _read_text_file(resolved, MAX_NOTE_CHARS)
                        output.append("Note:")
                        output.append(note_text)
                    except Exception as e:
                        output.append(f"❌ Error reading note: {str(e)}")
            else:
                output.append("❌ No filepath in metadata for this result.")

            if include_attachments and note_path is not None and max_attachments > 0:
                pdf_refs = _extract_pdf_refs(note_text or doc)
                if not pdf_refs:
                    output.append("Attachments: none")
                else:
                    output.append("Attachments:")
                    for ref in pdf_refs[:max_attachments]:
                        resolved_pdf, error = _resolve_attachment_path(note_path, ref)
                        if error:
                            output.append(f"- {ref}: {error}")
                            continue
                        try:
                            pdf_text, _ = _extract_pdf_text(resolved_pdf, max_pdf_pages, MAX_NOTE_CHARS)
                            output.append(f"- {ref} ({resolved_pdf})")
                            output.append(pdf_text)
                        except RuntimeError as e:
                            output.append(f"- {ref}: ❌ {str(e)}")
                        except Exception as e:
                            output.append(f"- {ref}: ❌ Error reading PDF: {str(e)}")

            output.append("")

        return [TextContent(type="text", text="\n".join(output))]

    except requests.exceptions.ConnectionError:
        return [TextContent(
            type="text",
            text=f"❌ Cannot connect to embedding service at {EMBEDDING_URL}\n"
                 f"Make sure the service is running: docker-compose up embedding-service"
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Search error: {str(e)}")]

async def get_vault_statistics(arguments: dict) -> list[TextContent]:
    """Get vault statistics"""
    try:
        # Try embedding service stats
        try:
            stats_response = requests.get(
                f"{EMBEDDING_URL}/stats",
                timeout=5,
                headers=_service_headers()
            )
            if stats_response.status_code == 200:
                stats = stats_response.json()
                output = "📊 **Vault Statistics:**\n\n"
                output += f"**Total Documents:** {stats.get('total_documents', 0):,}\n"
                output += f"**Total Chunks:** {stats.get('total_chunks', 0):,}\n"
                return [TextContent(type="text", text=output)]
        except:
            pass
        
        # Fallback
        return [TextContent(
            type="text",
            text="📊 **Vault Statistics:**\n\n"
                 "Unable to retrieve statistics. Make sure the embedding service is running."
        )]
    
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Stats error: {str(e)}")]


def _normalize_mode(raw_mode: str | None) -> str:
    mode = (raw_mode or "").strip().lower()
    aliases = {
        "deep_research": "deep-research",
        "deepresearch": "deep-research",
    }
    return aliases.get(mode, mode)


def _format_mode_result(mode: str, payload: dict) -> str:
    answer = ""
    if isinstance(payload, dict):
        answer = str(payload.get("answer") or payload.get("response") or "").strip()
        if not answer and mode == "deep-research":
            deep_result = payload.get("result")
            if isinstance(deep_result, dict):
                answer = str(
                    deep_result.get("answer")
                    or deep_result.get("final_answer")
                    or deep_result.get("response")
                    or ""
                ).strip()

    lines = [
        f"🔎 **Mode:** {mode}",
        f"Gateway: {_gateway_base_url()}",
    ]
    if answer:
        lines.extend(["", answer])

    raw_json = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    max_raw_chars = 30000
    if len(raw_json) > max_raw_chars:
        raw_json = raw_json[:max_raw_chars] + "\n...[TRUNCATED]"
    lines.extend(["", "Raw Result:", raw_json])
    return "\n".join(lines)


async def _run_deep_research_via_gateway(query: str, provider: str | None, model: str | None) -> dict:
    if not WEBSOCKETS_AVAILABLE:
        raise RuntimeError("websockets package is not installed")

    ws_url = _gateway_deep_research_ws_url()
    headers = _service_headers()
    ws_headers = headers if headers else None
    request_payload = {"query": query}
    if provider:
        request_payload["provider"] = provider
    if model:
        request_payload["model"] = model

    events = []
    async with websockets.connect(
        ws_url,
        additional_headers=ws_headers,
        open_timeout=10,
        close_timeout=5,
        max_size=8 * 1024 * 1024,
    ) as websocket:
        await websocket.send(json.dumps(request_payload))

        while True:
            message = await asyncio.wait_for(websocket.recv(), timeout=DEEP_RESEARCH_TIMEOUT)
            event = json.loads(message)
            event_type = event.get("type")
            if event_type == "error":
                raise RuntimeError(str(event.get("content") or event.get("message") or "Deep research failed"))
            if event_type == "result":
                return {
                    "mode": "deep-research",
                    "result": event.get("data"),
                    "events": events,
                }
            events.append(event)
            if len(events) > 50:
                events = events[-50:]


async def search_with_mode(arguments: dict) -> list[TextContent]:
    """Run gateway search modes, including deep-research over websocket."""
    args = arguments or {}
    query = str(args.get("query") or "").strip()
    mode = _normalize_mode(args.get("mode"))

    if not query:
        return [TextContent(type="text", text="❌ Query is required")]
    if not mode:
        return [TextContent(type="text", text="❌ Mode is required")]
    if mode not in MODE_TOOL_SUPPORTED_MODES:
        supported = ", ".join(sorted(MODE_TOOL_SUPPORTED_MODES))
        return [TextContent(type="text", text=f"❌ Unsupported mode '{mode}'. Supported: {supported}")]

    if mode == "deep-research":
        try:
            provider = args.get("provider") or args.get("llm_provider")
            model = args.get("model")
            result = await _run_deep_research_via_gateway(query, provider, model)
            return [TextContent(type="text", text=_format_mode_result(mode, result))]
        except Exception as e:
            return [TextContent(type="text", text=f"❌ Deep research error: {str(e)}")]

    gateway_mode = mode
    payload = {"query": query, "mode": gateway_mode}
    for field in MODE_PASSTHROUGH_FIELDS:
        if field in args and args[field] is not None:
            payload[field] = args[field]

    # Allow provider alias for convenience when running non-deep modes.
    if "provider" in args and args["provider"] and "llm_provider" not in payload:
        payload["llm_provider"] = args["provider"]

    try:
        response = requests.post(
            _gateway_query_url(),
            json=payload,
            headers=_service_headers(),
            timeout=GATEWAY_QUERY_TIMEOUT,
        )
        status_code = getattr(response, "status_code", None)
        if not isinstance(status_code, int):
            raise requests.exceptions.ConnectionError("Invalid response from API gateway")
        if status_code != 200:
            detail = response.text
            try:
                parsed = response.json()
                detail = parsed.get("detail") or parsed
            except Exception:
                pass
            return [TextContent(type="text", text=f"❌ Mode request failed ({status_code}): {detail}")]

        result = response.json()
        display_mode = gateway_mode
        return [TextContent(type="text", text=_format_mode_result(display_mode, result))]
    except requests.exceptions.ConnectionError:
        return [TextContent(
            type="text",
            text=f"❌ Cannot connect to API gateway at {_gateway_base_url()}. Make sure api-gateway is running."
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Mode search error: {str(e)}")]


def _is_medical_timeline_query(query: str) -> bool:
    lowered = (query or "").lower()
    if not lowered:
        return False
    has_medical = any(keyword in lowered for keyword in MEDICAL_QUERY_KEYWORDS)
    has_timeline = any(keyword in lowered for keyword in TIMELINE_QUERY_KEYWORDS)
    return has_medical and has_timeline


def _extract_unified_source_labels(payload: dict) -> list[str]:
    labels: list[str] = []
    sources = payload.get("sources")
    if not isinstance(sources, list):
        notes = payload.get("notes")
        if isinstance(notes, dict):
            notes_data = notes.get("data")
            if isinstance(notes_data, dict) and isinstance(notes_data.get("sources"), list):
                sources = notes_data.get("sources")
    if not isinstance(sources, list):
        return labels

    for source in sources:
        if isinstance(source, dict):
            raw_label = (
                source.get("path")
                or source.get("filepath")
                or source.get("filename")
                or source.get("note")
                or source.get("source")
            )
            if isinstance(raw_label, str) and raw_label.strip():
                labels.append(raw_label.strip())
        elif isinstance(source, str) and source.strip():
            labels.append(source.strip())
    return labels


def _answer_has_source_citation(answer: str, source_labels: list[str]) -> bool:
    lowered = (answer or "").lower()
    if not lowered:
        return False

    if re.search(r"\[[0-9]+\]", answer):
        return True
    if "source:" in lowered or "sources:" in lowered:
        return True

    for label in source_labels:
        base = Path(label).name.lower()
        if base and len(base) >= 6 and base in lowered:
            return True
    return False


def _should_force_unknown_answer(query: str, answer: str, payload: dict) -> bool:
    if not _is_medical_timeline_query(query):
        return False
    if (answer or "").strip().lower() == "unknown from current notes.":
        return False

    source_labels = _extract_unified_source_labels(payload)
    if not source_labels:
        return True
    if not _answer_has_source_citation(answer, source_labels):
        return True
    return False


def _format_unified_sources(payload: dict, limit: int = 5) -> list[str]:
    lines: list[str] = []
    sources = payload.get("sources")
    if not isinstance(sources, list):
        notes = payload.get("notes")
        if isinstance(notes, dict):
            notes_data = notes.get("data")
            if isinstance(notes_data, dict) and isinstance(notes_data.get("sources"), list):
                sources = notes_data.get("sources")
    if not isinstance(sources, list):
        return lines

    for source in sources[:max(1, limit)]:
        if isinstance(source, dict):
            label = (
                source.get("path")
                or source.get("filepath")
                or source.get("filename")
                or source.get("note")
                or source.get("source")
                or "source"
            )
            if source.get("relevance") is not None:
                lines.append(f"- {label} ({source.get('relevance')}%)")
            else:
                lines.append(f"- {label}")
        else:
            lines.append(f"- {str(source)}")
    return lines


def _extract_unified_answer(payload: dict) -> str:
    answer = str(payload.get("answer") or payload.get("response") or "").strip()
    if answer:
        return answer

    notes = payload.get("notes")
    if isinstance(notes, dict):
        notes_data = notes.get("data")
        if isinstance(notes_data, dict):
            answer = str(notes_data.get("answer") or notes_data.get("response") or "").strip()
            if answer:
                return answer

    deep_result = payload.get("result")
    if isinstance(deep_result, dict):
        answer = str(
            deep_result.get("answer")
            or deep_result.get("final_answer")
            or deep_result.get("response")
            or ""
        ).strip()
    return answer


async def obsidian_unified_query(arguments: dict) -> list[TextContent]:
    args = arguments or {}
    query = str(args.get("query") or "").strip()
    mode = _normalize_mode(args.get("mode") or "cascading")
    concise = bool(args.get("concise", True))

    if not query:
        return [TextContent(type="text", text="❌ Query is required")]
    if mode not in MODE_TOOL_SUPPORTED_MODES:
        supported = ", ".join(sorted(MODE_TOOL_SUPPORTED_MODES))
        return [TextContent(type="text", text=f"❌ Unsupported mode '{mode}'. Supported: {supported}")]

    try:
        if mode == "deep-research":
            provider = args.get("provider") or args.get("llm_provider")
            model = args.get("model")
            payload = await _run_deep_research_via_gateway(query, provider, model)
        else:
            gateway_mode = mode
            request_payload = {"query": query, "mode": gateway_mode}
            for field in MODE_PASSTHROUGH_FIELDS:
                if field in args and args[field] is not None:
                    request_payload[field] = args[field]
            if "provider" in args and args["provider"] and "llm_provider" not in request_payload:
                request_payload["llm_provider"] = args["provider"]

            response = requests.post(
                _gateway_query_url(),
                json=request_payload,
                headers=_service_headers(),
                timeout=GATEWAY_QUERY_TIMEOUT,
            )
            status_code = getattr(response, "status_code", None)
            if not isinstance(status_code, int):
                raise requests.exceptions.ConnectionError("Invalid response from API gateway")
            if status_code != 200:
                detail = response.text
                try:
                    parsed = response.json()
                    detail = parsed.get("detail") or parsed
                except Exception:
                    pass
                return [TextContent(type="text", text=f"❌ Unified query failed ({status_code}): {detail}")]
            payload = response.json()
            payload["mode"] = gateway_mode

        answer = _extract_unified_answer(payload)
        if _should_force_unknown_answer(query, answer, payload):
            answer = "Unknown from current notes."
        display_mode = mode
        lines = [f"🔎 **Mode:** {display_mode}"]
        if answer:
            lines.extend(["", answer])
        else:
            lines.extend(["", "No synthesized answer was returned by the gateway."])

        source_lines = _format_unified_sources(payload)
        if source_lines:
            lines.extend(["", "Sources:", *source_lines])

        if not concise:
            raw_json = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
            max_raw_chars = 30000
            if len(raw_json) > max_raw_chars:
                raw_json = raw_json[:max_raw_chars] + "\n...[TRUNCATED]"
            lines.extend(["", "Raw Result:", raw_json])

        return [TextContent(type="text", text="\n".join(lines))]
    except requests.exceptions.ConnectionError:
        return [TextContent(
            type="text",
            text=f"❌ Cannot connect to API gateway at {_gateway_base_url()}. Make sure api-gateway is running."
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Unified query error: {str(e)}")]


def _build_capture_values(title: str, source: str, content: str, points: list[str], tags: list[str]) -> dict[str, str]:
    now = datetime.now().astimezone()
    summary_block = "\n".join([f"- {point}" for point in points]) if points else "- (no summary)"
    details_block = content.strip() or "(empty)"
    tags_block = ", ".join(tags) if tags else "(none)"
    return {
        "title": title,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S %Z"),
        "datetime": now.isoformat(timespec="seconds"),
        "source": source,
        "summary": summary_block,
        "content": details_block,
        "tags": tags_block,
    }


def _save_capture_from_text(title: str, source: str, content: str, points: list[str], tags: list[str]) -> tuple[str | None, str | None]:
    template = _load_capture_template()
    values = _build_capture_values(title=title, source=source, content=content, points=points, tags=tags)
    markdown = _render_capture_note(template, values)
    saved_path, write_error = _write_capture_note(title=title, content=markdown)
    if write_error or saved_path is None:
        return None, write_error
    return _vault_relative_path(saved_path), None


async def capture_note(arguments: dict) -> list[TextContent]:
    args = arguments or {}
    content = str(args.get("content") or "").strip()
    title = str(args.get("title") or "").strip() or "Quick Capture"
    source = str(args.get("source") or "manual-capture").strip()

    if not content:
        return [TextContent(type="text", text="❌ content is required")]

    tags = []
    raw_tags = args.get("tags")
    if isinstance(raw_tags, list):
        for item in raw_tags:
            normalized = _normalize_tag(str(item))
            if normalized:
                tags.append(normalized)
    points = _summarize_to_points(content, max_points=6)
    path, error = _save_capture_from_text(title=title, source=source, content=content, points=points, tags=tags)
    if error:
        return [TextContent(type="text", text=error)]
    return [TextContent(type="text", text=f"✅ Capture saved: `{path}`")]


async def summarize_url_to_capture(arguments: dict) -> list[TextContent]:
    args = arguments or {}
    url = str(args.get("url") or "").strip()
    title_override = str(args.get("title") or "").strip()
    max_points = int(args.get("max_points", 8))
    max_points = max(1, min(20, max_points))

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return [TextContent(type="text", text="❌ url must be a valid http(s) URL")]

    try:
        response = requests.get(url, timeout=20, headers={"User-Agent": "obsidian-rag-mcp/1.0"})
        status = getattr(response, "status_code", None)
        if not isinstance(status, int):
            raise requests.exceptions.ConnectionError("Invalid response from URL fetch")
        if status >= 400:
            return [TextContent(type="text", text=f"❌ URL fetch failed ({status})")]

        content_type = (response.headers.get("Content-Type") or "").lower()
        raw_text = response.text
        extracted = _extract_text_from_html(raw_text) if "html" in content_type or "<html" in raw_text.lower() else raw_text
        extracted = extracted.strip()
        if not extracted:
            return [TextContent(type="text", text="❌ No readable text extracted from URL")]

        parsed_payload = _extract_json_object(extracted)
        health_points = (
            _summarize_health_payload_to_points(parsed_payload, max_points=max_points)
            if parsed_payload
            else []
        )

        details_content = extracted
        if health_points:
            points = health_points
            details_content = "\n".join([f"- {point}" for point in health_points])
        else:
            if len(extracted) > 30000:
                extracted = extracted[:30000]
            points = _summarize_to_points(extracted, max_points=max_points)
            details_content = extracted

        summary_text = "\n".join([f"- {point}" for point in points])
        title = title_override or f"Web Capture - {parsed.netloc}"
        path, error = _save_capture_from_text(
            title=title,
            source=url,
            content=details_content,
            points=points,
            tags=[],
        )
        if error:
            return [TextContent(type="text", text=error)]
        return [TextContent(type="text", text=f"✅ URL summary saved: `{path}`\n\n{summary_text}")]
    except requests.exceptions.ConnectionError:
        return [TextContent(type="text", text=f"❌ Could not connect to URL: {url}")]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ URL summarization error: {str(e)}")]


async def summarize_youtube_to_capture(arguments: dict) -> list[TextContent]:
    args = arguments or {}
    url = str(args.get("url") or "").strip()
    title_override = str(args.get("title") or "").strip()
    max_points = int(args.get("max_points", 8))
    max_points = max(1, min(20, max_points))

    video_id = _extract_youtube_video_id(url)
    if not video_id:
        return [TextContent(type="text", text="❌ Only YouTube URLs are supported (youtube.com or youtu.be)")]

    try:
        transcript_text = _fetch_youtube_transcript(video_id)
        if len(transcript_text) > 40000:
            transcript_text = transcript_text[:40000]
        filtered_points = _summarize_youtube_transcript_to_points(transcript_text, max_points=max_points * 2)
        if not filtered_points:
            return [TextContent(type="text", text="❌ Could not extract concise summary points from transcript")]

        rewritten_points, details_text = _rewrite_points_abstractive(filtered_points, max_points=max_points)
        points = _quality_gate_summary_bullets(
            rewritten_points,
            source_points=filtered_points,
            max_points=max_points,
        )
        if len(points) < MIN_SUMMARY_BULLETS:
            return [TextContent(type="text", text="❌ Could not extract concise summary points from transcript")]

        details_text = _quality_gate_details_paragraph(details_text, points)
        if not details_text:
            details_text = _quality_gate_details_paragraph(_synthesize_details_paragraph(points), points)
        if not details_text:
            return [TextContent(type="text", text="❌ Could not extract concise summary points from transcript")]

        title = title_override or _fetch_youtube_title(url)
        summary_block = "\n".join([f"- {point}" for point in points])
        path, error = _save_capture_from_text(
            title=title,
            source=url,
            content=details_text,
            points=points,
            tags=[],
        )
        if error:
            return [TextContent(type="text", text=error)]
        return [TextContent(type="text", text=f"✅ YouTube summary saved: `{path}`\n\n{summary_block}")]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ YouTube summarization error: {str(e)}")]


async def apply_existing_tags_frontmatter_only(arguments: dict) -> list[TextContent]:
    if not YAML_AVAILABLE:
        return [TextContent(type="text", text="❌ pyyaml is required for frontmatter tag updates")]

    args = arguments or {}
    raw_path = str(args.get("path") or "").strip()
    max_tags = int(args.get("max_tags", 5))
    max_tags = max(1, min(20, max_tags))
    if not raw_path:
        return [TextContent(type="text", text="❌ path is required")]

    resolved, error = _resolve_capture_note_path(raw_path)
    if error or resolved is None:
        return [TextContent(type="text", text=error or "❌ Invalid path")]
    if resolved.suffix.lower() != ".md":
        return [TextContent(type="text", text="❌ Only markdown notes are supported")]

    try:
        original = resolved.read_text(encoding="utf-8", errors="replace")
        frontmatter, body, had_frontmatter = _split_frontmatter(original)
        if not isinstance(frontmatter, dict):
            frontmatter = {}
        note_text = body if had_frontmatter else original

        existing_tags = _collect_existing_tags()
        if not existing_tags:
            return [TextContent(type="text", text="❌ No existing tags found in vault")]

        suggested_bare = _score_tags_for_note(note_text, existing_tags, max_tags=max_tags)
        if not suggested_bare:
            return [TextContent(type="text", text="ℹ️ No matching existing tags were detected for this note")]

        current_tags = _extract_tags_from_frontmatter(frontmatter)
        merged = []
        seen = set()
        for tag in sorted(current_tags):
            bare = tag.lstrip("#")
            if bare not in seen:
                seen.add(bare)
                merged.append(bare)
        for bare in suggested_bare:
            if bare not in seen:
                seen.add(bare)
                merged.append(bare)
            if len(merged) >= max_tags:
                break

        frontmatter["tags"] = merged[:max_tags]
        updated_markdown = _render_frontmatter(frontmatter, note_text)
        resolved.write_text(updated_markdown, encoding="utf-8")
        rel_path = _vault_relative_path(resolved)
        applied = ", ".join(frontmatter["tags"])
        return [TextContent(type="text", text=f"✅ Updated tags in `{rel_path}`\nTags: {applied}")]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Tag update error: {str(e)}")]


async def query_knowledge_graph(arguments: dict) -> list[TextContent]:
    """Query knowledge graph using the internal in-process graph adapter."""
    query = arguments.get("query", "")
    max_entities = arguments.get("max_entities", 20)

    if not query:
        return [TextContent(type="text", text="❌ Query is required")]

    try:
        from src.services.internal_graph_transport import query_networkx_graph

        status_code, result = await asyncio.to_thread(
            query_networkx_graph,
            {"query": query, "mode": "hybrid", "max_entities": max_entities},
        )
        if status_code == 200 and isinstance(result, dict):
            answer = result.get("response") or result.get("answer") or ""
            if answer:
                return [TextContent(type="text", text=f"🕸️ **(Internal Graph)** {answer}")]
    except Exception as e:
        logger.warning(f"Internal graph adapter failed, falling back to local graph: {e}")

    # Fallback to direct local NetworkX graph access
    if not GRAPH_AVAILABLE:
        return [TextContent(
            type="text",
            text="❌ Knowledge graph not available. LightRAG failed and networkx is not installed."
        )]
    
    if not load_graph():
        return [TextContent(
            type="text",
            text="❌ Could not load knowledge graph. Make sure:\n"
                 "1. LightRAG service is running OR\n"
                 "2. KNOWLEDGE_GRAPH_PATH points to a valid .pkl file"
        )]
    
    try:
        answer = querier.query_graph(query, max_entities=max_entities)
        return [TextContent(type="text", text=f"🕸️ **(Local Graph)** {answer}")]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Graph query error: {str(e)}")]

async def get_entity_info(arguments: dict) -> list[TextContent]:
    """Get entity information"""
    entity_name = arguments.get("entity_name", "")
    if not entity_name:
        return [TextContent(type="text", text="❌ Entity name is required")]

    if not load_graph():
        return [TextContent(type="text", text="❌ Graph not loaded")]
    
    try:
        neighborhood = querier.get_entity_neighborhood(entity_name)
        
        if not neighborhood.get('found', True):
            return [TextContent(
                type="text",
                text=f"❌ Entity '{entity_name}' not found in graph"
            )]
        
        result = f"📍 **Entity:** {neighborhood['entity']}\n"
        result += f"**Type:** {neighborhood['properties'].get('entity_type', 'Unknown')}\n\n"
        
        if neighborhood.get('outgoing'):
            result += "**Outgoing Relationships:**\n"
            for rel in neighborhood['outgoing'][:10]:
                result += f"  → {rel['relationship']} → {rel['target']}\n"
            result += "\n"
        
        if neighborhood.get('incoming'):
            result += "**Incoming Relationships:**\n"
            for rel in neighborhood['incoming'][:10]:
                result += f"  ← {rel['relationship']} ← {rel['source']}\n"
        
        return [TextContent(type="text", text=result)]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Error: {str(e)}")]


async def read_vault_note(arguments: dict) -> list[TextContent]:
    path = (arguments or {}).get("path", "")
    resolved, error = _resolve_vault_path(path)
    if error:
        return [TextContent(type="text", text=error)]

    try:
        content = _read_text_file(resolved, MAX_NOTE_CHARS)
        return [TextContent(type="text", text=content)]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Error reading note: {str(e)}")]


async def read_attachment_text(arguments: dict) -> list[TextContent]:
    path = (arguments or {}).get("path", "")
    max_pages = int((arguments or {}).get("max_pages", PDF_MAX_PAGES))
    resolved, error = _resolve_vault_path(path)
    if error:
        return [TextContent(type="text", text=error)]

    if resolved.suffix.lower() != ".pdf":
        return [TextContent(type="text", text="❌ Only PDF attachments are supported")]

    try:
        content, _ = _extract_pdf_text(resolved, max_pages, MAX_NOTE_CHARS)
        return [TextContent(type="text", text=content)]
    except RuntimeError as e:
        return [TextContent(type="text", text=f"❌ {str(e)}")]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Error reading PDF: {str(e)}")]

async def find_entity_path(arguments: dict) -> list[TextContent]:
    """Find path between entities"""
    source = arguments.get("source", "")
    target = arguments.get("target", "")
    max_depth = arguments.get("max_depth", 3)
    
    if not source or not target:
        return [TextContent(type="text", text="❌ Both source and target are required")]

    if not load_graph():
        return [TextContent(type="text", text="❌ Graph not loaded")]
    
    try:
        paths = querier.find_paths(source, target, max_depth=max_depth)
        
        if not paths:
            return [TextContent(
                type="text",
                text=f"❌ No path found between '{source}' and '{target}'"
            )]
        
        result = f"🛤️  **Found {len(paths)} path(s) between '{source}' and '{target}':**\n\n"
        for i, path in enumerate(paths[:5], 1):
            result += f"{i}. {' → '.join(path)}\n"
        
        return [TextContent(type="text", text=result)]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Error: {str(e)}")]

async def search_entities(arguments: dict) -> list[TextContent]:
    """Search entities"""
    search_term = arguments.get("search_term") or arguments.get("query") or ""
    search_term = search_term.lower()
    limit = arguments.get("limit", 10)
    
    if not search_term:
        return [TextContent(type="text", text="❌ Search term is required")]

    if not load_graph():
        return [TextContent(type="text", text="❌ Graph not loaded")]
    
    try:
        matching_entities = []
        for node in querier.graph.nodes():
            node_label = querier._node_label(node)
            if search_term in node_label.lower():
                node_data = dict(querier.graph.nodes[node])
                matching_entities.append({
                    'name': node_label,
                    'type': node_data.get('entity_type', 'Unknown'),
                    'connections': querier.graph.degree(node)
                })
        
        matching_entities.sort(key=lambda x: x['connections'], reverse=True)
        
        if not matching_entities:
            return [TextContent(
                type="text",
                text=f"❌ No entities found matching '{search_term}'"
            )]
        
        result = f"🔍 **Found {len(matching_entities)} entity(ies) matching '{search_term}':**\n\n"
        for entity in matching_entities[:limit]:
            result += f"• **{entity['name']}** ({entity['type']}) - {entity['connections']} connections\n"
        
        return [TextContent(type="text", text=result)]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Error: {str(e)}")]

async def get_graph_stats(arguments: dict) -> list[TextContent]:
    """Get graph statistics"""
    if not load_graph():
        return [TextContent(type="text", text="❌ Graph not loaded")]
    
    try:
        stats = querier.get_graph_stats()
        
        result = "📊 **Knowledge Graph Statistics:**\n\n"
        result += f"**Total Entities:** {stats['total_nodes']:,}\n"
        result += f"**Total Relationships:** {stats['total_edges']:,}\n"
        result += f"**Density:** {stats['density']:.4f}\n"
        result += f"**Connected:** {stats['is_connected']}\n\n"
        result += "**Top 10 Most Connected Entities:**\n"
        for entity in stats['top_entities'][:10]:
            result += f"  • {entity['entity']}: {entity['connections']} connections\n"
        
        return [TextContent(type="text", text=result)]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Error: {str(e)}")]

class _StreamableHTTPASGIApp:
    def __init__(self, session_manager, api_key: str | None):
        self.session_manager = session_manager
        self.api_key = api_key

    async def __call__(self, scope, receive, send):
        if self.api_key:
            from starlette.responses import PlainTextResponse

            headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
            auth = headers.get("authorization", "")
            token = auth.split(" ", 1)[1].strip() if auth.lower().startswith("bearer ") else auth.strip()
            api_key = headers.get("x-api-key", "").strip()
            if token != self.api_key and api_key != self.api_key:
                response = PlainTextResponse("Unauthorized", status_code=401)
                await response(scope, receive, send)
                return

        await self.session_manager.handle_request(scope, receive, send)


class _InMemoryOAuthProvider:
    def __init__(self, access_ttl: int, refresh_ttl: int, auth_code_ttl: int, store_path: Path | None):
        from mcp.server.auth.provider import AuthorizationCode, RefreshToken, AccessToken
        from mcp.shared.auth import OAuthClientInformationFull

        self.AuthorizationCode = AuthorizationCode
        self.RefreshToken = RefreshToken
        self.AccessToken = AccessToken
        self.OAuthClientInformationFull = OAuthClientInformationFull
        self.access_ttl = access_ttl
        self.refresh_ttl = refresh_ttl
        self.auth_code_ttl = auth_code_ttl
        self.clients = {}
        self.auth_codes = {}
        self.refresh_tokens = {}
        self.access_tokens = {}
        self.store_path = store_path
        self._load_clients()

    def _load_clients(self) -> None:
        if not self.store_path or not self.store_path.exists():
            return
        try:
            with open(self.store_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            for client_id, raw in data.items():
                client = self.OAuthClientInformationFull.model_validate(raw)
                if client.client_id:
                    self.clients[client_id] = client
        except Exception:
            pass

    def _save_clients(self) -> None:
        if not self.store_path:
            return
        try:
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                client_id: client.model_dump()
                for client_id, client in self.clients.items()
            }
            tmp_path = self.store_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
            tmp_path.replace(self.store_path)
        except Exception:
            pass

    async def get_client(self, client_id: str):
        return self.clients.get(client_id)

    async def register_client(self, client_info):
        if not client_info.client_id:
            from mcp.server.auth.provider import RegistrationError

            raise RegistrationError("invalid_client_metadata", "client_id is required")
        self.clients[client_info.client_id] = client_info
        self._save_clients()

    async def authorize(self, client, params):
        from mcp.server.auth.provider import construct_redirect_uri

        code = secrets.token_urlsafe(32)
        auth_code = self.AuthorizationCode(
            code=code,
            scopes=params.scopes or [],
            expires_at=time.time() + self.auth_code_ttl,
            client_id=client.client_id,
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,
        )
        self.auth_codes[code] = auth_code
        return construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state)

    async def load_authorization_code(self, client, authorization_code: str):
        return self.auth_codes.get(authorization_code)

    async def exchange_authorization_code(self, client, authorization_code):
        from mcp.shared.auth import OAuthToken

        self.auth_codes.pop(authorization_code.code, None)
        scopes = authorization_code.scopes or []
        now = int(time.time())
        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)

        access = self.AccessToken(
            token=access_token,
            client_id=client.client_id,
            scopes=scopes,
            expires_at=now + self.access_ttl,
            resource=authorization_code.resource,
        )
        refresh = self.RefreshToken(
            token=refresh_token,
            client_id=client.client_id,
            scopes=scopes,
            expires_at=now + self.refresh_ttl,
        )

        self.access_tokens[access_token] = access
        self.refresh_tokens[refresh_token] = refresh

        return OAuthToken(
            access_token=access_token,
            expires_in=self.access_ttl,
            refresh_token=refresh_token,
            scope=" ".join(scopes) if scopes else None,
        )

    async def load_refresh_token(self, client, refresh_token: str):
        return self.refresh_tokens.get(refresh_token)

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        from mcp.shared.auth import OAuthToken

        self.refresh_tokens.pop(refresh_token.token, None)
        now = int(time.time())
        access_token = secrets.token_urlsafe(32)
        new_refresh = secrets.token_urlsafe(32)

        access = self.AccessToken(
            token=access_token,
            client_id=client.client_id,
            scopes=scopes,
            expires_at=now + self.access_ttl,
        )
        refresh = self.RefreshToken(
            token=new_refresh,
            client_id=client.client_id,
            scopes=scopes,
            expires_at=now + self.refresh_ttl,
        )

        self.access_tokens[access_token] = access
        self.refresh_tokens[new_refresh] = refresh

        return OAuthToken(
            access_token=access_token,
            expires_in=self.access_ttl,
            refresh_token=new_refresh,
            scope=" ".join(scopes) if scopes else None,
        )

    async def load_access_token(self, token: str):
        return self.access_tokens.get(token)

    async def revoke_token(self, token):
        token_value = getattr(token, "token", None)
        if token_value:
            self.refresh_tokens.pop(token_value, None)
            self.access_tokens.pop(token_value, None)


def _normalize_http_path(path: str) -> str:
    if not path.startswith("/"):
        return f"/{path}"
    return path


def _parse_list(value: str | None) -> list[str] | None:
    if not value:
        return None
    parts = re.split(r"[\s,]+", value.strip())
    return [part for part in parts if part]


def _normalize_public_url(public_url: str | None, host: str, port: int) -> str:
    if public_url:
        return public_url.rstrip("/")
    return f"http://{host}:{port}"


def build_streamable_http_app(
    mount_path: str,
    stateless: bool,
    auth_mode: str,
    api_key: str | None,
    public_url: str | None,
    host: str,
    port: int,
):
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.authentication import AuthenticationMiddleware
    from starlette.responses import JSONResponse, PlainTextResponse
    from starlette.routing import Route
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    session_manager = StreamableHTTPSessionManager(app=app, stateless=stateless)
    if auth_mode == "oauth":
        api_key = None
    http_app = _StreamableHTTPASGIApp(session_manager, api_key=api_key)
    routes = []
    middleware = []

    normalized_mount_path = _normalize_http_path(mount_path)

    async def root_endpoint(request):
        public_base = _normalize_public_url(public_url, host, port)
        return JSONResponse(
            {
                "service": "obsidian-rag-unified-mcp",
                "status": "ok",
                "transport": "streamable-http",
                "path": normalized_mount_path,
                "auth_mode": auth_mode,
                "stateless": stateless,
                "public_url": public_base,
                "health": "/health",
            }
        )

    async def health_endpoint(request):
        return PlainTextResponse("ok", status_code=200)

    routes.extend(
        [
            Route("/", endpoint=root_endpoint, methods=["GET"]),
            Route("/health", endpoint=health_endpoint, methods=["GET"]),
        ]
    )

    if auth_mode == "oauth":
        from mcp.server.auth.middleware.bearer_auth import BearerAuthBackend, RequireAuthMiddleware
        from mcp.server.auth.provider import ProviderTokenVerifier
        from mcp.server.auth.routes import (
            create_auth_routes,
            create_protected_resource_routes,
            build_resource_metadata_url,
        )
        from mcp.server.auth.settings import ClientRegistrationOptions
        from pydantic import AnyHttpUrl, TypeAdapter

        access_ttl = int(os.getenv("MCP_OAUTH_ACCESS_TTL", "3600"))
        refresh_ttl = int(os.getenv("MCP_OAUTH_REFRESH_TTL", "2592000"))
        auth_code_ttl = int(os.getenv("MCP_OAUTH_AUTH_CODE_TTL", "600"))
        store_path_raw = os.getenv("MCP_OAUTH_STORE_PATH", "/tmp/obsidian_rag_oauth_store.json")
        store_path = Path(store_path_raw).expanduser() if store_path_raw else None
        provider = _InMemoryOAuthProvider(access_ttl, refresh_ttl, auth_code_ttl, store_path)

        scopes = _parse_list(os.getenv("MCP_OAUTH_SCOPES"))
        allow_registration = os.getenv("MCP_OAUTH_ALLOW_REGISTRATION", "true").lower() != "false"
        registration_options = ClientRegistrationOptions(
            enabled=allow_registration,
            valid_scopes=scopes,
            default_scopes=scopes,
        )

        client_id = os.getenv("MCP_OAUTH_CLIENT_ID")
        redirect_uris = _parse_list(os.getenv("MCP_OAUTH_REDIRECT_URIS"))
        if client_id and redirect_uris:
            from mcp.shared.auth import OAuthClientInformationFull

            client_secret = os.getenv("MCP_OAUTH_CLIENT_SECRET")
            token_auth_method = "client_secret_post" if client_secret else "none"
            provider.clients[client_id] = OAuthClientInformationFull(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uris=redirect_uris,
                token_endpoint_auth_method=token_auth_method,
                grant_types=["authorization_code", "refresh_token"],
                response_types=["code"],
                scope=" ".join(scopes) if scopes else None,
            )
            provider._save_clients()

        issuer_url_str = _normalize_public_url(public_url, host, port)
        issuer_url = TypeAdapter(AnyHttpUrl).validate_python(issuer_url_str)
        resource_url = TypeAdapter(AnyHttpUrl).validate_python(
            f"{str(issuer_url).rstrip('/')}{_normalize_http_path(mount_path)}"
        )

        token_verifier = ProviderTokenVerifier(provider)
        middleware = [
            Middleware(AuthenticationMiddleware, backend=BearerAuthBackend(token_verifier)),
        ]

        resource_metadata_url = build_resource_metadata_url(resource_url)
        routes.append(
            Route(
                normalized_mount_path,
                endpoint=RequireAuthMiddleware(http_app, [], resource_metadata_url),
            )
        )
        routes.extend(
            create_auth_routes(
                provider=provider,
                issuer_url=issuer_url,
                client_registration_options=registration_options,
            )
        )
        routes.extend(
            create_protected_resource_routes(
                resource_url=resource_url,
                authorization_servers=[issuer_url],
                scopes_supported=scopes,
            )
        )
    else:
        routes.append(Route(normalized_mount_path, http_app))

    return Starlette(routes=routes, middleware=middleware, lifespan=lambda _: session_manager.run())


async def run_stdio_server():
    """Run the MCP server over stdio (default)."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


def run_http_server(
    host: str,
    port: int,
    mount_path: str,
    stateless: bool,
    auth_mode: str,
    api_key: str | None,
    public_url: str | None,
) -> None:
    """Run the MCP server over streamable HTTP (for ChatGPT connectors)."""
    try:
        import uvicorn
    except ImportError:
        print("uvicorn is required for HTTP transport. Install with: pip install uvicorn", file=sys.stderr)
        sys.exit(1)

    http_app = build_streamable_http_app(
        mount_path=mount_path,
        stateless=stateless,
        auth_mode=auth_mode,
        api_key=api_key,
        public_url=public_url,
        host=host,
        port=port,
    )
    uvicorn.run(http_app, host=host, port=port, log_level="info")


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Obsidian RAG MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="Transport to use (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("MCP_HTTP_HOST", "127.0.0.1"),
        help="HTTP host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_HTTP_PORT", "8811")),
        help="HTTP port (default: 8811)",
    )
    parser.add_argument(
        "--path",
        default=os.getenv("MCP_HTTP_PATH", "/mcp"),
        help="HTTP path for MCP (default: /mcp)",
    )
    parser.add_argument(
        "--auth-mode",
        choices=["none", "api-key", "oauth"],
        default=os.getenv("MCP_HTTP_AUTH_MODE", "none"),
        help="HTTP auth mode (default: none)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("MCP_HTTP_API_KEY"),
        help="HTTP API key (default: MCP_HTTP_API_KEY)",
    )
    parser.add_argument(
        "--public-url",
        default=os.getenv("MCP_HTTP_PUBLIC_URL"),
        help="Public HTTPS base URL for OAuth metadata (example: https://xyz.ngrok.app)",
    )
    stateless_default = os.getenv("MCP_HTTP_STATELESS", "true").lower() != "false"
    parser.add_argument(
        "--stateless",
        dest="stateless",
        action="store_true",
        default=stateless_default,
        help="Serve MCP without session state (default: true)",
    )
    parser.add_argument(
        "--stateful",
        dest="stateless",
        action="store_false",
        help="Serve MCP with session state",
    )

    args = parser.parse_args(argv)
    auth_mode = args.auth_mode
    if auth_mode == "none" and args.api_key:
        auth_mode = "api-key"

    if args.transport == "stdio":
        asyncio.run(run_stdio_server())
    else:
        run_http_server(
            host=args.host,
            port=args.port,
            mount_path=args.path,
            stateless=args.stateless,
            auth_mode=auth_mode,
            api_key=args.api_key,
            public_url=args.public_url,
        )


async def main():
    """Backward-compatible entrypoint (stdio)."""
    await run_stdio_server()

if __name__ == "__main__":
    cli()
