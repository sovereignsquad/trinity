"""Runtime memory retrieval services."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from trinity_core.schemas import (
    ContactProfile,
    MemoryRecordFamily,
    MemoryScope,
    MemoryScopeKind,
    MemoryTier,
    RetrievedMemoryContext,
    RetrievedMemoryRecord,
    SpotReasoningRequest,
    ThreadSnapshot,
    ThreadState,
)

from .storage import ReplyMemoryStore


@dataclass(slots=True)
class ReplyMemoryResolver:
    """Resolve one bounded runtime memory context for Reply cycles."""

    store: ReplyMemoryStore

    def resolve_for_snapshot(self, snapshot: ThreadSnapshot) -> RetrievedMemoryContext:
        scopes = _scopes_for_snapshot(snapshot)
        records: list[RetrievedMemoryRecord] = []

        contact = self.store.load_contact_profile(snapshot.company_id, snapshot.contact_handle)
        if contact is not None:
            records.append(_record_from_contact(contact))

        thread = self.store.load_thread_state(snapshot.company_id, snapshot.thread_ref)
        if thread is not None:
            records.append(_record_from_thread(thread))

        for summary in self.store.list_memory_summaries(
            snapshot.company_id,
            scope_refs=tuple(scope.scope_ref for scope in scopes),
            limit=6,
        ):
            records.append(
                RetrievedMemoryRecord(
                    record_key=f"summary:{summary.summary_key}:{summary.scope_ref}",
                    family=_summary_family(summary.summary_key, dict(summary.metadata)),
                    tier=_tier_for_summary(summary.scope_ref),
                    scope=_scope_from_ref(summary.scope_ref),
                    content=summary.content,
                    updated_at=summary.updated_at,
                    metadata=dict(summary.metadata),
                )
            )

        for chunk in self.store.list_retrieval_chunks(snapshot.company_id, limit=3):
            records.append(
                RetrievedMemoryRecord(
                    record_key=f"chunk:{chunk.chunk_ref}",
                    family=MemoryRecordFamily.EVIDENCE,
                    tier=MemoryTier.ARCHIVAL,
                    scope=MemoryScope(
                        scope_kind=MemoryScopeKind.COMPANY,
                        scope_ref=f"company:{snapshot.company_id}",
                    ),
                    content=chunk.content,
                    updated_at=chunk.created_at,
                    metadata=dict(chunk.metadata),
                )
            )

        records = _rank_records(records, reference_time=snapshot.requested_at)
        return RetrievedMemoryContext(
            scopes=scopes,
            records=tuple(records),
            selected_keys=tuple(record.record_key for record in records),
            retrieval_context_hash=_context_hash(records),
            tier_counts=_tier_counts(records),
        )


@dataclass(slots=True)
class SpotMemoryResolver:
    """Resolve one bounded runtime memory context for Spot reasoning cycles."""

    store: ReplyMemoryStore

    def resolve_for_request(self, request: SpotReasoningRequest) -> RetrievedMemoryContext:
        scopes = _scopes_for_spot_request(request)
        records: list[RetrievedMemoryRecord] = []

        for summary in self.store.list_memory_summaries(
            request.company_id,
            scope_refs=tuple(scope.scope_ref for scope in scopes),
            limit=6,
        ):
            records.append(
                RetrievedMemoryRecord(
                    record_key=f"summary:{summary.summary_key}:{summary.scope_ref}",
                    family=_summary_family(summary.summary_key, dict(summary.metadata)),
                    tier=_tier_for_summary(summary.scope_ref),
                    scope=_scope_from_ref(summary.scope_ref),
                    content=summary.content,
                    updated_at=summary.updated_at,
                    metadata=dict(summary.metadata),
                )
            )

        for chunk in self.store.list_retrieval_chunks(request.company_id, limit=3):
            records.append(
                RetrievedMemoryRecord(
                    record_key=f"chunk:{chunk.chunk_ref}",
                    family=MemoryRecordFamily.EVIDENCE,
                    tier=MemoryTier.ARCHIVAL,
                    scope=MemoryScope(
                        scope_kind=MemoryScopeKind.COMPANY,
                        scope_ref=f"company:{request.company_id}",
                    ),
                    content=chunk.content,
                    updated_at=chunk.created_at,
                    metadata=dict(chunk.metadata),
                )
            )

        records = _rank_records(records, reference_time=datetime.now(UTC))
        return RetrievedMemoryContext(
            scopes=scopes,
            records=tuple(records),
            selected_keys=tuple(record.record_key for record in records),
            retrieval_context_hash=_context_hash(records),
            tier_counts=_tier_counts(records),
        )


def _scopes_for_snapshot(snapshot: ThreadSnapshot) -> tuple[MemoryScope, ...]:
    scopes: list[MemoryScope] = [
        MemoryScope(MemoryScopeKind.ADAPTER, "adapter:reply"),
        MemoryScope(MemoryScopeKind.PROJECT, "project:reply"),
        MemoryScope(MemoryScopeKind.COMPANY, f"company:{snapshot.company_id}"),
        MemoryScope(MemoryScopeKind.ITEM_FAMILY, f"thread:{snapshot.thread_ref}"),
        MemoryScope(MemoryScopeKind.HUMAN_RESOLUTION, f"human:thread:{snapshot.thread_ref}"),
    ]
    for topic in _snapshot_topics(snapshot)[:3]:
        normalized = str(topic or "").strip().lower()
        if normalized:
            scopes.append(MemoryScope(MemoryScopeKind.TOPIC, f"topic:{normalized}"))
    return tuple(scopes)


def _scopes_for_spot_request(request: SpotReasoningRequest) -> tuple[MemoryScope, ...]:
    scopes: list[MemoryScope] = [
        MemoryScope(MemoryScopeKind.ADAPTER, "adapter:spot"),
        MemoryScope(MemoryScopeKind.PROJECT, "project:spot"),
        MemoryScope(MemoryScopeKind.COMPANY, f"company:{request.company_id}"),
        MemoryScope(MemoryScopeKind.ITEM_FAMILY, f"row:{request.row_ref}"),
        MemoryScope(MemoryScopeKind.HUMAN_RESOLUTION, f"human:row:{request.row_ref}"),
        MemoryScope(MemoryScopeKind.TOPIC, f"language:{request.language.lower()}"),
    ]
    raw_topics = request.metadata.get("topic_hints", "")
    if raw_topics:
        for topic in str(raw_topics).split(","):
            normalized = topic.strip().lower()
            if normalized:
                scopes.append(MemoryScope(MemoryScopeKind.TOPIC, f"topic:{normalized}"))
    return tuple(scopes)


def _snapshot_topics(snapshot: ThreadSnapshot) -> tuple[str, ...]:
    raw_topics = snapshot.metadata.get("topic_hints", "")
    if not raw_topics:
        return ()
    return tuple(
        topic.strip()
        for topic in str(raw_topics).split(",")
        if topic and str(topic).strip()
    )


def _record_from_contact(profile: ContactProfile) -> RetrievedMemoryRecord:
    return RetrievedMemoryRecord(
        record_key=f"contact:{profile.contact_handle}",
        family=MemoryRecordFamily.PREFERENCE,
        tier=MemoryTier.CORE,
        scope=MemoryScope(MemoryScopeKind.COMPANY, f"company:{profile.company_id}"),
        content=profile.summary or profile.display_name or profile.contact_handle,
        updated_at=profile.updated_at or datetime.now(UTC),
        metadata=dict(profile.metadata),
    )


def _record_from_thread(state: ThreadState) -> RetrievedMemoryRecord:
    return RetrievedMemoryRecord(
        record_key=f"thread:{state.thread_ref}",
        family=MemoryRecordFamily.EVIDENCE,
        tier=MemoryTier.CORE,
        scope=MemoryScope(MemoryScopeKind.ITEM_FAMILY, f"thread:{state.thread_ref}"),
        content=state.latest_inbound_text,
        updated_at=state.last_snapshot_at or state.last_event_at or datetime.now(UTC),
        metadata=dict(state.metadata),
    )


def _scope_from_ref(scope_ref: str) -> MemoryScope:
    prefix = scope_ref.partition(":")[0]
    mapping = {
        "global": MemoryScopeKind.GLOBAL,
        "adapter": MemoryScopeKind.ADAPTER,
        "project": MemoryScopeKind.PROJECT,
        "company": MemoryScopeKind.COMPANY,
        "thread": MemoryScopeKind.ITEM_FAMILY,
        "topic": MemoryScopeKind.TOPIC,
        "stage": MemoryScopeKind.STAGE,
        "human": MemoryScopeKind.HUMAN_RESOLUTION,
    }
    return MemoryScope(mapping.get(prefix, MemoryScopeKind.PROJECT), scope_ref)


def _summary_family(summary_key: str, metadata: dict[str, object]) -> MemoryRecordFamily:
    raw_family = str(metadata.get("family") or "").strip().lower()
    for family in MemoryRecordFamily:
        if raw_family == family.value:
            return family
    lowered = summary_key.lower()
    if "anti" in lowered:
        return MemoryRecordFamily.ANTI_PATTERN
    if "success" in lowered:
        return MemoryRecordFamily.SUCCESSFUL_PATTERN
    if "correct" in lowered:
        return MemoryRecordFamily.CORRECTION
    if "disagree" in lowered or "minority" in lowered:
        return MemoryRecordFamily.DISAGREEMENT
    if "human" in lowered or "resolution" in lowered:
        return MemoryRecordFamily.HUMAN_RESOLUTION
    return MemoryRecordFamily.PREFERENCE


def _tier_for_summary(scope_ref: str) -> MemoryTier:
    if scope_ref.startswith("human:") or scope_ref.startswith("thread:") or scope_ref.startswith(
        "row:"
    ):
        return MemoryTier.CORE
    if scope_ref.startswith(("company:", "topic:", "stage:", "adapter:", "project:")):
        return MemoryTier.WORKING
    return MemoryTier.WORKING


def _context_hash(records: list[RetrievedMemoryRecord]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(record.record_key.encode("utf-8"))
        digest.update(record.tier.value.encode("utf-8"))
        digest.update(record.content.encode("utf-8"))
        digest.update(record.updated_at.isoformat().encode("utf-8"))
    return digest.hexdigest()[:24]


def _tier_counts(records: list[RetrievedMemoryRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        counts[record.tier.value] = counts.get(record.tier.value, 0) + 1
    return counts


def _rank_records(
    records: list[RetrievedMemoryRecord],
    *,
    reference_time: datetime,
) -> list[RetrievedMemoryRecord]:
    ranked: list[RetrievedMemoryRecord] = []
    for record in records:
        score, reason = _relevance_score(record, reference_time=reference_time)
        ranked.append(
            replace(
                record,
                relevance_score=score,
                selection_reason=reason,
            )
        )
    ranked.sort(
        key=lambda record: (
            -record.relevance_score,
            -record.updated_at.timestamp(),
            record.record_key,
        )
    )
    return ranked


def _relevance_score(
    record: RetrievedMemoryRecord,
    *,
    reference_time: datetime,
) -> tuple[float, str]:
    score = 0.0
    reasons: list[str] = []

    tier_boost = {
        MemoryTier.CORE: 300.0,
        MemoryTier.WORKING: 200.0,
        MemoryTier.ARCHIVAL: 100.0,
    }[record.tier]
    score += tier_boost
    reasons.append(f"tier:{record.tier.value}")

    scope_kind_boost = {
        MemoryScopeKind.HUMAN_RESOLUTION: 80.0,
        MemoryScopeKind.ITEM_FAMILY: 70.0,
        MemoryScopeKind.COMPANY: 50.0,
        MemoryScopeKind.TOPIC: 40.0,
        MemoryScopeKind.STAGE: 35.0,
        MemoryScopeKind.ADAPTER: 25.0,
        MemoryScopeKind.PROJECT: 20.0,
        MemoryScopeKind.GLOBAL: 10.0,
    }[record.scope.scope_kind]
    score += scope_kind_boost
    reasons.append(f"scope:{record.scope.scope_kind.value.lower()}")

    family_boost = {
        MemoryRecordFamily.HUMAN_RESOLUTION: 45.0,
        MemoryRecordFamily.CORRECTION: 40.0,
        MemoryRecordFamily.DISAGREEMENT: 35.0,
        MemoryRecordFamily.ANTI_PATTERN: 30.0,
        MemoryRecordFamily.SUCCESSFUL_PATTERN: 30.0,
        MemoryRecordFamily.PREFERENCE: 25.0,
        MemoryRecordFamily.EVIDENCE: 15.0,
    }[record.family]
    score += family_boost
    reasons.append(f"family:{record.family.value}")

    age_seconds = max((reference_time - record.updated_at).total_seconds(), 0.0)
    recency_boost = max(0.0, 20.0 - (age_seconds / 86400.0))
    if recency_boost > 0:
        score += recency_boost
        reasons.append("recent")

    return round(score, 2), ",".join(reasons)
