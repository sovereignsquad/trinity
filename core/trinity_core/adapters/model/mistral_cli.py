"""Bounded Mistral CLI-backed provider implementation for Trinity role runners."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from trinity_core.adapters.model.base import ModelProviderError
from trinity_core.model_config import TrinityRoleRoute


class MistralCLIError(ModelProviderError):
    """Raised when the Mistral CLI backend cannot satisfy a Trinity request."""


@dataclass(frozen=True)
class MistralCLIModelProvider:
    """Concrete provider for the current vibe-only Mistral CLI execution path."""

    executable: str
    extra_args: tuple[str, ...] = ()
    timeout_seconds: float = 45.0
    mode: str = "vibe"
    model_binding: str = "advisory"
    provider_name: str = "mistral-cli"
    supports_model_inventory: bool = False
    request_diagnostics: list[dict[str, Any]] = field(
        default_factory=list, init=False, repr=False, compare=False
    )

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
        started_at = datetime.now(UTC)
        started_perf = perf_counter()
        diag = {
            "started_at": started_at.isoformat(),
            "kind": "chat_json",
            "provider": self.provider_name,
            "model": route.model,
            "model_id": route.model_id,
            "timeout_seconds": (
                timeout_seconds if timeout_seconds is not None else self.timeout_seconds
            ),
            "command": command[:4],
        }
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds if timeout_seconds is not None else self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            diag.update({
                "status": "timeout",
                "duration_ms": round((perf_counter() - started_perf) * 1000, 3),
                "error": str(exc),
            })
            self.request_diagnostics.append(diag)
            raise MistralCLIError(
                "Mistral CLI timed out after "
                f"{timeout_seconds if timeout_seconds is not None else self.timeout_seconds:.0f}s."
            ) from exc
        except OSError as exc:
            diag.update({
                "status": "launch_error",
                "duration_ms": round((perf_counter() - started_perf) * 1000, 3),
                "error": str(exc),
            })
            self.request_diagnostics.append(diag)
            raise MistralCLIError(
                f"Mistral CLI process launch failed: {exc}"
            ) from exc

        diag.update({
            "status": "ok" if result.returncode == 0 else "nonzero_exit",
            "duration_ms": round((perf_counter() - started_perf) * 1000, 3),
            "returncode": result.returncode,
            "stdout_bytes": len((result.stdout or "").encode("utf-8")),
            "stderr_bytes": len((result.stderr or "").encode("utf-8")),
        })
        if result.returncode != 0:
            diag["error"] = (result.stderr or "").strip()[:500]
        self.request_diagnostics.append(diag)

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
