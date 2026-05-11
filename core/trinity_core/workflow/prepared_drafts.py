"""Prepared draft helpers for active-thread runtime refresh."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from trinity_core.schemas import PreparedDraftSet, RankedDraftSet, ThreadSnapshot


def build_prepared_draft_set(
    snapshot: ThreadSnapshot,
    ranked: RankedDraftSet,
    *,
    generation_reason: str,
    now: datetime | None = None,
    ttl: timedelta = timedelta(minutes=15),
) -> PreparedDraftSet:
    prepared_at = now or datetime.now(UTC)
    source_thread_version = _thread_version(snapshot)
    retrieval_context_hash = _retrieval_context_hash(snapshot)
    return PreparedDraftSet(
        company_id=snapshot.company_id,
        thread_ref=snapshot.thread_ref,
        prepared_at=prepared_at,
        expires_at=prepared_at + ttl,
        source_thread_version=source_thread_version,
        retrieval_context_hash=retrieval_context_hash,
        generation_reason=generation_reason,
        ranked_draft_set=replace(ranked),
    )


def _thread_version(snapshot: ThreadSnapshot) -> str:
    if snapshot.messages:
        latest = snapshot.messages[-1]
        return f"{latest.message_id}:{latest.occurred_at.isoformat()}"
    return hashlib.sha256(snapshot.latest_inbound_text.encode("utf-8")).hexdigest()[:16]


def _retrieval_context_hash(snapshot: ThreadSnapshot) -> str:
    joined = "\n".join(
        [snapshot.latest_inbound_text]
        + [snippet.text for snippet in snapshot.context_snippets]
        + [example.text for example in snapshot.golden_examples]
    )
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
