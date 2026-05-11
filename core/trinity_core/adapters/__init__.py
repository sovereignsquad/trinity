"""Adapter descriptors and helpers for product-specific Trinity embeddings."""

from .base import (
    REPLY_ADAPTER,
    REPLY_ADAPTER_NAME,
    SPOT_ADAPTER,
    SPOT_ADAPTER_NAME,
    SUPPORTED_ADAPTER_NAME_LIST,
    SUPPORTED_ADAPTER_NAMES,
    SUPPORTED_ADAPTERS,
    TrinityAdapterDescriptor,
    get_adapter_descriptor,
    instantiate_adapter_runtime,
    list_supported_adapters,
    normalize_adapter_name,
    require_supported_adapter,
)

__all__ = [
    "REPLY_ADAPTER",
    "REPLY_ADAPTER_NAME",
    "SPOT_ADAPTER",
    "SPOT_ADAPTER_NAME",
    "SUPPORTED_ADAPTERS",
    "SUPPORTED_ADAPTER_NAME_LIST",
    "SUPPORTED_ADAPTER_NAMES",
    "TrinityAdapterDescriptor",
    "get_adapter_descriptor",
    "instantiate_adapter_runtime",
    "list_supported_adapters",
    "normalize_adapter_name",
    "require_supported_adapter",
]
