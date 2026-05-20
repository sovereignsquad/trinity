from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from trinity_core.adapters.product.spot import SpotRuntime
from trinity_core.cli import main
from trinity_core.ops.cycle_store import RuntimeCyclePaths, RuntimeCycleStore
from trinity_core.reply_runtime import ReplyRuntime
from trinity_core.schemas import (
    SpotReasoningRequest,
    ThreadMessageRole,
    ThreadMessageSnapshot,
    ThreadSnapshot,
)


def _reply_snapshot() -> ThreadSnapshot:
    company_id = uuid4()
    return ThreadSnapshot(
        company_id=company_id,
        thread_ref="reply:email:test@example.com",
        channel="email",
        contact_handle="test@example.com",
        latest_inbound_text="Can you send the latest draft?",
        requested_at=datetime(2026, 5, 13, 8, 0, tzinfo=UTC),
        messages=(
            ThreadMessageSnapshot(
                message_id="msg-1",
                role=ThreadMessageRole.CONTACT,
                text="Can you send the latest draft?",
                occurred_at=datetime(2026, 5, 13, 7, 59, tzinfo=UTC),
                channel="email",
                source="email",
                handle="test@example.com",
            ),
        ),
    )


def test_reply_export_trace_public_contract(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    runtime = ReplyRuntime()
    ranked = runtime.suggest(_reply_snapshot())

    exit_code = main(
        [
            "export-trace",
            "--adapter",
            "reply",
            "--cycle-id",
            str(ranked.cycle_id),
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    trace = payload["trace"]

    assert exit_code == 0
    assert "runtime_score_audit" in trace
    assert "candidates" in trace
    assert "policy_resolution" in trace
    assert "model_route_details" in trace
    assert trace["runtime_score_audit"]["candidate_count"] >= 1
    assert "final_scores" in trace["runtime_score_audit"]["candidates"][0]
    assert "generator" in trace["model_route_details"]
    assert "model_id" in trace["model_route_details"]["generator"]


def test_spot_persisted_trace_public_contract(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    runtime = SpotRuntime(
        store=RuntimeCycleStore(
            RuntimeCyclePaths(
                adapter_name="spot",
                root_dir=tmp_path / "runtime",
                cycles_dir=tmp_path / "runtime" / "cycles",
                exports_dir=tmp_path / "runtime" / "exports",
            )
        )
    )
    runtime.store.paths.cycles_dir.mkdir(parents=True, exist_ok=True)
    runtime.store.paths.exports_dir.mkdir(parents=True, exist_ok=True)
    result = runtime.reason_spot(
        SpotReasoningRequest(
            company_id=uuid4(),
            run_id="run-public-contract",
            row_ref="sheet1:99",
            language="en",
            message_text="We should threaten them tonight.",
            occurred_at=datetime(2026, 5, 13, 8, 0, tzinfo=UTC),
        )
    )

    payload = json.loads(Path(str(result.trace_ref)).read_text(encoding="utf-8"))
    candidate = payload["spot_reasoning_result"]["candidates"][0]

    assert payload["spot_reasoning_result"]["candidate_count"] >= 1
    assert {"impact", "confidence", "ease", "ice_score", "priority_score"} <= set(candidate)
    assert "runtime_memory_context" in payload
    assert "runtime_loop_decision" in payload


def test_runtime_status_public_contract(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.setenv("TRINITY_MODEL_CONFIG_PATH", str(tmp_path / "config.json"))

    exit_code = main(["runtime-status", "--adapter", "reply"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["contract_version"] == "trinity_cli.v1"
    assert payload["status_schema_version"] == 5
    assert payload["command"] == "runtime-status"
    assert "generated_at" in payload
    assert "shared_model_inventory" in payload
    assert "inventory_status" in payload["roles"]["generator"]
    assert "readiness" in payload
    assert {"ready", "state", "can_suggest", "can_get_prepared_draft"} <= set(payload["readiness"])
