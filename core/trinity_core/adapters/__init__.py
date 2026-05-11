"""Adapter descriptors and helpers for product-specific Trinity embeddings."""

from .base import (
    REPLY_ADAPTER_NAME,
    SPOT_ADAPTER_NAME,
    SUPPORTED_ADAPTER_NAMES,
    TrinityAdapterDescriptor,
    normalize_adapter_name,
    require_supported_adapter,
)

__all__ = [
    "REPLY_ADAPTER_NAME",
    "SPOT_ADAPTER_NAME",
    "SUPPORTED_ADAPTER_NAMES",
    "TrinityAdapterDescriptor",
    "normalize_adapter_name",
    "require_supported_adapter",
]
