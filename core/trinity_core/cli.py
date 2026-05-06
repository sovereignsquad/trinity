"""Local CLI entrypoints for adapter-aware Trinity runtime operations."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from trinity_core.adapters import REPLY_ADAPTER_NAME, require_supported_adapter
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
    load_reply_shadow_fixtures,
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
    "reply-policy-accept": "policy-accept",
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
        result = runtime.suggest(thread_snapshot_from_payload(payload))
        _write_json(dataclass_payload(result))
        return 0

    if command == "record-outcome":
        payload = _load_json(args.input_file)
        result = runtime.record_outcome(outcome_event_from_payload(payload))
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
        result = accept_reply_behavior_policy(
            args.policy_file,
            bundle_files=list(args.bundle_file),
            regression_threshold=float(args.regression_threshold),
            reason=args.reason,
        )
        _write_json(dataclass_payload(result))
        return 0 if result.accepted else 2

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

    accept_parser = subparsers.add_parser(
        "policy-accept",
        help="Validate and accept one adapter policy artifact against training bundles.",
    )
    _add_adapter_argument(accept_parser)
    accept_parser.add_argument("--policy-file", required=True)
    accept_parser.add_argument("--bundle-file", action="append", required=True)
    accept_parser.add_argument("--regression-threshold", type=float, default=0.0)
    accept_parser.add_argument("--reason")

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

    accept_parser = subparsers.add_parser("reply-policy-accept")
    accept_parser.add_argument("--policy-file", required=True)
    accept_parser.add_argument("--bundle-file", action="append", required=True)
    accept_parser.add_argument("--regression-threshold", type=float, default=0.0)
    accept_parser.add_argument("--reason")

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
        help="Product adapter to use. Currently supported: reply.",
    )


def _load_json(input_file: str | None) -> dict[str, Any]:
    if input_file:
        with open(input_file, encoding="utf-8") as handle:
            return json.load(handle)
    return json.load(sys.stdin)


def _write_json(payload: dict[str, Any]) -> None:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware.")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
