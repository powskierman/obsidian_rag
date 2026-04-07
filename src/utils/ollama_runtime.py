import os
from typing import Iterator, Optional


def sanitize_ollama_base_url(value: Optional[str], default: str) -> str:
    cleaned = str(value or default).strip()
    if "=" in cleaned and cleaned.split("=", 1)[0].strip().upper() in {"OLLAMA_HOST", "OLLAMA_FALLBACK_HOST"}:
        cleaned = cleaned.split("=", 1)[1].strip()
    while cleaned and cleaned[-1] in {"`", ";", "'", '"'}:
        cleaned = cleaned[:-1].rstrip()
    if cleaned and not cleaned.startswith(("http://", "https://")):
        cleaned = f"http://{cleaned}"
    return cleaned.rstrip("/") or default.rstrip("/")


def resolve_ollama_host(default_host: str = "http://host.docker.internal:11434") -> str:
    return sanitize_ollama_base_url(os.getenv("OLLAMA_HOST"), default_host)


def resolve_ollama_fallback_host() -> Optional[str]:
    raw = os.getenv("OLLAMA_FALLBACK_HOST") or os.getenv("OLLAMA_LOCAL_FALLBACK_HOST")
    if not raw:
        return None
    return sanitize_ollama_base_url(raw, "http://host.docker.internal:11434")


def resolve_ollama_model(requested_model: str, fallback_default: str = "mistral") -> str:
    model = str(requested_model or "").strip()
    if not model or "claude" in model.lower() or "gpt" in model.lower():
        return os.getenv("OLLAMA_MODEL", fallback_default)
    return model


def resolve_ollama_fallback_model(requested_model: str) -> Optional[str]:
    fallback_model = (
        os.getenv("OLLAMA_FALLBACK_MODEL")
        or os.getenv("OLLAMA_LOCAL_MODEL")
        or ""
    ).strip()
    requested = str(requested_model or "").strip()
    if not fallback_model or fallback_model == requested:
        return None
    return fallback_model


def iter_ollama_routes(
    requested_model: str,
    *,
    default_host: str = "http://host.docker.internal:11434",
    fallback_default_model: str = "mistral",
) -> Iterator[tuple[str, str]]:
    primary_host = resolve_ollama_host(default_host=default_host)
    primary_model = resolve_ollama_model(requested_model, fallback_default=fallback_default_model)
    fallback_host = resolve_ollama_fallback_host()
    fallback_model = resolve_ollama_fallback_model(primary_model)

    seen: set[tuple[str, str]] = set()

    def emit(host: Optional[str], model: Optional[str]) -> Iterator[tuple[str, str]]:
        if not host or not model:
            return
        key = (host, model)
        if key in seen:
            return
        seen.add(key)
        yield key

    yield from emit(primary_host, primary_model)
    if fallback_host:
        yield from emit(fallback_host, primary_model)
        yield from emit(fallback_host, fallback_model)
