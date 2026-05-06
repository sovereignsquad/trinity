"""Replayable shadow fixtures for the Reply adapter."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from trinity_core.ops.cycle_store import dataclass_payload
from trinity_core.reply_runtime import ReplyRuntime, thread_snapshot_from_payload
from trinity_core.schemas import AcceptedArtifactVersion, ThreadSnapshot


@dataclass(frozen=True, slots=True)
class ReplyShadowFixture:
    """One replayable legacy-vs-Trinity comparison fixture."""

    fixture_id: str
    legacy_suggestion: str
    thread_snapshot: ThreadSnapshot
    description: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReplyShadowComparisonResult:
    """Comparison summary for one replayed shadow fixture."""

    fixture_id: str
    channel: str
    cycle_id: str
    trace_ref: str | None
    accepted_artifact_version: AcceptedArtifactVersion
    legacy_suggestion: str
    trinity_suggestion: str
    same_text: bool
    overlap_ratio: float
    edit_distance: float
    legacy_length: int
    trinity_length: int


def load_reply_shadow_fixture(path: str | Path) -> ReplyShadowFixture:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return ReplyShadowFixture(
        fixture_id=str(payload["fixture_id"]),
        legacy_suggestion=str(payload["legacy_suggestion"]).strip(),
        thread_snapshot=thread_snapshot_from_payload(payload["thread_snapshot"]),
        description=str(payload["description"]).strip() if payload.get("description") else None,
        metadata={str(key): str(value) for key, value in payload.get("metadata", {}).items()},
    )


def load_reply_shadow_fixtures(fixture_dir: str | Path) -> tuple[ReplyShadowFixture, ...]:
    root = Path(fixture_dir)
    fixtures = [load_reply_shadow_fixture(path) for path in sorted(root.glob("*.json"))]
    return tuple(fixtures)


def run_reply_shadow_fixture(
    runtime: ReplyRuntime,
    fixture: ReplyShadowFixture,
) -> ReplyShadowComparisonResult:
    ranked = runtime.suggest(fixture.thread_snapshot)
    top_draft = ranked.drafts[0]
    legacy = fixture.legacy_suggestion.strip()
    trinity = top_draft.draft_text.strip()
    return ReplyShadowComparisonResult(
        fixture_id=fixture.fixture_id,
        channel=fixture.thread_snapshot.channel,
        cycle_id=str(ranked.cycle_id),
        trace_ref=ranked.trace_ref,
        accepted_artifact_version=ranked.accepted_artifact_version,
        legacy_suggestion=legacy,
        trinity_suggestion=trinity,
        same_text=legacy == trinity,
        overlap_ratio=_token_overlap_ratio(legacy, trinity),
        edit_distance=_normalized_edit_distance(legacy, trinity),
        legacy_length=len(legacy),
        trinity_length=len(trinity),
    )


def run_reply_shadow_fixtures(
    runtime: ReplyRuntime,
    fixtures: Sequence[ReplyShadowFixture],
) -> tuple[ReplyShadowComparisonResult, ...]:
    return tuple(run_reply_shadow_fixture(runtime, fixture) for fixture in fixtures)


def summarize_reply_shadow_results(
    results: Sequence[ReplyShadowComparisonResult],
) -> dict[str, Any]:
    if not results:
        return {
            "fixture_count": 0,
            "exact_match_count": 0,
            "average_overlap_ratio": 0.0,
            "average_edit_distance": 0.0,
        }
    count = len(results)
    return {
        "fixture_count": count,
        "exact_match_count": sum(1 for result in results if result.same_text),
        "average_overlap_ratio": round(
            sum(result.overlap_ratio for result in results) / count,
            4,
        ),
        "average_edit_distance": round(
            sum(result.edit_distance for result in results) / count,
            4,
        ),
    }


def shadow_fixture_payload(result: ReplyShadowComparisonResult) -> dict[str, Any]:
    return dataclass_payload(result)


def _token_overlap_ratio(left: str, right: str) -> float:
    left_tokens = set(str(left or "").lower().split())
    right_tokens = set(str(right or "").lower().split())
    if not left_tokens and not right_tokens:
        return 1.0
    union = left_tokens | right_tokens
    if not union:
        return 1.0
    overlap = sum(1 for token in union if token in left_tokens and token in right_tokens)
    return round(overlap / len(union), 4)


def _normalized_edit_distance(left: str, right: str) -> float:
    source = str(left or "")
    target = str(right or "")
    if not source and not target:
        return 0.0
    rows = [[0] * (len(target) + 1) for _ in range(len(source) + 1)]
    for index in range(len(source) + 1):
        rows[index][0] = index
    for index in range(len(target) + 1):
        rows[0][index] = index
    for left_index in range(1, len(source) + 1):
        for right_index in range(1, len(target) + 1):
            cost = 0 if source[left_index - 1] == target[right_index - 1] else 1
            rows[left_index][right_index] = min(
                rows[left_index - 1][right_index] + 1,
                rows[left_index][right_index - 1] + 1,
                rows[left_index - 1][right_index - 1] + cost,
            )
    return round(rows[len(source)][len(target)] / max(len(source), len(target)), 4)
