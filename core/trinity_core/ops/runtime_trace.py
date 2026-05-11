"""Generic runtime trace payload helpers."""

from __future__ import annotations

from typing import Any

from trinity_core.ops.cycle_store import RuntimeCycleStore, dataclass_payload


def build_runtime_memory_context_payload(memory_context: Any) -> dict[str, Any]:
    return {
        "retrieval_context_hash": memory_context.retrieval_context_hash,
        "scope_refs": tuple(scope.scope_ref for scope in memory_context.scopes),
        "selected_keys": memory_context.selected_keys,
        "record_count": len(memory_context.records),
        "tier_counts": dict(getattr(memory_context, "tier_counts", {})),
        "top_records": [
            {
                "record_key": record.record_key,
                "family": record.family.value,
                "tier": record.tier.value,
                "scope_ref": record.scope.scope_ref,
                "relevance_score": record.relevance_score,
                "selection_reason": record.selection_reason,
            }
            for record in memory_context.records[:3]
        ],
    }


def build_runtime_loop_decision_payload(
    consensus: Any,
    loop_decision: Any,
) -> dict[str, Any]:
    return {
        "consensus": _payloadify(consensus),
        "loop_decision": _payloadify(loop_decision),
    }


def persist_runtime_trace(store: RuntimeCycleStore, trace: Any) -> None:
    if hasattr(trace, "payload") and hasattr(trace, "cycle_id"):
        payload = dataclass_payload(trace.payload)
        store.save_cycle(trace.cycle_id, payload)
        store.save_export(trace.cycle_id, payload)
        return
    payload = dataclass_payload(trace)
    store.save_cycle(trace.cycle_id, payload)
    store.save_export(trace.cycle_id, payload)


def _payloadify(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return dataclass_payload(value)
    if isinstance(value, dict):
        return {str(key): _payloadify(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_payloadify(item) for item in value]
    return value
