"""Provider-neutral model adapter contracts and implementations."""

from .base import (
    DeterministicModelProvider,
    ModelProviderError,
    TrinityModelProvider,
    UnsupportedModelProviderError,
    build_model_provider,
)
from .inventory import (
    DEFAULT_TRINITY_MODELS_ROOT,
    ModelInventoryError,
    TrinityModelInventory,
    TrinityModelInventoryEntry,
    default_manifest_path,
    load_model_inventory,
    resolve_models_root,
)
from .mistral_cli import MistralCLIError, MistralCLIModelProvider
from .ollama import OllamaClientError, OllamaModelProvider

__all__ = [
    "DEFAULT_TRINITY_MODELS_ROOT",
    "DeterministicModelProvider",
    "ModelInventoryError",
    "MistralCLIError",
    "MistralCLIModelProvider",
    "ModelProviderError",
    "OllamaClientError",
    "OllamaModelProvider",
    "TrinityModelInventory",
    "TrinityModelInventoryEntry",
    "TrinityModelProvider",
    "UnsupportedModelProviderError",
    "build_model_provider",
    "default_manifest_path",
    "load_model_inventory",
    "resolve_models_root",
]
