"""Runtime model routing for Trinity adapter roles."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from trinity_core.adapters import REPLY_ADAPTER_NAME, normalize_adapter_name
from trinity_core.ops.runtime_storage import resolve_adapter_runtime_paths

DEFAULT_TRINITY_GENERATOR_MODEL = "granite4:350m"
DEFAULT_TRINITY_REFINER_MODEL = "mistral:latest"
DEFAULT_TRINITY_EVALUATOR_MODEL = "qwen2.5:7b"


@dataclass(frozen=True)
class TrinityRoleRoute:
    provider: str
    model: str
    temperature: float
    keep_alive: str


@dataclass(frozen=True)
class TrinityReplyModelConfig:
    provider: str
    ollama_base_url: str
    timeout_seconds: float
    generator: TrinityRoleRoute
    refiner: TrinityRoleRoute
    evaluator: TrinityRoleRoute

    @property
    def llm_enabled(self) -> bool:
        return self.provider == "ollama"


def load_reply_model_config() -> TrinityReplyModelConfig:
    file_payload = _load_config_file(REPLY_ADAPTER_NAME)
    provider = _resolve_value(
        "TRINITY_MODEL_PROVIDER",
        file_payload,
        "provider",
        "deterministic",
    ).lower()
    return TrinityReplyModelConfig(
        provider=provider,
        ollama_base_url=_resolve_ollama_base_url(file_payload),
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


def save_reply_model_config(config: TrinityReplyModelConfig) -> Path:
    path = config_path_for_adapter(REPLY_ADAPTER_NAME)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_model_config_for_adapter(adapter_name: str) -> TrinityReplyModelConfig:
    normalized_adapter = normalize_adapter_name(adapter_name)
    if normalized_adapter != REPLY_ADAPTER_NAME:
        raise ValueError(f"Unsupported model configuration adapter: {normalized_adapter}.")
    return load_reply_model_config()


def save_model_config_for_adapter(
    adapter_name: str,
    config: TrinityReplyModelConfig,
) -> Path:
    normalized_adapter = normalize_adapter_name(adapter_name)
    if normalized_adapter != REPLY_ADAPTER_NAME:
        raise ValueError(f"Unsupported model configuration adapter: {normalized_adapter}.")
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
    raw = str(os.environ.get(env_key, file_payload.get(file_key, default)) or "").strip()
    return raw or default


def _resolve_float(
    env_key: str,
    file_payload: dict[str, Any],
    file_key: str,
    default: float,
    *,
    minimum: float,
    maximum: float,
) -> float:
    raw = os.environ.get(env_key, file_payload.get(file_key, default))
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))
