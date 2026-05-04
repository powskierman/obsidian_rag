"""Configuration for the optional PDF tree retrieval provider layer."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

PdfTreeProviderName = Literal["ollama", "lmstudio", "openrouter", "openai_compatible"]


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else default


def normalize_base_url(value: str, *, append_v1: bool = False) -> str:
    cleaned = str(value or "").strip().strip("`;'\"")
    if not cleaned:
        return ""
    if not cleaned.startswith(("http://", "https://")):
        cleaned = f"http://{cleaned}"
    cleaned = cleaned.rstrip("/")
    if append_v1 and not cleaned.lower().endswith("/v1"):
        cleaned = f"{cleaned}/v1"
    return cleaned


def normalize_pdf_tree_provider(value: str | None) -> PdfTreeProviderName:
    normalized = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "ollama": "ollama",
        "lmstudio": "lmstudio",
        "lm_studio": "lmstudio",
        "mlx": "lmstudio",
        "openrouter": "openrouter",
        "openai_compatible": "openai_compatible",
        "openai-compatible": "openai_compatible",
        "generic": "openai_compatible",
    }
    return aliases.get(normalized, "ollama")  # type: ignore[return-value]


@dataclass(frozen=True)
class PdfTreeProviderConfig:
    enabled: bool
    provider: PdfTreeProviderName
    model: str
    base_url: str
    api_key: str | None
    timeout_seconds: float
    max_tokens: int | None = None
    openrouter_http_referer: str | None = None
    openrouter_x_title: str | None = None

    @property
    def is_hosted(self) -> bool:
        return self.provider == "openrouter"


@dataclass(frozen=True)
class PdfTreeRetrievalLimits:
    max_documents_per_query: int = 3
    max_nodes_inspected: int = 12
    max_evidence: int = 5
    max_chars_per_evidence: int = 1800


def _env_int(name: str, default: int, *, minimum: int) -> int:
    raw = _env(name)
    try:
        value = int(raw) if raw else default
    except ValueError:
        value = default
    return max(minimum, value)


def load_pdf_tree_retrieval_limits() -> PdfTreeRetrievalLimits:
    return PdfTreeRetrievalLimits(
        max_documents_per_query=_env_int("PDF_TREE_MAX_DOCUMENTS_PER_QUERY", 3, minimum=1),
        max_nodes_inspected=_env_int("PDF_TREE_MAX_NODES_INSPECTED", 12, minimum=1),
        max_evidence=_env_int("PDF_TREE_MAX_EVIDENCE", 5, minimum=1),
        max_chars_per_evidence=_env_int("PDF_TREE_MAX_CHARS_PER_EVIDENCE", 1800, minimum=200),
    )


def load_pdf_tree_provider_config(
    provider_override: str | None = None,
    model_override: str | None = None,
) -> PdfTreeProviderConfig:
    provider = normalize_pdf_tree_provider(provider_override or _env("PDF_TREE_PROVIDER", "ollama"))
    enabled = _env("PDF_TREE_RETRIEVAL_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    timeout = float(_env("PDF_TREE_TIMEOUT_SECONDS", "120") or "120")
    max_tokens_raw = _env("PDF_TREE_MAX_TOKENS")
    max_tokens = int(max_tokens_raw) if max_tokens_raw.isdigit() else None

    if provider == "ollama":
        model = model_override or _env("PDF_TREE_MODEL") or _env("OLLAMA_MODEL", "llama3.1:8b")
        base_url = normalize_base_url(_env("OLLAMA_BASE_URL") or _env("OLLAMA_HOST", "http://localhost:11434"))
        api_key = None
    elif provider == "lmstudio":
        model = model_override or _env("PDF_TREE_MODEL") or _env("LMSTUDIO_MODEL") or _env("MLX_MODEL") or "local-model"
        base_url = normalize_base_url(
            _env("OPENAI_COMPATIBLE_BASE_URL")
            or _env("QUERY_LMSTUDIO_BASE_URL")
            or _env("LMSTUDIO_BASE_URL")
            or _env("MLX_BASE_URL")
            or "http://localhost:1234/v1",
            append_v1=True,
        )
        api_key = _env("OPENAI_COMPATIBLE_API_KEY") or _env("QUERY_LMSTUDIO_API_KEY") or _env("LMSTUDIO_API_KEY") or "lmstudio"
    elif provider == "openrouter":
        model = model_override or _env("PDF_TREE_MODEL") or _env("OPENROUTER_MODEL", "openrouter/auto")
        base_url = normalize_base_url(_env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"), append_v1=True)
        api_key = _env("OPENROUTER_API_KEY") or None
    else:
        model = model_override or _env("PDF_TREE_MODEL") or _env("OPENAI_COMPATIBLE_MODEL", "local-model")
        base_url = normalize_base_url(_env("OPENAI_COMPATIBLE_BASE_URL", "http://localhost:1234/v1"), append_v1=True)
        api_key = _env("OPENAI_COMPATIBLE_API_KEY") or None

    return PdfTreeProviderConfig(
        enabled=enabled,
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=timeout,
        max_tokens=max_tokens,
        openrouter_http_referer=_env("OPENROUTER_HTTP_REFERER") or None,
        openrouter_x_title=_env("OPENROUTER_X_TITLE", "obsidian_rag") or None,
    )
