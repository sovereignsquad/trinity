"""Core adapter primitives for product-specific Trinity runtime embeddings."""

from __future__ import annotations

from dataclasses import dataclass

REPLY_ADAPTER_NAME = "reply"
SPOT_ADAPTER_NAME = "spot"
SUPPORTED_ADAPTER_NAMES = (REPLY_ADAPTER_NAME, SPOT_ADAPTER_NAME)


@dataclass(frozen=True, slots=True)
class TrinityAdapterDescriptor:
    """Declared runtime adapter supported by this repository."""

    adapter_name: str
    display_name: str
    runtime_module: str
    default_contract_version: str | None = None


def normalize_adapter_name(adapter_name: str | None) -> str:
    """Normalize a caller-supplied adapter name into a stable storage key."""

    normalized = str(adapter_name or REPLY_ADAPTER_NAME).strip().lower()
    if not normalized:
        raise ValueError("adapter_name is required.")
    return normalized


def require_supported_adapter(adapter_name: str | None) -> str:
    """Validate adapter selection against the adapters implemented in this repo."""

    normalized = normalize_adapter_name(adapter_name)
    if normalized not in SUPPORTED_ADAPTER_NAMES:
        supported = ", ".join(SUPPORTED_ADAPTER_NAMES)
        raise ValueError(
            f"Unsupported Trinity adapter: {normalized}. Supported adapters: {supported}."
        )
    return normalized
