"""Ollama-backed model provider implementation for Trinity role runners."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from trinity_core.adapters.model.base import ModelProviderError
from trinity_core.model_config import TrinityRoleRoute


class OllamaClientError(ModelProviderError):
    """Raised when the Ollama backend cannot satisfy a Trinity request."""


@dataclass(frozen=True)
class OllamaModelProvider:
    """Concrete provider for Ollama-backed structured chat and model inventory."""

    base_url: str
    timeout_seconds: float = 45.0
    provider_name: str = "ollama"
    supports_model_inventory: bool = True

    def chat_json(
        self,
        *,
        route: TrinityRoleRoute,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        payload = {
            "model": route.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": "json",
            "keep_alive": route.keep_alive,
            "options": {"temperature": route.temperature},
        }
        payload = self._request_json("/api/chat", payload=payload, method="POST")

        try:
            content = payload["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise OllamaClientError("Ollama returned an invalid chat payload.") from exc

        try:
            return json.loads(_extract_json_object(content))
        except json.JSONDecodeError as exc:
            raise OllamaClientError("Ollama returned non-JSON content.") from exc

    def list_models(self) -> tuple[dict[str, Any], ...]:
        payload = self._request_json("/api/tags", method="GET")
        models = payload.get("models", [])
        if not isinstance(models, list):
            raise OllamaClientError("Ollama returned an invalid model inventory payload.")
        normalized: list[dict[str, Any]] = []
        for item in models:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            normalized.append(
                {
                    "name": name,
                    "size": item.get("size"),
                    "modified_at": item.get("modified_at"),
                    "digest": item.get("digest"),
                    "details": item.get("details") if isinstance(item.get("details"), dict) else {},
                }
            )
        return tuple(normalized)

    def _request_json(
        self,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        method: str = "POST",
    ) -> dict[str, Any]:
        endpoint = f"{self.base_url.rstrip('/')}{path}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise OllamaClientError(f"Ollama HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise OllamaClientError(f"Ollama is unreachable: {exc.reason}") from exc

        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OllamaClientError("Ollama returned invalid JSON.") from exc
        if not isinstance(decoded, dict):
            raise OllamaClientError("Ollama returned an unexpected JSON payload.")
        return decoded


def _extract_json_object(raw: str) -> str:
    text = str(raw or "").strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text
