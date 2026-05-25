"""Local CLI entrypoints for adapter-aware Trinity runtime operations."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from trinity_core.adapters import (
    REPLY_ADAPTER_NAME,
    SUPPORTED_ADAPTER_NAME_LIST,
    SUPPORTED_ADAPTER_NAMES,
    require_supported_adapter,
)
from trinity_core.adapters.model import (
    ModelInventoryError,
    UnsupportedModelProviderError,
    load_model_inventory,
)
from trinity_core.adapters.product.reply import (
    document_record_from_payload,
    memory_event_from_payload,
    outcome_event_from_payload,
    thread_snapshot_from_payload,
)
from trinity_core.adapters.product.spot import (
    spot_reasoning_request_from_payload,
    spot_review_outcome_from_payload,
)
from trinity_core.model_config import (
    TrinityModelConfig,
    TrinityRoleRoute,
    config_path_for_adapter,
    load_model_config_for_adapter,
    resolve_runtime_model_config,
    save_model_config_for_adapter,
)
from trinity_core.ops import (
    AcceptedArtifactRegistry,
    AdapterFoundationPolicy,
    ControlPlaneStore,
    GobiiAgentClient,
    GobiiNormalizationError,
    GobiiTaskClient,
    GobiiTaskClientError,
    TrainClientError,
    accept_reply_behavior_policy,
    accept_spot_review_policy,
    apply_post_training_curation_decision,
    build_cross_adapter_score_report,
    build_eval_dataset,
    build_foundation_provider_alignment,
    build_gobii_tracked_entity_enrichment_bundle,
    build_gobii_workflow_bundle,
    build_post_training_dataset,
    build_post_training_dataset_split,
    build_score_governance_dashboard_report,
    build_score_governance_release_report,
    build_score_governance_status_surface,
    build_score_governance_triage_report,
    build_score_health_report,
    check_reply_compatibility,
    compare_score_health_reports,
    curate_eval_case_from_trace_payload,
    current_config_route_set,
    default_train_proposal_paths,
    default_train_spot_proposal_paths,
    deterministic_route_set,
    evaluate_score_governance,
    gobii_task_normalization_request_from_payload,
    inspect_portable_export,
    inspect_runtime_candidate_import,
    load_control_plane_job,
    load_eval_dataset,
    load_eval_replay_report,
    load_gobii_tracked_entity_enrichment_bundle,
    load_gobii_workflow_bundle,
    load_persisted_gobii_task_record,
    load_post_training_dataset,
    load_provider_route_sets,
    load_reply_shadow_fixtures,
    load_score_governance_release_report,
    load_score_governance_triage_report,
    load_score_governance_triage_resolution,
    load_score_health_report,
    load_score_health_review_decision,
    load_score_health_trend_report,
    load_spot_review_policy_file,
    make_post_training_curation_decision,
    make_prepared_draft_refresh_job,
    make_provider_comparison_job,
    make_score_governance_release_decision,
    make_score_governance_triage_resolution,
    make_score_health_review_decision,
    merge_eval_dataset_cases,
    merge_gobii_task_context,
    normalize_gobii_task_output,
    normalize_gobii_tracked_entity_enrichment_bundle,
    persist_eval_dataset,
    persist_gobii_task_record,
    persist_gobii_tracked_entity_enrichment_bundle,
    persist_gobii_workflow_bundle,
    persist_post_training_curation_decision,
    persist_post_training_dataset,
    persist_post_training_dataset_split,
    persist_reply_policy_review_result,
    persist_score_governance_release_decision,
    persist_score_governance_release_report,
    persist_score_governance_triage_report,
    persist_score_governance_triage_resolution,
    persist_score_health_report,
    persist_score_health_review_decision,
    persist_score_health_trend_report,
    probe_gobii_seam,
    probe_train_seam,
    promote_post_training_dataset,
    propose_reply_policy_with_train,
    propose_spot_review_policy_with_train,
    register_gobii_workflow_bundle,
    replay_reply_eval_dataset,
    resolve_eval_dataset_paths,
    review_reply_behavior_policy,
    review_score_health_report,
    review_spot_review_policy,
    run_control_plane_job,
    run_foundation_check,
    run_reply_provider_comparison_from_fixture_dir,
    run_reply_shadow_fixtures,
    schedule_prepared_draft_refresh_jobs,
    shadow_fixture_payload,
    smoke_provider_routes,
    submit_gobii_tracked_entity_enrichment_bundle,
    summarize_cross_adapter_score_report,
    summarize_eval_replay_report,
    summarize_post_training_dataset,
    summarize_post_training_dataset_split,
    summarize_reply_shadow_results,
    summarize_score_governance_dashboard_report,
    summarize_score_governance_release_report,
    summarize_score_governance_status_surface,
    summarize_score_governance_triage_report,
    summarize_score_health_report,
    summarize_score_health_trend_report,
    validate_portable_export_lineage,
)
from trinity_core.ops import (
    adopt_runtime_candidate_import as adopt_runtime_candidate_import_op,
)
from trinity_core.ops.cycle_store import RuntimeCycleStore, dataclass_payload
from trinity_core.ops.foundation_policy import (
    TrinityFoundationPolicy,
    foundation_policy_path,
    load_foundation_policy,
    save_foundation_policy,
)
from trinity_core.ops.relation_health import classify_provider_error_code
from trinity_core.ops.spot_policy_store import SpotPolicyStore
from trinity_core.ops.train_client import DEFAULT_TRAIN_API_BASE_URL
from trinity_core.reply_runtime import training_bundle_type_from_payload
from trinity_core.runtime import TrinityRuntime
from trinity_core.schemas import (
    AcceptedArtifactVersion,
    GobiiTaskCreateRequest,
    PortableExportFamily,
    PostTrainingAnnotationStatus,
    PostTrainingDatasetStatus,
    PostTrainingPurpose,
    ScoreGovernancePolicy,
    gobii_tracked_entity_enrichment_request_from_payload,
)
from trinity_core.schemas.spot_policy import SpotReviewScopeKind

COMMAND_ALIASES = {
    "reply-suggest": "suggest",
    "reply-record-outcome": "record-outcome",
    "reply-export-trace": "export-trace",
    "reply-export-training-bundle": "export-training-bundle",
    "reply-run-shadow-fixtures": "run-shadow-fixtures",
    "reply-train-propose-policy": "train-propose-policy",
    "reply-policy-accept": "policy-accept",
    "reply-policy-review": "policy-review",
    "reply-policy-review-surface": "policy-review-surface",
    "reply-policy-promote": "policy-promote",
    "reply-policy-rollback": "policy-rollback",
    "reply-policy-status": "policy-status",
    "reply-show-config": "show-config",
    "reply-runtime-status": "runtime-status",
    "reply-write-config": "write-config",
    "reply-ingest-memory-event": "ingest-memory-event",
    "reply-register-document": "register-document",
    "reply-get-prepared-draft": "get-prepared-draft",
    "reply-refresh-prepared-draft": "refresh-prepared-draft",
}

CLI_CONTRACT_VERSION = "trinity_cli.v1"
RUNTIME_STATUS_SCHEMA_VERSION = 5
CLI_ERROR_SCHEMA_VERSION = 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trinity")
    subparsers = parser.add_subparsers(dest="command", required=True)

    _build_generic_parsers(subparsers)
    _build_reply_compat_parsers(subparsers)

    args = parser.parse_args(argv)
    command = COMMAND_ALIASES.get(args.command, args.command)
    adapter_arg = getattr(args, "adapter", REPLY_ADAPTER_NAME)
    adapter_name = require_supported_adapter(
        REPLY_ADAPTER_NAME if isinstance(adapter_arg, list) else adapter_arg
    )
    registry = AcceptedArtifactRegistry(adapter_name=adapter_name)
    runtime: TrinityRuntime | None = None

    def get_runtime() -> TrinityRuntime:
        nonlocal runtime
        if runtime is None:
            runtime = TrinityRuntime(adapter_name=adapter_name)
        return runtime

    if command == "suggest":
        payload = _load_json(args.input_file)
        result = get_runtime().suggest(thread_snapshot_from_payload(payload))
        _write_json(dataclass_payload(result))
        return 0

    if command == "reason-spot":
        _require_spot_adapter(adapter_name, command)
        payload = _load_json(args.input_file)
        result = get_runtime().reason_spot(spot_reasoning_request_from_payload(payload))
        _write_json(dataclass_payload(result))
        return 0

    if command == "record-outcome":
        payload = _load_json(args.input_file)
        result = get_runtime().record_outcome(outcome_event_from_payload(payload))
        _write_json(result)
        return 0

    if command == "record-outcomes-batch":
        payload = _load_json(args.input_file)
        items = _batch_items_from_payload(payload)
        results: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        runtime = get_runtime()
        for index, item in enumerate(items):
            try:
                result = runtime.record_outcome(outcome_event_from_payload(item))
                results.append({"index": index, "cycle_id": str(item.get("cycle_id") or ""), "result": result})
            except Exception as exc:  # pragma: no cover - exercised by live operator paths
                errors.append({"index": index, "cycle_id": str(item.get("cycle_id") or ""), "message": str(exc)})
        _write_json(
            {
                "status": "ok" if not errors else "partial",
                "processed_count": len(results),
                "error_count": len(errors),
                "results": results,
                "errors": errors,
            }
        )
        return 0

    if command == "record-spot-review-outcome":
        _require_spot_adapter(adapter_name, command)
        payload = _load_json(args.input_file)
        result = get_runtime().record_spot_review_outcome(spot_review_outcome_from_payload(payload))
        _write_json(result)
        return 0

    if command == "ingest-memory-event":
        payload = _load_json(args.input_file)
        result = get_runtime().ingest_memory_event(memory_event_from_payload(payload))
        _write_json(result)
        return 0

    if command == "ingest-memory-events-batch":
        payload = _load_json(args.input_file)
        items = _batch_items_from_payload(payload)
        results: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        runtime = get_runtime()
        for index, item in enumerate(items):
            try:
                result = runtime.ingest_memory_event(memory_event_from_payload(item))
                results.append({"index": index, "source_ref": str(item.get("source_ref") or ""), "result": result})
            except Exception as exc:  # pragma: no cover - exercised by live operator paths
                errors.append({"index": index, "source_ref": str(item.get("source_ref") or ""), "message": str(exc)})
        _write_json(
            {
                "status": "ok" if not errors else "partial",
                "processed_count": len(results),
                "error_count": len(errors),
                "results": results,
                "errors": errors,
            }
        )
        return 0

    if command == "register-document":
        payload = _load_json(args.input_file)
        result = get_runtime().register_document(document_record_from_payload(payload))
        _write_json(result)
        return 0

    if command == "register-documents-batch":
        payload = _load_json(args.input_file)
        items = _batch_items_from_payload(payload)
        results: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        runtime = get_runtime()
        for index, item in enumerate(items):
            try:
                result = runtime.register_document(document_record_from_payload(item))
                results.append({"index": index, "document_ref": str(item.get("document_ref") or ""), "result": result})
            except Exception as exc:  # pragma: no cover - exercised by live operator paths
                errors.append({"index": index, "document_ref": str(item.get("document_ref") or ""), "message": str(exc)})
        _write_json(
            {
                "status": "ok" if not errors else "partial",
                "processed_count": len(results),
                "error_count": len(errors),
                "results": results,
                "errors": errors,
            }
        )
        return 0

    if command == "get-prepared-draft":
        result = get_runtime().get_prepared_draft(
            company_id=args.company_id,
            thread_ref=str(args.thread_ref),
        )
        _write_json(result)
        return 0

    if command == "refresh-prepared-draft":
        result = get_runtime().refresh_prepared_draft(
            company_id=args.company_id,
            thread_ref=str(args.thread_ref),
            generation_reason=str(args.reason or "manual_refresh"),
            overwrite_mode=str(args.overwrite_mode or "if_stale_or_dirty"),
        )
        _write_json(result)
        return 0

    if command == "plan-prepared-draft-refresh":
        result = get_runtime().inspect_prepared_draft_refresh(
            company_id=args.company_id,
            limit=int(args.limit),
            stale_after_minutes=int(args.stale_after_minutes),
        )
        _write_json(result)
        return 0

    if command == "schedule-prepared-draft-refresh":
        inspection, jobs, job_paths = schedule_prepared_draft_refresh_jobs(
            company_id=str(args.company_id),
            limit=int(args.limit),
            stale_after_minutes=int(args.stale_after_minutes),
            generation_reason=str(args.reason or "scheduled_active_thread_refresh"),
            schedule_hint=args.schedule_hint,
            description=args.description,
        )
        _write_json(
            {
                "inspection": inspection,
                "job_paths": [str(path) for path in job_paths],
                "jobs": [dataclass_payload(job) for job in jobs],
            }
        )
        return 0

    if command == "export-trace":
        result = get_runtime().export_trace(UUID(args.cycle_id))
        _write_json(result)
        return 0

    if command == "build-source-export":
        _require_reply_adapter(adapter_name, command)
        result = get_runtime().build_source_export(
            company_id=args.company_id,
            snapshot_ref=args.snapshot_ref,
        )
        _write_json(result)
        return 0

    if command == "build-outcome-export":
        _require_reply_adapter(adapter_name, command)
        result = get_runtime().build_outcome_export(
            company_id=args.company_id,
            snapshot_ref=args.snapshot_ref,
        )
        _write_json(result)
        return 0

    if command == "build-memory-export":
        _require_reply_adapter(adapter_name, command)
        result = get_runtime().build_memory_export(
            company_id=args.company_id,
            snapshot_ref=args.snapshot_ref,
        )
        _write_json(result)
        return 0

    if command == "build-delta-export":
        _require_reply_adapter(adapter_name, command)
        if not args.prior_snapshot_ref and not args.prior_export_id:
            raise ValueError(
                "build-delta-export requires --prior-snapshot-ref or --prior-export-id."
            )
        result = get_runtime().build_delta_export(
            company_id=args.company_id,
            cutoff_at=_parse_datetime(str(args.cutoff_at)),
            snapshot_ref=str(args.snapshot_ref),
            prior_snapshot_ref=args.prior_snapshot_ref,
            prior_export_id=args.prior_export_id,
        )
        _write_json(result)
        return 0

    if command == "inspect-export-metadata":
        _require_reply_adapter(adapter_name, command)
        result = inspect_portable_export(
            adapter_name=adapter_name,
            company_id=args.company_id,
            export_family=str(args.export_family),
            export_id=str(args.export_id),
        )
        _write_json(result)
        return 0

    if command == "validate-export-lineage":
        _require_reply_adapter(adapter_name, command)
        result = validate_portable_export_lineage(
            adapter_name=adapter_name,
            company_id=args.company_id,
            export_family=str(args.export_family),
            export_id=str(args.export_id),
        )
        _write_json(result)
        return 0 if result["valid"] else 2

    if command == "import-runtime-candidate-pack":
        _require_reply_adapter(adapter_name, command)
        result = get_runtime().import_runtime_candidate_pack(
            company_id=args.company_id,
            manifest_path=args.manifest_file,
            import_id=args.import_id,
        )
        _write_json(result)
        return 0

    if command == "inspect-runtime-candidate-import":
        _require_reply_adapter(adapter_name, command)
        result = inspect_runtime_candidate_import(
            adapter_name=adapter_name,
            company_id=args.company_id,
            import_id=str(args.import_id),
        )
        _write_json(result)
        return 0

    if command == "adopt-runtime-candidate-import":
        _require_reply_adapter(adapter_name, command)
        result = adopt_runtime_candidate_import_op(
            adapter_name=adapter_name,
            company_id=args.company_id,
            import_id=str(args.import_id),
            min_confidence=float(args.min_confidence),
            allow_conflicted=bool(args.allow_conflicted),
        )
        _write_json(result)
        return 0

    if command == "curate-eval-dataset":
        trace_payloads: list[dict[str, Any]] = []
        cycle_store = RuntimeCycleStore(adapter_name=adapter_name)
        for cycle_id in args.cycle_id:
            trace_payloads.append(cycle_store.load_cycle(UUID(cycle_id)))
        for trace_file in args.trace_file:
            trace_payloads.append(_load_json(trace_file))
        if not trace_payloads:
            raise ValueError("At least one --cycle-id or --trace-file is required.")
        curated_cases = tuple(
            curate_eval_case_from_trace_payload(
                adapter_name,
                payload,
                selection_reason=str(args.selection_reason),
            )
            for payload in trace_payloads
        )
        if args.dataset_file:
            dataset = load_eval_dataset(args.dataset_file)
            dataset = merge_eval_dataset_cases(dataset, curated_cases)
        else:
            if not str(args.dataset_name or "").strip():
                raise ValueError("--dataset-name is required when --dataset-file is not provided.")
            dataset = build_eval_dataset(
                dataset_name=str(args.dataset_name),
                adapter_name=adapter_name,
                cases=curated_cases,
                metadata={"selection_reason": str(args.selection_reason)},
            )
        dataset_path = persist_eval_dataset(dataset)
        _write_json({"dataset_path": str(dataset_path), "dataset": dataclass_payload(dataset)})
        return 0

    if command == "replay-eval-dataset":
        dataset = load_eval_dataset(args.dataset_file)
        report, report_path = replay_reply_eval_dataset(dataset)
        _write_json(
            {
                "report_path": str(report_path),
                "report": dataclass_payload(report),
                "summary": summarize_eval_replay_report(report),
            }
        )
        return 0

    if command == "report-score-health":
        trace_payloads: list[dict[str, Any]] = []
        cycle_store = RuntimeCycleStore(adapter_name=adapter_name)
        for cycle_id in args.cycle_id:
            trace_payloads.append(cycle_store.load_cycle(UUID(cycle_id)))
        for trace_file in args.trace_file:
            trace_payloads.append(_load_json(trace_file))
        if not trace_payloads:
            raise ValueError("At least one --cycle-id or --trace-file is required.")
        if not str(args.report_name or "").strip():
            raise ValueError("--report-name is required.")
        report = build_score_health_report(
            report_name=str(args.report_name),
            adapter_name=adapter_name,
            trace_payloads=tuple(trace_payloads),
            metadata={"selection_reason": str(args.selection_reason or "manual_score_health")},
        )
        report_path = persist_score_health_report(adapter_name, report)
        _write_json(
            {
                "report_path": str(report_path),
                "report": dataclass_payload(report),
                "summary": summarize_score_health_report(report),
            }
        )
        return 0

    if command == "review-score-health":
        report = load_score_health_report(args.report_file)
        replay_report = (
            load_eval_replay_report(args.replay_report_file) if args.replay_report_file else None
        )
        review = review_score_health_report(
            report,
            replay_report=replay_report,
        )
        payload = {
            "report_file": str(args.report_file),
            "replay_report_file": str(args.replay_report_file) if args.replay_report_file else None,
            "review": review,
        }
        if args.decision_status:
            decision = make_score_health_review_decision(
                report,
                status=str(args.decision_status),
                notes=str(args.decision_notes or ""),
                replay_report=replay_report,
                metadata={"review_report_file": str(args.report_file)},
            )
            decision_path = persist_score_health_review_decision(report.adapter_name, decision)
            payload["decision_path"] = str(decision_path)
            payload["decision"] = dataclass_payload(decision)
        _write_json(payload)
        return 0

    if command == "compare-score-health":
        if not args.report_file:
            raise ValueError("At least one --report-file is required.")
        reports = tuple(load_score_health_report(path) for path in args.report_file)
        trend_report = compare_score_health_reports(
            reports,
            trend_report_name=str(args.trend_report_name),
            metadata={"selection_reason": str(args.selection_reason or "manual_trend_review")},
        )
        trend_report_path = persist_score_health_trend_report(
            trend_report.adapter_name,
            trend_report,
        )
        _write_json(
            {
                "trend_report_path": str(trend_report_path),
                "trend_report": dataclass_payload(trend_report),
                "summary": summarize_score_health_trend_report(trend_report),
            }
        )
        return 0

    if command == "check-score-governance":
        report = load_score_health_report(args.report_file)
        decision = (
            load_score_health_review_decision(args.decision_file) if args.decision_file else None
        )
        trend_report = (
            load_score_health_trend_report(args.trend_report_file)
            if args.trend_report_file
            else None
        )
        governance = evaluate_score_governance(
            report,
            decision=decision,
            trend_report=trend_report,
            policy=_score_governance_policy_from_args(args),
        )
        _write_json(
            {
                "allowed": governance.allowed,
                "override_required": governance.override_required,
                "score_governance": dataclass_payload(governance),
            }
        )
        return 0 if governance.allowed else 2

    if command == "check-release-governance":
        report = load_score_health_report(args.report_file)
        decision = (
            load_score_health_review_decision(args.decision_file) if args.decision_file else None
        )
        trend_report = (
            load_score_health_trend_report(args.trend_report_file)
            if args.trend_report_file
            else None
        )
        replay_report = (
            load_eval_replay_report(args.replay_report_file) if args.replay_report_file else None
        )
        governance = evaluate_score_governance(
            report,
            decision=decision,
            trend_report=trend_report,
            policy=_score_governance_policy_from_args(args),
        )
        release_report = build_score_governance_release_report(
            release_report_name=str(args.release_report_name),
            report=report,
            governance=governance,
            decision=decision,
            trend_report=trend_report,
            replay_report=replay_report,
            metadata={"selection_reason": str(args.selection_reason or "release_governance")},
        )
        release_report_path = persist_score_governance_release_report(
            report.adapter_name,
            release_report,
        )
        loaded_release_report = load_score_governance_release_report(release_report_path)
        _write_json(
            {
                "release_report_path": str(release_report_path),
                "release_report": dataclass_payload(loaded_release_report),
                "summary": summarize_score_governance_release_report(loaded_release_report),
            }
        )
        return 0 if loaded_release_report.allowed else 2

    if command == "list-score-governance-work":
        paths = resolve_eval_dataset_paths(adapter_name)
        decisions = tuple(
            load_score_health_review_decision(path)
            for path in sorted(paths.score_health_review_decisions_dir.glob("*.json"))
        )
        trend_reports = tuple(
            load_score_health_trend_report(path)
            for path in sorted(paths.score_health_trend_reports_dir.glob("*.json"))
        )
        resolutions = tuple(
            load_score_governance_triage_resolution(path)
            for path in sorted(paths.score_governance_triage_resolutions_dir.glob("*.json"))
        )
        triage_report = build_score_governance_triage_report(
            triage_report_name=str(args.triage_report_name),
            adapter_name=adapter_name,
            decisions=decisions,
            trend_reports=trend_reports,
            resolutions=resolutions,
            registry=AcceptedArtifactRegistry(adapter_name=adapter_name),
            metadata={"selection_reason": str(args.selection_reason or "triage_refresh")},
        )
        triage_report_path = persist_score_governance_triage_report(
            adapter_name,
            triage_report,
        )
        loaded_triage_report = load_score_governance_triage_report(triage_report_path)
        _write_json(
            {
                "triage_report_path": str(triage_report_path),
                "triage_report": dataclass_payload(loaded_triage_report),
                "summary": summarize_score_governance_triage_report(loaded_triage_report),
            }
        )
        return 0

    if command == "resolve-score-governance-item":
        resolution = make_score_governance_triage_resolution(
            adapter_name=adapter_name,
            item_id=str(args.item_id),
            resolution_status=str(args.resolution_status),
            notes=str(args.notes or ""),
        )
        resolution_path = persist_score_governance_triage_resolution(
            adapter_name,
            resolution,
        )
        loaded_resolution = load_score_governance_triage_resolution(resolution_path)
        _write_json(
            {
                "resolution_path": str(resolution_path),
                "resolution": dataclass_payload(loaded_resolution),
            }
        )
        return 0

    if command == "record-release-governance-decision":
        release_report = load_score_governance_release_report(args.release_report_file)
        decision = make_score_governance_release_decision(
            release_report,
            decision_status=str(args.decision_status),
            notes=str(args.notes or ""),
            metadata={"release_report_file": str(args.release_report_file)},
        )
        decision_path = persist_score_governance_release_decision(
            release_report.adapter_name,
            decision,
        )
        _write_json(
            {
                "release_decision_path": str(decision_path),
                "release_decision": dataclass_payload(decision),
            }
        )
        return 0

    if command == "governance-status":
        surface = build_score_governance_status_surface(adapter_name)
        _write_json(
            {
                "governance_status": dataclass_payload(surface),
                "summary": summarize_score_governance_status_surface(surface),
            }
        )
        return 0

    if command == "report-cross-adapter-scores":
        report = build_cross_adapter_score_report(
            report_name=str(args.report_name),
            adapter_names=tuple(args.adapter or SUPPORTED_ADAPTER_NAMES),
            top_n=int(args.top_n),
        )
        _write_json(
            {
                "report": dataclass_payload(report),
                "summary": summarize_cross_adapter_score_report(report),
            }
        )
        return 0

    if command == "report-score-governance-dashboard":
        report = build_score_governance_dashboard_report(
            report_name=str(args.report_name),
            adapter_names=tuple(args.adapter or SUPPORTED_ADAPTER_NAMES),
        )
        _write_json(
            {
                "report": dataclass_payload(report),
                "summary": summarize_score_governance_dashboard_report(report),
            }
        )
        return 0

    if command == "export-training-bundle":
        result = get_runtime().export_training_bundle(
            UUID(args.cycle_id),
            bundle_type=(
                str(args.bundle_type)
                if adapter_name == "spot"
                else training_bundle_type_from_payload(args.bundle_type)
            ),
        )
        _write_json(result)
        return 0

    if command == "export-post-training-dataset":
        if bool(args.bundle_file) == bool(args.cycle_id):
            raise ValueError(
                "Provide either --bundle-file or --cycle-id for export-post-training-dataset."
            )
        bundle_payloads: list[dict[str, Any]] = []
        if args.bundle_file:
            for bundle_file in args.bundle_file:
                payload = _load_json(bundle_file)
                bundle_payloads.append(payload)
        else:
            if not args.bundle_type:
                raise ValueError("--bundle-type is required when using --cycle-id.")
            for cycle_id in args.cycle_id:
                exported = get_runtime().export_training_bundle(
                    UUID(cycle_id),
                    bundle_type=(
                        str(args.bundle_type)
                        if adapter_name == "spot"
                        else training_bundle_type_from_payload(str(args.bundle_type))
                    ),
                )
                bundle_payloads.append(exported["bundle"])
        dataset = build_post_training_dataset(
            dataset_name=str(args.dataset_name),
            adapter_name=adapter_name,
            bundle_payloads=tuple(bundle_payloads),
            purposes=tuple(PostTrainingPurpose(str(item)) for item in args.purpose),
            metadata={
                "selection_reason": str(args.selection_reason or ""),
            },
        )
        dataset_path = persist_post_training_dataset(dataset)
        _write_json(
            {
                "dataset_path": str(dataset_path),
                "dataset": dataclass_payload(dataset),
                "summary": summarize_post_training_dataset(dataset),
            }
        )
        return 0

    if command == "build-post-training-split":
        dataset = load_post_training_dataset(args.dataset_file)
        split = build_post_training_dataset_split(
            dataset,
            split_name=str(args.split_name),
            validation_ratio=float(args.validation_ratio),
            holdout_ratio=float(args.holdout_ratio),
            metadata={"selection_reason": str(args.selection_reason or "")},
        )
        split_path = persist_post_training_dataset_split(split)
        _write_json(
            {
                "split_path": str(split_path),
                "split": dataclass_payload(split),
                "summary": summarize_post_training_dataset_split(split),
            }
        )
        return 0

    if command == "curate-post-training-example":
        dataset = load_post_training_dataset(args.dataset_file)
        decision = make_post_training_curation_decision(
            dataset,
            example_id=str(args.example_id),
            annotation_status=PostTrainingAnnotationStatus(str(args.annotation_status)),
            rationale=str(args.reason),
        )
        updated_dataset = apply_post_training_curation_decision(dataset, decision)
        decision_path = persist_post_training_curation_decision(
            updated_dataset.adapter_name,
            decision,
        )
        dataset_path = persist_post_training_dataset(updated_dataset)
        _write_json(
            {
                "decision_path": str(decision_path),
                "dataset_path": str(dataset_path),
                "decision": dataclass_payload(decision),
                "dataset": dataclass_payload(updated_dataset),
                "summary": summarize_post_training_dataset(updated_dataset),
            }
        )
        return 0

    if command == "promote-post-training-dataset":
        dataset = load_post_training_dataset(args.dataset_file)
        promoted = promote_post_training_dataset(
            dataset,
            status=PostTrainingDatasetStatus(str(args.dataset_status)),
            rationale=str(args.reason),
        )
        dataset_path = persist_post_training_dataset(promoted)
        _write_json(
            {
                "dataset_path": str(dataset_path),
                "dataset": dataclass_payload(promoted),
                "summary": summarize_post_training_dataset(promoted),
            }
        )
        return 0

    if command == "run-shadow-fixtures":
        _require_reply_adapter(adapter_name, command)
        fixture_dir = args.fixture_dir or str(
            Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "reply_shadow"
        )
        fixtures = load_reply_shadow_fixtures(fixture_dir)
        results = run_reply_shadow_fixtures(get_runtime()._runtime, fixtures)
        _write_json(
            {
                "fixture_dir": fixture_dir,
                "results": [shadow_fixture_payload(result) for result in results],
                "summary": summarize_reply_shadow_results(results),
            }
        )
        return 0

    if command == "compare-providers":
        _require_reply_adapter(adapter_name, command)
        fixture_dir = args.fixture_dir or str(
            Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "reply_shadow"
        )
        route_sets = []
        include_current = args.include_current_config or not args.route_set_file
        include_deterministic = args.include_deterministic_baseline or not args.route_set_file
        if include_deterministic:
            route_sets.append(deterministic_route_set())
        if include_current:
            route_sets.append(current_config_route_set(adapter_name))
        for route_set_file in args.route_set_file:
            route_sets.extend(load_provider_route_sets(route_set_file))
        report, report_path = run_reply_provider_comparison_from_fixture_dir(
            route_sets,
            fixture_dir,
            corpus_id=args.corpus_id,
        )
        _write_json(
            {
                "report_path": str(report_path),
                "report": dataclass_payload(report),
            }
        )
        return 0

    if command == "make-control-job":
        if args.job_kind == "reply_provider_comparison":
            fixture_dir = args.fixture_dir or str(
                Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "reply_shadow"
            )
            job = make_provider_comparison_job(
                job_id=args.job_id,
                fixture_dir=fixture_dir,
                route_set_files=tuple(args.route_set_file),
                corpus_id=args.corpus_id,
                include_current_config=args.include_current_config,
                include_deterministic_baseline=args.include_deterministic_baseline,
                schedule_hint=args.schedule_hint,
                description=args.description,
            )
        elif args.job_kind == "reply_prepared_draft_refresh":
            job = make_prepared_draft_refresh_job(
                job_id=args.job_id,
                company_id=args.company_id,
                thread_ref=args.thread_ref,
                generation_reason=str(args.reason or "control_plane_refresh"),
                schedule_hint=args.schedule_hint,
                description=args.description,
            )
        else:
            raise AssertionError(f"Unhandled control-plane job kind: {args.job_kind}")
        store = ControlPlaneStore(adapter_name=job.adapter_name)
        job_path = store.save_job(job)
        _write_json({"job_path": str(job_path), "job": dataclass_payload(job)})
        return 0

    if command == "run-control-job":
        job = load_control_plane_job(args.job_file)
        run, run_path = run_control_plane_job(job)
        _write_json({"run_path": str(run_path), "run": dataclass_payload(run)})
        return 0 if run.status.value == "succeeded" else 2

    if command == "control-run-status":
        store = ControlPlaneStore(adapter_name=adapter_name)
        run = store.load_run(args.run_id)
        _write_json(dataclass_payload(run))
        return 0

    if command == "make-gobii-workflow":
        job = load_control_plane_job(args.job_file)
        bundle = build_gobii_workflow_bundle(
            job,
            schedule=args.schedule,
            job_path=args.job_file,
        )
        bundle_path = persist_gobii_workflow_bundle(bundle)
        _write_json({"bundle_path": str(bundle_path), "bundle": dataclass_payload(bundle)})
        return 0

    if command == "make-gobii-profile-enrichment":
        payload = _load_json(args.input_file)
        request = gobii_tracked_entity_enrichment_request_from_payload(payload)
        bundle = build_gobii_tracked_entity_enrichment_bundle(
            adapter_name,
            request,
            agent_id=args.agent_id,
            webhook=args.webhook,
            wait_seconds=args.wait_seconds,
        )
        bundle_path = persist_gobii_tracked_entity_enrichment_bundle(bundle)
        _write_json({"bundle_path": str(bundle_path), "bundle": dataclass_payload(bundle)})
        return 0

    if command == "register-gobii-workflow":
        bundle = load_gobii_workflow_bundle(args.bundle_file)
        api_key = os.environ.get(str(args.api_key_env or "GOBII_API_KEY"), "").strip()
        if not api_key:
            raise RuntimeError(
                f"Missing Gobii API key in env var: {str(args.api_key_env or 'GOBII_API_KEY')}"
            )
        client = GobiiAgentClient(
            base_url=str(args.gobii_api_base_url).strip(),
            api_key=api_key,
        )
        agent, registration_path = register_gobii_workflow_bundle(bundle, client)
        _write_json(
            {
                "registration_path": str(registration_path),
                "agent": dataclass_payload(agent),
            }
        )
        return 0

    if command == "submit-gobii-profile-enrichment":
        bundle = load_gobii_tracked_entity_enrichment_bundle(args.bundle_file)
        api_key = os.environ.get(str(args.api_key_env or "GOBII_API_KEY"), "").strip()
        if not api_key:
            raise RuntimeError(
                f"Missing Gobii API key in env var: {str(args.api_key_env or 'GOBII_API_KEY')}"
            )
        client = GobiiTaskClient(
            base_url=str(args.gobii_api_base_url).strip(),
            api_key=api_key,
        )
        bundle, bundle_path, record, record_path = submit_gobii_tracked_entity_enrichment_bundle(
            bundle,
            client,
        )
        _write_json(
            {
                "bundle_path": str(bundle_path),
                "task_path": str(record_path),
                "bundle": dataclass_payload(bundle),
                "task": dataclass_payload(record),
            }
        )
        return 0

    if command == "submit-gobii-task":
        api_key = os.environ.get(str(args.api_key_env or "GOBII_API_KEY"), "").strip()
        if not api_key:
            raise RuntimeError(
                f"Missing Gobii API key in env var: {str(args.api_key_env or 'GOBII_API_KEY')}"
            )
        client = GobiiTaskClient(
            base_url=str(args.gobii_api_base_url).strip(),
            api_key=api_key,
        )
        record = client.create_task(
            GobiiTaskCreateRequest(
                prompt=str(args.prompt),
                agent_id=args.agent_id,
                webhook=args.webhook,
                wait_seconds=args.wait_seconds,
            ),
        )
        record = merge_gobii_task_context(
            record,
            adapter_name=adapter_name,
            company_id=str(args.company_id).strip() if args.company_id else None,
        )
        record_path = persist_gobii_task_record(adapter_name, record)
        _write_json({"task_path": str(record_path), "task": dataclass_payload(record)})
        return 0

    if command == "gobii-task-result":
        api_key = os.environ.get(str(args.api_key_env or "GOBII_API_KEY"), "").strip()
        if not api_key:
            raise RuntimeError(
                f"Missing Gobii API key in env var: {str(args.api_key_env or 'GOBII_API_KEY')}"
            )
        client = GobiiTaskClient(
            base_url=str(args.gobii_api_base_url).strip(),
            api_key=api_key,
        )
        record = client.get_task_result(str(args.task_id))
        try:
            existing_record, _ = load_persisted_gobii_task_record(adapter_name, str(args.task_id))
            record = merge_gobii_task_context(
                record,
                adapter_name=existing_record.adapter_name or adapter_name,
                company_id=existing_record.company_id,
            )
        except GobiiTaskClientError:
            record = merge_gobii_task_context(record, adapter_name=adapter_name)
        record_path = persist_gobii_task_record(adapter_name, record)
        _write_json({"task_path": str(record_path), "task": dataclass_payload(record)})
        return 0

    if command == "list-gobii-tasks":
        api_key = os.environ.get(str(args.api_key_env or "GOBII_API_KEY"), "").strip()
        if not api_key:
            raise RuntimeError(
                f"Missing Gobii API key in env var: {str(args.api_key_env or 'GOBII_API_KEY')}"
            )
        client = GobiiTaskClient(
            base_url=str(args.gobii_api_base_url).strip(),
            api_key=api_key,
        )
        records = client.list_tasks(page=args.page, page_size=args.page_size)
        normalized_records = []
        persisted_paths = []
        for record in records:
            try:
                existing_record, _ = load_persisted_gobii_task_record(adapter_name, record.id)
                record = merge_gobii_task_context(
                    record,
                    adapter_name=existing_record.adapter_name or adapter_name,
                    company_id=existing_record.company_id,
                )
            except GobiiTaskClientError:
                record = merge_gobii_task_context(record, adapter_name=adapter_name)
            normalized_records.append(record)
            persisted_paths.append(str(persist_gobii_task_record(adapter_name, record)))
        _write_json(
            {
                "task_paths": persisted_paths,
                "tasks": [dataclass_payload(record) for record in normalized_records],
            }
        )
        return 0

    if command == "cancel-gobii-task":
        api_key = os.environ.get(str(args.api_key_env or "GOBII_API_KEY"), "").strip()
        if not api_key:
            raise RuntimeError(
                f"Missing Gobii API key in env var: {str(args.api_key_env or 'GOBII_API_KEY')}"
            )
        client = GobiiTaskClient(
            base_url=str(args.gobii_api_base_url).strip(),
            api_key=api_key,
        )
        record = client.cancel_task(str(args.task_id))
        try:
            existing_record, _ = load_persisted_gobii_task_record(adapter_name, str(args.task_id))
            record = merge_gobii_task_context(
                record,
                adapter_name=existing_record.adapter_name or adapter_name,
                company_id=existing_record.company_id,
            )
        except GobiiTaskClientError:
            record = merge_gobii_task_context(record, adapter_name=adapter_name)
        record_path = persist_gobii_task_record(adapter_name, record)
        _write_json({"task_path": str(record_path), "task": dataclass_payload(record)})
        return 0

    if command == "normalize-gobii-task":
        payload = _load_json(args.input_file)
        try:
            request = gobii_task_normalization_request_from_payload(payload)
            bundle, bundle_path = normalize_gobii_task_output(adapter_name, request)
        except GobiiNormalizationError as exc:
            _write_json({"status": "rejected", "reason": str(exc)})
            return 2
        _write_json({"bundle_path": str(bundle_path), "bundle": dataclass_payload(bundle)})
        return 0

    if command == "normalize-gobii-profile-enrichment":
        bundle = load_gobii_tracked_entity_enrichment_bundle(args.bundle_file)
        try:
            artifact_bundle, artifact_path = normalize_gobii_tracked_entity_enrichment_bundle(
                adapter_name,
                bundle,
            )
        except GobiiNormalizationError as exc:
            _write_json({"status": "rejected", "reason": str(exc)})
            return 2
        _write_json(
            {
                "bundle_path": str(artifact_path),
                "bundle": dataclass_payload(artifact_bundle),
            }
        )
        return 0

    if command == "policy-accept":
        require_holdout = _resolve_holdout_requirement(args)
        score_governance = _resolve_score_governance_check(args)
        if score_governance is not None and not score_governance.allowed:
            if not args.allow_score_governance_override:
                _write_json(
                    {
                        "accepted": False,
                        "reason": "Rejected: score governance requires explicit override.",
                        "score_governance": dataclass_payload(score_governance),
                    }
                )
                return 2
            if not str(args.score_governance_override_note or "").strip():
                raise ValueError(
                    "--score-governance-override-note is required when overriding "
                    "a blocked score-governance decision."
                )
        skeptical_notes = _policy_accept_skeptical_notes(args, score_governance)
        governance_kwargs = _policy_accept_score_governance_kwargs(args, score_governance)
        release_governance = _resolve_release_governance_decision(args, score_governance)
        if release_governance is not None:
            release_report, release_decision = release_governance
            governance_kwargs.update(
                {
                    "release_governance_report_id": release_report.release_report_id,
                    "release_governance_decision_id": release_decision.release_decision_id,
                    "release_governance_decision_status": release_decision.decision_status,
                }
            )
        if adapter_name == REPLY_ADAPTER_NAME:
            result = accept_reply_behavior_policy(
                args.policy_file,
                bundle_files=list(args.bundle_file),
                holdout_bundle_files=list(args.holdout_bundle_file),
                require_holdout=require_holdout,
                regression_threshold=float(args.regression_threshold),
                reason=args.reason,
                source_train_project_key=args.source_train_project_key,
                source_train_run_id=args.source_train_run_id,
                skeptical_notes=skeptical_notes,
                **governance_kwargs,
            )
        elif adapter_name == "spot":
            result = accept_spot_review_policy(
                args.policy_file,
                bundle_files=list(args.bundle_file),
                holdout_bundle_files=list(args.holdout_bundle_file),
                require_holdout=require_holdout,
                regression_threshold=float(args.regression_threshold),
                reason=args.reason,
                source_train_project_key=args.source_train_project_key,
                source_train_run_id=args.source_train_run_id,
                skeptical_notes=skeptical_notes,
                **governance_kwargs,
            )
        else:
            raise AssertionError(f"Unhandled adapter: {adapter_name}")
        payload = dataclass_payload(result)
        if score_governance is not None:
            payload["score_governance"] = dataclass_payload(score_governance)
        if release_governance is not None:
            payload["release_governance_report"] = dataclass_payload(release_governance[0])
            payload["release_governance_decision"] = dataclass_payload(release_governance[1])
        _write_json(payload)
        return 0 if result.accepted else 2

    if command == "policy-review":
        require_holdout = _resolve_holdout_requirement(args)
        if adapter_name == REPLY_ADAPTER_NAME:
            result = review_reply_behavior_policy(
                args.policy_file,
                bundle_files=list(args.bundle_file),
                holdout_bundle_files=list(args.holdout_bundle_file),
                require_holdout=require_holdout,
                regression_threshold=float(args.regression_threshold),
                source_train_project_key=args.source_train_project_key,
                source_train_run_id=args.source_train_run_id,
                skeptical_notes=tuple(args.skeptical_note),
            )
            result = persist_reply_policy_review_result(registry, result)
        elif adapter_name == "spot":
            result = review_spot_review_policy(
                args.policy_file,
                bundle_files=list(args.bundle_file),
                holdout_bundle_files=list(args.holdout_bundle_file),
                require_holdout=require_holdout,
                regression_threshold=float(args.regression_threshold),
                source_train_project_key=args.source_train_project_key,
                source_train_run_id=args.source_train_run_id,
                skeptical_notes=tuple(args.skeptical_note),
            )
        else:
            raise AssertionError(f"Unhandled adapter: {adapter_name}")
        _write_json(dataclass_payload(result))
        return 0 if result.ready_for_acceptance else 2

    if command == "policy-review-surface":
        _require_reply_adapter(adapter_name, command)
        require_holdout = _resolve_holdout_requirement(args)
        result = review_reply_behavior_policy(
            args.policy_file,
            bundle_files=list(args.bundle_file),
            holdout_bundle_files=list(args.holdout_bundle_file),
            require_holdout=require_holdout,
            regression_threshold=float(args.regression_threshold),
            source_train_project_key=args.source_train_project_key,
            source_train_run_id=args.source_train_run_id,
            skeptical_notes=tuple(args.skeptical_note),
        )
        result = persist_reply_policy_review_result(registry, result)
        payload = _policy_review_surface_payload(result)
        payload["governance_status"] = dataclass_payload(
            build_score_governance_status_surface(adapter_name, registry=registry)
        )
        _write_json(payload)
        return 0 if result.ready_for_acceptance else 2

    if command == "policy-promote":
        foundation_check: dict[str, Any] | None = None
        if not args.allow_foundation_bypass:
            foundation_check = run_foundation_check(
                adapter_name=adapter_name,
                default_train_api_base_url=DEFAULT_TRAIN_API_BASE_URL,
            )
            if not foundation_check["ready"]:
                _write_json(
                    {
                        "promoted": False,
                        "reason": "Rejected: foundation check failed before promotion.",
                        "foundation_check": foundation_check,
                    }
                )
                return 2
        elif not str(args.foundation_bypass_note or "").strip():
            raise ValueError(
                "--foundation-bypass-note is required when bypassing foundation checks."
            )
        accepted_at = _parse_datetime(args.accepted_at) if args.accepted_at else datetime.now(UTC)
        artifact = AcceptedArtifactVersion(
            artifact_key=str(args.artifact_key),
            version=str(args.version),
            source_project=str(args.source_project),
            accepted_at=accepted_at,
        )
        if adapter_name == "spot":
            if not args.policy_file:
                raise ValueError("--policy-file is required when promoting a Spot policy.")
            policy = load_spot_review_policy_file(args.policy_file)
            result = registry.promote(
                artifact,
                reason=args.reason,
                promoted_at=accepted_at,
                contract_version=policy.contract_version,
                scope_kind=policy.scope_kind.value,
                scope_value=policy.scope_value,
            )
            SpotPolicyStore().accept(policy, artifact=artifact)
        else:
            result = registry.promote(artifact, reason=args.reason, promoted_at=accepted_at)
        payload = dataclass_payload(result)
        if foundation_check is not None:
            payload["foundation_check"] = foundation_check
        if args.allow_foundation_bypass:
            payload["foundation_bypass_note"] = str(args.foundation_bypass_note).strip()
        _write_json(payload)
        return 0

    if command == "policy-rollback":
        result = registry.rollback(
            str(args.artifact_key),
            target_version=args.target_version,
            reason=args.reason,
            promoted_at=datetime.now(UTC),
        )
        if adapter_name == "spot":
            SpotPolicyStore().activate_version(
                scope_kind=SpotReviewScopeKind(str(result.scope_kind or "global")),
                scope_value=result.scope_value,
                version=result.artifact.version,
            )
        _write_json(dataclass_payload(result))
        return 0

    if command == "policy-status":
        current = registry.current_pointer(str(args.artifact_key))
        history = registry.history(str(args.artifact_key))
        governance_surface = build_score_governance_status_surface(adapter_name, registry=registry)
        _write_json(
            {
                "artifact_key": str(args.artifact_key),
                "current": current,
                "history": [dataclass_payload(record) for record in history],
                "governance_status": dataclass_payload(governance_surface),
            }
        )
        return 0

    if command == "show-config":
        payload = dataclass_payload(load_model_config_for_adapter(adapter_name))
        if args.include_path:
            payload["config_path"] = str(config_path_for_adapter(adapter_name))
        _write_json(payload)
        return 0

    if command == "show-foundation-policy":
        payload = dataclass_payload(load_foundation_policy())
        if args.include_path:
            payload["policy_path"] = str(foundation_policy_path())
        _write_json(payload)
        return 0

    if command == "write-foundation-policy":
        current_policy = load_foundation_policy()
        updated_train = current_policy.train
        if args.train_default_transport:
            updated_train = type(current_policy.train)(
                default_transport=str(args.train_default_transport).strip().lower()
            )
        updated_reply = current_policy.reply
        updated_spot = current_policy.spot
        if args.adapter:
            current_adapter_policy = (
                current_policy.reply
                if require_supported_adapter(args.adapter) == REPLY_ADAPTER_NAME
                else current_policy.spot
            )
            updated_adapter_policy = AdapterFoundationPolicy(
                supported_providers=tuple(
                    str(item).strip().lower()
                    for item in (
                        args.supported_provider or current_adapter_policy.supported_providers
                    )
                    if str(item).strip()
                ),
                preferred_live_provider=(
                    str(
                        args.preferred_live_provider
                        or current_adapter_policy.preferred_live_provider
                        or ""
                    )
                    .strip()
                    .lower()
                    or None
                ),
                release_gate_roles=tuple(
                    str(item).strip().lower()
                    for item in (
                        args.release_gate_role or current_adapter_policy.release_gate_roles
                    )
                    if str(item).strip()
                ),
            )
            if require_supported_adapter(args.adapter) == REPLY_ADAPTER_NAME:
                updated_reply = updated_adapter_policy
            else:
                updated_spot = updated_adapter_policy
        updated_optional = type(current_policy.optional_seams)(
            gobii_required_for_release=(
                True
                if args.gobii_required_for_release
                else False
                if args.gobii_optional_for_release
                else current_policy.optional_seams.gobii_required_for_release
            )
        )
        updated_policy = TrinityFoundationPolicy(
            contract_version=current_policy.contract_version,
            train=updated_train,
            reply=updated_reply,
            spot=updated_spot,
            optional_seams=updated_optional,
        )
        path = save_foundation_policy(updated_policy)
        payload = dataclass_payload(updated_policy)
        payload["policy_path"] = str(path)
        _write_json(payload)
        return 0

    if command == "train-propose-policy":
        train_transport = str(args.transport or load_foundation_policy().train.default_transport)
        bundle_files = list(args.bundle_file or [])
        if args.cycle_id and not args.bundle_type:
            raise ValueError("--bundle-type is required when using --cycle-id.")
        for cycle_id in list(args.cycle_id or []):
            exported = get_runtime().export_training_bundle(
                UUID(cycle_id),
                bundle_type=(
                    str(args.bundle_type)
                    if adapter_name == "spot"
                    else training_bundle_type_from_payload(args.bundle_type)
                ),
            )
            bundle_files.append(exported["bundle_path"])
        if not bundle_files:
            raise ValueError("At least one --cycle-id or --bundle-file is required.")
        proposal_output_path = args.proposal_output_path
        eval_output_path = args.eval_output_path
        comparison_output_path = getattr(args, "comparison_output_path", None)
        if adapter_name == REPLY_ADAPTER_NAME and (
            not proposal_output_path or not eval_output_path
        ):
            default_proposal_path, default_eval_path = default_train_proposal_paths(
                adapter_name=adapter_name,
                learner_kind=str(args.learner_kind),
            )
            proposal_output_path = proposal_output_path or str(default_proposal_path)
            eval_output_path = eval_output_path or str(default_eval_path)
        if adapter_name == "spot" and (
            not proposal_output_path or not eval_output_path or not comparison_output_path
        ):
            default_proposal_path, default_eval_path, default_comparison_path = (
                default_train_spot_proposal_paths(
                    adapter_name=adapter_name,
                    learner_kind=str(args.learner_kind),
                )
            )
            proposal_output_path = proposal_output_path or str(default_proposal_path)
            eval_output_path = eval_output_path or str(default_eval_path)
            comparison_output_path = comparison_output_path or str(default_comparison_path)
        if adapter_name == REPLY_ADAPTER_NAME:
            train_result = propose_reply_policy_with_train(
                learner_kind=str(args.learner_kind),
                bundle_files=bundle_files,
                transport=train_transport,
                train_api_base_url=args.train_api_base_url,
                train_root_dir=args.train_root_dir,
                proposal_output_path=proposal_output_path,
                eval_output_path=eval_output_path,
            )
        elif adapter_name == "spot":
            train_result = propose_spot_review_policy_with_train(
                learner_kind=str(args.learner_kind),
                bundle_files=bundle_files,
                transport=train_transport,
                train_api_base_url=args.train_api_base_url,
                train_root_dir=args.train_root_dir,
                proposal_output_path=proposal_output_path,
                eval_output_path=eval_output_path,
                comparison_output_path=comparison_output_path,
            )
        else:
            raise AssertionError(f"Unhandled adapter: {adapter_name}")
        payload = {
            "adapter": adapter_name,
            "transport": train_transport,
            "learner_kind": str(args.learner_kind),
            "bundle_files": bundle_files,
            "train_result": train_result,
        }
        if args.accept:
            require_holdout = _resolve_holdout_requirement(args)
            score_governance = _resolve_score_governance_check(args)
            if score_governance is not None and not score_governance.allowed:
                if not args.allow_score_governance_override:
                    payload["acceptance_result"] = {
                        "accepted": False,
                        "reason": "Rejected: score governance requires explicit override.",
                        "score_governance": dataclass_payload(score_governance),
                    }
                    _write_json(payload)
                    return 2
                if not str(args.score_governance_override_note or "").strip():
                    raise ValueError(
                        "--score-governance-override-note is required when overriding "
                        "a blocked score-governance decision."
                    )
            skeptical_notes = _policy_accept_skeptical_notes(args, score_governance)
            governance_kwargs = _policy_accept_score_governance_kwargs(
                args,
                score_governance,
            )
            release_governance = _resolve_release_governance_decision(args, score_governance)
            if release_governance is not None:
                release_report, release_decision = release_governance
                governance_kwargs.update(
                    {
                        "release_governance_report_id": release_report.release_report_id,
                        "release_governance_decision_id": release_decision.release_decision_id,
                        "release_governance_decision_status": release_decision.decision_status,
                    }
                )
            if adapter_name == REPLY_ADAPTER_NAME:
                acceptance = accept_reply_behavior_policy(
                    train_result["proposal_path"],
                    bundle_files=bundle_files,
                    holdout_bundle_files=list(args.holdout_bundle_file),
                    require_holdout=require_holdout,
                    regression_threshold=float(args.regression_threshold),
                    reason=args.reason,
                    source_train_project_key=train_result.get("train_project_key"),
                    source_train_run_id=train_result.get("train_run_id"),
                    skeptical_notes=skeptical_notes,
                    **governance_kwargs,
                )
            elif adapter_name == "spot":
                acceptance = accept_spot_review_policy(
                    train_result["proposal_path"],
                    bundle_files=bundle_files,
                    holdout_bundle_files=list(args.holdout_bundle_file),
                    require_holdout=require_holdout,
                    regression_threshold=float(args.regression_threshold),
                    reason=args.reason,
                    source_train_project_key=train_result.get("train_project_key"),
                    source_train_run_id=train_result.get("train_run_id"),
                    skeptical_notes=skeptical_notes,
                    **governance_kwargs,
                )
            else:
                raise AssertionError(f"Unhandled adapter: {adapter_name}")
            payload["acceptance_result"] = dataclass_payload(acceptance)
            if score_governance is not None:
                payload["acceptance_result"]["score_governance"] = dataclass_payload(
                    score_governance
                )
            if release_governance is not None:
                payload["acceptance_result"]["release_governance_report"] = dataclass_payload(
                    release_governance[0]
                )
                payload["acceptance_result"]["release_governance_decision"] = dataclass_payload(
                    release_governance[1]
                )
            _write_json(payload)
            return 0 if acceptance.accepted else 2
        _write_json(payload)
        return 0

    if command == "runtime-status":
        configured_config = load_model_config_for_adapter(adapter_name)
        config, config_resolution = resolve_runtime_model_config(configured_config)
        foundation_policy = load_foundation_policy()
        shared_inventory_payload = _build_shared_model_inventory_payload()
        payload = {
            "contract_version": CLI_CONTRACT_VERSION,
            "status_schema_version": RUNTIME_STATUS_SCHEMA_VERSION,
            "command": "runtime-status",
            "generated_at": datetime.now(UTC).isoformat(),
            "config_path": str(config_path_for_adapter(adapter_name)),
            "adapter": adapter_name,
            "provider": config.provider,
            "configured_provider": configured_config.provider,
            "effective_provider": config.provider,
            "provider_fallback": {
                "applied": bool(config_resolution.get("fallback_applied")),
                "reason": config_resolution.get("reason"),
            },
            "llm_enabled": config.llm_enabled,
            "ollama_base_url": config.ollama_base_url,
            "mistral_cli_executable": config.mistral_cli_executable,
            "mistral_cli_args": list(config.mistral_cli_args),
            "mistral_cli_mode": config.mistral_cli_mode,
            "mistral_cli_model_binding": config.mistral_cli_model_binding,
            "timeout_seconds": config.timeout_seconds,
            "provider_status": "not_configured",
            "provider_error": None,
            "provider_error_code": None,
            "available_models": [],
            "provider_inventory_supported": False,
            "foundation_policy": {
                "policy_path": str(foundation_policy_path()),
                "train_default_transport": foundation_policy.train.default_transport,
                "provider_alignment": build_foundation_provider_alignment(
                    adapter_name=adapter_name,
                    provider=config.provider,
                    llm_enabled=config.llm_enabled,
                    policy=foundation_policy,
                ),
            },
            "shared_model_inventory": {
                key: value
                for key, value in shared_inventory_payload.items()
                if not key.startswith("_")
            },
            "roles": {
                "generator": dataclass_payload(config.generator),
                "refiner": dataclass_payload(config.refiner),
                "evaluator": dataclass_payload(config.evaluator),
            },
        }
        if config.llm_enabled:
            try:
                provider_runtime = get_runtime()
                models = provider_runtime.model_provider.list_models()
                installed_names = {str(item.get("name") or "").strip() for item in models}
                inventory_supported = provider_runtime.model_provider.supports_model_inventory
                payload["provider_status"] = "online" if inventory_supported else "configured"
                if payload["provider_fallback"]["applied"]:
                    payload["provider_status"] = "fallback_online" if inventory_supported else "fallback_configured"
                payload["provider_inventory_supported"] = inventory_supported
                payload["available_models"] = list(models)
                for role_name, route in (
                    ("generator", config.generator),
                    ("refiner", config.refiner),
                    ("evaluator", config.evaluator),
                ):
                    payload["roles"][role_name] = {
                        **dataclass_payload(route),
                        "installed": route.model in installed_names,
                        **_build_role_inventory_payload(
                            shared_inventory_payload=shared_inventory_payload,
                            provider=payload["provider"],
                            route_model_id=route.model_id,
                            route_model=route.model,
                        ),
                    }
            except UnsupportedModelProviderError as exc:
                payload["provider_status"] = "unsupported"
                payload["provider_error"] = str(exc)
                payload["provider_error_code"] = "provider_unsupported"
                for role_name, route in (
                    ("generator", config.generator),
                    ("refiner", config.refiner),
                    ("evaluator", config.evaluator),
                ):
                    payload["roles"][role_name] = {
                        **dataclass_payload(route),
                        "installed": False,
                        **_build_role_inventory_payload(
                            shared_inventory_payload=shared_inventory_payload,
                            provider=payload["provider"],
                            route_model_id=route.model_id,
                            route_model=route.model,
                        ),
                    }
            except Exception as exc:
                payload["provider_status"] = "offline"
                payload["provider_error"] = str(exc)
                payload["provider_error_code"] = classify_provider_error_code(exc)
                for role_name, route in (
                    ("generator", config.generator),
                    ("refiner", config.refiner),
                    ("evaluator", config.evaluator),
                ):
                    payload["roles"][role_name] = {
                        **dataclass_payload(route),
                        "installed": False,
                        **_build_role_inventory_payload(
                            shared_inventory_payload=shared_inventory_payload,
                            provider=payload["provider"],
                            route_model_id=route.model_id,
                            route_model=route.model,
                        ),
                    }
        else:
            for role_name, route in (
                ("generator", config.generator),
                ("refiner", config.refiner),
                ("evaluator", config.evaluator),
            ):
                payload["roles"][role_name] = {
                    **dataclass_payload(route),
                    "installed": False,
                    **_build_role_inventory_payload(
                        shared_inventory_payload=shared_inventory_payload,
                        provider=payload["provider"],
                        route_model_id=route.model_id,
                        route_model=route.model,
                    ),
                }
        payload["readiness"] = _build_runtime_readiness_payload(payload)
        _write_json(payload)
        return 0

    if command == "train-status":
        foundation_policy = load_foundation_policy()
        payload = probe_train_seam(
            default_train_api_base_url=DEFAULT_TRAIN_API_BASE_URL,
            train_api_base_url=args.train_api_base_url,
            train_root_dir=args.train_root_dir,
            transport=str(args.transport or "both"),
            preferred_transport=foundation_policy.train.default_transport,
        )
        _write_json(payload)
        return 0

    if command == "foundation-check":
        payload = run_foundation_check(
            adapter_name=adapter_name,
            default_train_api_base_url=DEFAULT_TRAIN_API_BASE_URL,
            train_api_base_url=args.train_api_base_url,
            train_root_dir=args.train_root_dir,
            train_transport=args.transport,
            reply_root_dir=args.reply_root_dir,
            gobii_api_base_url=str(args.gobii_api_base_url).strip(),
            gobii_api_key_env=str(args.api_key_env or "GOBII_API_KEY"),
            check_gobii_live=bool(args.check_gobii_live),
        )
        _write_json(payload)
        return 0 if payload["ready"] else 2

    if command == "provider-smoke":
        role_names = tuple(args.role) if args.role else ("generator", "refiner", "evaluator")
        payload = smoke_provider_routes(
            adapter_name=adapter_name,
            role_names=role_names,
            inventory_only=bool(args.inventory_only),
        )
        _write_json(payload)
        return 0

    if command == "check-reply-compatibility":
        payload = check_reply_compatibility(reply_root_dir=args.reply_root_dir)
        _write_json(payload)
        return 0

    if command == "gobii-status":
        payload = probe_gobii_seam(
            adapter_name=adapter_name,
            base_url=str(args.gobii_api_base_url).strip(),
            api_key_env=str(args.api_key_env or "GOBII_API_KEY"),
            check_live=bool(args.check_live),
        )
        _write_json(payload)
        return 0

    if command == "write-config":
        current = load_model_config_for_adapter(adapter_name)
        foundation_policy = load_foundation_policy()
        updated_provider = str(args.provider or current.provider)
        updated = TrinityModelConfig(
            provider=updated_provider,
            ollama_base_url=str(args.ollama_base_url or current.ollama_base_url),
            mistral_cli_executable=str(
                args.mistral_cli_executable or current.mistral_cli_executable
            ),
            mistral_cli_args=tuple(
                args.mistral_cli_arg if args.mistral_cli_arg else current.mistral_cli_args
            ),
            mistral_cli_mode=str(args.mistral_cli_mode or current.mistral_cli_mode),
            mistral_cli_model_binding=str(
                args.mistral_cli_model_binding or current.mistral_cli_model_binding
            ),
            timeout_seconds=float(args.timeout_seconds or current.timeout_seconds),
            generator=TrinityRoleRoute(
                provider=updated_provider,
                model=str(args.generator_model or current.generator.model),
                temperature=current.generator.temperature,
                keep_alive=current.generator.keep_alive,
                model_id=_resolve_cli_role_model_id(
                    explicit_model_id=args.generator_model_id,
                    provider=updated_provider,
                    route_model=str(args.generator_model or current.generator.model),
                    current_model_id=current.generator.model_id,
                ),
            ),
            refiner=TrinityRoleRoute(
                provider=updated_provider,
                model=str(args.refiner_model or current.refiner.model),
                temperature=current.refiner.temperature,
                keep_alive=current.refiner.keep_alive,
                model_id=_resolve_cli_role_model_id(
                    explicit_model_id=args.refiner_model_id,
                    provider=updated_provider,
                    route_model=str(args.refiner_model or current.refiner.model),
                    current_model_id=current.refiner.model_id,
                ),
            ),
            evaluator=TrinityRoleRoute(
                provider=updated_provider,
                model=str(args.evaluator_model or current.evaluator.model),
                temperature=current.evaluator.temperature,
                keep_alive=current.evaluator.keep_alive,
                model_id=_resolve_cli_role_model_id(
                    explicit_model_id=args.evaluator_model_id,
                    provider=updated_provider,
                    route_model=str(args.evaluator_model or current.evaluator.model),
                    current_model_id=current.evaluator.model_id,
                ),
            ),
        )
        path = save_model_config_for_adapter(adapter_name, updated)
        payload = dataclass_payload(updated)
        payload["config_path"] = str(path)
        payload["foundation_policy"] = {
            "policy_path": str(foundation_policy_path()),
            "provider_alignment": build_foundation_provider_alignment(
                adapter_name=adapter_name,
                provider=updated.provider,
                llm_enabled=updated.llm_enabled,
                policy=foundation_policy,
            ),
        }
        _write_json(payload)
        return 0

    raise AssertionError("Unhandled command.")


def _build_generic_parsers(subparsers: Any) -> None:
    suggest_parser = subparsers.add_parser(
        "suggest",
        help="Generate ranked drafts through the selected product adapter.",
    )
    _add_adapter_argument(suggest_parser)
    suggest_parser.add_argument("--input-file")

    reason_spot_parser = subparsers.add_parser(
        "reason-spot",
        help="Run bounded Spot reasoning for one normalized row/message payload.",
    )
    _add_adapter_argument(reason_spot_parser)
    reason_spot_parser.add_argument("--input-file")

    outcome_parser = subparsers.add_parser(
        "record-outcome",
        help="Persist one operator outcome event for a prior runtime cycle.",
    )
    _add_adapter_argument(outcome_parser)
    outcome_parser.add_argument("--input-file")

    outcome_batch_parser = subparsers.add_parser(
        "record-outcomes-batch",
        help="Persist a bounded batch of operator outcome events for prior runtime cycles.",
    )
    _add_adapter_argument(outcome_batch_parser)
    outcome_batch_parser.add_argument("--input-file")

    spot_review_parser = subparsers.add_parser(
        "record-spot-review-outcome",
        help="Persist one human review outcome for a prior Spot reasoning cycle.",
    )
    _add_adapter_argument(spot_review_parser)
    spot_review_parser.add_argument("--input-file")

    memory_event_parser = subparsers.add_parser(
        "ingest-memory-event",
        help="Persist one normalized product memory event for runtime-owned memory updates.",
    )
    _add_adapter_argument(memory_event_parser)
    memory_event_parser.add_argument("--input-file")

    memory_event_batch_parser = subparsers.add_parser(
        "ingest-memory-events-batch",
        help="Persist a bounded batch of normalized product memory events.",
    )
    _add_adapter_argument(memory_event_batch_parser)
    memory_event_batch_parser.add_argument("--input-file")

    document_parser = subparsers.add_parser(
        "register-document",
        help="Register one product document with runtime-owned memory and retrieval state.",
    )
    _add_adapter_argument(document_parser)
    document_parser.add_argument("--input-file")

    document_batch_parser = subparsers.add_parser(
        "register-documents-batch",
        help="Register a bounded batch of product documents with runtime-owned memory and retrieval state.",
    )
    _add_adapter_argument(document_batch_parser)
    document_batch_parser.add_argument("--input-file")

    get_prepared_parser = subparsers.add_parser(
        "get-prepared-draft",
        help="Load the latest prepared runtime draft for one thread.",
    )
    _add_adapter_argument(get_prepared_parser)
    get_prepared_parser.add_argument("--company-id", required=True)
    get_prepared_parser.add_argument("--thread-ref", required=True)

    refresh_prepared_parser = subparsers.add_parser(
        "refresh-prepared-draft",
        help="Refresh the prepared runtime draft for one thread using the latest stored snapshot.",
    )
    _add_adapter_argument(refresh_prepared_parser)
    refresh_prepared_parser.add_argument("--company-id", required=True)
    refresh_prepared_parser.add_argument("--thread-ref", required=True)
    refresh_prepared_parser.add_argument("--reason")
    refresh_prepared_parser.add_argument(
        "--overwrite-mode",
        choices=("if_stale_or_dirty", "always"),
        default="if_stale_or_dirty",
    )

    plan_prepared_refresh_parser = subparsers.add_parser(
        "plan-prepared-draft-refresh",
        help="Inspect bounded active-thread prepared-draft refresh candidates.",
    )
    _add_adapter_argument(plan_prepared_refresh_parser)
    plan_prepared_refresh_parser.add_argument("--company-id", required=True)
    plan_prepared_refresh_parser.add_argument("--limit", type=int, default=10)
    plan_prepared_refresh_parser.add_argument("--stale-after-minutes", type=int, default=15)

    schedule_prepared_refresh_parser = subparsers.add_parser(
        "schedule-prepared-draft-refresh",
        help="Persist bounded prepared-draft refresh jobs for active threads.",
    )
    _add_adapter_argument(schedule_prepared_refresh_parser)
    schedule_prepared_refresh_parser.add_argument("--company-id", required=True)
    schedule_prepared_refresh_parser.add_argument("--limit", type=int, default=10)
    schedule_prepared_refresh_parser.add_argument("--stale-after-minutes", type=int, default=15)
    schedule_prepared_refresh_parser.add_argument("--reason")
    schedule_prepared_refresh_parser.add_argument("--schedule-hint")
    schedule_prepared_refresh_parser.add_argument("--description")

    export_parser = subparsers.add_parser(
        "export-trace",
        help="Export one persisted runtime trace by cycle id.",
    )
    _add_adapter_argument(export_parser)
    export_parser.add_argument("--cycle-id", required=True)

    source_export_parser = subparsers.add_parser(
        "build-source-export",
        help="Build one explicit versioned raw source export for Train portable packs.",
    )
    _add_adapter_argument(source_export_parser)
    source_export_parser.add_argument("--company-id", required=True)
    source_export_parser.add_argument("--snapshot-ref")

    outcome_export_parser = subparsers.add_parser(
        "build-outcome-export",
        help="Build one explicit versioned outcome export for Train supervision corpora.",
    )
    _add_adapter_argument(outcome_export_parser)
    outcome_export_parser.add_argument("--company-id", required=True)
    outcome_export_parser.add_argument("--snapshot-ref")

    memory_export_parser = subparsers.add_parser(
        "build-memory-export",
        help="Build one explicit versioned memory export for Train knowledge packs.",
    )
    _add_adapter_argument(memory_export_parser)
    memory_export_parser.add_argument("--company-id", required=True)
    memory_export_parser.add_argument("--snapshot-ref")

    delta_export_parser = subparsers.add_parser(
        "build-delta-export",
        help="Build one explicit cutoff-linked delta export for Train delta packs.",
    )
    _add_adapter_argument(delta_export_parser)
    delta_export_parser.add_argument("--company-id", required=True)
    delta_export_parser.add_argument("--cutoff-at", required=True)
    delta_export_parser.add_argument("--snapshot-ref", required=True)
    delta_export_parser.add_argument("--prior-snapshot-ref")
    delta_export_parser.add_argument("--prior-export-id")

    inspect_export_parser = subparsers.add_parser(
        "inspect-export-metadata",
        help="Inspect persisted portable export metadata without scraping runtime storage.",
    )
    _add_adapter_argument(inspect_export_parser)
    inspect_export_parser.add_argument("--company-id", required=True)
    inspect_export_parser.add_argument(
        "--export-family",
        required=True,
        choices=tuple(item.value for item in PortableExportFamily),
    )
    inspect_export_parser.add_argument("--export-id", required=True)

    validate_export_parser = subparsers.add_parser(
        "validate-export-lineage",
        help="Validate tenant scope, cutoff, and lineage invariants for one portable export.",
    )
    _add_adapter_argument(validate_export_parser)
    validate_export_parser.add_argument("--company-id", required=True)
    validate_export_parser.add_argument(
        "--export-family",
        required=True,
        choices=tuple(item.value for item in PortableExportFamily),
    )
    validate_export_parser.add_argument("--export-id", required=True)

    import_runtime_candidate_parser = subparsers.add_parser(
        "import-runtime-candidate-pack",
        help="Stage one Train runtime-candidate pack into the governed Trinity import surface.",
    )
    _add_adapter_argument(import_runtime_candidate_parser)
    import_runtime_candidate_parser.add_argument("--company-id", required=True)
    import_runtime_candidate_parser.add_argument("--manifest-file", required=True)
    import_runtime_candidate_parser.add_argument("--import-id")

    inspect_runtime_candidate_parser = subparsers.add_parser(
        "inspect-runtime-candidate-import",
        help="Inspect one staged Train runtime-candidate import before runtime adoption.",
    )
    _add_adapter_argument(inspect_runtime_candidate_parser)
    inspect_runtime_candidate_parser.add_argument("--company-id", required=True)
    inspect_runtime_candidate_parser.add_argument("--import-id", required=True)

    adopt_runtime_candidate_parser = subparsers.add_parser(
        "adopt-runtime-candidate-import",
        help="Adopt one staged Train runtime-candidate import into governed runtime memory and retrieval.",
    )
    _add_adapter_argument(adopt_runtime_candidate_parser)
    adopt_runtime_candidate_parser.add_argument("--company-id", required=True)
    adopt_runtime_candidate_parser.add_argument("--import-id", required=True)
    adopt_runtime_candidate_parser.add_argument("--min-confidence", type=float, default=0.6)
    adopt_runtime_candidate_parser.add_argument("--allow-conflicted", action="store_true")

    curate_eval_dataset_parser = subparsers.add_parser(
        "curate-eval-dataset",
        help="Promote persisted runtime traces into one replayable evaluation dataset.",
    )
    _add_adapter_argument(curate_eval_dataset_parser)
    curate_eval_dataset_parser.add_argument("--dataset-name")
    curate_eval_dataset_parser.add_argument("--dataset-file")
    curate_eval_dataset_parser.add_argument("--cycle-id", action="append", default=[])
    curate_eval_dataset_parser.add_argument("--trace-file", action="append", default=[])
    curate_eval_dataset_parser.add_argument("--selection-reason", required=True)

    replay_eval_dataset_parser = subparsers.add_parser(
        "replay-eval-dataset",
        help="Replay one curated evaluation dataset through the runtime.",
    )
    replay_eval_dataset_parser.add_argument("--dataset-file", required=True)

    report_score_health_parser = subparsers.add_parser(
        "report-score-health",
        help="Build one aggregate score-health report from persisted runtime traces.",
    )
    _add_adapter_argument(report_score_health_parser)
    report_score_health_parser.add_argument("--report-name", required=True)
    report_score_health_parser.add_argument("--cycle-id", action="append", default=[])
    report_score_health_parser.add_argument("--trace-file", action="append", default=[])
    report_score_health_parser.add_argument("--selection-reason")

    review_score_health_parser = subparsers.add_parser(
        "review-score-health",
        help="Build one operator review surface from a score-health report.",
    )
    review_score_health_parser.add_argument("--report-file", required=True)
    review_score_health_parser.add_argument("--replay-report-file")
    review_score_health_parser.add_argument("--decision-status")
    review_score_health_parser.add_argument("--decision-notes")

    compare_score_health_parser = subparsers.add_parser(
        "compare-score-health",
        help="Compare multiple score-health reports and persist one trend report.",
    )
    compare_score_health_parser.add_argument("--report-file", action="append", default=[])
    compare_score_health_parser.add_argument("--trend-report-name", required=True)
    compare_score_health_parser.add_argument("--selection-reason")

    check_score_governance_parser = subparsers.add_parser(
        "check-score-governance",
        help="Evaluate score-health governance artifacts for workflow gating.",
    )
    check_score_governance_parser.add_argument("--report-file", required=True)
    check_score_governance_parser.add_argument("--decision-file")
    check_score_governance_parser.add_argument("--trend-report-file")
    check_score_governance_parser.add_argument("--max-flagged-candidate-ratio", type=float)
    check_score_governance_parser.add_argument("--blocked-flag", action="append", default=[])
    check_score_governance_parser.add_argument("--persistent-flag-tolerance", type=int)
    check_score_governance_parser.add_argument("--rising-flag-tolerance", type=int)
    check_score_governance_parser.add_argument("--recurring-tuple-cluster-tolerance", type=int)
    check_score_governance_parser.add_argument(
        "--blocked-decision-status",
        action="append",
        default=[],
    )

    check_release_governance_parser = subparsers.add_parser(
        "check-release-governance",
        help="Build one persisted release-readiness view from score-governance artifacts.",
    )
    check_release_governance_parser.add_argument("--report-file", required=True)
    check_release_governance_parser.add_argument("--decision-file")
    check_release_governance_parser.add_argument("--trend-report-file")
    check_release_governance_parser.add_argument("--replay-report-file")
    check_release_governance_parser.add_argument("--release-report-name", required=True)
    check_release_governance_parser.add_argument("--selection-reason")
    check_release_governance_parser.add_argument("--max-flagged-candidate-ratio", type=float)
    check_release_governance_parser.add_argument("--blocked-flag", action="append", default=[])
    check_release_governance_parser.add_argument("--persistent-flag-tolerance", type=int)
    check_release_governance_parser.add_argument("--rising-flag-tolerance", type=int)
    check_release_governance_parser.add_argument(
        "--recurring-tuple-cluster-tolerance",
        type=int,
    )
    check_release_governance_parser.add_argument(
        "--blocked-decision-status",
        action="append",
        default=[],
    )

    list_score_governance_work_parser = subparsers.add_parser(
        "list-score-governance-work",
        help="Build one operator triage queue from persisted governance artifacts.",
    )
    _add_adapter_argument(list_score_governance_work_parser)
    list_score_governance_work_parser.add_argument("--triage-report-name", required=True)
    list_score_governance_work_parser.add_argument("--selection-reason")

    resolve_score_governance_item_parser = subparsers.add_parser(
        "resolve-score-governance-item",
        help="Persist one operator resolution for a score-governance triage item.",
    )
    _add_adapter_argument(resolve_score_governance_item_parser)
    resolve_score_governance_item_parser.add_argument("--item-id", required=True)
    resolve_score_governance_item_parser.add_argument("--resolution-status", required=True)
    resolve_score_governance_item_parser.add_argument("--notes")

    record_release_governance_decision_parser = subparsers.add_parser(
        "record-release-governance-decision",
        help="Persist one operator release decision for a release-governance report.",
    )
    record_release_governance_decision_parser.add_argument("--release-report-file", required=True)
    record_release_governance_decision_parser.add_argument("--decision-status", required=True)
    record_release_governance_decision_parser.add_argument("--notes")

    governance_status_parser = subparsers.add_parser(
        "governance-status",
        help="Show the latest joined governance status surface for one adapter.",
    )
    _add_adapter_argument(governance_status_parser)

    cross_adapter_scores_parser = subparsers.add_parser(
        "report-cross-adapter-scores",
        help="Build one comparable score inspection report across adapters.",
    )
    cross_adapter_scores_parser.add_argument("--report-name", required=True)
    cross_adapter_scores_parser.add_argument(
        "--adapter",
        action="append",
        default=[],
    )
    cross_adapter_scores_parser.add_argument("--top-n", type=int, default=25)

    governance_dashboard_parser = subparsers.add_parser(
        "report-score-governance-dashboard",
        help="Build one aggregate governance dashboard report across adapters.",
    )
    governance_dashboard_parser.add_argument("--report-name", required=True)
    governance_dashboard_parser.add_argument(
        "--adapter",
        action="append",
        default=[],
    )

    bundle_parser = subparsers.add_parser(
        "export-training-bundle",
        help="Export one bounded training bundle from a recorded cycle.",
    )
    _add_adapter_argument(bundle_parser)
    bundle_parser.add_argument("--cycle-id", required=True)
    bundle_parser.add_argument("--bundle-type", required=True)

    post_training_dataset_parser = subparsers.add_parser(
        "export-post-training-dataset",
        help="Build and persist one Trinity-owned post-training dataset from training bundles.",
    )
    _add_adapter_argument(post_training_dataset_parser)
    post_training_dataset_parser.add_argument("--dataset-name", required=True)
    post_training_dataset_parser.add_argument("--bundle-file", action="append", default=[])
    post_training_dataset_parser.add_argument("--cycle-id", action="append", default=[])
    post_training_dataset_parser.add_argument("--bundle-type")
    post_training_dataset_parser.add_argument(
        "--purpose",
        action="append",
        default=[
            PostTrainingPurpose.SFT.value,
            PostTrainingPurpose.LORA.value,
            PostTrainingPurpose.QLORA.value,
        ],
    )
    post_training_dataset_parser.add_argument("--selection-reason")

    post_training_split_parser = subparsers.add_parser(
        "build-post-training-split",
        help="Build and persist one deterministic split for a Trinity post-training dataset.",
    )
    post_training_split_parser.add_argument("--dataset-file", required=True)
    post_training_split_parser.add_argument("--split-name", required=True)
    post_training_split_parser.add_argument("--validation-ratio", type=float, default=0.1)
    post_training_split_parser.add_argument("--holdout-ratio", type=float, default=0.1)
    post_training_split_parser.add_argument("--selection-reason")

    post_training_curation_parser = subparsers.add_parser(
        "curate-post-training-example",
        help="Persist one curation decision and apply it to a post-training dataset.",
    )
    post_training_curation_parser.add_argument("--dataset-file", required=True)
    post_training_curation_parser.add_argument("--example-id", required=True)
    post_training_curation_parser.add_argument("--annotation-status", required=True)
    post_training_curation_parser.add_argument("--reason", required=True)

    post_training_promotion_parser = subparsers.add_parser(
        "promote-post-training-dataset",
        help="Promote one post-training dataset from candidate to curated or ready.",
    )
    post_training_promotion_parser.add_argument("--dataset-file", required=True)
    post_training_promotion_parser.add_argument("--dataset-status", required=True)
    post_training_promotion_parser.add_argument("--reason", required=True)

    shadow_parser = subparsers.add_parser(
        "run-shadow-fixtures",
        help="Replay adapter fixtures against the live runtime implementation.",
    )
    _add_adapter_argument(shadow_parser)
    shadow_parser.add_argument("--fixture-dir")

    compare_parser = subparsers.add_parser(
        "compare-providers",
        help="Run a bounded provider comparison harness over Reply shadow fixtures.",
    )
    _add_adapter_argument(compare_parser)
    compare_parser.add_argument("--fixture-dir")
    compare_parser.add_argument("--corpus-id")
    compare_parser.add_argument("--route-set-file", action="append", default=[])
    compare_parser.add_argument("--include-current-config", action="store_true")
    compare_parser.add_argument("--include-deterministic-baseline", action="store_true")

    make_control_job_parser = subparsers.add_parser(
        "make-control-job",
        help="Create and persist one bounded control-plane job definition.",
    )
    _add_adapter_argument(make_control_job_parser)
    make_control_job_parser.add_argument(
        "--job-kind",
        required=True,
        choices=("reply_provider_comparison", "reply_prepared_draft_refresh"),
    )
    make_control_job_parser.add_argument("--job-id", required=True)
    make_control_job_parser.add_argument("--description")
    make_control_job_parser.add_argument("--schedule-hint")
    make_control_job_parser.add_argument("--fixture-dir")
    make_control_job_parser.add_argument("--corpus-id")
    make_control_job_parser.add_argument("--route-set-file", action="append", default=[])
    make_control_job_parser.add_argument("--include-current-config", action="store_true")
    make_control_job_parser.add_argument("--include-deterministic-baseline", action="store_true")
    make_control_job_parser.add_argument("--company-id")
    make_control_job_parser.add_argument("--thread-ref")
    make_control_job_parser.add_argument("--reason")

    run_control_job_parser = subparsers.add_parser(
        "run-control-job",
        help="Run one persisted bounded control-plane job definition.",
    )
    run_control_job_parser.add_argument("--job-file", required=True)

    control_run_status_parser = subparsers.add_parser(
        "control-run-status",
        help="Inspect one persisted control-plane run artifact.",
    )
    _add_adapter_argument(control_run_status_parser)
    control_run_status_parser.add_argument("--run-id", required=True)

    make_gobii_workflow_parser = subparsers.add_parser(
        "make-gobii-workflow",
        help="Build and persist one Gobii-ready recurring workflow bundle for a control-plane job.",
    )
    make_gobii_workflow_parser.add_argument("--job-file", required=True)
    make_gobii_workflow_parser.add_argument("--schedule", required=True)

    make_gobii_profile_enrichment_parser = subparsers.add_parser(
        "make-gobii-profile-enrichment",
        help="Build and persist one bounded Gobii tracked-entity profile-enrichment bundle.",
    )
    _add_adapter_argument(make_gobii_profile_enrichment_parser)
    make_gobii_profile_enrichment_parser.add_argument("--input-file", required=True)
    make_gobii_profile_enrichment_parser.add_argument("--agent-id")
    make_gobii_profile_enrichment_parser.add_argument("--webhook")
    make_gobii_profile_enrichment_parser.add_argument("--wait-seconds", type=int)

    register_gobii_workflow_parser = subparsers.add_parser(
        "register-gobii-workflow",
        help="Register one persisted Gobii workflow bundle through the Gobii Agent API.",
    )
    register_gobii_workflow_parser.add_argument("--bundle-file", required=True)
    register_gobii_workflow_parser.add_argument(
        "--gobii-api-base-url",
        default="https://gobii.ai",
    )
    register_gobii_workflow_parser.add_argument(
        "--api-key-env",
        default="GOBII_API_KEY",
    )

    submit_gobii_task_parser = subparsers.add_parser(
        "submit-gobii-task",
        help="Submit one bounded Gobii browser-use task and persist the normalized task record.",
    )
    _add_adapter_argument(submit_gobii_task_parser)
    submit_gobii_task_parser.add_argument("--prompt", required=True)
    submit_gobii_task_parser.add_argument("--agent-id")
    submit_gobii_task_parser.add_argument("--webhook")
    submit_gobii_task_parser.add_argument("--wait-seconds", type=int)
    submit_gobii_task_parser.add_argument("--company-id")
    submit_gobii_task_parser.add_argument("--gobii-api-base-url", default="https://gobii.ai")
    submit_gobii_task_parser.add_argument("--api-key-env", default="GOBII_API_KEY")

    submit_gobii_profile_enrichment_parser = subparsers.add_parser(
        "submit-gobii-profile-enrichment",
        help=(
            "Submit one persisted Gobii tracked-entity enrichment bundle "
            "and persist the task record."
        ),
    )
    _add_adapter_argument(submit_gobii_profile_enrichment_parser)
    submit_gobii_profile_enrichment_parser.add_argument("--bundle-file", required=True)
    submit_gobii_profile_enrichment_parser.add_argument(
        "--gobii-api-base-url",
        default="https://gobii.ai",
    )
    submit_gobii_profile_enrichment_parser.add_argument(
        "--api-key-env",
        default="GOBII_API_KEY",
    )

    gobii_task_result_parser = subparsers.add_parser(
        "gobii-task-result",
        help="Fetch and persist one Gobii browser-use task result.",
    )
    _add_adapter_argument(gobii_task_result_parser)
    gobii_task_result_parser.add_argument("--task-id", required=True)
    gobii_task_result_parser.add_argument("--gobii-api-base-url", default="https://gobii.ai")
    gobii_task_result_parser.add_argument("--api-key-env", default="GOBII_API_KEY")

    list_gobii_tasks_parser = subparsers.add_parser(
        "list-gobii-tasks",
        help="List and persist Gobii browser-use task records.",
    )
    _add_adapter_argument(list_gobii_tasks_parser)
    list_gobii_tasks_parser.add_argument("--page", type=int)
    list_gobii_tasks_parser.add_argument("--page-size", type=int)
    list_gobii_tasks_parser.add_argument("--gobii-api-base-url", default="https://gobii.ai")
    list_gobii_tasks_parser.add_argument("--api-key-env", default="GOBII_API_KEY")

    cancel_gobii_task_parser = subparsers.add_parser(
        "cancel-gobii-task",
        help="Cancel and persist one Gobii browser-use task record.",
    )
    _add_adapter_argument(cancel_gobii_task_parser)
    cancel_gobii_task_parser.add_argument("--task-id", required=True)
    cancel_gobii_task_parser.add_argument("--gobii-api-base-url", default="https://gobii.ai")
    cancel_gobii_task_parser.add_argument("--api-key-env", default="GOBII_API_KEY")

    normalize_gobii_task_parser = subparsers.add_parser(
        "normalize-gobii-task",
        help=(
            "Normalize one Gobii task result into Trinity-owned "
            "document, memory, and evidence artifacts."
        ),
    )
    _add_adapter_argument(normalize_gobii_task_parser)
    normalize_gobii_task_parser.add_argument("--input-file", required=True)

    normalize_gobii_profile_enrichment_parser = subparsers.add_parser(
        "normalize-gobii-profile-enrichment",
        help=(
            "Normalize one persisted Gobii tracked-entity enrichment bundle into Trinity artifacts."
        ),
    )
    _add_adapter_argument(normalize_gobii_profile_enrichment_parser)
    normalize_gobii_profile_enrichment_parser.add_argument("--bundle-file", required=True)

    train_parser = subparsers.add_parser(
        "train-propose-policy",
        help="Export Trinity bundles, invoke Train, and optionally accept the returned policy.",
    )
    _add_adapter_argument(train_parser)
    train_parser.add_argument("--cycle-id", action="append")
    train_parser.add_argument("--bundle-file", action="append")
    train_parser.add_argument("--bundle-type")
    train_parser.add_argument("--learner-kind", required=True)
    train_parser.add_argument("--transport", choices=("api", "cli"))
    train_parser.add_argument("--train-api-base-url")
    train_parser.add_argument("--train-root-dir")
    train_parser.add_argument("--proposal-output-path")
    train_parser.add_argument("--eval-output-path")
    train_parser.add_argument("--comparison-output-path")
    train_parser.add_argument("--accept", action="store_true")
    train_parser.add_argument("--holdout-bundle-file", action="append", default=[])
    train_parser.add_argument("--require-holdout", action="store_true")
    train_parser.add_argument("--allow-no-holdout", action="store_true")
    train_parser.add_argument("--skeptical-note", action="append", default=[])
    train_parser.add_argument("--regression-threshold", type=float, default=0.0)
    train_parser.add_argument("--reason")
    _add_score_governance_acceptance_arguments(train_parser)

    accept_parser = subparsers.add_parser(
        "policy-accept",
        help="Validate and accept one adapter policy artifact against training bundles.",
    )
    _add_adapter_argument(accept_parser)
    accept_parser.add_argument("--policy-file", required=True)
    accept_parser.add_argument("--bundle-file", action="append", required=True)
    accept_parser.add_argument("--holdout-bundle-file", action="append", default=[])
    accept_parser.add_argument("--require-holdout", action="store_true")
    accept_parser.add_argument("--allow-no-holdout", action="store_true")
    accept_parser.add_argument("--regression-threshold", type=float, default=0.0)
    accept_parser.add_argument("--source-train-project-key")
    accept_parser.add_argument("--source-train-run-id")
    accept_parser.add_argument("--skeptical-note", action="append", default=[])
    accept_parser.add_argument("--reason")
    _add_score_governance_acceptance_arguments(accept_parser)

    review_parser = subparsers.add_parser(
        "policy-review",
        help="Review one adapter policy artifact against proposal and optional holdout bundles.",
    )
    _add_adapter_argument(review_parser)
    review_parser.add_argument("--policy-file", required=True)
    review_parser.add_argument("--bundle-file", action="append", required=True)
    review_parser.add_argument("--holdout-bundle-file", action="append", default=[])
    review_parser.add_argument("--require-holdout", action="store_true")
    review_parser.add_argument("--allow-no-holdout", action="store_true")
    review_parser.add_argument("--regression-threshold", type=float, default=0.0)
    review_parser.add_argument("--source-train-project-key")
    review_parser.add_argument("--source-train-run-id")
    review_parser.add_argument("--skeptical-note", action="append", default=[])

    review_surface_parser = subparsers.add_parser(
        "policy-review-surface",
        help=(
            "Render a promotion-oriented review surface with acceptance mode and Train provenance."
        ),
    )
    _add_adapter_argument(review_surface_parser)
    review_surface_parser.add_argument("--policy-file", required=True)
    review_surface_parser.add_argument("--bundle-file", action="append", required=True)
    review_surface_parser.add_argument("--holdout-bundle-file", action="append", default=[])
    review_surface_parser.add_argument("--require-holdout", action="store_true")
    review_surface_parser.add_argument("--allow-no-holdout", action="store_true")
    review_surface_parser.add_argument("--regression-threshold", type=float, default=0.0)
    review_surface_parser.add_argument("--source-train-project-key")
    review_surface_parser.add_argument("--source-train-run-id")
    review_surface_parser.add_argument("--skeptical-note", action="append", default=[])

    promote_parser = subparsers.add_parser(
        "policy-promote",
        help="Promote one accepted artifact version into current runtime state.",
    )
    _add_adapter_argument(promote_parser)
    promote_parser.add_argument("--artifact-key", required=True)
    promote_parser.add_argument("--version", required=True)
    promote_parser.add_argument("--source-project", required=True)
    promote_parser.add_argument("--accepted-at")
    promote_parser.add_argument("--policy-file")
    promote_parser.add_argument("--reason")
    promote_parser.add_argument("--allow-foundation-bypass", action="store_true")
    promote_parser.add_argument("--foundation-bypass-note")

    rollback_parser = subparsers.add_parser(
        "policy-rollback",
        help="Rollback the current artifact pointer to a prior accepted version.",
    )
    _add_adapter_argument(rollback_parser)
    rollback_parser.add_argument("--artifact-key", required=True)
    rollback_parser.add_argument("--target-version")
    rollback_parser.add_argument("--reason")

    policy_status_parser = subparsers.add_parser(
        "policy-status",
        help="Show the current artifact pointer and history for one policy family.",
    )
    _add_adapter_argument(policy_status_parser)
    policy_status_parser.add_argument("--artifact-key", required=True)

    show_config_parser = subparsers.add_parser(
        "show-config",
        help="Print the active model routing configuration for the selected adapter.",
    )
    _add_adapter_argument(show_config_parser)
    show_config_parser.add_argument("--include-path", action="store_true")

    show_foundation_policy_parser = subparsers.add_parser(
        "show-foundation-policy",
        help="Show the machine-local foundation policy used for release gates and seam policy.",
    )
    show_foundation_policy_parser.add_argument("--include-path", action="store_true")

    write_foundation_policy_parser = subparsers.add_parser(
        "write-foundation-policy",
        help=(
            "Persist machine-local foundation policy defaults "
            "for Train and adapter provider support."
        ),
    )
    write_foundation_policy_parser.add_argument("--train-default-transport", choices=("api", "cli"))
    write_foundation_policy_parser.add_argument("--adapter")
    write_foundation_policy_parser.add_argument("--supported-provider", action="append")
    write_foundation_policy_parser.add_argument("--preferred-live-provider")
    write_foundation_policy_parser.add_argument(
        "--release-gate-role",
        choices=("generator", "refiner", "evaluator"),
        action="append",
    )
    write_foundation_policy_parser.add_argument("--gobii-required-for-release", action="store_true")
    write_foundation_policy_parser.add_argument("--gobii-optional-for-release", action="store_true")

    runtime_status_parser = subparsers.add_parser(
        "runtime-status",
        help="Show runtime model availability and adapter wiring status.",
    )
    _add_adapter_argument(runtime_status_parser)

    train_status_parser = subparsers.add_parser(
        "train-status",
        help="Show bounded Train seam health across API and CLI paths.",
    )
    train_status_parser.add_argument("--transport", choices=("api", "cli", "both"), default="both")
    train_status_parser.add_argument("--train-api-base-url")
    train_status_parser.add_argument("--train-root-dir")

    foundation_check_parser = subparsers.add_parser(
        "foundation-check",
        help="Run the standard Train, provider, Reply, and optional Gobii release preflight.",
    )
    _add_adapter_argument(foundation_check_parser)
    foundation_check_parser.add_argument("--transport", choices=("api", "cli", "both"))
    foundation_check_parser.add_argument("--train-api-base-url")
    foundation_check_parser.add_argument("--train-root-dir")
    foundation_check_parser.add_argument("--reply-root-dir")
    foundation_check_parser.add_argument("--gobii-api-base-url", default="https://gobii.ai")
    foundation_check_parser.add_argument("--api-key-env", default="GOBII_API_KEY")
    foundation_check_parser.add_argument("--check-gobii-live", action="store_true")

    provider_smoke_parser = subparsers.add_parser(
        "provider-smoke",
        help="Run one bounded provider readiness check for configured adapter roles.",
    )
    _add_adapter_argument(provider_smoke_parser)
    provider_smoke_parser.add_argument(
        "--role",
        choices=("generator", "refiner", "evaluator"),
        action="append",
    )
    provider_smoke_parser.add_argument("--inventory-only", action="store_true")

    reply_compat_parser = subparsers.add_parser(
        "check-reply-compatibility",
        help="Run one bounded cross-repo compatibility check for the Reply seam.",
    )
    reply_compat_parser.add_argument("--reply-root-dir")

    gobii_status_parser = subparsers.add_parser(
        "gobii-status",
        help="Show bounded Gobii seam status and optional live connectivity checks.",
    )
    _add_adapter_argument(gobii_status_parser)
    gobii_status_parser.add_argument("--gobii-api-base-url", default="https://gobii.ai")
    gobii_status_parser.add_argument("--api-key-env", default="GOBII_API_KEY")
    gobii_status_parser.add_argument("--check-live", action="store_true")

    write_config_parser = subparsers.add_parser(
        "write-config",
        help="Persist a new model routing configuration for the selected adapter.",
    )
    _add_adapter_argument(write_config_parser)
    write_config_parser.add_argument("--provider")
    write_config_parser.add_argument("--ollama-base-url")
    write_config_parser.add_argument("--mistral-cli-executable")
    write_config_parser.add_argument("--mistral-cli-arg", action="append")
    write_config_parser.add_argument("--mistral-cli-mode")
    write_config_parser.add_argument("--mistral-cli-model-binding")
    write_config_parser.add_argument("--timeout-seconds", type=float)
    write_config_parser.add_argument("--generator-model")
    write_config_parser.add_argument("--generator-model-id")
    write_config_parser.add_argument("--refiner-model")
    write_config_parser.add_argument("--refiner-model-id")
    write_config_parser.add_argument("--evaluator-model")
    write_config_parser.add_argument("--evaluator-model-id")


def _build_reply_compat_parsers(subparsers: Any) -> None:
    suggest_parser = subparsers.add_parser("reply-suggest")
    suggest_parser.add_argument("--input-file")

    outcome_parser = subparsers.add_parser("reply-record-outcome")
    outcome_parser.add_argument("--input-file")

    memory_event_parser = subparsers.add_parser("reply-ingest-memory-event")
    memory_event_parser.add_argument("--input-file")

    document_parser = subparsers.add_parser("reply-register-document")
    document_parser.add_argument("--input-file")

    get_prepared_parser = subparsers.add_parser("reply-get-prepared-draft")
    get_prepared_parser.add_argument("--company-id", required=True)
    get_prepared_parser.add_argument("--thread-ref", required=True)

    refresh_prepared_parser = subparsers.add_parser("reply-refresh-prepared-draft")
    refresh_prepared_parser.add_argument("--company-id", required=True)
    refresh_prepared_parser.add_argument("--thread-ref", required=True)
    refresh_prepared_parser.add_argument("--reason")

    export_parser = subparsers.add_parser("reply-export-trace")
    export_parser.add_argument("--cycle-id", required=True)

    bundle_parser = subparsers.add_parser("reply-export-training-bundle")
    bundle_parser.add_argument("--cycle-id", required=True)
    bundle_parser.add_argument("--bundle-type", required=True)

    shadow_parser = subparsers.add_parser("reply-run-shadow-fixtures")
    shadow_parser.add_argument("--fixture-dir")

    train_parser = subparsers.add_parser("reply-train-propose-policy")
    train_parser.add_argument("--cycle-id", action="append")
    train_parser.add_argument("--bundle-file", action="append")
    train_parser.add_argument("--bundle-type")
    train_parser.add_argument("--learner-kind", required=True)
    train_parser.add_argument("--transport", choices=("api", "cli"))
    train_parser.add_argument("--train-api-base-url")
    train_parser.add_argument("--train-root-dir")
    train_parser.add_argument("--proposal-output-path")
    train_parser.add_argument("--eval-output-path")
    train_parser.add_argument("--accept", action="store_true")
    train_parser.add_argument("--holdout-bundle-file", action="append", default=[])
    train_parser.add_argument("--require-holdout", action="store_true")
    train_parser.add_argument("--allow-no-holdout", action="store_true")
    train_parser.add_argument("--skeptical-note", action="append", default=[])
    train_parser.add_argument("--regression-threshold", type=float, default=0.0)
    train_parser.add_argument("--reason")

    accept_parser = subparsers.add_parser("reply-policy-accept")
    accept_parser.add_argument("--policy-file", required=True)
    accept_parser.add_argument("--bundle-file", action="append", required=True)
    accept_parser.add_argument("--holdout-bundle-file", action="append", default=[])
    accept_parser.add_argument("--require-holdout", action="store_true")
    accept_parser.add_argument("--allow-no-holdout", action="store_true")
    accept_parser.add_argument("--regression-threshold", type=float, default=0.0)
    accept_parser.add_argument("--source-train-project-key")
    accept_parser.add_argument("--source-train-run-id")
    accept_parser.add_argument("--skeptical-note", action="append", default=[])
    accept_parser.add_argument("--reason")

    review_parser = subparsers.add_parser("reply-policy-review")
    review_parser.add_argument("--policy-file", required=True)
    review_parser.add_argument("--bundle-file", action="append", required=True)
    review_parser.add_argument("--holdout-bundle-file", action="append", default=[])
    review_parser.add_argument("--require-holdout", action="store_true")
    review_parser.add_argument("--allow-no-holdout", action="store_true")
    review_parser.add_argument("--regression-threshold", type=float, default=0.0)
    review_parser.add_argument("--source-train-project-key")
    review_parser.add_argument("--source-train-run-id")
    review_parser.add_argument("--skeptical-note", action="append", default=[])

    review_surface_parser = subparsers.add_parser("reply-policy-review-surface")
    review_surface_parser.add_argument("--policy-file", required=True)
    review_surface_parser.add_argument("--bundle-file", action="append", required=True)
    review_surface_parser.add_argument("--holdout-bundle-file", action="append", default=[])
    review_surface_parser.add_argument("--require-holdout", action="store_true")
    review_surface_parser.add_argument("--allow-no-holdout", action="store_true")
    review_surface_parser.add_argument("--regression-threshold", type=float, default=0.0)
    review_surface_parser.add_argument("--source-train-project-key")
    review_surface_parser.add_argument("--source-train-run-id")
    review_surface_parser.add_argument("--skeptical-note", action="append", default=[])

    promote_parser = subparsers.add_parser("reply-policy-promote")
    promote_parser.add_argument("--artifact-key", required=True)
    promote_parser.add_argument("--version", required=True)
    promote_parser.add_argument("--source-project", required=True)
    promote_parser.add_argument("--accepted-at")
    promote_parser.add_argument("--allow-foundation-bypass", action="store_true")
    promote_parser.add_argument("--foundation-bypass-note")
    promote_parser.add_argument("--reason")

    rollback_parser = subparsers.add_parser("reply-policy-rollback")
    rollback_parser.add_argument("--artifact-key", required=True)
    rollback_parser.add_argument("--target-version")
    rollback_parser.add_argument("--reason")

    policy_status_parser = subparsers.add_parser("reply-policy-status")
    policy_status_parser.add_argument("--artifact-key", required=True)

    show_config_parser = subparsers.add_parser("reply-show-config")
    show_config_parser.add_argument("--include-path", action="store_true")

    subparsers.add_parser("reply-runtime-status")

    write_config_parser = subparsers.add_parser("reply-write-config")
    write_config_parser.add_argument("--provider")
    write_config_parser.add_argument("--ollama-base-url")
    write_config_parser.add_argument("--mistral-cli-executable")
    write_config_parser.add_argument("--mistral-cli-arg", action="append")
    write_config_parser.add_argument("--mistral-cli-mode")
    write_config_parser.add_argument("--mistral-cli-model-binding")
    write_config_parser.add_argument("--timeout-seconds", type=float)
    write_config_parser.add_argument("--generator-model")
    write_config_parser.add_argument("--generator-model-id")
    write_config_parser.add_argument("--refiner-model")
    write_config_parser.add_argument("--refiner-model-id")
    write_config_parser.add_argument("--evaluator-model")
    write_config_parser.add_argument("--evaluator-model-id")


def _add_adapter_argument(parser: Any) -> None:
    parser.add_argument(
        "--adapter",
        default=REPLY_ADAPTER_NAME,
        help=(
            "Product adapter to use. "
            f"Currently implemented adapters: {SUPPORTED_ADAPTER_NAME_LIST}."
        ),
    )


def _require_spot_adapter(adapter_name: str, command: str) -> None:
    if adapter_name != "spot":
        raise ValueError(f"{command} requires --adapter spot.")


def _load_json(input_file: str | None) -> dict[str, Any]:
    if input_file:
        with open(input_file, encoding="utf-8") as handle:
            return json.load(handle)
    return json.load(sys.stdin)


def _batch_items_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict) and isinstance(payload.get("items"), list):
        items = payload["items"]
    else:
        raise ValueError("Batch payload must be a JSON array or an object with an 'items' array.")
    normalized = [item for item in items if isinstance(item, dict)]
    if len(normalized) != len(items):
        raise ValueError("Batch payload items must all be JSON objects.")
    return normalized


def _add_score_governance_acceptance_arguments(parser: Any) -> None:
    parser.add_argument("--score-health-report-file")
    parser.add_argument("--score-health-decision-file")
    parser.add_argument("--score-health-trend-report-file")
    parser.add_argument("--release-governance-report-file")
    parser.add_argument("--release-governance-decision-status")
    parser.add_argument("--release-governance-notes")
    parser.add_argument("--allow-score-governance-override", action="store_true")
    parser.add_argument("--score-governance-override-note")
    parser.add_argument("--max-flagged-candidate-ratio", type=float)
    parser.add_argument("--blocked-flag", action="append", default=[])
    parser.add_argument("--persistent-flag-tolerance", type=int)
    parser.add_argument("--rising-flag-tolerance", type=int)
    parser.add_argument("--recurring-tuple-cluster-tolerance", type=int)
    parser.add_argument("--blocked-decision-status", action="append", default=[])


def _score_governance_policy_from_args(args: Any) -> ScoreGovernancePolicy:
    blocked_statuses = (
        tuple(
            str(status).strip()
            for status in getattr(args, "blocked_decision_status", ())
            if str(status).strip()
        )
        or ScoreGovernancePolicy().blocked_decision_statuses
    )
    return ScoreGovernancePolicy(
        blocked_decision_statuses=blocked_statuses,
        blocked_flags=tuple(
            str(flag).strip() for flag in getattr(args, "blocked_flag", ()) if str(flag).strip()
        ),
        max_flagged_candidate_ratio=getattr(args, "max_flagged_candidate_ratio", None),
        persistent_flag_tolerance=getattr(args, "persistent_flag_tolerance", None),
        rising_flag_tolerance=getattr(args, "rising_flag_tolerance", None),
        recurring_tuple_cluster_tolerance=getattr(
            args,
            "recurring_tuple_cluster_tolerance",
            None,
        ),
    )


def _resolve_score_governance_check(args: Any) -> Any | None:
    report_file = getattr(args, "score_health_report_file", None)
    if not report_file:
        return None
    report = load_score_health_report(report_file)
    decision_file = getattr(args, "score_health_decision_file", None)
    trend_report_file = getattr(args, "score_health_trend_report_file", None)
    decision = load_score_health_review_decision(decision_file) if decision_file else None
    trend_report = load_score_health_trend_report(trend_report_file) if trend_report_file else None
    return evaluate_score_governance(
        report,
        decision=decision,
        trend_report=trend_report,
        policy=_score_governance_policy_from_args(args),
    )


def _policy_accept_skeptical_notes(args: Any, score_governance: Any | None) -> tuple[str, ...]:
    notes = [str(note).strip() for note in getattr(args, "skeptical_note", ()) if str(note).strip()]
    if score_governance is None:
        return tuple(notes)
    notes.append(
        "Score governance checked "
        f"for report {score_governance.report_id or 'unknown'} with "
        f"{len(score_governance.blocking_reasons)} blocking reasons and "
        f"{len(score_governance.warnings)} warnings."
    )
    override_note = str(getattr(args, "score_governance_override_note", "") or "").strip()
    if override_note:
        notes.append(f"Score governance override: {override_note}")
    return tuple(notes)


def _policy_accept_score_governance_kwargs(
    args: Any,
    score_governance: Any | None,
) -> dict[str, Any]:
    if score_governance is None:
        return {}
    override_note = str(getattr(args, "score_governance_override_note", "") or "").strip()
    return {
        "score_governance_status": (
            "override"
            if override_note and not score_governance.allowed
            else (score_governance.decision_status or "checked")
        ),
        "score_governance_report_id": score_governance.report_id,
        "score_governance_decision_id": score_governance.decision_id,
        "score_governance_trend_report_id": score_governance.trend_report_id,
        "score_governance_override_notes": ((override_note,) if override_note else ()),
    }


def _resolve_release_governance_decision(args: Any, score_governance: Any | None) -> Any | None:
    report_file = getattr(args, "release_governance_report_file", None)
    if not report_file:
        if score_governance is not None:
            raise ValueError(
                "--release-governance-report-file is required when accepting with "
                "score-governance artifacts."
            )
        return None
    report = load_score_governance_release_report(report_file)
    decision_status = str(getattr(args, "release_governance_decision_status", "") or "").strip()
    if not decision_status:
        raise ValueError(
            "--release-governance-decision-status is required when "
            "--release-governance-report-file is provided."
        )
    decision = make_score_governance_release_decision(
        report,
        decision_status=decision_status,
        notes=str(getattr(args, "release_governance_notes", "") or ""),
        metadata={"release_report_file": str(report_file)},
    )
    persist_score_governance_release_decision(report.adapter_name, decision)
    return report, decision


def _write_json(payload: dict[str, Any]) -> None:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def _build_shared_model_inventory_payload() -> dict[str, Any]:
    try:
        inventory = load_model_inventory(repo_root=Path(__file__).resolve().parents[2])
    except ModelInventoryError as exc:
        return {
            "enabled": False,
            "manifest_version": None,
            "models_root": None,
            "manifest_path": None,
            "entry_count": 0,
            "error": str(exc),
            "_inventory": None,
        }

    return {
        "enabled": inventory.loaded,
        "manifest_version": inventory.manifest_version,
        "models_root": str(inventory.models_root),
        "manifest_path": str(inventory.manifest_path),
        "entry_count": len(inventory.entries),
        "error": None,
        "_inventory": inventory,
    }


def _build_role_inventory_payload(
    *,
    shared_inventory_payload: dict[str, Any],
    provider: str,
    route_model_id: str | None,
    route_model: str,
) -> dict[str, Any]:
    inventory = shared_inventory_payload.get("_inventory")
    if inventory is None or not shared_inventory_payload.get("enabled"):
        return {
            "inventory_found": False,
            "inventory_model_id": None,
            "inventory_path": None,
            "inventory_format": None,
            "inventory_status": "inventory_disabled",
        }

    entry = None
    normalized_model_id = str(route_model_id or "").strip()
    if normalized_model_id:
        entry = inventory.find_by_model_id(normalized_model_id)
    if entry is None:
        entry = inventory.find_for_route(provider=provider, route_model=route_model)

    inventory_path = str(entry.local_path) if entry is not None and entry.local_path else None
    return {
        "inventory_found": entry is not None,
        "inventory_model_id": entry.model_id if entry is not None else None,
        "inventory_path": inventory_path,
        "inventory_format": entry.format if entry is not None else None,
        "inventory_status": _inventory_status_for_entry(entry, provider=provider),
    }


def _inventory_status_for_entry(entry: Any, *, provider: str) -> str:
    if entry is None:
        return "unknown"

    local_path = getattr(entry, "local_path", None)
    if local_path is not None:
        return "present" if Path(local_path).exists() else "missing"

    provider_modes = {
        str(item).strip().lower()
        for item in getattr(entry, "provider_modes", ())
        if str(item).strip()
    }
    provider_refs = getattr(entry, "provider_refs", {})
    normalized_provider = str(provider or "").strip().lower()
    if (
        normalized_provider in provider_refs
        or normalized_provider in provider_modes
        or "provider-managed" in provider_modes
    ):
        return "provider_managed"
    return "unknown"


def _resolve_cli_role_model_id(
    *,
    explicit_model_id: str | None,
    provider: str,
    route_model: str,
    current_model_id: str | None,
) -> str | None:
    normalized_explicit = str(explicit_model_id or "").strip()
    if normalized_explicit:
        return normalized_explicit
    shared_inventory_payload = _build_shared_model_inventory_payload()
    inventory = shared_inventory_payload.get("_inventory")
    if inventory is not None and shared_inventory_payload.get("enabled"):
        entry = inventory.find_for_route(provider=provider, route_model=route_model)
        if entry is not None:
            return entry.model_id
    return current_model_id


def _build_runtime_readiness_payload(payload: dict[str, Any]) -> dict[str, Any]:
    llm_enabled = bool(payload.get("llm_enabled"))
    provider_status = str(payload.get("provider_status") or "not_configured").strip().lower()
    provider_error_code = str(payload.get("provider_error_code") or "").strip().lower()
    roles = payload.get("roles") if isinstance(payload.get("roles"), dict) else {}
    role_readiness: dict[str, bool] = {}
    missing_models: list[str] = []

    for role_name in ("generator", "refiner", "evaluator"):
        route = roles.get(role_name) if isinstance(roles, dict) else None
        installed = bool(route.get("installed")) if isinstance(route, dict) else False
        model_name = str(route.get("model") or "").strip() if isinstance(route, dict) else ""
        ready = (
            (not llm_enabled)
            or provider_status == "configured"
            or (provider_status == "online" and installed)
        )
        role_readiness[role_name] = ready
        if llm_enabled and provider_status == "online" and model_name and not installed:
            missing_models.append(f"{role_name}:{model_name}")

    reasons: list[str] = []
    state = "ready"
    if not llm_enabled:
        state = "disabled"
        reasons.append("llm_disabled")
    elif provider_status == "not_configured":
        state = "not_configured"
        reasons.append("provider_not_configured")
    elif provider_status == "unsupported":
        state = "unsupported"
        reasons.append("provider_unsupported")
    elif provider_status == "offline":
        state = "offline"
        reasons.append("provider_offline")
        if provider_error_code:
            reasons.append(f"provider_error:{provider_error_code}")
    elif missing_models:
        state = "degraded"
        reasons.extend([f"missing_model:{item}" for item in missing_models])

    ready = state in {"ready", "configured"}
    if state == "ready" and llm_enabled and provider_status == "configured":
        state = "configured"

    return {
        "state": state,
        "ready": ready,
        "can_suggest": ready,
        "can_get_prepared_draft": ready,
        "can_record_outcome": True,
        "can_ingest_memory_event": True,
        "can_register_document": True,
        "role_readiness": role_readiness,
        "reasons": reasons,
    }


def _structured_cli_error_payload(
    exc: Exception,
    *,
    argv: list[str] | None = None,
) -> dict[str, Any]:
    command = str(argv[0]) if argv else None
    adapter_name = None
    if argv:
        for index, value in enumerate(argv):
            if value == "--adapter" and index + 1 < len(argv):
                adapter_name = str(argv[index + 1])
                break
    error_type = type(exc).__name__
    if isinstance(exc, UnsupportedModelProviderError):
        code = "unsupported_model_provider"
    elif isinstance(exc, TrainClientError):
        code = f"train_{exc.code}"
    elif isinstance(exc, ValueError):
        code = "invalid_request"
    elif isinstance(exc, RuntimeError):
        code = "runtime_error"
    else:
        code = "internal_error"
    return {
        "ok": False,
        "contract_version": CLI_CONTRACT_VERSION,
        "error_schema_version": CLI_ERROR_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "error": {
            "code": code,
            "type": error_type,
            "message": str(exc),
            "command": command,
            "adapter": adapter_name,
        },
    }


def run_cli(argv: list[str] | None = None) -> int:
    try:
        return main(argv)
    except Exception as exc:  # pragma: no cover - exercised via tests on stderr
        payload = _structured_cli_error_payload(exc, argv=argv)
        json.dump(payload, sys.stderr, indent=2, sort_keys=True)
        sys.stderr.write("\n")
        return 2 if payload["error"]["code"] != "internal_error" else 1


def _resolve_holdout_requirement(args: Any) -> bool:
    if bool(getattr(args, "allow_no_holdout", False)):
        return False
    return True or bool(getattr(args, "require_holdout", False))


def _policy_review_surface_payload(result: Any) -> dict[str, Any]:
    review_payload = dataclass_payload(result)
    policy_payload = review_payload["policy"]
    scope_kind = str(policy_payload["scope_kind"])
    scope_value = policy_payload.get("scope_value")
    return {
        "ready_for_acceptance": bool(result.ready_for_acceptance),
        "recommended_action": ("accept" if result.ready_for_acceptance else "revise_or_reject"),
        "review_decision_id": result.review_decision_id,
        "acceptance_mode": result.acceptance_mode,
        "holdout_required": bool(result.holdout_required),
        "holdout_bundle_count": int(result.holdout_bundle_count),
        "scope": {
            "kind": scope_kind,
            "value": scope_value,
        },
        "candidate_policy": {
            "artifact_key": policy_payload["artifact_key"],
            "version": policy_payload["version"],
            "source_project": policy_payload["source_project"],
            "contract_version": policy_payload["contract_version"],
        },
        "incumbent_policy_version": result.incumbent_policy_version,
        "train_provenance": {
            "project_key": result.source_train_project_key,
            "run_id": result.source_train_run_id,
        },
        "scores": {
            "candidate": result.candidate_score,
            "incumbent": result.incumbent_score,
            "proposal_delta": result.regression_delta,
            "holdout_candidate": result.holdout_candidate_score,
            "holdout_incumbent": result.holdout_incumbent_score,
            "holdout_delta": result.holdout_regression_delta,
        },
        "skeptical_notes": list(result.skeptical_notes),
        "reason": result.reason,
        "review": review_payload,
    }


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware.")
    return parsed


def _require_reply_adapter(adapter_name: str, command: str) -> None:
    if adapter_name != REPLY_ADAPTER_NAME:
        raise ValueError(
            f"{command} is currently implemented only for the reply adapter. "
            "Use --adapter reply for policy, Train, and shadow-fixture workflows."
        )


if __name__ == "__main__":
    raise SystemExit(run_cli(sys.argv[1:]))
