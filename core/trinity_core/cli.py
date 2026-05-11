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

from trinity_core.adapters import REPLY_ADAPTER_NAME, require_supported_adapter
from trinity_core.adapters.model import UnsupportedModelProviderError
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
    save_model_config_for_adapter,
)
from trinity_core.ops import (
    AcceptedArtifactRegistry,
    ControlPlaneStore,
    GobiiAgentClient,
    GobiiNormalizationError,
    GobiiTaskClient,
    GobiiTaskClientError,
    accept_reply_behavior_policy,
    accept_spot_review_policy,
    build_eval_dataset,
    build_gobii_tracked_entity_enrichment_bundle,
    build_gobii_workflow_bundle,
    curate_eval_case_from_trace_payload,
    current_config_route_set,
    default_train_proposal_paths,
    default_train_spot_proposal_paths,
    deterministic_route_set,
    gobii_task_normalization_request_from_payload,
    load_control_plane_job,
    load_eval_dataset,
    load_gobii_tracked_entity_enrichment_bundle,
    load_gobii_workflow_bundle,
    load_persisted_gobii_task_record,
    load_provider_route_sets,
    load_reply_shadow_fixtures,
    load_spot_review_policy_file,
    make_prepared_draft_refresh_job,
    make_provider_comparison_job,
    merge_eval_dataset_cases,
    merge_gobii_task_context,
    normalize_gobii_task_output,
    normalize_gobii_tracked_entity_enrichment_bundle,
    persist_eval_dataset,
    persist_gobii_task_record,
    persist_gobii_tracked_entity_enrichment_bundle,
    persist_gobii_workflow_bundle,
    persist_reply_policy_review_result,
    propose_reply_policy_with_train,
    propose_spot_review_policy_with_train,
    register_gobii_workflow_bundle,
    replay_reply_eval_dataset,
    review_reply_behavior_policy,
    review_spot_review_policy,
    run_control_plane_job,
    run_reply_provider_comparison_from_fixture_dir,
    run_reply_shadow_fixtures,
    schedule_prepared_draft_refresh_jobs,
    shadow_fixture_payload,
    submit_gobii_tracked_entity_enrichment_bundle,
    summarize_eval_replay_report,
    summarize_reply_shadow_results,
)
from trinity_core.ops.cycle_store import RuntimeCycleStore, dataclass_payload
from trinity_core.ops.spot_policy_store import SpotPolicyStore
from trinity_core.reply_runtime import training_bundle_type_from_payload
from trinity_core.runtime import TrinityRuntime
from trinity_core.schemas import (
    AcceptedArtifactVersion,
    GobiiTaskCreateRequest,
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trinity")
    subparsers = parser.add_subparsers(dest="command", required=True)

    _build_generic_parsers(subparsers)
    _build_reply_compat_parsers(subparsers)

    args = parser.parse_args(argv)
    command = COMMAND_ALIASES.get(args.command, args.command)
    adapter_name = require_supported_adapter(getattr(args, "adapter", REPLY_ADAPTER_NAME))
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

    if command == "record-spot-review-outcome":
        _require_spot_adapter(adapter_name, command)
        payload = _load_json(args.input_file)
        result = get_runtime().record_spot_review_outcome(
            spot_review_outcome_from_payload(payload)
        )
        _write_json(result)
        return 0

    if command == "ingest-memory-event":
        payload = _load_json(args.input_file)
        result = get_runtime().ingest_memory_event(memory_event_from_payload(payload))
        _write_json(result)
        return 0

    if command == "register-document":
        payload = _load_json(args.input_file)
        result = get_runtime().register_document(document_record_from_payload(payload))
        _write_json(result)
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
                skeptical_notes=tuple(args.skeptical_note),
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
                skeptical_notes=tuple(args.skeptical_note),
            )
        else:
            raise AssertionError(f"Unhandled adapter: {adapter_name}")
        _write_json(dataclass_payload(result))
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
        _write_json(_policy_review_surface_payload(result))
        return 0 if result.ready_for_acceptance else 2

    if command == "policy-promote":
        accepted_at = (
            _parse_datetime(args.accepted_at)
            if args.accepted_at
            else datetime.now(UTC)
        )
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
        _write_json(dataclass_payload(result))
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
        _write_json(
            {
                "artifact_key": str(args.artifact_key),
                "current": current,
                "history": [dataclass_payload(record) for record in history],
            }
        )
        return 0

    if command == "show-config":
        payload = dataclass_payload(load_model_config_for_adapter(adapter_name))
        if args.include_path:
            payload["config_path"] = str(config_path_for_adapter(adapter_name))
        _write_json(payload)
        return 0

    if command == "train-propose-policy":
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
                transport=str(args.transport),
                train_api_base_url=args.train_api_base_url,
                train_root_dir=args.train_root_dir,
                proposal_output_path=proposal_output_path,
                eval_output_path=eval_output_path,
            )
        elif adapter_name == "spot":
            train_result = propose_spot_review_policy_with_train(
                learner_kind=str(args.learner_kind),
                bundle_files=bundle_files,
                transport=str(args.transport),
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
            "transport": str(args.transport),
            "learner_kind": str(args.learner_kind),
            "bundle_files": bundle_files,
            "train_result": train_result,
        }
        if args.accept:
            require_holdout = _resolve_holdout_requirement(args)
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
                    skeptical_notes=tuple(args.skeptical_note),
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
                    skeptical_notes=tuple(args.skeptical_note),
                )
            else:
                raise AssertionError(f"Unhandled adapter: {adapter_name}")
            payload["acceptance_result"] = dataclass_payload(acceptance)
            _write_json(payload)
            return 0 if acceptance.accepted else 2
        _write_json(payload)
        return 0

    if command == "runtime-status":
        config = load_model_config_for_adapter(adapter_name)
        payload = {
            "config_path": str(config_path_for_adapter(adapter_name)),
            "adapter": adapter_name,
            "provider": config.provider,
            "llm_enabled": config.llm_enabled,
            "ollama_base_url": config.ollama_base_url,
            "mistral_cli_executable": config.mistral_cli_executable,
            "mistral_cli_args": list(config.mistral_cli_args),
            "mistral_cli_mode": config.mistral_cli_mode,
            "mistral_cli_model_binding": config.mistral_cli_model_binding,
            "timeout_seconds": config.timeout_seconds,
            "provider_status": "not_configured",
            "provider_error": None,
            "available_models": [],
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
                payload["provider_status"] = (
                    "online"
                    if provider_runtime.model_provider.supports_model_inventory
                    else "configured"
                )
                payload["available_models"] = list(models)
                for role_name, route in (
                    ("generator", config.generator),
                    ("refiner", config.refiner),
                    ("evaluator", config.evaluator),
                ):
                    payload["roles"][role_name] = {
                        **dataclass_payload(route),
                        "installed": route.model in installed_names,
                    }
            except UnsupportedModelProviderError as exc:
                payload["provider_status"] = "unsupported"
                payload["provider_error"] = str(exc)
                for role_name, route in (
                    ("generator", config.generator),
                    ("refiner", config.refiner),
                    ("evaluator", config.evaluator),
                ):
                    payload["roles"][role_name] = {
                        **dataclass_payload(route),
                        "installed": False,
                    }
            except Exception as exc:
                payload["provider_status"] = "offline"
                payload["provider_error"] = str(exc)
                for role_name, route in (
                    ("generator", config.generator),
                    ("refiner", config.refiner),
                    ("evaluator", config.evaluator),
                ):
                    payload["roles"][role_name] = {
                        **dataclass_payload(route),
                        "installed": False,
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
                }
        _write_json(payload)
        return 0

    if command == "write-config":
        current = load_model_config_for_adapter(adapter_name)
        updated_provider = str(args.provider or current.provider)
        updated = TrinityModelConfig(
            provider=updated_provider,
            ollama_base_url=str(args.ollama_base_url or current.ollama_base_url),
            mistral_cli_executable=str(
                args.mistral_cli_executable or current.mistral_cli_executable
            ),
            mistral_cli_args=tuple(
                args.mistral_cli_arg
                if args.mistral_cli_arg
                else current.mistral_cli_args
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
            ),
            refiner=TrinityRoleRoute(
                provider=updated_provider,
                model=str(args.refiner_model or current.refiner.model),
                temperature=current.refiner.temperature,
                keep_alive=current.refiner.keep_alive,
            ),
            evaluator=TrinityRoleRoute(
                provider=updated_provider,
                model=str(args.evaluator_model or current.evaluator.model),
                temperature=current.evaluator.temperature,
                keep_alive=current.evaluator.keep_alive,
            ),
        )
        path = save_model_config_for_adapter(adapter_name, updated)
        payload = dataclass_payload(updated)
        payload["config_path"] = str(path)
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

    document_parser = subparsers.add_parser(
        "register-document",
        help="Register one product document with runtime-owned memory and retrieval state.",
    )
    _add_adapter_argument(document_parser)
    document_parser.add_argument("--input-file")

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

    bundle_parser = subparsers.add_parser(
        "export-training-bundle",
        help="Export one bounded training bundle from a recorded cycle.",
    )
    _add_adapter_argument(bundle_parser)
    bundle_parser.add_argument("--cycle-id", required=True)
    bundle_parser.add_argument("--bundle-type", required=True)

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
            "Normalize one persisted Gobii tracked-entity enrichment bundle "
            "into Trinity artifacts."
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
    train_parser.add_argument("--transport", choices=("api", "cli"), default="api")
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
            "Render a promotion-oriented review surface with acceptance mode "
            "and Train provenance."
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

    runtime_status_parser = subparsers.add_parser(
        "runtime-status",
        help="Show runtime model availability and adapter wiring status.",
    )
    _add_adapter_argument(runtime_status_parser)

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
    write_config_parser.add_argument("--refiner-model")
    write_config_parser.add_argument("--evaluator-model")


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
    train_parser.add_argument("--transport", choices=("api", "cli"), default="api")
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
    write_config_parser.add_argument("--refiner-model")
    write_config_parser.add_argument("--evaluator-model")


def _add_adapter_argument(parser: Any) -> None:
    parser.add_argument(
        "--adapter",
        default=REPLY_ADAPTER_NAME,
        help="Product adapter to use. Currently supported: reply, spot.",
    )


def _require_spot_adapter(adapter_name: str, command: str) -> None:
    if adapter_name != "spot":
        raise ValueError(f"{command} requires --adapter spot.")


def _load_json(input_file: str | None) -> dict[str, Any]:
    if input_file:
        with open(input_file, encoding="utf-8") as handle:
            return json.load(handle)
    return json.load(sys.stdin)


def _write_json(payload: dict[str, Any]) -> None:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


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
        "recommended_action": (
            "accept" if result.ready_for_acceptance else "revise_or_reject"
        ),
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
    raise SystemExit(main())
