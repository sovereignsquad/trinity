"""Local CLI entrypoints for adapter-aware Trinity runtime operations."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from trinity_core.adapters import IMPACT_ADAPTER_NAME, REPLY_ADAPTER_NAME, require_supported_adapter
from trinity_core.impact_runtime import (
    impact_outcome_event_from_payload,
    impact_profile_snapshot_from_payload,
)
from trinity_core.model_config import (
    TrinityReplyModelConfig,
    TrinityRoleRoute,
    config_path_for_adapter,
    load_model_config_for_adapter,
    save_model_config_for_adapter,
)
from trinity_core.ops import (
    AcceptedArtifactRegistry,
    accept_reply_behavior_policy,
    default_train_proposal_paths,
    load_reply_shadow_fixtures,
    persist_reply_policy_review_result,
    propose_reply_policy_with_train,
    review_reply_behavior_policy,
    run_reply_shadow_fixtures,
    shadow_fixture_payload,
    summarize_reply_shadow_results,
)
from trinity_core.ops.cycle_store import dataclass_payload
from trinity_core.reply_runtime import (
    outcome_event_from_payload,
    thread_snapshot_from_payload,
    training_bundle_type_from_payload,
)
from trinity_core.runtime import TrinityRuntime
from trinity_core.schemas import AcceptedArtifactVersion

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
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trinity")
    subparsers = parser.add_subparsers(dest="command", required=True)

    _build_generic_parsers(subparsers)
    _build_reply_compat_parsers(subparsers)

    args = parser.parse_args(argv)
    command = COMMAND_ALIASES.get(args.command, args.command)
    adapter_name = require_supported_adapter(getattr(args, "adapter", REPLY_ADAPTER_NAME))
    runtime = TrinityRuntime(adapter_name=adapter_name)
    registry = AcceptedArtifactRegistry(adapter_name=adapter_name)

    if command == "suggest":
        payload = _load_json(args.input_file)
        result = runtime.suggest(_load_snapshot_for_adapter(adapter_name, payload))
        _write_json(dataclass_payload(result))
        return 0

    if command == "record-outcome":
        payload = _load_json(args.input_file)
        result = runtime.record_outcome(_load_outcome_for_adapter(adapter_name, payload))
        _write_json(result)
        return 0

    if command == "export-trace":
        result = runtime.export_trace(UUID(args.cycle_id))
        _write_json(result)
        return 0

    if command == "export-training-bundle":
        result = runtime.export_training_bundle(
            UUID(args.cycle_id),
            bundle_type=training_bundle_type_from_payload(args.bundle_type),
        )
        _write_json(result)
        return 0

    if command == "run-shadow-fixtures":
        _require_reply_adapter(adapter_name, command)
        fixture_dir = args.fixture_dir or str(
            Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "reply_shadow"
        )
        fixtures = load_reply_shadow_fixtures(fixture_dir)
        results = run_reply_shadow_fixtures(runtime._runtime, fixtures)
        _write_json(
            {
                "fixture_dir": fixture_dir,
                "results": [shadow_fixture_payload(result) for result in results],
                "summary": summarize_reply_shadow_results(results),
            }
        )
        return 0

    if command == "policy-accept":
        _require_reply_adapter(adapter_name, command)
        require_holdout = _resolve_holdout_requirement(args)
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
        _write_json(dataclass_payload(result))
        return 0 if result.accepted else 2

    if command == "policy-review":
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
        _require_reply_adapter(adapter_name, command)
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
        result = registry.promote(artifact, reason=args.reason, promoted_at=accepted_at)
        _write_json(dataclass_payload(result))
        return 0

    if command == "policy-rollback":
        _require_reply_adapter(adapter_name, command)
        result = registry.rollback(
            str(args.artifact_key),
            target_version=args.target_version,
            reason=args.reason,
            promoted_at=datetime.now(UTC),
        )
        _write_json(dataclass_payload(result))
        return 0

    if command == "policy-status":
        _require_reply_adapter(adapter_name, command)
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
        _require_reply_adapter(adapter_name, command)
        bundle_files = list(args.bundle_file or [])
        if args.cycle_id and not args.bundle_type:
            raise ValueError("--bundle-type is required when using --cycle-id.")
        for cycle_id in list(args.cycle_id or []):
            exported = runtime.export_training_bundle(
                UUID(cycle_id),
                bundle_type=training_bundle_type_from_payload(args.bundle_type),
            )
            bundle_files.append(exported["bundle_path"])
        if not bundle_files:
            raise ValueError("At least one --cycle-id or --bundle-file is required.")
        proposal_output_path = args.proposal_output_path
        eval_output_path = args.eval_output_path
        if not proposal_output_path or not eval_output_path:
            default_proposal_path, default_eval_path = default_train_proposal_paths(
                adapter_name=adapter_name,
                learner_kind=str(args.learner_kind),
            )
            proposal_output_path = proposal_output_path or str(default_proposal_path)
            eval_output_path = eval_output_path or str(default_eval_path)
        train_result = propose_reply_policy_with_train(
            learner_kind=str(args.learner_kind),
            bundle_files=bundle_files,
            transport=str(args.transport),
            train_api_base_url=args.train_api_base_url,
            train_root_dir=args.train_root_dir,
            proposal_output_path=proposal_output_path,
            eval_output_path=eval_output_path,
        )
        payload = {
            "adapter": adapter_name,
            "transport": str(args.transport),
            "learner_kind": str(args.learner_kind),
            "bundle_files": bundle_files,
            "train_result": train_result,
        }
        if args.accept:
            require_holdout = _resolve_holdout_requirement(args)
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
                models = runtime.ollama_client.list_models()
                installed_names = {str(item.get("name") or "").strip() for item in models}
                payload["provider_status"] = "online"
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
        updated = TrinityReplyModelConfig(
            provider=str(args.provider or current.provider),
            ollama_base_url=str(args.ollama_base_url or current.ollama_base_url),
            timeout_seconds=float(args.timeout_seconds or current.timeout_seconds),
            generator=TrinityRoleRoute(
                provider=current.generator.provider,
                model=str(args.generator_model or current.generator.model),
                temperature=current.generator.temperature,
                keep_alive=current.generator.keep_alive,
            ),
            refiner=TrinityRoleRoute(
                provider=current.refiner.provider,
                model=str(args.refiner_model or current.refiner.model),
                temperature=current.refiner.temperature,
                keep_alive=current.refiner.keep_alive,
            ),
            evaluator=TrinityRoleRoute(
                provider=current.evaluator.provider,
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

    outcome_parser = subparsers.add_parser(
        "record-outcome",
        help="Persist one operator outcome event for a prior runtime cycle.",
    )
    _add_adapter_argument(outcome_parser)
    outcome_parser.add_argument("--input-file")

    export_parser = subparsers.add_parser(
        "export-trace",
        help="Export one persisted runtime trace by cycle id.",
    )
    _add_adapter_argument(export_parser)
    export_parser.add_argument("--cycle-id", required=True)

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
    write_config_parser.add_argument("--timeout-seconds", type=float)
    write_config_parser.add_argument("--generator-model")
    write_config_parser.add_argument("--refiner-model")
    write_config_parser.add_argument("--evaluator-model")


def _build_reply_compat_parsers(subparsers: Any) -> None:
    suggest_parser = subparsers.add_parser("reply-suggest")
    suggest_parser.add_argument("--input-file")

    outcome_parser = subparsers.add_parser("reply-record-outcome")
    outcome_parser.add_argument("--input-file")

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
    write_config_parser.add_argument("--timeout-seconds", type=float)
    write_config_parser.add_argument("--generator-model")
    write_config_parser.add_argument("--refiner-model")
    write_config_parser.add_argument("--evaluator-model")


def _add_adapter_argument(parser: Any) -> None:
    parser.add_argument(
        "--adapter",
        default=REPLY_ADAPTER_NAME,
        help="Product adapter to use. Currently supported: reply, impact.",
    )


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


def _load_snapshot_for_adapter(adapter_name: str, payload: dict[str, Any]) -> Any:
    if adapter_name == REPLY_ADAPTER_NAME:
        return thread_snapshot_from_payload(payload)
    if adapter_name == IMPACT_ADAPTER_NAME:
        return impact_profile_snapshot_from_payload(payload)
    raise AssertionError(f"Unhandled adapter snapshot loader: {adapter_name}")


def _load_outcome_for_adapter(adapter_name: str, payload: dict[str, Any]) -> Any:
    if adapter_name == REPLY_ADAPTER_NAME:
        return outcome_event_from_payload(payload)
    if adapter_name == IMPACT_ADAPTER_NAME:
        return impact_outcome_event_from_payload(payload)
    raise AssertionError(f"Unhandled adapter outcome loader: {adapter_name}")


def _require_reply_adapter(adapter_name: str, command: str) -> None:
    if adapter_name != REPLY_ADAPTER_NAME:
        raise ValueError(
            f"{command} is currently implemented only for the reply adapter. "
            "Use --adapter reply for policy, Train, and shadow-fixture workflows."
        )


if __name__ == "__main__":
    raise SystemExit(main())
