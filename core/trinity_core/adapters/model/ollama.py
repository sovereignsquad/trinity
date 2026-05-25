"""Ollama-backed model provider implementation for Trinity role runners."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
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
    request_diagnostics: list[dict[str, Any]] = field(default_factory=list, init=False, repr=False, compare=False)

    def reset_request_diagnostics(self) -> None:
        self.request_diagnostics.clear()

    def get_request_diagnostics(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.request_diagnostics)

    def chat_json(
        self,
        *,
        route: TrinityRoleRoute,
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: float | None = None,
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
        payload = self._request_json(
            "/api/chat",
            payload=payload,
            method="POST",
            diagnostics={
                "kind": "chat_json",
                "provider": self.provider_name,
                "model": route.model,
                "model_id": route.model_id,
                "timeout_seconds": timeout_seconds if timeout_seconds is not None else self.timeout_seconds,
            },
            timeout_seconds=timeout_seconds,
        )

        try:
            content = payload["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise OllamaClientError("Ollama returned an invalid chat payload.") from exc

        try:
            return json.loads(_extract_json_object(content))
        except json.JSONDecodeError as exc:
            raise OllamaClientError("Ollama returned non-JSON content.") from exc

    def list_models(self) -> tuple[dict[str, Any], ...]:
        payload = self._request_json(
            "/api/tags",
            method="GET",
            diagnostics={"kind": "list_models", "provider": self.provider_name},
        )
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
        diagnostics: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        endpoint = f"{self.base_url.rstrip('/')}{path}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        started_at = datetime.now(UTC)
        started_perf = perf_counter()
        diag = {
            "started_at": started_at.isoformat(),
            "method": method,
            "endpoint": endpoint,
            "path": path,
            **(diagnostics or {}),
        }
        try:
            with request.urlopen(
                req,
                timeout=timeout_seconds if timeout_seconds is not None else self.timeout_seconds,
            ) as response:
                raw = response.read().decode("utf-8")
                diag.update({
                    "status": "ok",
                    "http_status": getattr(response, "status", None),
                    "duration_ms": round((perf_counter() - started_perf) * 1000, 3),
                    "response_bytes": len(raw.encode("utf-8")),
                })
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            diag.update({
                "status": "http_error",
                "http_status": exc.code,
                "duration_ms": round((perf_counter() - started_perf) * 1000, 3),
                "error": detail[:500],
            })
            self.request_diagnostics.append(diag)
            raise OllamaClientError(f"Ollama HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            diag.update({
                "status": "transport_error",
                "duration_ms": round((perf_counter() - started_perf) * 1000, 3),
                "error": str(exc.reason),
            })
            self.request_diagnostics.append(diag)
            raise OllamaClientError(f"Ollama is unreachable: {exc.reason}") from exc

        self.request_diagnostics.append(diag)

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
