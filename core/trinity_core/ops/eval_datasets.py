"""Evaluation, replay, and governance artifacts derived from persisted runtime traces."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from trinity_core.adapters import SUPPORTED_ADAPTER_NAME_LIST
from trinity_core.ops.cycle_store import (
    dataclass_payload,
    resolve_cycle_storage_paths,
    write_json_atomic,
)
from trinity_core.ops.policy_registry import AcceptedArtifactRegistry
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
    CrossAdapterScoreEntry,
    CrossAdapterScoreReport,
    CuratedEvalCase,
    DraftOutcomeDisposition,
    EvalDataset,
    EvalReplayCaseResult,
    EvalReplayReport,
    ScoreGovernanceAdapterDashboardSummary,
    ScoreGovernanceArtifactStatus,
    ScoreGovernanceCheckResult,
    ScoreGovernanceDashboardReport,
    ScoreGovernancePolicy,
    ScoreGovernanceReleaseDecision,
    ScoreGovernanceReleaseReport,
    ScoreGovernanceStatusSurface,
    ScoreGovernanceTriageItem,
    ScoreGovernanceTriageReport,
    ScoreGovernanceTriageResolution,
    ScoreHealthReport,
    ScoreHealthReviewDecision,
    ScoreHealthTrendReport,
    ScoreHealthTupleCluster,
)


@dataclass(frozen=True, slots=True)
class EvalDatasetPaths:
    """Persistent artifact paths for curated eval datasets and replay reports."""

    adapter_name: str
    root_dir: Path
    datasets_dir: Path
    reports_dir: Path
    score_health_reports_dir: Path
    score_health_review_decisions_dir: Path
    score_health_trend_reports_dir: Path
    score_governance_release_reports_dir: Path
    score_governance_triage_reports_dir: Path
    score_governance_triage_resolutions_dir: Path
    score_governance_release_decisions_dir: Path


def resolve_eval_dataset_paths(adapter_name: str) -> EvalDatasetPaths:
    adapter_paths = resolve_adapter_runtime_paths(
        adapter_name,
        repo_root=Path(__file__).resolve().parents[3],
    )
    root_dir = adapter_paths.root_dir / "eval_datasets"
    datasets_dir = root_dir / "datasets"
    reports_dir = root_dir / "reports"
    score_health_reports_dir = root_dir / "score_health_reports"
    score_health_review_decisions_dir = root_dir / "score_health_review_decisions"
    score_health_trend_reports_dir = root_dir / "score_health_trend_reports"
    score_governance_release_reports_dir = root_dir / "score_governance_release_reports"
    score_governance_triage_reports_dir = root_dir / "score_governance_triage_reports"
    score_governance_triage_resolutions_dir = root_dir / "score_governance_triage_resolutions"
    score_governance_release_decisions_dir = root_dir / "score_governance_release_decisions"
    for path in (
        root_dir,
        datasets_dir,
        reports_dir,
        score_health_reports_dir,
        score_health_review_decisions_dir,
        score_health_trend_reports_dir,
        score_governance_release_reports_dir,
        score_governance_triage_reports_dir,
        score_governance_triage_resolutions_dir,
        score_governance_release_decisions_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
    return EvalDatasetPaths(
        adapter_name=adapter_paths.adapter_name,
        root_dir=root_dir,
        datasets_dir=datasets_dir,
        reports_dir=reports_dir,
        score_health_reports_dir=score_health_reports_dir,
        score_health_review_decisions_dir=score_health_review_decisions_dir,
        score_health_trend_reports_dir=score_health_trend_reports_dir,
        score_governance_release_reports_dir=score_governance_release_reports_dir,
        score_governance_triage_reports_dir=score_governance_triage_reports_dir,
        score_governance_triage_resolutions_dir=score_governance_triage_resolutions_dir,
        score_governance_release_decisions_dir=score_governance_release_decisions_dir,
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


def load_eval_replay_report(path: str | Path) -> EvalReplayReport:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Eval replay report payload must be a JSON object.")
    return EvalReplayReport(
        dataset_id=str(payload["dataset_id"]),
        adapter_name=str(payload["adapter_name"]),
        replayed_at=_parse_datetime(str(payload["replayed_at"])),
        case_results=tuple(
            EvalReplayCaseResult(
                case_id=str(item["case_id"]),
                cycle_id=str(item["cycle_id"]),
                trace_ref=(str(item["trace_ref"]).strip() if item.get("trace_ref") else None),
                expected_text=str(item["expected_text"]),
                actual_text=str(item["actual_text"]),
                same_text=bool(item["same_text"]),
                overlap_ratio=float(item["overlap_ratio"]),
                edit_distance=float(item["edit_distance"]),
            )
            for item in payload.get("case_results", [])
        ),
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


def build_score_health_report(
    *,
    report_name: str,
    adapter_name: str,
    trace_payloads: tuple[dict[str, Any], ...],
    metadata: dict[str, Any] | None = None,
) -> ScoreHealthReport:
    flag_counts: Counter[str] = Counter()
    tuple_counts: Counter[tuple[int, int, int]] = Counter()
    tuple_flag_counts: Counter[tuple[int, int, int]] = Counter()
    tuple_flags: dict[tuple[int, int, int], set[str]] = {}
    candidate_count = 0
    flagged_candidate_count = 0

    for payload in trace_payloads:
        for candidate in _score_health_candidates(payload):
            candidate_count += 1
            score_tuple = (
                int(candidate["final_scores"]["impact"]),
                int(candidate["final_scores"]["confidence"]),
                int(candidate["final_scores"]["ease"]),
            )
            tuple_counts[score_tuple] += 1
            flags = tuple(
                str(flag).strip() for flag in candidate.get("audit_flags", ()) if str(flag).strip()
            )
            if flags:
                flagged_candidate_count += 1
                tuple_flag_counts[score_tuple] += 1
                tuple_flags.setdefault(score_tuple, set()).update(flags)
                flag_counts.update(flags)

    tuple_clusters = tuple(
        ScoreHealthTupleCluster(
            impact=score_tuple[0],
            confidence=score_tuple[1],
            ease=score_tuple[2],
            occurrence_count=count,
            flagged_occurrence_count=tuple_flag_counts.get(score_tuple, 0),
            flags=tuple(sorted(tuple_flags.get(score_tuple, set()))),
        )
        for score_tuple, count in sorted(
            tuple_counts.items(),
            key=lambda item: (-item[1], -tuple_flag_counts.get(item[0], 0), item[0]),
        )
        if count > 1 or tuple_flag_counts.get(score_tuple, 0) > 0
    )

    return ScoreHealthReport(
        report_id=_slugify(report_name),
        adapter_name=adapter_name,
        created_at=datetime.now(UTC),
        trace_count=len(trace_payloads),
        candidate_count=candidate_count,
        flagged_candidate_count=flagged_candidate_count,
        flag_counts=dict(sorted(flag_counts.items())),
        tuple_clusters=tuple_clusters,
        metadata=metadata or {},
    )


def persist_score_health_report(adapter_name: str, report: ScoreHealthReport) -> Path:
    paths = resolve_eval_dataset_paths(adapter_name)
    path = paths.score_health_reports_dir / f"{report.report_id}.json"
    write_json_atomic(path, dataclass_payload(report))
    return path


def load_score_health_report(path: str | Path) -> ScoreHealthReport:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Score health report payload must be a JSON object.")
    return ScoreHealthReport(
        report_id=str(payload["report_id"]),
        adapter_name=str(payload["adapter_name"]),
        created_at=_parse_datetime(str(payload["created_at"])),
        trace_count=int(payload["trace_count"]),
        candidate_count=int(payload["candidate_count"]),
        flagged_candidate_count=int(payload["flagged_candidate_count"]),
        flag_counts={
            str(key): int(value) for key, value in dict(payload.get("flag_counts", {})).items()
        },
        tuple_clusters=tuple(
            ScoreHealthTupleCluster(
                impact=int(item["impact"]),
                confidence=int(item["confidence"]),
                ease=int(item["ease"]),
                occurrence_count=int(item["occurrence_count"]),
                flagged_occurrence_count=int(item["flagged_occurrence_count"]),
                flags=tuple(str(flag) for flag in item.get("flags", ())),
            )
            for item in payload.get("tuple_clusters", [])
        ),
        metadata=dict(payload.get("metadata", {})),
        contract_version=str(payload.get("contract_version") or ""),
    )


def persist_score_health_review_decision(
    adapter_name: str,
    decision: ScoreHealthReviewDecision,
) -> Path:
    paths = resolve_eval_dataset_paths(adapter_name)
    path = paths.score_health_review_decisions_dir / f"{decision.decision_id}.json"
    write_json_atomic(path, dataclass_payload(decision))
    return path


def load_score_health_review_decision(path: str | Path) -> ScoreHealthReviewDecision:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Score health review decision payload must be a JSON object.")
    return ScoreHealthReviewDecision(
        decision_id=str(payload["decision_id"]),
        report_id=str(payload["report_id"]),
        adapter_name=str(payload["adapter_name"]),
        decided_at=_parse_datetime(str(payload["decided_at"])),
        status=str(payload["status"]),
        notes=str(payload.get("notes") or ""),
        replay_report_dataset_id=(
            str(payload["replay_report_dataset_id"]).strip()
            if payload.get("replay_report_dataset_id")
            else None
        ),
        metadata=dict(payload.get("metadata", {})),
        contract_version=str(payload.get("contract_version") or ""),
    )


def load_score_health_trend_report(path: str | Path) -> ScoreHealthTrendReport:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Score health trend report payload must be a JSON object.")
    return ScoreHealthTrendReport(
        trend_report_id=str(payload["trend_report_id"]),
        adapter_name=str(payload["adapter_name"]),
        created_at=_parse_datetime(str(payload["created_at"])),
        report_ids=tuple(str(item) for item in payload.get("report_ids", ())),
        compared_report_count=int(payload["compared_report_count"]),
        persistent_flags={
            str(key): int(value) for key, value in dict(payload.get("persistent_flags", {})).items()
        },
        rising_flags={
            str(key): int(value) for key, value in dict(payload.get("rising_flags", {})).items()
        },
        recurring_tuple_clusters=tuple(
            ScoreHealthTupleCluster(
                impact=int(item["impact"]),
                confidence=int(item["confidence"]),
                ease=int(item["ease"]),
                occurrence_count=int(item["occurrence_count"]),
                flagged_occurrence_count=int(item["flagged_occurrence_count"]),
                flags=tuple(str(flag) for flag in item.get("flags", ())),
            )
            for item in payload.get("recurring_tuple_clusters", [])
        ),
        metadata=dict(payload.get("metadata", {})),
        contract_version=str(payload.get("contract_version") or ""),
    )


def persist_score_health_trend_report(
    adapter_name: str,
    report: ScoreHealthTrendReport,
) -> Path:
    paths = resolve_eval_dataset_paths(adapter_name)
    path = paths.score_health_trend_reports_dir / f"{report.trend_report_id}.json"
    write_json_atomic(path, dataclass_payload(report))
    return path


def persist_score_governance_release_report(
    adapter_name: str,
    report: ScoreGovernanceReleaseReport,
) -> Path:
    paths = resolve_eval_dataset_paths(adapter_name)
    path = paths.score_governance_release_reports_dir / f"{report.release_report_id}.json"
    write_json_atomic(path, dataclass_payload(report))
    return path


def load_score_governance_release_report(path: str | Path) -> ScoreGovernanceReleaseReport:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Score governance release report payload must be a JSON object.")
    return ScoreGovernanceReleaseReport(
        release_report_id=str(payload["release_report_id"]),
        adapter_name=str(payload["adapter_name"]),
        created_at=_parse_datetime(str(payload["created_at"])),
        allowed=bool(payload["allowed"]),
        override_required=bool(payload["override_required"]),
        release_risk=str(payload["release_risk"]),
        recommendation=str(payload["recommendation"]),
        report_id=(str(payload["report_id"]).strip() if payload.get("report_id") else None),
        decision_id=(str(payload["decision_id"]).strip() if payload.get("decision_id") else None),
        trend_report_id=(
            str(payload["trend_report_id"]).strip() if payload.get("trend_report_id") else None
        ),
        replay_report_dataset_id=(
            str(payload["replay_report_dataset_id"]).strip()
            if payload.get("replay_report_dataset_id")
            else None
        ),
        decision_status=(
            str(payload["decision_status"]).strip() if payload.get("decision_status") else None
        ),
        flagged_candidate_ratio=(
            float(payload["flagged_candidate_ratio"])
            if payload.get("flagged_candidate_ratio") is not None
            else None
        ),
        persistent_flag_count=int(payload.get("persistent_flag_count", 0)),
        rising_flag_count=int(payload.get("rising_flag_count", 0)),
        recurring_tuple_cluster_count=int(payload.get("recurring_tuple_cluster_count", 0)),
        blocking_reasons=tuple(str(item) for item in payload.get("blocking_reasons", ())),
        warnings=tuple(str(item) for item in payload.get("warnings", ())),
        metadata=dict(payload.get("metadata", {})),
        contract_version=str(payload.get("contract_version") or ""),
    )


def persist_score_governance_triage_report(
    adapter_name: str,
    report: ScoreGovernanceTriageReport,
) -> Path:
    paths = resolve_eval_dataset_paths(adapter_name)
    path = paths.score_governance_triage_reports_dir / f"{report.triage_report_id}.json"
    write_json_atomic(path, dataclass_payload(report))
    return path


def load_score_governance_triage_report(path: str | Path) -> ScoreGovernanceTriageReport:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Score governance triage report payload must be a JSON object.")
    return ScoreGovernanceTriageReport(
        triage_report_id=str(payload["triage_report_id"]),
        adapter_name=str(payload["adapter_name"]),
        created_at=_parse_datetime(str(payload["created_at"])),
        item_count=int(payload["item_count"]),
        items=tuple(
            ScoreGovernanceTriageItem(
                item_id=str(item["item_id"]),
                adapter_name=str(item["adapter_name"]),
                item_kind=str(item["item_kind"]),
                severity=str(item["severity"]),
                status=str(item["status"]),
                summary=str(item["summary"]),
                report_id=(str(item["report_id"]).strip() if item.get("report_id") else None),
                decision_id=(str(item["decision_id"]).strip() if item.get("decision_id") else None),
                trend_report_id=(
                    str(item["trend_report_id"]).strip() if item.get("trend_report_id") else None
                ),
                artifact_key=(
                    str(item["artifact_key"]).strip() if item.get("artifact_key") else None
                ),
                artifact_version=(
                    str(item["artifact_version"]).strip() if item.get("artifact_version") else None
                ),
                override_count=int(item.get("override_count", 0)),
                metadata=dict(item.get("metadata", {})),
                contract_version=str(item.get("contract_version") or ""),
            )
            for item in payload.get("items", [])
        ),
        metadata=dict(payload.get("metadata", {})),
        contract_version=str(payload.get("contract_version") or ""),
    )


def persist_score_governance_triage_resolution(
    adapter_name: str,
    resolution: ScoreGovernanceTriageResolution,
) -> Path:
    paths = resolve_eval_dataset_paths(adapter_name)
    path = paths.score_governance_triage_resolutions_dir / f"{resolution.resolution_id}.json"
    write_json_atomic(path, dataclass_payload(resolution))
    return path


def load_score_governance_triage_resolution(
    path: str | Path,
) -> ScoreGovernanceTriageResolution:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Score governance triage resolution payload must be a JSON object.")
    return ScoreGovernanceTriageResolution(
        resolution_id=str(payload["resolution_id"]),
        item_id=str(payload["item_id"]),
        adapter_name=str(payload["adapter_name"]),
        resolved_at=_parse_datetime(str(payload["resolved_at"])),
        resolution_status=str(payload["resolution_status"]),
        notes=str(payload.get("notes") or ""),
        metadata=dict(payload.get("metadata", {})),
        contract_version=str(payload.get("contract_version") or ""),
    )


def persist_score_governance_release_decision(
    adapter_name: str,
    decision: ScoreGovernanceReleaseDecision,
) -> Path:
    paths = resolve_eval_dataset_paths(adapter_name)
    path = paths.score_governance_release_decisions_dir / f"{decision.release_decision_id}.json"
    write_json_atomic(path, dataclass_payload(decision))
    return path


def load_score_governance_release_decision(path: str | Path) -> ScoreGovernanceReleaseDecision:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Score governance release decision payload must be a JSON object.")
    return ScoreGovernanceReleaseDecision(
        release_decision_id=str(payload["release_decision_id"]),
        release_report_id=str(payload["release_report_id"]),
        adapter_name=str(payload["adapter_name"]),
        decided_at=_parse_datetime(str(payload["decided_at"])),
        decision_status=str(payload["decision_status"]),
        notes=str(payload.get("notes") or ""),
        metadata=dict(payload.get("metadata", {})),
        contract_version=str(payload.get("contract_version") or ""),
    )


def build_score_governance_status_surface(
    adapter_name: str,
    *,
    registry: AcceptedArtifactRegistry | None = None,
) -> ScoreGovernanceStatusSurface:
    paths = resolve_eval_dataset_paths(adapter_name)
    accepted_registry = registry or AcceptedArtifactRegistry(adapter_name=adapter_name)
    latest_report_path = _latest_artifact_path(paths.score_health_reports_dir)
    latest_decision_path = _latest_artifact_path(paths.score_health_review_decisions_dir)
    latest_trend_path = _latest_artifact_path(paths.score_health_trend_reports_dir)
    latest_release_report_path = _latest_artifact_path(paths.score_governance_release_reports_dir)
    latest_release_decision_path = _latest_artifact_path(
        paths.score_governance_release_decisions_dir
    )
    latest_triage_path = _latest_artifact_path(paths.score_governance_triage_reports_dir)

    latest_report = (
        load_score_health_report(latest_report_path) if latest_report_path is not None else None
    )
    latest_decision = (
        load_score_health_review_decision(latest_decision_path)
        if latest_decision_path is not None
        else None
    )
    latest_trend = (
        load_score_health_trend_report(latest_trend_path) if latest_trend_path is not None else None
    )
    latest_release_report = (
        load_score_governance_release_report(latest_release_report_path)
        if latest_release_report_path is not None
        else None
    )
    latest_release_decision = (
        load_score_governance_release_decision(latest_release_decision_path)
        if latest_release_decision_path is not None
        else None
    )
    latest_triage = (
        load_score_governance_triage_report(latest_triage_path)
        if latest_triage_path is not None
        else None
    )
    resolutions = tuple(
        load_score_governance_triage_resolution(path)
        for path in sorted(paths.score_governance_triage_resolutions_dir.glob("*.json"))
    )
    artifact_statuses = tuple(
        _artifact_status_from_current_pointer(
            artifact_key,
            accepted_registry.current_pointer(artifact_key),
        )
        for artifact_key in accepted_registry.artifact_keys()
        if accepted_registry.current_pointer(artifact_key) is not None
    )

    return ScoreGovernanceStatusSurface(
        adapter_name=adapter_name,
        generated_at=datetime.now(UTC),
        latest_score_health_report_id=(
            latest_report.report_id if latest_report is not None else None
        ),
        latest_review_decision_id=(
            latest_decision.decision_id if latest_decision is not None else None
        ),
        latest_review_decision_status=(
            latest_decision.status if latest_decision is not None else None
        ),
        latest_trend_report_id=(
            latest_trend.trend_report_id if latest_trend is not None else None
        ),
        latest_release_report_id=(
            latest_release_report.release_report_id if latest_release_report is not None else None
        ),
        latest_release_decision_id=(
            latest_release_decision.release_decision_id
            if latest_release_decision is not None
            else None
        ),
        latest_release_decision_status=(
            latest_release_decision.decision_status
            if latest_release_decision is not None
            else None
        ),
        open_triage_item_count=(latest_triage.item_count if latest_triage is not None else 0),
        resolved_triage_resolution_count=sum(
            1
            for resolution in resolutions
            if resolution.resolution_status in {"resolved", "known_noise"}
        ),
        artifact_statuses=artifact_statuses,
        top_open_triage_summaries=tuple(
            item.summary for item in (latest_triage.items[:3] if latest_triage is not None else ())
        ),
        metadata={
            "latest_report_path": str(latest_report_path) if latest_report_path else None,
            "latest_decision_path": str(latest_decision_path) if latest_decision_path else None,
            "latest_trend_path": str(latest_trend_path) if latest_trend_path else None,
            "latest_release_report_path": (
                str(latest_release_report_path) if latest_release_report_path else None
            ),
            "latest_release_decision_path": (
                str(latest_release_decision_path) if latest_release_decision_path else None
            ),
            "latest_triage_path": str(latest_triage_path) if latest_triage_path else None,
        },
    )


def build_cross_adapter_score_report(
    *,
    report_name: str,
    adapter_names: tuple[str, ...] = SUPPORTED_ADAPTER_NAME_LIST,
    top_n: int = 5,
) -> CrossAdapterScoreReport:
    entries: list[CrossAdapterScoreEntry] = []
    for adapter_name in adapter_names:
        status_surface = build_score_governance_status_surface(adapter_name)
        cycle_paths = resolve_cycle_storage_paths(adapter_name)
        for cycle_path in _all_cycle_paths(cycle_paths.root_dir):
            payload = json.loads(cycle_path.read_text(encoding="utf-8"))
            entries.extend(_score_entries_from_trace_payload(payload, status_surface))

    ranked_entries = tuple(
        sorted(
            entries,
            key=lambda entry: (
                -entry.priority_score,
                -entry.ice_score,
                entry.adapter_name,
                entry.title,
            ),
        )
    )
    limited_entries = ranked_entries[: max(0, top_n)] if top_n else ranked_entries
    return CrossAdapterScoreReport(
        report_id=_slugify(report_name),
        created_at=datetime.now(UTC),
        adapter_names=tuple(adapter_names),
        candidate_count=len(entries),
        entries=limited_entries,
        metadata={"top_n": top_n},
    )


def build_score_governance_dashboard_report(
    *,
    report_name: str,
    adapter_names: tuple[str, ...] = SUPPORTED_ADAPTER_NAME_LIST,
) -> ScoreGovernanceDashboardReport:
    adapter_summaries: list[ScoreGovernanceAdapterDashboardSummary] = []
    persistent_flags: Counter[str] = Counter()
    rising_flags: Counter[str] = Counter()
    unresolved_override_count = 0
    unresolved_triage_item_count = 0

    for adapter_name in adapter_names:
        paths = resolve_eval_dataset_paths(adapter_name)
        latest_trend_path = _latest_artifact_path(paths.score_health_trend_reports_dir)
        latest_release_report_path = _latest_artifact_path(
            paths.score_governance_release_reports_dir
        )
        latest_triage_path = _latest_artifact_path(paths.score_governance_triage_reports_dir)
        trend_report = (
            load_score_health_trend_report(latest_trend_path)
            if latest_trend_path is not None
            else None
        )
        release_report = (
            load_score_governance_release_report(latest_release_report_path)
            if latest_release_report_path is not None
            else None
        )
        triage_report = (
            load_score_governance_triage_report(latest_triage_path)
            if latest_triage_path is not None
            else None
        )
        registry = AcceptedArtifactRegistry(adapter_name=adapter_name)
        override_count = sum(
            1
            for record in registry.all_transition_records()
            if record.score_governance_status == "override"
        )
        unresolved_override_count += override_count
        unresolved_triage_item_count += triage_report.item_count if triage_report is not None else 0
        if trend_report is not None:
            persistent_flags.update(trend_report.persistent_flags)
            rising_flags.update(trend_report.rising_flags)
        adapter_summaries.append(
            ScoreGovernanceAdapterDashboardSummary(
                adapter_name=adapter_name,
                unresolved_triage_item_count=(
                    triage_report.item_count if triage_report is not None else 0
                ),
                override_transition_count=override_count,
                persistent_flag_count=(
                    len(trend_report.persistent_flags) if trend_report is not None else 0
                ),
                rising_flag_count=(
                    len(trend_report.rising_flags) if trend_report is not None else 0
                ),
                recurring_tuple_cluster_count=(
                    len(trend_report.recurring_tuple_clusters)
                    if trend_report is not None
                    else 0
                ),
                latest_release_risk=(
                    release_report.release_risk if release_report is not None else None
                ),
            )
        )

    return ScoreGovernanceDashboardReport(
        report_id=_slugify(report_name),
        created_at=datetime.now(UTC),
        adapter_summaries=tuple(
            sorted(adapter_summaries, key=lambda item: (item.adapter_name,))
        ),
        top_persistent_flags=dict(
            sorted(persistent_flags.items(), key=lambda item: (-item[1], item[0]))[:5]
        ),
        top_rising_flags=dict(
            sorted(rising_flags.items(), key=lambda item: (-item[1], item[0]))[:5]
        ),
        unresolved_override_count=unresolved_override_count,
        unresolved_triage_item_count=unresolved_triage_item_count,
        metadata={},
    )


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


def summarize_score_health_report(report: ScoreHealthReport) -> dict[str, Any]:
    return {
        "trace_count": report.trace_count,
        "candidate_count": report.candidate_count,
        "flagged_candidate_count": report.flagged_candidate_count,
        "flag_type_count": len(report.flag_counts),
        "top_flags": [
            {"flag": flag, "count": count}
            for flag, count in sorted(
                report.flag_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[:5]
        ],
        "tuple_cluster_count": len(report.tuple_clusters),
    }


def review_score_health_report(
    report: ScoreHealthReport,
    *,
    replay_report: EvalReplayReport | None = None,
) -> dict[str, Any]:
    flagged_ratio = (
        round(report.flagged_candidate_count / report.candidate_count, 4)
        if report.candidate_count
        else 0.0
    )
    top_clusters = [
        {
            "score_tuple": [cluster.impact, cluster.confidence, cluster.ease],
            "occurrence_count": cluster.occurrence_count,
            "flagged_occurrence_count": cluster.flagged_occurrence_count,
            "flags": list(cluster.flags),
        }
        for cluster in report.tuple_clusters[:5]
    ]
    review = {
        "overview": {
            "report_id": report.report_id,
            "trace_count": report.trace_count,
            "candidate_count": report.candidate_count,
            "flagged_candidate_count": report.flagged_candidate_count,
            "flagged_candidate_ratio": flagged_ratio,
            "flag_type_count": len(report.flag_counts),
            "tuple_cluster_count": len(report.tuple_clusters),
        },
        "top_flags": [
            {"flag": flag, "count": count}
            for flag, count in sorted(
                report.flag_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[:5]
        ],
        "top_tuple_clusters": top_clusters,
        "triage_recommendations": _triage_recommendations(report, flagged_ratio),
    }
    if replay_report is not None:
        replay_summary = summarize_eval_replay_report(replay_report)
        review["replay_analytics"] = {
            **replay_summary,
            "quality_risk": _replay_quality_risk(replay_summary),
        }
    return review


def make_score_health_review_decision(
    report: ScoreHealthReport,
    *,
    status: str,
    notes: str = "",
    replay_report: EvalReplayReport | None = None,
    metadata: dict[str, Any] | None = None,
) -> ScoreHealthReviewDecision:
    decision_slug = _slugify(f"{report.report_id}-{status}")
    return ScoreHealthReviewDecision(
        decision_id=decision_slug,
        report_id=report.report_id,
        adapter_name=report.adapter_name,
        decided_at=datetime.now(UTC),
        status=str(status),
        notes=str(notes or ""),
        replay_report_dataset_id=(replay_report.dataset_id if replay_report is not None else None),
        metadata=metadata or {},
    )


def compare_score_health_reports(
    reports: tuple[ScoreHealthReport, ...],
    *,
    trend_report_name: str,
    metadata: dict[str, Any] | None = None,
) -> ScoreHealthTrendReport:
    if not reports:
        raise ValueError("At least one score-health report is required for comparison.")
    adapter_name = reports[0].adapter_name
    if any(report.adapter_name != adapter_name for report in reports):
        raise ValueError("All compared score-health reports must share the same adapter.")

    flag_occurrences: Counter[str] = Counter()
    first_counts: Counter[str] = Counter(reports[0].flag_counts)
    last_counts: Counter[str] = Counter(reports[-1].flag_counts)
    tuple_occurrences: Counter[tuple[int, int, int]] = Counter()
    tuple_flag_occurrences: Counter[tuple[int, int, int]] = Counter()
    tuple_flags: dict[tuple[int, int, int], set[str]] = {}

    for report in reports:
        for flag, count in report.flag_counts.items():
            if count > 0:
                flag_occurrences[flag] += 1
        for cluster in report.tuple_clusters:
            score_tuple = (cluster.impact, cluster.confidence, cluster.ease)
            tuple_occurrences[score_tuple] += 1
            tuple_flag_occurrences[score_tuple] += cluster.flagged_occurrence_count
            tuple_flags.setdefault(score_tuple, set()).update(cluster.flags)

    persistent_flags = {
        flag: flag_occurrences[flag]
        for flag in sorted(flag_occurrences)
        if flag_occurrences[flag] == len(reports)
    }
    rising_flags = {
        flag: last_counts.get(flag, 0) - first_counts.get(flag, 0)
        for flag in sorted(set(first_counts) | set(last_counts))
        if last_counts.get(flag, 0) > first_counts.get(flag, 0)
    }
    recurring_tuple_clusters = tuple(
        ScoreHealthTupleCluster(
            impact=score_tuple[0],
            confidence=score_tuple[1],
            ease=score_tuple[2],
            occurrence_count=occurrence_count,
            flagged_occurrence_count=tuple_flag_occurrences.get(score_tuple, 0),
            flags=tuple(sorted(tuple_flags.get(score_tuple, set()))),
        )
        for score_tuple, occurrence_count in sorted(
            tuple_occurrences.items(),
            key=lambda item: (-item[1], -tuple_flag_occurrences.get(item[0], 0), item[0]),
        )
        if occurrence_count > 1
    )

    return ScoreHealthTrendReport(
        trend_report_id=_slugify(trend_report_name),
        adapter_name=adapter_name,
        created_at=datetime.now(UTC),
        report_ids=tuple(report.report_id for report in reports),
        compared_report_count=len(reports),
        persistent_flags=persistent_flags,
        rising_flags=rising_flags,
        recurring_tuple_clusters=recurring_tuple_clusters,
        metadata=metadata or {},
    )


def summarize_score_health_trend_report(report: ScoreHealthTrendReport) -> dict[str, Any]:
    return {
        "compared_report_count": report.compared_report_count,
        "persistent_flag_count": len(report.persistent_flags),
        "rising_flag_count": len(report.rising_flags),
        "recurring_tuple_cluster_count": len(report.recurring_tuple_clusters),
        "top_persistent_flags": [
            {"flag": flag, "report_count": count}
            for flag, count in sorted(
                report.persistent_flags.items(),
                key=lambda item: (-item[1], item[0]),
            )[:5]
        ],
    }


def evaluate_score_governance(
    report: ScoreHealthReport,
    *,
    decision: ScoreHealthReviewDecision | None = None,
    trend_report: ScoreHealthTrendReport | None = None,
    policy: ScoreGovernancePolicy | None = None,
) -> ScoreGovernanceCheckResult:
    resolved_policy = policy or ScoreGovernancePolicy()
    blocking_reasons: list[str] = []
    warnings: list[str] = []
    flagged_ratio = (
        round(report.flagged_candidate_count / report.candidate_count, 4)
        if report.candidate_count
        else 0.0
    )

    if decision is not None:
        if decision.adapter_name != report.adapter_name:
            raise ValueError("Score-health decision adapter must match the report adapter.")
        if decision.report_id != report.report_id:
            raise ValueError("Score-health decision must reference the provided report.")
        if decision.status in resolved_policy.blocked_decision_statuses:
            blocking_reasons.append(
                f"review_decision:{decision.status}:operator review requires investigation "
                "before workflow acceptance"
            )
        else:
            warnings.append(f"review_decision:{decision.status}")

    if resolved_policy.max_flagged_candidate_ratio is not None:
        if flagged_ratio > resolved_policy.max_flagged_candidate_ratio:
            blocking_reasons.append(
                "flagged_candidate_ratio:"
                f"{flagged_ratio:.4f}>{resolved_policy.max_flagged_candidate_ratio:.4f}"
            )

    blocked_flags = {
        flag for flag in resolved_policy.blocked_flags if report.flag_counts.get(flag, 0) > 0
    }
    for flag in sorted(blocked_flags):
        blocking_reasons.append(f"blocked_flag:{flag}")

    if trend_report is not None:
        if trend_report.adapter_name != report.adapter_name:
            raise ValueError("Score-health trend report adapter must match the report adapter.")
        if report.report_id not in trend_report.report_ids:
            raise ValueError("Score-health trend report must include the provided report.")
        if resolved_policy.persistent_flag_tolerance is not None:
            persistent_count = len(trend_report.persistent_flags)
            if persistent_count > resolved_policy.persistent_flag_tolerance:
                blocking_reasons.append(
                    "persistent_flag_count:"
                    f"{persistent_count}>{resolved_policy.persistent_flag_tolerance}"
                )
        if resolved_policy.rising_flag_tolerance is not None:
            rising_count = len(trend_report.rising_flags)
            if rising_count > resolved_policy.rising_flag_tolerance:
                blocking_reasons.append(
                    f"rising_flag_count:{rising_count}>{resolved_policy.rising_flag_tolerance}"
                )
        if resolved_policy.recurring_tuple_cluster_tolerance is not None:
            cluster_count = len(trend_report.recurring_tuple_clusters)
            if cluster_count > resolved_policy.recurring_tuple_cluster_tolerance:
                blocking_reasons.append(
                    "recurring_tuple_cluster_count:"
                    f"{cluster_count}>{resolved_policy.recurring_tuple_cluster_tolerance}"
                )
        if not blocking_reasons:
            if trend_report.persistent_flags:
                warnings.append("persistent_flags_present")
            if trend_report.rising_flags:
                warnings.append("rising_flags_present")

    return ScoreGovernanceCheckResult(
        adapter_name=report.adapter_name,
        allowed=not blocking_reasons,
        override_required=bool(blocking_reasons),
        decision_status=decision.status if decision is not None else None,
        report_id=report.report_id,
        decision_id=decision.decision_id if decision is not None else None,
        trend_report_id=trend_report.trend_report_id if trend_report is not None else None,
        flagged_candidate_ratio=flagged_ratio,
        blocking_reasons=tuple(blocking_reasons),
        warnings=tuple(warnings),
    )


def build_score_governance_release_report(
    *,
    release_report_name: str,
    report: ScoreHealthReport,
    governance: ScoreGovernanceCheckResult,
    decision: ScoreHealthReviewDecision | None = None,
    trend_report: ScoreHealthTrendReport | None = None,
    replay_report: EvalReplayReport | None = None,
    metadata: dict[str, Any] | None = None,
) -> ScoreGovernanceReleaseReport:
    replay_quality_risk = (
        _replay_quality_risk(summarize_eval_replay_report(replay_report))
        if replay_report is not None
        else "unknown"
    )
    release_risk = _release_governance_risk(governance, trend_report, replay_quality_risk)
    recommendation = _release_governance_recommendation(
        governance,
        decision=decision,
        trend_report=trend_report,
        replay_quality_risk=replay_quality_risk,
    )
    return ScoreGovernanceReleaseReport(
        release_report_id=_slugify(release_report_name),
        adapter_name=report.adapter_name,
        created_at=datetime.now(UTC),
        allowed=governance.allowed,
        override_required=governance.override_required,
        release_risk=release_risk,
        recommendation=recommendation,
        report_id=report.report_id,
        decision_id=decision.decision_id if decision is not None else governance.decision_id,
        trend_report_id=(
            trend_report.trend_report_id if trend_report is not None else governance.trend_report_id
        ),
        replay_report_dataset_id=(replay_report.dataset_id if replay_report is not None else None),
        decision_status=governance.decision_status,
        flagged_candidate_ratio=governance.flagged_candidate_ratio,
        persistent_flag_count=(
            len(trend_report.persistent_flags) if trend_report is not None else 0
        ),
        rising_flag_count=(len(trend_report.rising_flags) if trend_report is not None else 0),
        recurring_tuple_cluster_count=(
            len(trend_report.recurring_tuple_clusters) if trend_report is not None else 0
        ),
        blocking_reasons=governance.blocking_reasons,
        warnings=governance.warnings,
        metadata={
            **(metadata or {}),
            "replay_quality_risk": replay_quality_risk,
        },
    )


def summarize_score_governance_release_report(
    report: ScoreGovernanceReleaseReport,
) -> dict[str, Any]:
    return {
        "allowed": report.allowed,
        "override_required": report.override_required,
        "release_risk": report.release_risk,
        "recommendation": report.recommendation,
        "blocking_reason_count": len(report.blocking_reasons),
        "warning_count": len(report.warnings),
        "persistent_flag_count": report.persistent_flag_count,
        "rising_flag_count": report.rising_flag_count,
        "recurring_tuple_cluster_count": report.recurring_tuple_cluster_count,
        "replay_quality_risk": report.metadata.get("replay_quality_risk"),
    }


def build_score_governance_triage_report(
    *,
    triage_report_name: str,
    adapter_name: str,
    decisions: tuple[ScoreHealthReviewDecision, ...],
    trend_reports: tuple[ScoreHealthTrendReport, ...],
    resolutions: tuple[ScoreGovernanceTriageResolution, ...] = (),
    registry: AcceptedArtifactRegistry | None = None,
    metadata: dict[str, Any] | None = None,
) -> ScoreGovernanceTriageReport:
    items: list[ScoreGovernanceTriageItem] = []
    resolution_map = {
        resolution.item_id: resolution
        for resolution in sorted(
            resolutions,
            key=lambda item: (item.resolved_at, item.resolution_id),
        )
    }
    unresolved_statuses = {"investigate", "blocked_release"}
    for decision in sorted(decisions, key=lambda item: (item.decided_at, item.decision_id)):
        if decision.status not in unresolved_statuses:
            continue
        severity = "high" if decision.status == "blocked_release" else "medium"
        item_id = _slugify(f"decision-{decision.decision_id}")
        resolution = resolution_map.get(item_id)
        if resolution is not None and resolution.resolution_status in {"resolved", "known_noise"}:
            continue
        items.append(
            ScoreGovernanceTriageItem(
                item_id=item_id,
                adapter_name=adapter_name,
                item_kind="review_decision",
                severity=severity,
                status=resolution.resolution_status if resolution is not None else "open",
                summary=(
                    f"Review decision {decision.decision_id} remains {decision.status} for "
                    f"report {decision.report_id}."
                ),
                report_id=decision.report_id,
                decision_id=decision.decision_id,
                metadata={
                    "notes": decision.notes,
                    "resolution_notes": resolution.notes if resolution is not None else "",
                },
            )
        )

    for trend_report in sorted(
        trend_reports,
        key=lambda item: (item.created_at, item.trend_report_id),
    ):
        if not trend_report.persistent_flags and not trend_report.rising_flags:
            continue
        item_id = _slugify(f"trend-{trend_report.trend_report_id}")
        resolution = resolution_map.get(item_id)
        if resolution is not None and resolution.resolution_status in {"resolved", "known_noise"}:
            continue
        items.append(
            ScoreGovernanceTriageItem(
                item_id=item_id,
                adapter_name=adapter_name,
                item_kind="trend_report",
                severity="medium",
                status=resolution.resolution_status if resolution is not None else "open",
                summary=(
                    f"Trend report {trend_report.trend_report_id} has "
                    f"{len(trend_report.persistent_flags)} persistent flags and "
                    f"{len(trend_report.rising_flags)} rising flags."
                ),
                trend_report_id=trend_report.trend_report_id,
                override_count=0,
                metadata={
                    "persistent_flags": dict(trend_report.persistent_flags),
                    "rising_flags": dict(trend_report.rising_flags),
                    "resolution_notes": resolution.notes if resolution is not None else "",
                },
            )
        )

    override_counts: Counter[tuple[str, str]] = Counter()
    latest_override: dict[tuple[str, str], Any] = {}
    if registry is not None:
        for transition in registry.all_transition_records():
            if transition.score_governance_status != "override":
                continue
            key = (transition.artifact.artifact_key, transition.artifact.version)
            override_counts[key] += 1
            latest_override[key] = transition
    for (artifact_key, artifact_version), count in sorted(
        override_counts.items(),
        key=lambda item: (-item[1], item[0]),
    ):
        transition = latest_override[(artifact_key, artifact_version)]
        item_id = _slugify(f"override-{artifact_key}-{artifact_version}")
        resolution = resolution_map.get(item_id)
        if resolution is not None and resolution.resolution_status in {"resolved", "known_noise"}:
            continue
        items.append(
            ScoreGovernanceTriageItem(
                item_id=item_id,
                adapter_name=adapter_name,
                item_kind="override_transition",
                severity="high" if count > 1 else "medium",
                status=resolution.resolution_status if resolution is not None else "open",
                summary=(
                    f"Accepted artifact {artifact_key}:{artifact_version} has {count} "
                    "score-governance override transition(s)."
                ),
                report_id=transition.score_governance_report_id,
                decision_id=transition.score_governance_decision_id,
                trend_report_id=transition.score_governance_trend_report_id,
                artifact_key=artifact_key,
                artifact_version=artifact_version,
                override_count=count,
                metadata={
                    "override_notes": list(transition.score_governance_override_notes),
                    "resolution_notes": resolution.notes if resolution is not None else "",
                },
            )
        )

    ordered_items = tuple(
        sorted(
            items,
            key=lambda item: (
                {"high": 0, "medium": 1, "low": 2}.get(item.severity, 3),
                item.item_kind,
                item.item_id,
            ),
        )
    )
    return ScoreGovernanceTriageReport(
        triage_report_id=_slugify(triage_report_name),
        adapter_name=adapter_name,
        created_at=datetime.now(UTC),
        item_count=len(ordered_items),
        items=ordered_items,
        metadata=metadata or {},
    )


def summarize_score_governance_triage_report(
    report: ScoreGovernanceTriageReport,
) -> dict[str, Any]:
    severity_counts = Counter(item.severity for item in report.items)
    kind_counts = Counter(item.item_kind for item in report.items)
    return {
        "item_count": report.item_count,
        "high_severity_count": severity_counts.get("high", 0),
        "medium_severity_count": severity_counts.get("medium", 0),
        "kind_counts": dict(sorted(kind_counts.items())),
    }


def summarize_score_governance_status_surface(
    surface: ScoreGovernanceStatusSurface,
) -> dict[str, Any]:
    return {
        "adapter_name": surface.adapter_name,
        "latest_score_health_report_id": surface.latest_score_health_report_id,
        "latest_review_decision_status": surface.latest_review_decision_status,
        "latest_release_decision_status": surface.latest_release_decision_status,
        "open_triage_item_count": surface.open_triage_item_count,
        "resolved_triage_resolution_count": surface.resolved_triage_resolution_count,
        "artifact_count": len(surface.artifact_statuses),
    }


def summarize_cross_adapter_score_report(report: CrossAdapterScoreReport) -> dict[str, Any]:
    top_ice = sorted(
        report.entries,
        key=lambda entry: (
            -entry.ice_score,
            -entry.priority_score,
            entry.adapter_name,
            entry.title,
        ),
    )[:5]
    top_priority = sorted(
        report.entries,
        key=lambda entry: (
            -entry.priority_score,
            -entry.ice_score,
            entry.adapter_name,
            entry.title,
        ),
    )[:5]
    return {
        "adapter_count": len(report.adapter_names),
        "candidate_count": report.candidate_count,
        "top_ice": [
            {
                "adapter_name": entry.adapter_name,
                "title": entry.title,
                "ice_score": entry.ice_score,
                "priority_score": entry.priority_score,
            }
            for entry in top_ice
        ],
        "top_priority": [
            {
                "adapter_name": entry.adapter_name,
                "title": entry.title,
                "ice_score": entry.ice_score,
                "priority_score": entry.priority_score,
            }
            for entry in top_priority
        ],
    }


def summarize_score_governance_dashboard_report(
    report: ScoreGovernanceDashboardReport,
) -> dict[str, Any]:
    return {
        "adapter_count": len(report.adapter_summaries),
        "unresolved_override_count": report.unresolved_override_count,
        "unresolved_triage_item_count": report.unresolved_triage_item_count,
        "top_persistent_flags": report.top_persistent_flags,
        "top_rising_flags": report.top_rising_flags,
    }


def make_score_governance_triage_resolution(
    *,
    adapter_name: str,
    item_id: str,
    resolution_status: str,
    notes: str = "",
    metadata: dict[str, Any] | None = None,
) -> ScoreGovernanceTriageResolution:
    return ScoreGovernanceTriageResolution(
        resolution_id=_slugify(f"{item_id}-{resolution_status}"),
        item_id=str(item_id),
        adapter_name=adapter_name,
        resolved_at=datetime.now(UTC),
        resolution_status=str(resolution_status),
        notes=str(notes or ""),
        metadata=metadata or {},
    )


def make_score_governance_release_decision(
    report: ScoreGovernanceReleaseReport,
    *,
    decision_status: str,
    notes: str = "",
    metadata: dict[str, Any] | None = None,
) -> ScoreGovernanceReleaseDecision:
    return ScoreGovernanceReleaseDecision(
        release_decision_id=_slugify(f"{report.release_report_id}-{decision_status}"),
        release_report_id=report.release_report_id,
        adapter_name=report.adapter_name,
        decided_at=datetime.now(UTC),
        decision_status=str(decision_status),
        notes=str(notes or ""),
        metadata=metadata or {},
    )


def _latest_artifact_path(directory: Path) -> Path | None:
    paths = sorted(
        directory.glob("*.json"),
        key=lambda path: (path.stat().st_mtime, path.name),
    )
    return paths[-1] if paths else None


def _artifact_status_from_current_pointer(
    artifact_key: str,
    pointer: dict[str, Any] | None,
) -> ScoreGovernanceArtifactStatus:
    if pointer is None:
        raise ValueError("Current pointer is required.")
    artifact_payload = dict(pointer.get("artifact", {}))
    return ScoreGovernanceArtifactStatus(
        artifact_key=artifact_key,
        current_version=str(artifact_payload["version"]),
        acceptance_mode=(
            str(pointer["acceptance_mode"]).strip() if pointer.get("acceptance_mode") else None
        ),
        score_governance_status=(
            str(pointer["score_governance_status"]).strip()
            if pointer.get("score_governance_status")
            else None
        ),
        score_governance_report_id=(
            str(pointer["score_governance_report_id"]).strip()
            if pointer.get("score_governance_report_id")
            else None
        ),
        score_governance_decision_id=(
            str(pointer["score_governance_decision_id"]).strip()
            if pointer.get("score_governance_decision_id")
            else None
        ),
        score_governance_trend_report_id=(
            str(pointer["score_governance_trend_report_id"]).strip()
            if pointer.get("score_governance_trend_report_id")
            else None
        ),
        release_governance_report_id=(
            str(pointer["release_governance_report_id"]).strip()
            if pointer.get("release_governance_report_id")
            else None
        ),
        release_governance_decision_id=(
            str(pointer["release_governance_decision_id"]).strip()
            if pointer.get("release_governance_decision_id")
            else None
        ),
        release_governance_decision_status=(
            str(pointer["release_governance_decision_status"]).strip()
            if pointer.get("release_governance_decision_status")
            else None
        ),
        override_note_count=len(tuple(pointer.get("score_governance_override_notes") or ())),
    )


def _all_cycle_paths(root_dir: Path) -> tuple[Path, ...]:
    cycle_paths = set(root_dir.glob("cycles/*.json"))
    cycle_paths.update(root_dir.glob("companies/*/cycles/*.json"))
    return tuple(sorted(cycle_paths))


def _score_entries_from_trace_payload(
    payload: dict[str, Any],
    surface: ScoreGovernanceStatusSurface,
) -> tuple[CrossAdapterScoreEntry, ...]:
    adapter_name = (
        str(payload.get("adapter_name") or surface.adapter_name).strip()
        or surface.adapter_name
    )
    cycle_id = str(payload.get("cycle_id") or "").strip()
    if not cycle_id:
        return ()
    release_status = surface.latest_release_decision_status
    governance_status = (
        surface.artifact_statuses[0].score_governance_status if surface.artifact_statuses else None
    )
    entries: list[CrossAdapterScoreEntry] = []
    if adapter_name == "spot":
        result = dict(payload.get("spot_reasoning_result", {}))
        for candidate in result.get("candidates", ()):
            if not isinstance(candidate, dict):
                continue
            entries.append(
                CrossAdapterScoreEntry(
                    adapter_name=adapter_name,
                    cycle_id=cycle_id,
                    candidate_id=str(candidate.get("candidate_key") or ""),
                    title=str(
                        candidate.get("interpretation")
                        or candidate.get("candidate_key")
                        or ""
                    ),
                    candidate_type="ACTION",
                    ice_score=float(candidate.get("ice_score") or 0.0),
                    priority_score=float(candidate.get("priority_score") or 0.0),
                    audit_flags=(),
                    score_governance_status=governance_status,
                    release_governance_decision_status=release_status,
                )
            )
        return tuple(entry for entry in entries if entry.candidate_id and entry.title)

    audit_by_candidate = {
        str(candidate.get("candidate_id") or ""): tuple(
            str(flag).strip() for flag in candidate.get("audit_flags", ()) if str(flag).strip()
        )
        for candidate in payload.get("runtime_score_audit", {}).get("candidates", ())
        if isinstance(candidate, dict)
    }
    for candidate in payload.get("candidates", ()):
        if not isinstance(candidate, dict):
            continue
        scores = dict(candidate.get("scores", {}))
        if not {"impact", "confidence", "ease"} <= scores.keys():
            continue
        ice_score = float(
            int(scores["impact"]) * int(scores["confidence"]) * int(scores["ease"])
        )
        priority_score = round(
            (_percent(scores.get("quality_score")) * 0.35)
            + (_percent(scores.get("urgency_score")) * 0.25)
            + (_percent(scores.get("freshness_score")) * 0.20)
            + (_percent(scores.get("feedback_score")) * 0.10)
            + (((ice_score / 1000.0) * 100.0) * 0.10),
            6,
        )
        candidate_id = str(candidate.get("candidate_id") or "")
        entries.append(
            CrossAdapterScoreEntry(
                adapter_name=adapter_name,
                cycle_id=cycle_id,
                candidate_id=candidate_id,
                title=str(candidate.get("title") or candidate_id),
                candidate_type=str(candidate.get("candidate_type") or "ACTION"),
                ice_score=ice_score,
                priority_score=priority_score,
                audit_flags=audit_by_candidate.get(candidate_id, ()),
                score_governance_status=governance_status,
                release_governance_decision_status=release_status,
            )
        )
    return tuple(entries)


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


def _score_health_candidates(payload: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    runtime_score_audit = payload.get("runtime_score_audit", {})
    candidates = runtime_score_audit.get("candidates", ())
    if candidates:
        return tuple(dict(candidate) for candidate in candidates if isinstance(candidate, dict))

    fallback: list[dict[str, Any]] = []
    for candidate in payload.get("candidates", ()):
        if not isinstance(candidate, dict):
            continue
        scores = dict(candidate.get("scores", {}))
        if not {"impact", "confidence", "ease"} <= scores.keys():
            continue
        fallback.append(
            {
                "final_scores": {
                    "impact": int(scores["impact"]),
                    "confidence": int(scores["confidence"]),
                    "ease": int(scores["ease"]),
                },
                "audit_flags": tuple(scores.get("audit_flags", ())),
            }
        )
    return tuple(fallback)


def _triage_recommendations(
    report: ScoreHealthReport,
    flagged_ratio: float,
) -> list[str]:
    recommendations: list[str] = []
    if flagged_ratio >= 0.5:
        recommendations.append(
            "High flagged-candidate ratio suggests score calibration needs prompt "
            "or evidence review."
        )
    if report.flag_counts.get("cross_run_tuple_clustering", 0) > 0:
        recommendations.append(
            "Recurring cross-run tuple clustering suggests repeated unsupported score habits."
        )
    if report.flag_counts.get("weak_confidence_rationale", 0) > 0:
        recommendations.append(
            "Weak confidence rationales are recurring; strengthen evidence anchors "
            "or rationale generation."
        )
    if report.tuple_clusters and report.tuple_clusters[0].occurrence_count >= 3:
        recommendations.append(
            "A recurring score tuple dominates the trace set; inspect whether "
            "scoring diversity is collapsing."
        )
    if not recommendations:
        recommendations.append(
            "No acute score-health pattern requires immediate operator intervention."
        )
    return recommendations


def _replay_quality_risk(summary: dict[str, Any]) -> str:
    if summary["case_count"] == 0:
        return "unknown"
    if summary["exact_match_count"] == summary["case_count"]:
        return "low"
    if summary["average_edit_distance"] >= 0.35 or summary["average_overlap_ratio"] < 0.7:
        return "high"
    return "medium"


def _release_governance_risk(
    governance: ScoreGovernanceCheckResult,
    trend_report: ScoreHealthTrendReport | None,
    replay_quality_risk: str,
) -> str:
    if not governance.allowed:
        return "high"
    if replay_quality_risk == "high":
        return "high"
    if trend_report is not None and (trend_report.persistent_flags or trend_report.rising_flags):
        return "medium"
    if governance.warnings or replay_quality_risk == "medium":
        return "medium"
    return "low"


def _release_governance_recommendation(
    governance: ScoreGovernanceCheckResult,
    *,
    decision: ScoreHealthReviewDecision | None,
    trend_report: ScoreHealthTrendReport | None,
    replay_quality_risk: str,
) -> str:
    if not governance.allowed:
        return (
            "Block release by default; require explicit operator override with notes "
            "before promotion."
        )
    if replay_quality_risk == "high":
        return (
            "Pause release and inspect replay drift before promotion, even though the "
            "score-governance gate passed."
        )
    if decision is not None and decision.status == "known_noise":
        return "Release may proceed with documented known-noise rationale."
    if trend_report is not None and (trend_report.persistent_flags or trend_report.rising_flags):
        return "Release may proceed, but review persistent/rising governance patterns first."
    if governance.warnings:
        return "Release may proceed with operator awareness of non-blocking governance warnings."
    return "Release may proceed."


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


def _percent(value: float | None) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(100.0, float(value)))
