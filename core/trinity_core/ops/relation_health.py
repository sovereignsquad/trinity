"""Bounded seam-health helpers for external and cross-repo Trinity relations."""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from trinity_core.adapters import require_supported_adapter
from trinity_core.adapters.model.base import UnsupportedModelProviderError, build_model_provider
from trinity_core.model_config import load_model_config_for_adapter
from trinity_core.ops.foundation_policy import (
    TrinityFoundationPolicy,
    build_foundation_provider_alignment,
    foundation_policy_path,
    load_foundation_policy,
)
from trinity_core.ops.gobii_tasks import GobiiTaskClient, GobiiTaskClientError

TRAIN_STATUS_CONTRACT_VERSION = "trinity_train_status.v1"
PROVIDER_SMOKE_CONTRACT_VERSION = "trinity_provider_smoke.v1"
REPLY_COMPAT_CONTRACT_VERSION = "trinity_reply_compat.v1"
GOBII_STATUS_CONTRACT_VERSION = "trinity_gobii_status.v1"

REPLY_REQUIRED_PATHS = (
    "chat/brain-runtime.js",
    "chat/routes/messaging.js",
    "chat/js/api.js",
    "app/reply-app/Sources/NativeSettingsView.swift",
)


class TrainClientError(RuntimeError):
    """Structured Train seam transport error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = str(code)


def request_train_json(
    *,
    url: str,
    payload: dict[str, Any],
    timeout_seconds: float = 45.0,
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return _read_train_json(request, timeout_seconds=timeout_seconds)


def probe_train_seam(
    *,
    default_train_api_base_url: str,
    train_api_base_url: str | None = None,
    train_root_dir: str | Path | None = None,
    transport: str = "both",
    timeout_seconds: float = 10.0,
    preferred_transport: str = "cli",
) -> dict[str, Any]:
    normalized = str(transport or "both").strip().lower()
    if normalized not in {"api", "cli", "both"}:
        raise ValueError("transport must be one of: api, cli, both.")
    base_url = str(
        train_api_base_url
        or os.environ.get("TRINITY_TRAIN_API_BASE_URL")
        or default_train_api_base_url
    ).rstrip("/")
    root_dir = _resolve_train_root_dir(train_root_dir)
    payload = {
        "contract_version": TRAIN_STATUS_CONTRACT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "transport": normalized,
        "train_api_base_url": base_url,
        "train_root_dir": str(root_dir),
        "preferred_transport": preferred_transport,
        "api": _probe_train_api(base_url, timeout_seconds=timeout_seconds)
        if normalized in {"api", "both"}
        else {"enabled": False, "ready": False, "state": "skipped"},
        "cli": _probe_train_cli(root_dir, timeout_seconds=timeout_seconds)
        if normalized in {"cli", "both"}
        else {"enabled": False, "ready": False, "state": "skipped"},
    }
    api_ready = bool(payload["api"].get("ready"))
    cli_ready = bool(payload["cli"].get("ready"))
    payload["ready"] = api_ready or cli_ready
    normalized_preferred = str(preferred_transport or "cli").strip().lower()
    if normalized_preferred == "api" and api_ready:
        payload["recommended_transport"] = "api"
    elif normalized_preferred == "cli" and cli_ready:
        payload["recommended_transport"] = "cli"
    else:
        payload["recommended_transport"] = "api" if api_ready else "cli" if cli_ready else None
    return payload


def smoke_provider_routes(
    *,
    adapter_name: str,
    role_names: tuple[str, ...] = ("generator", "refiner", "evaluator"),
    inventory_only: bool = False,
) -> dict[str, Any]:
    normalized_adapter = require_supported_adapter(adapter_name)
    config = load_model_config_for_adapter(normalized_adapter)
    payload = {
        "contract_version": PROVIDER_SMOKE_CONTRACT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "adapter": normalized_adapter,
        "provider": config.provider,
        "inventory_only": bool(inventory_only),
        "ready": False,
        "state": "disabled",
        "roles": {},
    }
    if not config.llm_enabled:
        for role_name in role_names:
            payload["roles"][role_name] = {
                "state": "disabled",
                "ready": False,
                "reason": "llm_disabled",
            }
        return payload

    try:
        provider = build_model_provider(config)
    except UnsupportedModelProviderError as exc:
        payload["state"] = "unsupported"
        payload["error"] = str(exc)
        for role_name in role_names:
            payload["roles"][role_name] = {
                "state": "unsupported",
                "ready": False,
                "reason": "provider_unsupported",
            }
        return payload

    installed_names: set[str] = set()
    inventory_error: str | None = None
    if provider.supports_model_inventory:
        try:
            installed_names = {
                str(item.get("name") or "").strip()
                for item in provider.list_models()
                if str(item.get("name") or "").strip()
            }
        except Exception as exc:
            inventory_error = str(exc)

    all_ready = True
    for role_name in role_names:
        route = getattr(config, role_name)
        result: dict[str, Any] = {
            "provider": route.provider,
            "model": route.model,
            "model_id": route.model_id,
        }
        if inventory_error is not None:
            result.update(
                {
                    "state": "offline",
                    "ready": False,
                    "reason": "inventory_probe_failed",
                    "error": inventory_error,
                }
            )
            all_ready = False
        elif inventory_only:
            installed = (not provider.supports_model_inventory) or route.model in installed_names
            result.update(
                {
                    "state": "ready" if installed else "missing_model",
                    "ready": installed,
                    "inventory_checked": provider.supports_model_inventory,
                }
            )
            all_ready = all_ready and installed
        else:
            try:
                smoke = provider.chat_json(
                    route=route,
                    system_prompt="Return only one valid JSON object.",
                    user_prompt=(
                        "Return exactly this JSON object with no extra text: "
                        f'{{"ok": true, "role": "{role_name}"}}'
                    ),
                )
                result.update({"state": "ready", "ready": True, "response": smoke})
            except Exception as exc:
                result.update(
                    {
                        "state": "offline",
                        "ready": False,
                        "reason": classify_provider_error_code(exc),
                        "error": str(exc),
                    }
                )
                all_ready = False
        payload["roles"][role_name] = result

    payload["ready"] = all_ready
    payload["state"] = "ready" if all_ready else "degraded"
    return payload


def check_reply_compatibility(*, reply_root_dir: str | Path | None = None) -> dict[str, Any]:
    root_dir = _resolve_reply_root_dir(reply_root_dir)
    required_files: list[dict[str, Any]] = []
    required_ready = True
    for relative_path in REPLY_REQUIRED_PATHS:
        full_path = root_dir / relative_path
        exists = full_path.exists()
        required_ready = required_ready and exists
        required_files.append(
            {
                "path": relative_path,
                "full_path": str(full_path),
                "exists": exists,
            }
        )
    contract_checks = _build_reply_contract_check_payload()
    ready = bool(root_dir.exists()) and required_ready and all(contract_checks.values())
    return {
        "contract_version": REPLY_COMPAT_CONTRACT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "reply_root_dir": str(root_dir),
        "repo_present": root_dir.exists(),
        "required_files_ready": required_ready,
        "required_files": required_files,
        "trinity_contract_checks": contract_checks,
        "ready": ready,
        "state": "ready" if ready else "degraded",
    }


def probe_gobii_seam(
    *,
    adapter_name: str,
    base_url: str,
    api_key_env: str = "GOBII_API_KEY",
    check_live: bool = False,
) -> dict[str, Any]:
    normalized_adapter = require_supported_adapter(adapter_name)
    api_key = os.environ.get(str(api_key_env or "GOBII_API_KEY"), "").strip()
    payload = {
        "contract_version": GOBII_STATUS_CONTRACT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "adapter": normalized_adapter,
        "base_url": str(base_url).strip(),
        "api_key_env": str(api_key_env or "GOBII_API_KEY"),
        "api_key_present": bool(api_key),
        "check_live": bool(check_live),
        "ready": False,
        "state": "not_configured",
    }
    if not api_key:
        payload["reason"] = "missing_api_key"
        return payload
    if not check_live:
        payload["ready"] = True
        payload["state"] = "configured"
        return payload
    try:
        records = GobiiTaskClient(
            base_url=str(base_url).strip(),
            api_key=api_key,
        ).list_tasks(page_size=1)
        payload["ready"] = True
        payload["state"] = "online"
        payload["task_count_sample"] = len(records)
        return payload
    except GobiiTaskClientError as exc:
        payload["state"] = "offline"
        payload["reason"] = classify_gobii_error_code(exc)
        payload["error"] = str(exc)
        return payload


def run_foundation_check(
    *,
    adapter_name: str,
    default_train_api_base_url: str,
    train_api_base_url: str | None = None,
    train_root_dir: str | Path | None = None,
    train_transport: str | None = None,
    reply_root_dir: str | Path | None = None,
    gobii_api_base_url: str = "https://gobii.ai",
    gobii_api_key_env: str = "GOBII_API_KEY",
    check_gobii_live: bool = False,
    foundation_policy: TrinityFoundationPolicy | None = None,
) -> dict[str, Any]:
    normalized_adapter = require_supported_adapter(adapter_name)
    policy = foundation_policy or load_foundation_policy()
    config = load_model_config_for_adapter(normalized_adapter)
    adapter_policy = policy.adapter_policy(normalized_adapter)
    train_payload = probe_train_seam(
        default_train_api_base_url=default_train_api_base_url,
        train_api_base_url=train_api_base_url,
        train_root_dir=train_root_dir,
        transport=str(train_transport or policy.train.default_transport),
        preferred_transport=policy.train.default_transport,
    )
    provider_alignment = build_foundation_provider_alignment(
        adapter_name=normalized_adapter,
        provider=config.provider,
        llm_enabled=config.llm_enabled,
        policy=policy,
    )
    if (
        config.llm_enabled
        or adapter_policy.preferred_live_provider
        or adapter_policy.release_gate_roles
    ):
        smoke_roles = adapter_policy.release_gate_roles or ("generator", "refiner", "evaluator")
        provider_smoke = smoke_provider_routes(
            adapter_name=normalized_adapter,
            role_names=tuple(smoke_roles),
            inventory_only=False,
        )
    else:
        provider_smoke = {
            "contract_version": PROVIDER_SMOKE_CONTRACT_VERSION,
            "generated_at": datetime.now(UTC).isoformat(),
            "adapter": normalized_adapter,
            "provider": config.provider,
            "inventory_only": False,
            "ready": True,
            "state": "skipped",
            "roles": {},
        }
    reply_compatibility = (
        check_reply_compatibility(reply_root_dir=reply_root_dir)
        if normalized_adapter == "reply"
        else None
    )
    gobii_status = probe_gobii_seam(
        adapter_name=normalized_adapter,
        base_url=str(gobii_api_base_url).strip(),
        api_key_env=str(gobii_api_key_env or "GOBII_API_KEY"),
        check_live=bool(check_gobii_live),
    )
    failures: list[str] = []
    warnings: list[str] = []
    preferred_transport = str(policy.train.default_transport).strip().lower()
    train_state = (
        train_payload.get(preferred_transport)
        if preferred_transport in {"api", "cli"}
        else {}
    )
    if not isinstance(train_state, dict) or not bool(train_state.get("ready")):
        failures.append(f"train_{preferred_transport}_not_ready")
    if not bool(provider_alignment.get("provider_supported")):
        failures.append("provider_not_supported_by_foundation_policy")
    if not bool(provider_alignment.get("provider_matches_preferred_live_provider")):
        failures.append("provider_not_on_preferred_live_path")
    if not bool(provider_smoke.get("ready")):
        failures.append("provider_smoke_failed")
    if reply_compatibility is not None and not bool(reply_compatibility.get("ready")):
        failures.append("reply_compatibility_failed")
    if bool(policy.optional_seams.gobii_required_for_release):
        if not bool(gobii_status.get("ready")):
            failures.append("gobii_required_but_not_ready")
    elif not bool(gobii_status.get("ready")):
        warnings.append("gobii_optional_not_ready")
    return {
        "contract_version": "trinity_foundation_check.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "adapter": normalized_adapter,
        "ready": not failures,
        "state": "ready" if not failures else "degraded",
        "failures": failures,
        "warnings": warnings,
        "foundation_policy": {
            "contract_version": policy.contract_version,
            "path": str(foundation_policy_path()),
            "train_default_transport": policy.train.default_transport,
            "optional_seams": {
                "gobii_required_for_release": policy.optional_seams.gobii_required_for_release
            },
        },
        "provider_alignment": provider_alignment,
        "train": train_payload,
        "provider_smoke": provider_smoke,
        "reply_compatibility": reply_compatibility,
        "gobii": gobii_status,
    }


def classify_provider_error_code(exc: Exception) -> str:
    message = str(exc).lower()
    if "executable is not available" in message:
        return "executable_missing"
    if "unsupported mistral-cli mode" in message:
        return "invalid_mode"
    if "unsupported mistral-cli model binding" in message:
        return "invalid_model_binding"
    if "timed out" in message:
        return "timeout"
    if "unreachable" in message:
        return "unreachable"
    if "non-zero exit status" in message:
        return "command_failed"
    return "provider_error"


def classify_gobii_error_code(exc: Exception) -> str:
    message = str(exc).lower()
    if "authentication failed" in message:
        return "auth_failed"
    if "timed out" in message:
        return "timeout"
    if "unreachable" in message:
        return "unreachable"
    if "invalid" in message:
        return "invalid_response"
    return "transport_error"


def _probe_train_api(base_url: str, *, timeout_seconds: float) -> dict[str, Any]:
    request = urllib.request.Request(f"{base_url}/health", method="GET")
    try:
        response = _read_train_raw(request, timeout_seconds=timeout_seconds)
    except TrainClientError as exc:
        return {
            "enabled": True,
            "ready": False,
            "state": exc.code,
            "detail": str(exc),
        }
    return {
        "enabled": True,
        "ready": True,
        "state": "online",
        "http_status": response.get("http_status"),
        "body": response.get("body"),
        "json": response.get("json"),
    }


def _probe_train_cli(root_dir: Path, *, timeout_seconds: float) -> dict[str, Any]:
    if not root_dir.exists():
        return {
            "enabled": True,
            "ready": False,
            "state": "missing_root_dir",
            "detail": f"Train root dir is missing: {root_dir}",
        }
    command = ["uv", "run", "python", "-m", "train_core.cli", "--help"]
    try:
        completed = subprocess.run(
            command,
            cwd=root_dir,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return {
            "enabled": True,
            "ready": False,
            "state": "timeout",
            "detail": f"Train CLI timed out after {timeout_seconds:.0f}s.",
        }
    except OSError as exc:
        return {
            "enabled": True,
            "ready": False,
            "state": "launch_failed",
            "detail": str(exc),
        }
    if completed.returncode != 0:
        return {
            "enabled": True,
            "ready": False,
            "state": "command_failed",
            "detail": completed.stderr.strip() or completed.stdout.strip() or "Train CLI failed.",
        }
    return {
        "enabled": True,
        "ready": True,
        "state": "online",
        "detail": "Train CLI responded to --help.",
    }


def _read_train_json(request: urllib.request.Request, *, timeout_seconds: float) -> dict[str, Any]:
    response = _read_train_raw(request, timeout_seconds=timeout_seconds)
    if not isinstance(response.get("json"), dict):
        raise TrainClientError("invalid_json", "Train returned invalid JSON.")
    return response["json"]


def _read_train_raw(
    request: urllib.request.Request,
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        try:
            response_context = urllib.request.urlopen(request, timeout=timeout_seconds)
        except TypeError:
            response_context = urllib.request.urlopen(request)
        with response_context as response:
            raw = response.read().decode("utf-8")
            http_status = getattr(response, "status", None)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise TrainClientError("http_error", f"Train HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, TimeoutError):
            raise TrainClientError("timeout", "Train request timed out.") from exc
        if isinstance(reason, ConnectionRefusedError):
            raise TrainClientError("connection_refused", "Train connection was refused.") from exc
        raise TrainClientError("unreachable", f"Train is unreachable: {reason}") from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None
    return {"http_status": http_status, "body": raw.strip(), "json": parsed}


def _build_reply_contract_check_payload() -> dict[str, bool]:
    from trinity_core.adapters.product.reply import (
        document_record_from_payload,
        memory_event_from_payload,
        outcome_event_from_payload,
        thread_snapshot_from_payload,
    )
    from trinity_core.cli import CLI_CONTRACT_VERSION, RUNTIME_STATUS_SCHEMA_VERSION
    from trinity_core.runtime import TrinityRuntime

    company_id = UUID("11111111-1111-1111-1111-111111111111")
    occurred_at = "2026-05-19T12:00:00+00:00"
    thread_snapshot_from_payload(
        {
            "company_id": str(company_id),
            "thread_ref": "reply:email:test@example.com",
            "channel": "email",
            "contact_handle": "test@example.com",
            "latest_inbound_text": "Can you send the latest draft?",
            "requested_at": occurred_at,
            "messages": [
                {
                    "message_id": "msg-1",
                    "role": "CONTACT",
                    "text": "Can you send the latest draft?",
                    "occurred_at": occurred_at,
                    "channel": "email",
                    "source": "email",
                    "handle": "test@example.com",
                }
            ],
        }
    )
    outcome_event_from_payload(
        {
            "cycle_id": "22222222-2222-2222-2222-222222222222",
            "company_id": str(company_id),
            "thread_ref": "reply:email:test@example.com",
            "channel": "email",
            "candidate_id": "33333333-3333-3333-3333-333333333333",
            "disposition": "SELECTED",
            "occurred_at": occurred_at,
        }
    )
    memory_event_from_payload(
        {
            "company_id": str(company_id),
            "source_ref": "reply:email:test@example.com:msg-1",
            "thread_ref": "reply:email:test@example.com",
            "channel": "email",
            "contact_handle": "test@example.com",
            "event_kind": "inbound_message_recorded",
            "occurred_at": occurred_at,
            "content_text": "Can you send the latest draft?",
        }
    )
    document_record_from_payload(
        {
            "company_id": str(company_id),
            "document_ref": "reply-doc-1",
            "source": "reply",
            "path": "notes/reply-note.txt",
            "title": "Reply note",
            "content_text": "Draft guidance for the thread.",
            "occurred_at": occurred_at,
        }
    )
    return {
        "reply_adapter_supported": True,
        "runtime_status_contract_declared": CLI_CONTRACT_VERSION == "trinity_cli.v1",
        "runtime_status_schema_supported": RUNTIME_STATUS_SCHEMA_VERSION >= 4,
        "payload_parsers_ok": True,
        "sample_runtime_ok": callable(getattr(TrinityRuntime, "suggest", None)),
    }


def _resolve_train_root_dir(train_root_dir: str | Path | None) -> Path:
    if train_root_dir is not None:
        return Path(train_root_dir).expanduser().resolve()
    configured = os.environ.get("TRINITY_TRAIN_ROOT_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[4] / "train"


def _resolve_reply_root_dir(reply_root_dir: str | Path | None) -> Path:
    if reply_root_dir is not None:
        return Path(reply_root_dir).expanduser().resolve()
    configured = os.environ.get("TRINITY_REPLY_ROOT_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[4] / "reply"
