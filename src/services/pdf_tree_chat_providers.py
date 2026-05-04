"""Provider-neutral chat client for the planned PDF tree retriever."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import httpx

from src.services.pdf_tree_config import PdfTreeProviderConfig


class PdfTreeProviderError(RuntimeError):
    """Raised when a configured PDF tree provider cannot complete a request."""


@dataclass(frozen=True)
class ProviderHealth:
    provider: str
    configured: bool
    reachable: bool
    model: str
    base_url: str
    hosted: bool
    models: list[str]
    error: str | None = None


class ChatProvider:
    async def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> str:
        raise NotImplementedError

    async def health(self) -> ProviderHealth:
        raise NotImplementedError


class OpenAICompatibleChatProvider(ChatProvider):
    def __init__(
        self,
        config: PdfTreeProviderConfig,
        *,
        client: httpx.AsyncClient | None = None,
        owns_client: bool = False,
    ) -> None:
        self.config = config
        self._client = client or httpx.AsyncClient()
        self._owns_client = owns_client or client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        if self.config.provider == "openrouter":
            if self.config.openrouter_http_referer:
                headers["HTTP-Referer"] = self.config.openrouter_http_referer
            if self.config.openrouter_x_title:
                headers["X-Title"] = self.config.openrouter_x_title
        return headers

    async def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model or self.config.model,
            "messages": list(messages),
            "temperature": temperature,
        }
        resolved_max_tokens = max_tokens if max_tokens is not None else self.config.max_tokens
        if resolved_max_tokens is not None:
            payload["max_tokens"] = resolved_max_tokens

        response = await self._client.post(
            f"{self.config.base_url}/chat/completions",
            json=payload,
            headers=self._headers(),
            timeout=timeout or self.config.timeout_seconds,
        )
        if response.status_code >= 400:
            raise PdfTreeProviderError(f"{self.config.provider} returned HTTP {response.status_code}: {response.text[:300]}")
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return str(content).strip()

    async def list_models(self) -> list[str]:
        response = await self._client.get(
            f"{self.config.base_url}/models",
            headers=self._headers(),
            timeout=min(self.config.timeout_seconds, 10),
        )
        if response.status_code >= 400:
            raise PdfTreeProviderError(f"{self.config.provider} model listing returned HTTP {response.status_code}")
        data = response.json()
        return [
            str(item.get("id") or item.get("name") or "").strip()
            for item in data.get("data", [])
            if str(item.get("id") or item.get("name") or "").strip()
        ]

    async def health(self) -> ProviderHealth:
        configured = bool(self.config.base_url and (self.config.provider != "openrouter" or self.config.api_key))
        try:
            models = await self.list_models()
            return ProviderHealth(
                provider=self.config.provider,
                configured=configured,
                reachable=True,
                model=self.config.model,
                base_url=self.config.base_url,
                hosted=self.config.is_hosted,
                models=models,
            )
        except Exception as exc:
            return ProviderHealth(
                provider=self.config.provider,
                configured=configured,
                reachable=False,
                model=self.config.model,
                base_url=self.config.base_url,
                hosted=self.config.is_hosted,
                models=[],
                error=str(exc),
            )


class OllamaChatProvider(ChatProvider):
    def __init__(
        self,
        config: PdfTreeProviderConfig,
        *,
        client: httpx.AsyncClient | None = None,
        owns_client: bool = False,
    ) -> None:
        self.config = config
        self._client = client or httpx.AsyncClient()
        self._owns_client = owns_client or client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> str:
        options: dict[str, Any] = {"temperature": temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        payload = {
            "model": model or self.config.model,
            "messages": list(messages),
            "stream": False,
            "options": options,
        }
        response = await self._client.post(
            f"{self.config.base_url}/api/chat",
            json=payload,
            timeout=timeout or self.config.timeout_seconds,
        )
        if response.status_code >= 400:
            raise PdfTreeProviderError(f"ollama returned HTTP {response.status_code}: {response.text[:300]}")
        data = response.json()
        return str(data.get("message", {}).get("content", "")).strip()

    async def list_models(self) -> list[str]:
        response = await self._client.get(
            f"{self.config.base_url}/api/tags",
            timeout=min(self.config.timeout_seconds, 10),
        )
        if response.status_code >= 400:
            raise PdfTreeProviderError(f"ollama model listing returned HTTP {response.status_code}")
        data = response.json()
        return [
            str(item.get("name") or "").strip()
            for item in data.get("models", [])
            if str(item.get("name") or "").strip()
        ]

    async def health(self) -> ProviderHealth:
        configured = bool(self.config.base_url and self.config.model)
        try:
            models = await self.list_models()
            return ProviderHealth(
                provider=self.config.provider,
                configured=configured,
                reachable=True,
                model=self.config.model,
                base_url=self.config.base_url,
                hosted=False,
                models=models,
            )
        except Exception as exc:
            return ProviderHealth(
                provider=self.config.provider,
                configured=configured,
                reachable=False,
                model=self.config.model,
                base_url=self.config.base_url,
                hosted=False,
                models=[],
                error=str(exc),
            )


def build_chat_provider(
    config: PdfTreeProviderConfig,
    *,
    client: httpx.AsyncClient | None = None,
) -> ChatProvider:
    if config.provider == "ollama":
        return OllamaChatProvider(config, client=client)
    return OpenAICompatibleChatProvider(config, client=client)
