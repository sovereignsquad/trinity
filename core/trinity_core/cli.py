"""Local CLI entrypoints for the Reply/Trinity integration spine."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from uuid import UUID

from trinity_core.model_config import (
    TrinityReplyModelConfig,
    TrinityRoleRoute,
    config_path,
    load_reply_model_config,
    save_reply_model_config,
)
from trinity_core.ops.cycle_store import dataclass_payload
from trinity_core.reply_runtime import (
    ReplyRuntime,
    outcome_event_from_payload,
    thread_snapshot_from_payload,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trinity-reply-runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)

    suggest_parser = subparsers.add_parser("reply-suggest")
    suggest_parser.add_argument("--input-file")

    outcome_parser = subparsers.add_parser("reply-record-outcome")
    outcome_parser.add_argument("--input-file")

    export_parser = subparsers.add_parser("reply-export-trace")
    export_parser.add_argument("--cycle-id", required=True)

    show_config_parser = subparsers.add_parser("reply-show-config")
    show_config_parser.add_argument("--include-path", action="store_true")

    write_config_parser = subparsers.add_parser("reply-write-config")
    write_config_parser.add_argument("--provider")
    write_config_parser.add_argument("--ollama-base-url")
    write_config_parser.add_argument("--timeout-seconds", type=float)
    write_config_parser.add_argument("--generator-model")
    write_config_parser.add_argument("--refiner-model")
    write_config_parser.add_argument("--evaluator-model")

    args = parser.parse_args(argv)
    runtime = ReplyRuntime()

    if args.command == "reply-suggest":
        payload = _load_json(args.input_file)
        result = runtime.suggest(thread_snapshot_from_payload(payload))
        _write_json(dataclass_payload(result))
        return 0

    if args.command == "reply-record-outcome":
        payload = _load_json(args.input_file)
        result = runtime.record_outcome(outcome_event_from_payload(payload))
        _write_json(result)
        return 0

    if args.command == "reply-export-trace":
        result = runtime.export_trace(UUID(args.cycle_id))
        _write_json(result)
        return 0

    if args.command == "reply-show-config":
        payload = dataclass_payload(load_reply_model_config())
        if args.include_path:
            payload["config_path"] = str(config_path())
        _write_json(payload)
        return 0

    if args.command == "reply-write-config":
        current = load_reply_model_config()
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
        path = save_reply_model_config(updated)
        payload = dataclass_payload(updated)
        payload["config_path"] = str(path)
        _write_json(payload)
        return 0

    raise AssertionError("Unhandled command.")


def _load_json(input_file: str | None) -> dict[str, Any]:
    if input_file:
        with open(input_file, encoding="utf-8") as handle:
            return json.load(handle)
    return json.load(sys.stdin)


def _write_json(payload: dict[str, Any]) -> None:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
