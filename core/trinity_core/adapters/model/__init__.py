"""Provider-neutral model adapter contracts and implementations."""

from .base import (
    DeterministicModelProvider,
    ModelProviderError,
    TrinityModelProvider,
    UnsupportedModelProviderError,
    build_model_provider,
)
from .mistral_cli import MistralCLIError, MistralCLIModelProvider
from .ollama import OllamaClientError, OllamaModelProvider

__all__ = [
    "DeterministicModelProvider",
    "MistralCLIError",
    "MistralCLIModelProvider",
    "ModelProviderError",
    "OllamaClientError",
    "OllamaModelProvider",
    "TrinityModelProvider",
    "UnsupportedModelProviderError",
    "build_model_provider",
]
