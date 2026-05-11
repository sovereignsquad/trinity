"""Shared memory profile helpers for runtime reasoning surfaces."""

from __future__ import annotations

from dataclasses import dataclass

from trinity_core.schemas import (
    MemoryRecordFamily,
    MemoryTier,
    RetrievedMemoryContext,
    RetrievedMemoryRecord,
)


@dataclass(frozen=True, slots=True)
class RuntimeMemoryProfile:
    preference_hints: tuple[str, ...]
    correction_hints: tuple[str, ...]
    anti_pattern_hints: tuple[str, ...]
    successful_pattern_hints: tuple[str, ...]
    disagreement_hints: tuple[str, ...]
    evidence_hints: tuple[str, ...]
    ranked_memory_lines: tuple[str, ...] = ()
    core_summary: str = ""
    working_summary: str = ""
    archival_summary: str = ""
    retrieval_summary: str = ""

    def prompt_payload(self) -> dict[str, list[str]]:
        return {
            "preference_hints": list(self.preference_hints),
            "correction_hints": list(self.correction_hints),
            "anti_pattern_hints": list(self.anti_pattern_hints),
            "successful_pattern_hints": list(self.successful_pattern_hints),
            "disagreement_hints": list(self.disagreement_hints),
            "evidence_hints": list(self.evidence_hints),
            "ranked_memory_lines": list(self.ranked_memory_lines),
            "core_summary": [self.core_summary] if self.core_summary else [],
            "working_summary": [self.working_summary] if self.working_summary else [],
            "archival_summary": [self.archival_summary] if self.archival_summary else [],
            "retrieval_summary": [self.retrieval_summary] if self.retrieval_summary else [],
        }


def build_runtime_memory_profile(context: RetrievedMemoryContext) -> RuntimeMemoryProfile:
    preference_hints = _top_contents(context, MemoryRecordFamily.PREFERENCE)
    correction_hints = _top_contents(context, MemoryRecordFamily.CORRECTION)
    anti_pattern_hints = _top_contents(context, MemoryRecordFamily.ANTI_PATTERN)
    successful_pattern_hints = _top_contents(context, MemoryRecordFamily.SUCCESSFUL_PATTERN)
    disagreement_hints = _top_contents(context, MemoryRecordFamily.DISAGREEMENT)
    evidence_hints = _top_contents(context, MemoryRecordFamily.EVIDENCE)
    return RuntimeMemoryProfile(
        preference_hints=preference_hints,
        correction_hints=correction_hints,
        anti_pattern_hints=anti_pattern_hints,
        successful_pattern_hints=successful_pattern_hints,
        disagreement_hints=disagreement_hints,
        evidence_hints=evidence_hints,
        ranked_memory_lines=_ranked_memory_lines(context),
        core_summary=_tier_summary(context, MemoryTier.CORE),
        working_summary=_tier_summary(context, MemoryTier.WORKING),
        archival_summary=_tier_summary(context, MemoryTier.ARCHIVAL),
        retrieval_summary=_retrieval_summary(context),
    )


def _top_contents(
    context: RetrievedMemoryContext,
    family: MemoryRecordFamily,
    *,
    limit: int = 3,
) -> tuple[str, ...]:
    values: list[str] = []
    for record in context.records:
        if record.family is not family:
            continue
        content = _normalize_hint(record)
        if content:
            values.append(content)
        if len(values) >= limit:
            break
    return tuple(values)


def _normalize_hint(record: RetrievedMemoryRecord) -> str:
    content = " ".join(str(record.content or "").split()).strip()
    if not content:
        return ""
    if len(content) <= 200:
        return content
    return content[:197].rstrip() + "..."


def _tier_summary(
    context: RetrievedMemoryContext,
    tier: MemoryTier,
    *,
    limit: int = 2,
) -> str:
    fragments: list[str] = []
    for record in context.records:
        if record.tier is not tier:
            continue
        label = _record_label(record)
        content = _normalize_hint(record)
        if not content:
            continue
        if label:
            fragments.append(f"{label}: {content}")
        else:
            fragments.append(content)
        if len(fragments) >= limit:
            break
    return " | ".join(fragments)


def _retrieval_summary(context: RetrievedMemoryContext) -> str:
    pieces: list[str] = []
    for tier in (MemoryTier.CORE, MemoryTier.WORKING, MemoryTier.ARCHIVAL):
        count = sum(1 for record in context.records if record.tier is tier)
        if count <= 0:
            continue
        pieces.append(f"{tier.value}={count}")
    selected = ",".join(context.selected_keys[:3])
    if selected:
        pieces.append(f"top={selected}")
    return "; ".join(pieces)


def _record_label(record: RetrievedMemoryRecord) -> str:
    if record.family is MemoryRecordFamily.HUMAN_RESOLUTION:
        return "human_resolution"
    if record.family is MemoryRecordFamily.DISAGREEMENT:
        return "disagreement"
    if record.family is MemoryRecordFamily.CORRECTION:
        return "correction"
    if record.family is MemoryRecordFamily.ANTI_PATTERN:
        return "anti_pattern"
    if record.family is MemoryRecordFamily.SUCCESSFUL_PATTERN:
        return "successful_pattern"
    if record.family is MemoryRecordFamily.PREFERENCE:
        return "preference"
    if record.family is MemoryRecordFamily.EVIDENCE:
        return "evidence"
    return record.family.value


def _ranked_memory_lines(
    context: RetrievedMemoryContext,
    *,
    limit: int = 3,
) -> tuple[str, ...]:
    lines: list[str] = []
    for record in context.records[:limit]:
        content = _normalize_hint(record)
        if not content:
            continue
        reason = str(record.selection_reason or "").strip()
        score = f"{record.relevance_score:.0f}"
        prefix = f"{record.record_key} [{record.tier.value}/{score}]"
        if reason:
            prefix += f" {reason}"
        lines.append(f"{prefix}: {content}")
    return tuple(lines)
