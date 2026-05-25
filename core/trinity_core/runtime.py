"""Generic Trinity runtime entrypoint with adapter dispatch."""

from __future__ import annotations

from typing import Any

from trinity_core.adapters import (
    REPLY_ADAPTER_NAME,
    instantiate_adapter_runtime,
    require_supported_adapter,
)


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
        self._runtime = instantiate_adapter_runtime(
            self.adapter_name,
            store=store,
            policy_store=policy_store,
        )

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

    def build_source_export(self, *, company_id: Any, snapshot_ref: str | None = None) -> Any:
        return self._runtime.build_source_export(company_id=company_id, snapshot_ref=snapshot_ref)

    def build_outcome_export(self, *, company_id: Any, snapshot_ref: str | None = None) -> Any:
        return self._runtime.build_outcome_export(company_id=company_id, snapshot_ref=snapshot_ref)

    def build_memory_export(self, *, company_id: Any, snapshot_ref: str | None = None) -> Any:
        return self._runtime.build_memory_export(company_id=company_id, snapshot_ref=snapshot_ref)

    def build_delta_export(
        self,
        *,
        company_id: Any,
        cutoff_at: Any,
        snapshot_ref: str,
        prior_snapshot_ref: str | None = None,
        prior_export_id: str | None = None,
    ) -> Any:
        return self._runtime.build_delta_export(
            company_id=company_id,
            cutoff_at=cutoff_at,
            snapshot_ref=snapshot_ref,
            prior_snapshot_ref=prior_snapshot_ref,
            prior_export_id=prior_export_id,
        )

    def ingest_memory_event(self, event: Any) -> Any:
        return self._runtime.ingest_memory_event(event)

    def register_document(self, document: Any) -> Any:
        return self._runtime.register_document(document)

    def import_runtime_candidate_pack(
        self,
        *,
        company_id: Any,
        manifest_path: Any,
        import_id: str | None = None,
    ) -> Any:
        return self._runtime.import_runtime_candidate_pack(
            company_id=company_id,
            manifest_path=manifest_path,
            import_id=import_id,
        )

    def inspect_runtime_candidate_import(self, *, company_id: Any, import_id: str) -> Any:
        return self._runtime.inspect_runtime_candidate_import(
            company_id=company_id,
            import_id=import_id,
        )

    def adopt_runtime_candidate_import(
        self,
        *,
        company_id: Any,
        import_id: str,
        min_confidence: float = 0.6,
        allow_conflicted: bool = False,
    ) -> Any:
        return self._runtime.adopt_runtime_candidate_import(
            company_id=company_id,
            import_id=import_id,
            min_confidence=min_confidence,
            allow_conflicted=allow_conflicted,
        )

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
