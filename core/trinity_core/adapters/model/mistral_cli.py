"""Mistral CLI-backed provider implementation for Trinity role runners."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from trinity_core.adapters.model.base import ModelProviderError
from trinity_core.model_config import TrinityRoleRoute


class MistralCLIError(ModelProviderError):
    """Raised when the Mistral CLI backend cannot satisfy a Trinity request."""


@dataclass(frozen=True)
class MistralCLIModelProvider:
    """Concrete provider for Mistral CLI programmatic execution."""

    executable: str
    extra_args: tuple[str, ...] = ()
    timeout_seconds: float = 45.0
    mode: str = "vibe"
    model_binding: str = "advisory"
    provider_name: str = "mistral-cli"
    supports_model_inventory: bool = False

    def chat_json(
        self,
        *,
        route: TrinityRoleRoute,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        executable_path = shutil.which(self.executable)
        if not executable_path:
            raise MistralCLIError(
                f"Mistral CLI executable is not available: {self.executable}"
            )
        if self.mode != "vibe":
            raise MistralCLIError(f"Unsupported mistral-cli mode: {self.mode}")
        if self.model_binding not in {"advisory"}:
            raise MistralCLIError(
                "Unsupported mistral-cli model binding: "
                f"{self.model_binding}"
            )

        prompt = (
            "Return only one valid JSON object.\n\n"
            f"System instructions:\n{system_prompt}\n\n"
            f"User request:\n{user_prompt}\n\n"
            f"Route role: {route.provider}:{route.model}\n"
            "The configured route model is advisory only for this provider."
        )
        command = [
            executable_path,
            "--prompt",
            prompt,
            "--output",
            "json",
            "--max-turns",
            "1",
            "--trust",
            *self.extra_args,
        ]
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise MistralCLIError(
                f"Mistral CLI timed out after {self.timeout_seconds:.0f}s."
            ) from exc
        except OSError as exc:
            raise MistralCLIError(
                f"Mistral CLI process launch failed: {exc}"
            ) from exc

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise MistralCLIError(
                "Mistral CLI returned a non-zero exit status"
                f" ({result.returncode}): {stderr or 'no stderr'}"
            )

        stdout = (result.stdout or "").strip()
        if not stdout:
            raise MistralCLIError("Mistral CLI returned empty output.")
        return _extract_structured_payload(stdout)

    def list_models(self) -> tuple[dict[str, Any], ...]:
        if not shutil.which(self.executable):
            raise MistralCLIError(
                f"Mistral CLI executable is not available: {self.executable}"
            )
        return ()


def _extract_structured_payload(raw: str) -> dict[str, Any]:
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MistralCLIError("Mistral CLI returned invalid JSON.") from exc

    payload = _payload_from_decoded(decoded)
    if payload is not None:
        return payload
    raise MistralCLIError("Mistral CLI returned a JSON payload without assistant content.")


def _payload_from_decoded(decoded: Any) -> dict[str, Any] | None:
    if isinstance(decoded, dict):
        if _looks_like_runtime_json(decoded):
            return decoded
        assistant_payload = _extract_assistant_payload(decoded)
        if assistant_payload is not None:
            return assistant_payload
        for value in decoded.values():
            candidate = _payload_from_decoded(value)
            if candidate is not None:
                return candidate
        return None

    if isinstance(decoded, list):
        for item in reversed(decoded):
            candidate = _payload_from_decoded(item)
            if candidate is not None:
                return candidate
        return None

    if isinstance(decoded, str):
        text = decoded.strip()
        if not text:
            return None
        try:
            nested = json.loads(_extract_json_object(text))
        except json.JSONDecodeError:
            return None
        if isinstance(nested, dict):
            return nested
    return None


def _extract_assistant_payload(decoded: dict[str, Any]) -> dict[str, Any] | None:
    messages = decoded.get("messages")
    if not isinstance(messages, list):
        return None
    for message in reversed(messages):
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "").strip().lower()
        if role != "assistant":
            continue
        content = message.get("content")
        if isinstance(content, str):
            try:
                parsed = json.loads(_extract_json_object(content))
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if not isinstance(text, str):
                    continue
                try:
                    parsed = json.loads(_extract_json_object(text))
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    return parsed
    return None


def _looks_like_runtime_json(decoded: dict[str, Any]) -> bool:
    if "messages" in decoded:
        return False
    return True


def _extract_json_object(raw: str) -> str:
    text = str(raw or "").strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text
