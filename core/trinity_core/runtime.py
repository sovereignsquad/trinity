"""Generic Trinity runtime entrypoint with adapter dispatch."""

from __future__ import annotations

from typing import Any

from trinity_core.adapters import REPLY_ADAPTER_NAME, SPOT_ADAPTER_NAME, require_supported_adapter
from trinity_core.adapters.product.spot import SpotRuntime
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
        if self.adapter_name == SPOT_ADAPTER_NAME:
            self._runtime = SpotRuntime(store=store, policy_store=policy_store)
            return
        raise AssertionError(f"Unhandled adapter: {self.adapter_name}")

    @property
    def model_provider(self) -> Any:
        return self._runtime.model_provider

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

    def ingest_memory_event(self, event: Any) -> Any:
        return self._runtime.ingest_memory_event(event)

    def register_document(self, document: Any) -> Any:
        return self._runtime.register_document(document)

    def get_prepared_draft(self, *, company_id: Any, thread_ref: str) -> Any:
        return self._runtime.get_prepared_draft(company_id=company_id, thread_ref=thread_ref)

    def refresh_prepared_draft(
        self,
        *,
        company_id: Any,
        thread_ref: str,
        generation_reason: str = "manual_refresh",
        overwrite_mode: str = "if_stale_or_dirty",
    ) -> Any:
        return self._runtime.refresh_prepared_draft(
            company_id=company_id,
            thread_ref=thread_ref,
            generation_reason=generation_reason,
            overwrite_mode=overwrite_mode,
        )

    def inspect_prepared_draft_refresh(
        self,
        *,
        company_id: Any,
        limit: int = 10,
        stale_after_minutes: int = 15,
    ) -> Any:
        return self._runtime.inspect_prepared_draft_refresh(
            company_id=company_id,
            limit=limit,
            stale_after_minutes=stale_after_minutes,
        )

    def reason_spot(self, request: Any) -> Any:
        return self._runtime.reason_spot(request)

    def record_spot_review_outcome(self, outcome: Any) -> Any:
        return self._runtime.record_review_outcome(outcome)
