"""Product-adapter mapping ownership for Trinity embeddings."""

from .reply import (
    document_record_from_payload,
    memory_event_from_payload,
    outcome_event_from_payload,
    thread_snapshot_from_payload,
)
from .spot import spot_reasoning_request_from_payload, spot_review_outcome_from_payload

__all__ = [
    "document_record_from_payload",
    "memory_event_from_payload",
    "outcome_event_from_payload",
    "spot_reasoning_request_from_payload",
    "spot_review_outcome_from_payload",
    "thread_snapshot_from_payload",
]
