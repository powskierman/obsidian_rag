import os
import re
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "mkt_tok",
    "ref",
    "si",
    "srsltid",
}
_TRACKING_QUERY_PREFIXES = (
    "utm_",
)


def normalize_vault_path(value: str) -> str:
    text = str(value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def canonicalize_web_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    while raw and raw[-1] in {"`", ";", "'", '"'}:
        raw = raw[:-1].rstrip()
    if not raw:
        return ""

    try:
        parsed = urlsplit(raw)
    except ValueError:
        return raw

    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not parsed.netloc:
        return raw

    hostname = (parsed.hostname or "").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]

    try:
        port = parsed.port
    except ValueError:
        port = None
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{hostname}:{port}"
    else:
        netloc = hostname

    path = parsed.path or "/"
    path = re.sub(r"/{2,}", "/", path)
    if path != "/":
        path = path.rstrip("/")

    filtered_query = []
    for key, val in parse_qsl(parsed.query, keep_blank_values=False):
        lowered = key.lower()
        if lowered in _TRACKING_QUERY_KEYS:
            continue
        if any(lowered.startswith(prefix) for prefix in _TRACKING_QUERY_PREFIXES):
            continue
        filtered_query.append((key, val))

    query = urlencode(filtered_query, doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def is_web_locator(value: Any) -> bool:
    raw = str(value or "").strip().lower()
    return raw.startswith("http://") or raw.startswith("https://")


def extract_source_locator(value: Any) -> str:
    if isinstance(value, Mapping):
        for key in ("filepath", "url", "source", "filename", "title"):
            candidate = str(value.get(key) or "").strip()
            if candidate:
                return candidate
        return ""
    return str(value or "").strip()


def infer_source_category(value: Any, default: str = "vault") -> str:
    if isinstance(value, Mapping):
        category = str(value.get("source_category") or value.get("type") or "").strip().lower()
        if category in {"vault", "web"}:
            return category
        if category == "note":
            return "vault"
        if category in {"url", "website", "webpage"}:
            return "web"
    locator = extract_source_locator(value)
    if is_web_locator(locator):
        return "web"
    return "vault" if default not in {"vault", "web"} else default


def canonicalize_source_locator(value: Any, default_category: str = "vault") -> tuple[str, str]:
    category = infer_source_category(value, default=default_category)
    locator = extract_source_locator(value)

    if category == "web":
        candidate = locator
        if isinstance(value, Mapping):
            candidate = str(value.get("canonical_url") or locator).strip()
        canonical = canonicalize_web_url(candidate) or candidate
        return "web", canonical

    normalized = normalize_vault_path(locator)
    return "vault", normalized


def canonical_source_identity(value: Any, default_category: str = "vault") -> tuple[str, str]:
    category, locator = canonicalize_source_locator(value, default_category=default_category)
    return category, locator.lower()


def canonical_source_display_name(value: Any, default_category: str = "vault") -> str:
    if isinstance(value, Mapping):
        explicit = str(value.get("filename") or value.get("title") or "").strip()
        if explicit:
            return explicit
    category, locator = canonicalize_source_locator(value, default_category=default_category)
    if not locator:
        return "Unknown"
    if category == "web":
        return locator
    return os.path.basename(locator) or locator


def normalize_source_record(value: Mapping[str, Any], default_category: str = "vault") -> dict[str, Any]:
    category, locator = canonicalize_source_locator(value, default_category=default_category)
    normalized = dict(value)
    normalized["source_category"] = category
    normalized["canonical_locator"] = locator

    if category == "web":
        normalized["canonical_url"] = locator
        normalized["url"] = locator
        normalized["filepath"] = locator
        if not str(normalized.get("filename") or "").strip():
            normalized["filename"] = locator
    else:
        normalized["filepath"] = locator
        if not str(normalized.get("filename") or "").strip():
            normalized["filename"] = os.path.basename(locator) or locator or "Unknown"

    normalized["_source_identity"] = canonical_source_identity(normalized, default_category=default_category)
    return normalized
