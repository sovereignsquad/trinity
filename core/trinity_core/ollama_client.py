"""Minimal Ollama chat client for Trinity role runners."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from trinity_core.model_config import TrinityRoleRoute


class OllamaClientError(RuntimeError):
    """Raised when the Ollama backend cannot satisfy a Trinity request."""


@dataclass(frozen=True)
class OllamaChatClient:
    base_url: str
    timeout_seconds: float = 45.0

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
        endpoint = f"{self.base_url.rstrip('/')}/api/chat"
        req = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
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
            payload = json.loads(raw)
            content = payload["message"]["content"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise OllamaClientError("Ollama returned an invalid chat payload.") from exc

        try:
            return json.loads(_extract_json_object(content))
        except json.JSONDecodeError as exc:
            raise OllamaClientError("Ollama returned non-JSON content.") from exc


def _extract_json_object(raw: str) -> str:
    text = str(raw or "").strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text
