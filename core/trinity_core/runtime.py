"""Generic Trinity runtime entrypoint with adapter dispatch."""

from __future__ import annotations

from typing import Any

from trinity_core.adapters import IMPACT_ADAPTER_NAME, REPLY_ADAPTER_NAME, require_supported_adapter
from trinity_core.impact_runtime import ImpactRuntime
from trinity_core.reply_runtime import ReplyRuntime


class TrinityRuntime:
    """Adapter-aware runtime facade used by generic CLI and future integrations."""

    def __init__(
        self,
        *,
        adapter_name: str = REPLY_ADAPTER_NAME,
        store: Any | None = None,
        policy_store: Any | None = None,
    ) -> None:
        self.adapter_name = require_supported_adapter(adapter_name)
        if self.adapter_name == REPLY_ADAPTER_NAME:
            self._runtime = ReplyRuntime(store=store, policy_store=policy_store)
            return
        if self.adapter_name == IMPACT_ADAPTER_NAME:
            self._runtime = ImpactRuntime(store=store)
            return
        raise AssertionError(f"Unhandled adapter: {self.adapter_name}")

    @property
    def ollama_client(self) -> Any:
        return self._runtime.ollama_client

    def suggest(self, snapshot: Any) -> Any:
        return self._runtime.suggest(snapshot)

    def record_outcome(self, event: Any) -> Any:
        return self._runtime.record_outcome(event)

    def export_trace(self, cycle_id: Any) -> Any:
        return self._runtime.export_trace(cycle_id)

    def export_training_bundle(self, cycle_id: Any, *, bundle_type: Any) -> Any:
        return self._runtime.export_training_bundle(cycle_id, bundle_type=bundle_type)
