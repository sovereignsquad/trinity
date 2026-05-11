from __future__ import annotations

from datetime import UTC, datetime

from trinity_core.memory import build_runtime_memory_profile
from trinity_core.schemas import (
    MemoryRecordFamily,
    MemoryScope,
    MemoryScopeKind,
    MemoryTier,
    RetrievedMemoryContext,
    RetrievedMemoryRecord,
)


def test_runtime_memory_profile_groups_hints_by_family() -> None:
    now = datetime.now(UTC)
    context = RetrievedMemoryContext(
        scopes=(MemoryScope(MemoryScopeKind.COMPANY, "company:test"),),
        records=(
            RetrievedMemoryRecord(
                record_key="pref-1",
                family=MemoryRecordFamily.PREFERENCE,
                scope=MemoryScope(MemoryScopeKind.COMPANY, "company:test"),
                content="Prefer concise updates.",
                updated_at=now,
                tier=MemoryTier.CORE,
            ),
            RetrievedMemoryRecord(
                record_key="anti-1",
                family=MemoryRecordFamily.ANTI_PATTERN,
                scope=MemoryScope(MemoryScopeKind.COMPANY, "company:test"),
                content="Avoid vague risk-heavy phrasing.",
                updated_at=now,
                tier=MemoryTier.WORKING,
            ),
            RetrievedMemoryRecord(
                record_key="success-1",
                family=MemoryRecordFamily.SUCCESSFUL_PATTERN,
                scope=MemoryScope(MemoryScopeKind.COMPANY, "company:test"),
                content="Short direct responses perform well.",
                updated_at=now,
                tier=MemoryTier.ARCHIVAL,
            ),
        ),
        selected_keys=("pref-1", "anti-1", "success-1"),
        retrieval_context_hash="ctx-1",
        tier_counts={"core": 1, "working": 1, "archival": 1},
    )

    profile = build_runtime_memory_profile(context)

    assert profile.preference_hints == ("Prefer concise updates.",)
    assert profile.anti_pattern_hints == ("Avoid vague risk-heavy phrasing.",)
    assert profile.successful_pattern_hints == ("Short direct responses perform well.",)
    assert profile.ranked_memory_lines[0].startswith("pref-1 [core/0]")
    assert profile.core_summary == "preference: Prefer concise updates."
    assert profile.working_summary == "anti_pattern: Avoid vague risk-heavy phrasing."
    assert profile.archival_summary == "successful_pattern: Short direct responses perform well."
    assert profile.retrieval_summary == "core=1; working=1; archival=1; top=pref-1,anti-1,success-1"
    payload = profile.prompt_payload()
    assert payload["preference_hints"] == ["Prefer concise updates."]
    assert payload["ranked_memory_lines"][0].startswith("pref-1 [core/0]")
    assert payload["core_summary"] == ["preference: Prefer concise updates."]
