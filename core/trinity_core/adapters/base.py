"""Core adapter primitives for product-specific Trinity runtime embeddings."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any

REPLY_ADAPTER_NAME = "reply"
SPOT_ADAPTER_NAME = "spot"


@dataclass(frozen=True, slots=True)
class TrinityAdapterDescriptor:
    """Declared runtime adapter supported by this repository."""

    adapter_name: str
    display_name: str
    runtime_module: str
    runtime_class_name: str
    default_contract_version: str | None = None


REPLY_ADAPTER = TrinityAdapterDescriptor(
    adapter_name=REPLY_ADAPTER_NAME,
    display_name="Reply",
    runtime_module="trinity_core.reply_runtime",
    runtime_class_name="ReplyRuntime",
)

SPOT_ADAPTER = TrinityAdapterDescriptor(
    adapter_name=SPOT_ADAPTER_NAME,
    display_name="Spot",
    runtime_module="trinity_core.adapters.product.spot.runtime",
    runtime_class_name="SpotRuntime",
)

SUPPORTED_ADAPTERS = (
    REPLY_ADAPTER,
    SPOT_ADAPTER,
)
SUPPORTED_ADAPTER_NAMES = tuple(adapter.adapter_name for adapter in SUPPORTED_ADAPTERS)
SUPPORTED_ADAPTER_NAME_LIST = ", ".join(SUPPORTED_ADAPTER_NAMES)
_SUPPORTED_ADAPTER_MAP = {adapter.adapter_name: adapter for adapter in SUPPORTED_ADAPTERS}


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
        raise ValueError(
            "Unsupported Trinity adapter: "
            f"{normalized}. Supported adapters: {SUPPORTED_ADAPTER_NAME_LIST}."
        )
    return normalized


def get_adapter_descriptor(adapter_name: str | None) -> TrinityAdapterDescriptor:
    """Return the declared descriptor for one supported adapter."""

    normalized = require_supported_adapter(adapter_name)
    return _SUPPORTED_ADAPTER_MAP[normalized]


def list_supported_adapters() -> tuple[TrinityAdapterDescriptor, ...]:
    """Return the adapters currently implemented in this repository."""

    return SUPPORTED_ADAPTERS


def instantiate_adapter_runtime(
    adapter_name: str | None,
    *,
    store: Any | None = None,
    policy_store: Any | None = None,
) -> Any:
    """Instantiate the runtime implementation declared for one adapter."""

    descriptor = get_adapter_descriptor(adapter_name)
    runtime_module = import_module(descriptor.runtime_module)
    runtime_class = getattr(runtime_module, descriptor.runtime_class_name)
    return runtime_class(store=store, policy_store=policy_store)
