"""Curate persisted runtime traces into replayable evaluation datasets."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from trinity_core.ops.cycle_store import dataclass_payload, write_json_atomic
from trinity_core.ops.reply_shadow_fixtures import (
    _normalized_edit_distance,
    _token_overlap_ratio,
)
from trinity_core.ops.runtime_storage import resolve_adapter_runtime_paths
from trinity_core.reply_runtime import (
    ReplyRuntime,
    outcome_event_from_payload,
    thread_snapshot_from_payload,
)
from trinity_core.schemas import (
    AcceptedArtifactVersion,
    CuratedEvalCase,
    DraftOutcomeDisposition,
    EvalDataset,
    EvalReplayCaseResult,
    EvalReplayReport,
)


@dataclass(frozen=True, slots=True)
class EvalDatasetPaths:
    """Persistent artifact paths for curated eval datasets and replay reports."""

    adapter_name: str
    root_dir: Path
    datasets_dir: Path
    reports_dir: Path


def resolve_eval_dataset_paths(adapter_name: str) -> EvalDatasetPaths:
    adapter_paths = resolve_adapter_runtime_paths(
        adapter_name,
        repo_root=Path(__file__).resolve().parents[3],
    )
    root_dir = adapter_paths.root_dir / "eval_datasets"
    datasets_dir = root_dir / "datasets"
    reports_dir = root_dir / "reports"
    for path in (root_dir, datasets_dir, reports_dir):
        path.mkdir(parents=True, exist_ok=True)
    return EvalDatasetPaths(
        adapter_name=adapter_paths.adapter_name,
        root_dir=root_dir,
        datasets_dir=datasets_dir,
        reports_dir=reports_dir,
    )


def curate_eval_case_from_trace_payload(
    adapter_name: str,
    payload: dict[str, Any],
    *,
    selection_reason: str,
) -> CuratedEvalCase:
    if adapter_name != "reply":
        raise ValueError(f"Unsupported eval dataset adapter: {adapter_name}")
    outcome = _curated_outcome(payload)
    expected_text = str(outcome.final_text or outcome.original_draft_text or "").strip()
    if not expected_text:
        raise ValueError("Curated eval case requires final_text or original_draft_text.")
    cycle_id = UUID(str(payload["cycle_id"]))
    thread_snapshot = thread_snapshot_from_payload(dict(payload["thread_snapshot"]))
    accepted_artifact_version = _accepted_artifact_version_from_payload(
        dict(payload["accepted_artifact_version"])
    )
    case_id = f"reply-trace-{cycle_id}"
    return CuratedEvalCase(
        case_id=case_id,
        adapter_name=adapter_name,
        curated_at=datetime.now(UTC),
        curated_from_cycle_id=cycle_id,
        curated_from_trace_ref=(
            str(payload.get("trace_ref")).strip() if payload.get("trace_ref") else None
        ),
        selection_reason=selection_reason,
        expected_text=expected_text,
        expected_disposition=outcome.disposition.value,
        thread_snapshot=thread_snapshot,
        accepted_artifact_version=accepted_artifact_version,
        metadata={
            "source_contract_version": str(payload.get("contract_version") or ""),
            "channel": thread_snapshot.channel,
            "thread_ref": thread_snapshot.thread_ref,
        },
    )


def build_eval_dataset(
    *,
    dataset_name: str,
    adapter_name: str,
    cases: tuple[CuratedEvalCase, ...],
    metadata: dict[str, Any] | None = None,
) -> EvalDataset:
    return EvalDataset(
        dataset_id=_slugify(dataset_name),
        name=dataset_name,
        adapter_name=adapter_name,
        created_at=datetime.now(UTC),
        cases=cases,
        metadata=metadata or {},
    )


def merge_eval_dataset_cases(
    dataset: EvalDataset,
    new_cases: tuple[CuratedEvalCase, ...],
) -> EvalDataset:
    merged = {case.case_id: case for case in dataset.cases}
    for case in new_cases:
        merged[case.case_id] = case
    return EvalDataset(
        dataset_id=dataset.dataset_id,
        name=dataset.name,
        adapter_name=dataset.adapter_name,
        created_at=dataset.created_at,
        cases=tuple(merged[key] for key in sorted(merged)),
        metadata=dict(dataset.metadata),
    )


def persist_eval_dataset(dataset: EvalDataset) -> Path:
    paths = resolve_eval_dataset_paths(dataset.adapter_name)
    path = paths.datasets_dir / f"{dataset.dataset_id}.json"
    write_json_atomic(path, dataclass_payload(dataset))
    return path


def load_eval_dataset(path: str | Path) -> EvalDataset:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Eval dataset payload must be a JSON object.")
    return EvalDataset(
        dataset_id=str(payload["dataset_id"]),
        name=str(payload["name"]),
        adapter_name=str(payload["adapter_name"]),
        created_at=_parse_datetime(str(payload["created_at"])),
        cases=tuple(_curated_eval_case_from_payload(item) for item in payload.get("cases", [])),
        metadata=dict(payload.get("metadata", {})),
        contract_version=str(payload.get("contract_version") or ""),
    )


def replay_reply_eval_dataset(
    dataset: EvalDataset,
    *,
    runtime: ReplyRuntime | None = None,
) -> tuple[EvalReplayReport, Path]:
    if dataset.adapter_name != "reply":
        raise ValueError(f"Unsupported replay adapter: {dataset.adapter_name}")
    resolved_runtime = runtime or ReplyRuntime()
    results: list[EvalReplayCaseResult] = []
    for case in dataset.cases:
        ranked = resolved_runtime.suggest(case.thread_snapshot)
        actual_text = ranked.drafts[0].draft_text.strip()
        results.append(
            EvalReplayCaseResult(
                case_id=case.case_id,
                cycle_id=str(ranked.cycle_id),
                trace_ref=ranked.trace_ref,
                expected_text=case.expected_text,
                actual_text=actual_text,
                same_text=actual_text == case.expected_text,
                overlap_ratio=_token_overlap_ratio(case.expected_text, actual_text),
                edit_distance=_normalized_edit_distance(case.expected_text, actual_text),
            )
        )
    report = EvalReplayReport(
        dataset_id=dataset.dataset_id,
        adapter_name=dataset.adapter_name,
        replayed_at=datetime.now(UTC),
        case_results=tuple(results),
        metadata={"dataset_name": dataset.name},
    )
    report_path = persist_eval_replay_report(dataset.adapter_name, report)
    return report, report_path


def persist_eval_replay_report(adapter_name: str, report: EvalReplayReport) -> Path:
    paths = resolve_eval_dataset_paths(adapter_name)
    timestamp = report.replayed_at.strftime("%Y%m%dT%H%M%SZ")
    path = paths.reports_dir / f"{report.dataset_id}--{timestamp}.json"
    write_json_atomic(path, dataclass_payload(report))
    return path


def summarize_eval_replay_report(report: EvalReplayReport) -> dict[str, Any]:
    if not report.case_results:
        return {
            "case_count": 0,
            "exact_match_count": 0,
            "average_overlap_ratio": 0.0,
            "average_edit_distance": 0.0,
        }
    count = len(report.case_results)
    return {
        "case_count": count,
        "exact_match_count": sum(1 for case in report.case_results if case.same_text),
        "average_overlap_ratio": round(
            sum(case.overlap_ratio for case in report.case_results) / count,
            4,
        ),
        "average_edit_distance": round(
            sum(case.edit_distance for case in report.case_results) / count,
            4,
        ),
    }


def _curated_outcome(payload: dict[str, Any]):
    feedback_payloads = payload.get("feedback_events", [])
    if not feedback_payloads:
        raise ValueError("Cannot curate eval dataset case without feedback_events.")
    eligible = [
        outcome_event_from_payload(item)
        for item in feedback_payloads
        if str(item.get("disposition")) != DraftOutcomeDisposition.SHOWN.value
    ]
    if not eligible:
        raise ValueError("Cannot curate eval dataset case with only SHOWN feedback events.")
    return sorted(
        eligible,
        key=lambda event: (
            event.occurred_at.timestamp(),
            event.disposition.value,
            str(event.candidate_id or ""),
        ),
    )[-1]


def _accepted_artifact_version_from_payload(payload: dict[str, Any]) -> AcceptedArtifactVersion:
    return AcceptedArtifactVersion(
        artifact_key=str(payload["artifact_key"]),
        version=str(payload["version"]),
        source_project=str(payload["source_project"]),
        accepted_at=_parse_datetime(str(payload["accepted_at"])),
    )


def _curated_eval_case_from_payload(payload: dict[str, Any]) -> CuratedEvalCase:
    return CuratedEvalCase(
        case_id=str(payload["case_id"]),
        adapter_name=str(payload["adapter_name"]),
        curated_at=_parse_datetime(str(payload["curated_at"])),
        curated_from_cycle_id=UUID(str(payload["curated_from_cycle_id"])),
        curated_from_trace_ref=(
            str(payload["curated_from_trace_ref"]).strip()
            if payload.get("curated_from_trace_ref")
            else None
        ),
        selection_reason=str(payload["selection_reason"]),
        expected_text=str(payload["expected_text"]),
        expected_disposition=str(payload["expected_disposition"]),
        thread_snapshot=thread_snapshot_from_payload(dict(payload["thread_snapshot"])),
        accepted_artifact_version=_accepted_artifact_version_from_payload(
            dict(payload["accepted_artifact_version"])
        ),
        metadata=dict(payload.get("metadata", {})),
        contract_version=str(payload.get("contract_version") or ""),
    )


def _slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")
    if not text:
        raise ValueError("dataset_name must contain at least one alphanumeric character.")
    return text


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
