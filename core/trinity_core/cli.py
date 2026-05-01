"""Local CLI entrypoints for the Reply/Trinity integration spine."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from uuid import UUID

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
