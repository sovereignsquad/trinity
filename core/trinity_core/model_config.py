"""Runtime model routing for Trinity adapter roles."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from trinity_core.adapters import (
    REPLY_ADAPTER_NAME,
    normalize_adapter_name,
    require_supported_adapter,
)
from trinity_core.adapters.model.inventory import load_model_inventory
from trinity_core.ops.runtime_storage import resolve_adapter_runtime_paths

DEFAULT_TRINITY_GENERATOR_MODEL = "granite4:350m"
DEFAULT_TRINITY_REFINER_MODEL = "mistral:latest"
DEFAULT_TRINITY_EVALUATOR_MODEL = "qwen2.5:7b"
DEFAULT_TRINITY_FALLBACK_OLLAMA_GENERATOR_MODEL = "granite4:350m"
DEFAULT_TRINITY_FALLBACK_OLLAMA_REFINER_MODEL = "llama3.2:1b"
DEFAULT_TRINITY_FALLBACK_OLLAMA_EVALUATOR_MODEL = "llama3.2:1b"


@dataclass(frozen=True)
class TrinityRoleRoute:
    provider: str
    model: str
    temperature: float
    keep_alive: str
    model_id: str | None = None


@dataclass(frozen=True)
class TrinityModelConfig:
    provider: str
    ollama_base_url: str
    timeout_seconds: float
    generator: TrinityRoleRoute
    refiner: TrinityRoleRoute
    evaluator: TrinityRoleRoute
    mistral_cli_executable: str = "vibe"
    mistral_cli_args: tuple[str, ...] = ()
    mistral_cli_mode: str = "vibe"
    mistral_cli_model_binding: str = "advisory"

    @property
    def llm_enabled(self) -> bool:
        return self.provider != "deterministic"


TrinityReplyModelConfig = TrinityModelConfig


def load_reply_model_config() -> TrinityModelConfig:
    return load_model_config(REPLY_ADAPTER_NAME)


def load_model_config(adapter_name: str) -> TrinityModelConfig:
    file_payload = _load_config_file(normalize_adapter_name(adapter_name))
    provider = _resolve_value(
        "TRINITY_MODEL_PROVIDER",
        file_payload,
        "provider",
        "deterministic",
    ).lower()
    return TrinityModelConfig(
        provider=provider,
        ollama_base_url=_resolve_ollama_base_url(file_payload),
        mistral_cli_executable=_resolve_value(
            "TRINITY_MISTRAL_CLI_EXECUTABLE",
            file_payload,
            "mistral_cli_executable",
            "vibe",
        ),
        mistral_cli_args=_resolve_string_tuple(
            "TRINITY_MISTRAL_CLI_ARGS",
            file_payload,
            "mistral_cli_args",
            (),
        ),
        mistral_cli_mode=_resolve_value(
            "TRINITY_MISTRAL_CLI_MODE",
            file_payload,
            "mistral_cli_mode",
            "vibe",
        ).lower(),
        mistral_cli_model_binding=_resolve_value(
            "TRINITY_MISTRAL_CLI_MODEL_BINDING",
            file_payload,
            "mistral_cli_model_binding",
            "advisory",
        ).lower(),
        timeout_seconds=_resolve_float(
            "TRINITY_LLM_TIMEOUT_SECONDS",
            file_payload,
            "timeout_seconds",
            45.0,
            minimum=1.0,
            maximum=300.0,
        ),
        generator=TrinityRoleRoute(
            provider=provider,
            model=_resolve_value(
                "TRINITY_GENERATOR_MODEL",
                file_payload,
                "generator_model",
                DEFAULT_TRINITY_GENERATOR_MODEL,
            ),
            model_id=_resolve_role_model_id(
                env_key="TRINITY_GENERATOR_MODEL_ID",
                file_payload=file_payload,
                role_key="generator",
                file_key="generator_model_id",
                provider=provider,
                model=_resolve_value(
                    "TRINITY_GENERATOR_MODEL",
                    file_payload,
                    "generator_model",
                    DEFAULT_TRINITY_GENERATOR_MODEL,
                ),
            ),
            temperature=_resolve_float(
                "TRINITY_GENERATOR_TEMPERATURE",
                file_payload,
                "generator_temperature",
                0.25,
                minimum=0.0,
                maximum=2.0,
            ),
            keep_alive=_resolve_value(
                "TRINITY_GENERATOR_KEEP_ALIVE",
                file_payload,
                "generator_keep_alive",
                "10m",
            ),
        ),
        refiner=TrinityRoleRoute(
            provider=provider,
            model=_resolve_value(
                "TRINITY_REFINER_MODEL",
                file_payload,
                "refiner_model",
                DEFAULT_TRINITY_REFINER_MODEL,
            ),
            model_id=_resolve_role_model_id(
                env_key="TRINITY_REFINER_MODEL_ID",
                file_payload=file_payload,
                role_key="refiner",
                file_key="refiner_model_id",
                provider=provider,
                model=_resolve_value(
                    "TRINITY_REFINER_MODEL",
                    file_payload,
                    "refiner_model",
                    DEFAULT_TRINITY_REFINER_MODEL,
                ),
            ),
            temperature=_resolve_float(
                "TRINITY_REFINER_TEMPERATURE",
                file_payload,
                "refiner_temperature",
                0.35,
                minimum=0.0,
                maximum=2.0,
            ),
            keep_alive=_resolve_value(
                "TRINITY_REFINER_KEEP_ALIVE",
                file_payload,
                "refiner_keep_alive",
                "10m",
            ),
        ),
        evaluator=TrinityRoleRoute(
            provider=provider,
            model=_resolve_value(
                "TRINITY_EVALUATOR_MODEL",
                file_payload,
                "evaluator_model",
                DEFAULT_TRINITY_EVALUATOR_MODEL,
            ),
            model_id=_resolve_role_model_id(
                env_key="TRINITY_EVALUATOR_MODEL_ID",
                file_payload=file_payload,
                role_key="evaluator",
                file_key="evaluator_model_id",
                provider=provider,
                model=_resolve_value(
                    "TRINITY_EVALUATOR_MODEL",
                    file_payload,
                    "evaluator_model",
                    DEFAULT_TRINITY_EVALUATOR_MODEL,
                ),
            ),
            temperature=_resolve_float(
                "TRINITY_EVALUATOR_TEMPERATURE",
                file_payload,
                "evaluator_temperature",
                0.1,
                minimum=0.0,
                maximum=2.0,
            ),
            keep_alive=_resolve_value(
                "TRINITY_EVALUATOR_KEEP_ALIVE",
                file_payload,
                "evaluator_keep_alive",
                "10m",
            ),
        ),
    )


def resolve_runtime_model_config(config: TrinityModelConfig) -> tuple[TrinityModelConfig, dict[str, Any]]:
    provider = str(config.provider or "").strip().lower()
    resolution = {
        "configured_provider": provider or "deterministic",
        "effective_provider": provider or "deterministic",
        "fallback_applied": False,
        "reason": None,
    }
    if provider == "mistral-cli" and not _mistral_cli_available():
        fallback = _build_ollama_fallback_config(config)
        resolution.update({
            "effective_provider": fallback.provider,
            "fallback_applied": True,
            "reason": "mistral_cli_unavailable",
        })
        return fallback, resolution
    return config, resolution


def config_path() -> Path:
    return config_path_for_adapter(REPLY_ADAPTER_NAME)


def config_path_for_adapter(adapter_name: str) -> Path:
    explicit = os.environ.get("TRINITY_MODEL_CONFIG_PATH")
    if explicit:
        return Path(explicit).expanduser().resolve()
    adapter_paths = resolve_adapter_runtime_paths(
        normalize_adapter_name(adapter_name),
        repo_root=Path(__file__).resolve().parents[3],
    )
    return adapter_paths.root_dir / "model_config.json"


def save_reply_model_config(config: TrinityModelConfig) -> Path:
    path = config_path_for_adapter(REPLY_ADAPTER_NAME)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_model_config_for_adapter(adapter_name: str) -> TrinityModelConfig:
    normalized_adapter = require_supported_adapter(adapter_name)
    return load_model_config(normalized_adapter)


def save_model_config_for_adapter(
    adapter_name: str,
    config: TrinityModelConfig,
) -> Path:
    normalized_adapter = require_supported_adapter(adapter_name)
    path = config_path_for_adapter(normalized_adapter)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _load_config_file(adapter_name: str) -> dict[str, Any]:
    path = config_path_for_adapter(adapter_name)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        return {}


def _resolve_role_model_id(
    *,
    env_key: str,
    file_payload: dict[str, Any],
    role_key: str,
    file_key: str,
    provider: str,
    model: str,
) -> str | None:
    explicit = _optional_resolve_value(env_key, file_payload, file_key)
    if explicit is not None:
        return explicit
    explicit_nested = _nested_optional_string(file_payload, role_key, "model_id")
    if explicit_nested is not None:
        return explicit_nested
    return _derive_model_id_from_inventory(provider=provider, model=model)


def _resolve_ollama_base_url(file_payload: dict[str, Any]) -> str:
    raw = _resolve_value(
        "TRINITY_OLLAMA_BASE_URL",
        file_payload,
        "ollama_base_url",
        os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"),
    )
    if raw.startswith(("http://", "https://")):
        return raw.rstrip("/")
    return f"http://{raw.rstrip('/')}"


def _resolve_value(env_key: str, file_payload: dict[str, Any], file_key: str, default: str) -> str:
    raw = str(
        os.environ.get(
            env_key,
            _file_value(file_payload, file_key, default),
        )
        or ""
    ).strip()
    return raw or default


def _optional_resolve_value(
    env_key: str,
    file_payload: dict[str, Any],
    file_key: str,
) -> str | None:
    raw = os.environ.get(env_key)
    if raw is not None:
        value = str(raw or "").strip()
        return value or None
    file_value = _file_value(file_payload, file_key, None)
    if file_value is None:
        return None
    value = str(file_value or "").strip()
    return value or None


def _resolve_string_tuple(
    env_key: str,
    file_payload: dict[str, Any],
    file_key: str,
    default: tuple[str, ...],
) -> tuple[str, ...]:
    raw = os.environ.get(env_key)
    if raw is not None:
        return tuple(part for part in str(raw).split() if part)

    file_value = _file_value(file_payload, file_key, default)
    if isinstance(file_value, (list, tuple)):
        return tuple(str(item).strip() for item in file_value if str(item).strip())
    if isinstance(file_value, str):
        return tuple(part for part in file_value.split() if part)
    return default


def _resolve_float(
    env_key: str,
    file_payload: dict[str, Any],
    file_key: str,
    default: float,
    *,
    minimum: float,
    maximum: float,
) -> float:
    raw = os.environ.get(env_key, _file_value(file_payload, file_key, default))
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _file_value(file_payload: dict[str, Any], file_key: str, default: object) -> object:
    if file_key in file_payload:
        return file_payload[file_key]
    if file_key.endswith("_model"):
        role_key = file_key[: -len("_model")]
        return _nested_role_value(file_payload, role_key, "model", default)
    if file_key.endswith("_model_id"):
        role_key = file_key[: -len("_model_id")]
        return _nested_role_value(file_payload, role_key, "model_id", default)
    if file_key.endswith("_temperature"):
        role_key = file_key[: -len("_temperature")]
        return _nested_role_value(file_payload, role_key, "temperature", default)
    if file_key.endswith("_keep_alive"):
        role_key = file_key[: -len("_keep_alive")]
        return _nested_role_value(file_payload, role_key, "keep_alive", default)
    return default


def _nested_role_value(
    file_payload: dict[str, Any],
    role_key: str,
    nested_key: str,
    default: object,
) -> object:
    nested = file_payload.get(role_key)
    if not isinstance(nested, dict):
        return default
    return nested.get(nested_key, default)


def _nested_optional_string(
    file_payload: dict[str, Any],
    role_key: str,
    nested_key: str,
) -> str | None:
    nested = file_payload.get(role_key)
    if not isinstance(nested, dict):
        return None
    value = str(nested.get(nested_key) or "").strip()
    return value or None


def _derive_model_id_from_inventory(*, provider: str, model: str) -> str | None:
    inventory = load_model_inventory(repo_root=Path(__file__).resolve().parents[3])
    entry = inventory.find_for_route(provider=provider, route_model=model)
    return entry.model_id if entry is not None else None


def _mistral_cli_available() -> bool:
    api_key = str(os.environ.get("MISTRAL_API_KEY") or "").strip()
    return bool(api_key)


def _build_ollama_fallback_config(config: TrinityModelConfig) -> TrinityModelConfig:
    generator_model = str(
        os.environ.get("TRINITY_FALLBACK_OLLAMA_GENERATOR_MODEL")
        or DEFAULT_TRINITY_FALLBACK_OLLAMA_GENERATOR_MODEL
    ).strip()
    refiner_model = str(
        os.environ.get("TRINITY_FALLBACK_OLLAMA_REFINER_MODEL")
        or DEFAULT_TRINITY_FALLBACK_OLLAMA_REFINER_MODEL
    ).strip()
    evaluator_model = str(
        os.environ.get("TRINITY_FALLBACK_OLLAMA_EVALUATOR_MODEL")
        or DEFAULT_TRINITY_FALLBACK_OLLAMA_EVALUATOR_MODEL
    ).strip()
    return replace(
        config,
        provider="ollama",
        generator=replace(
            config.generator,
            provider="ollama",
            model=generator_model,
            model_id=_derive_model_id_from_inventory(provider="ollama", model=generator_model),
        ),
        refiner=replace(
            config.refiner,
            provider="ollama",
            model=refiner_model,
            model_id=_derive_model_id_from_inventory(provider="ollama", model=refiner_model),
        ),
        evaluator=replace(
            config.evaluator,
            provider="ollama",
            model=evaluator_model,
            model_id=_derive_model_id_from_inventory(provider="ollama", model=evaluator_model),
        ),
    )
