"""Provider-neutral model adapter primitives for Trinity runtime roles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from trinity_core.model_config import TrinityModelConfig, TrinityRoleRoute


class ModelProviderError(RuntimeError):
    """Raised when a concrete model provider cannot satisfy a Trinity request."""


class UnsupportedModelProviderError(ModelProviderError):
    """Raised when Trinity is configured with a provider not implemented in this repo."""


@runtime_checkable
class TrinityModelProvider(Protocol):
    """Capability provider used by runtime stages without backend-specific coupling."""

    provider_name: str
    supports_model_inventory: bool

    def chat_json(
        self,
        *,
        route: TrinityRoleRoute,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        """Execute one structured chat request through the provider."""

    def list_models(self) -> tuple[dict[str, Any], ...]:
        """Return provider inventory when supported."""


@dataclass(frozen=True)
class DeterministicModelProvider:
    """Non-LLM placeholder provider used for deterministic fallback mode."""

    provider_name: str = "deterministic"
    supports_model_inventory: bool = False

    def chat_json(
        self,
        *,
        route: TrinityRoleRoute,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        raise ModelProviderError(
            "Deterministic provider does not implement chat_json; "
            "runtime should use fallback runners."
        )

    def list_models(self) -> tuple[dict[str, Any], ...]:
        return ()


def build_model_provider(config: TrinityModelConfig) -> TrinityModelProvider:
    """Construct the configured provider implementation for runtime use."""

    provider = str(config.provider or "").strip().lower()
    if provider == "deterministic":
        return DeterministicModelProvider()
    if provider == "ollama":
        from trinity_core.adapters.model.ollama import OllamaModelProvider

        return OllamaModelProvider(
            base_url=str(config.ollama_base_url or "").strip(),
            timeout_seconds=config.timeout_seconds,
        )
    if provider == "mistral-cli":
        from trinity_core.adapters.model.mistral_cli import MistralCLIModelProvider

        return MistralCLIModelProvider(
            executable=str(config.mistral_cli_executable or "").strip(),
            extra_args=tuple(config.mistral_cli_args),
            timeout_seconds=config.timeout_seconds,
            mode=str(config.mistral_cli_mode or "").strip().lower(),
            model_binding=str(config.mistral_cli_model_binding or "").strip().lower(),
        )
    raise UnsupportedModelProviderError(
        "Unsupported Trinity model provider: "
        f"{provider}. Supported providers: deterministic, ollama, mistral-cli."
    )
