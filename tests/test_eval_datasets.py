from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from trinity_core.cli import main
from trinity_core.ops.cycle_store import RuntimeCyclePaths, RuntimeCycleStore
from trinity_core.ops.eval_datasets import (
    build_eval_dataset,
    curate_eval_case_from_trace_payload,
    load_eval_dataset,
    merge_eval_dataset_cases,
    persist_eval_dataset,
    replay_reply_eval_dataset,
    summarize_eval_replay_report,
)
from trinity_core.reply_runtime import ReplyRuntime
from trinity_core.schemas import (
    DraftOutcomeDisposition,
    DraftOutcomeEvent,
    ThreadMessageRole,
    ThreadMessageSnapshot,
    ThreadSnapshot,
)


def _runtime(tmp_path: Path) -> ReplyRuntime:
    store = RuntimeCycleStore(
        RuntimeCyclePaths(
            adapter_name="reply",
            root_dir=tmp_path / "runtime",
            cycles_dir=tmp_path / "runtime" / "cycles",
            exports_dir=tmp_path / "runtime" / "exports",
        )
    )
    store.paths.cycles_dir.mkdir(parents=True, exist_ok=True)
    store.paths.exports_dir.mkdir(parents=True, exist_ok=True)
    return ReplyRuntime(store=store)


def _thread_snapshot() -> ThreadSnapshot:
    company_id = UUID("11111111-1111-5111-8111-111111111111")
    return ThreadSnapshot(
        company_id=company_id,
        thread_ref="reply:email:alice@example.com",
        channel="email",
        contact_handle="alice@example.com",
        latest_inbound_text="Can you send the updated numbers today?",
        requested_at=datetime(2026, 5, 11, 6, 0, tzinfo=UTC),
        messages=(
            ThreadMessageSnapshot(
                message_id="msg-1",
                role=ThreadMessageRole.CONTACT,
                text="Can you send the updated numbers today?",
                occurred_at=datetime(2026, 5, 11, 5, 59, tzinfo=UTC),
                channel="email",
                source="email",
                handle="alice@example.com",
            ),
        ),
    )


def _record_outcome(runtime: ReplyRuntime, snapshot: ThreadSnapshot) -> dict[str, object]:
    ranked = runtime.suggest(snapshot)
    outcome = DraftOutcomeEvent(
        company_id=snapshot.company_id,
        cycle_id=ranked.cycle_id,
        thread_ref=snapshot.thread_ref,
        channel=snapshot.channel,
        candidate_id=ranked.drafts[0].candidate_id,
        disposition=DraftOutcomeDisposition.SENT_AS_IS,
        occurred_at=datetime(2026, 5, 11, 6, 1, tzinfo=UTC),
        original_draft_text=ranked.drafts[0].draft_text,
        final_text=ranked.drafts[0].draft_text,
        edit_distance=0.0,
        latency_ms=1000,
        send_result="ok",
    )
    runtime.record_outcome(outcome)
    return runtime.store.load_cycle(ranked.cycle_id)


def test_curate_eval_dataset_from_runtime_trace_and_replay(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    payload = _record_outcome(runtime, _thread_snapshot())

    case = curate_eval_case_from_trace_payload(
        "reply",
        payload,
        selection_reason="high-signal production trace",
    )
    dataset = build_eval_dataset(
        dataset_name="Reply Production Trace Goldens",
        adapter_name="reply",
        cases=(case,),
    )
    dataset = merge_eval_dataset_cases(dataset, (case,))
    dataset_path = persist_eval_dataset(dataset)
    loaded = load_eval_dataset(dataset_path)

    assert len(loaded.cases) == 1
    assert loaded.cases[0].selection_reason == "high-signal production trace"
    assert loaded.cases[0].expected_disposition == DraftOutcomeDisposition.SENT_AS_IS.value

    report, report_path = replay_reply_eval_dataset(loaded, runtime=_runtime(tmp_path / "replay"))

    assert report_path.exists()
    assert len(report.case_results) == 1
    assert report.case_results[0].same_text is True
    summary = summarize_eval_replay_report(report)
    assert summary["case_count"] == 1
    assert summary["exact_match_count"] == 1


def test_curate_and_replay_eval_dataset_cli(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    runtime = ReplyRuntime()
    payload = _record_outcome(runtime, _thread_snapshot())
    cycle_id = str(payload["cycle_id"])

    exit_code = main(
        [
            "curate-eval-dataset",
            "--adapter",
            "reply",
            "--dataset-name",
            "Reply Production Trace Goldens",
            "--cycle-id",
            cycle_id,
            "--selection-reason",
            "human-reviewed gold trace",
        ]
    )
    curated = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    dataset_path = Path(curated["dataset_path"])
    assert dataset_path.exists()
    assert curated["dataset"]["cases"][0]["curated_from_cycle_id"] == cycle_id

    exit_code = main(
        [
            "replay-eval-dataset",
            "--dataset-file",
            str(dataset_path),
        ]
    )
    replayed = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert Path(replayed["report_path"]).exists()
    assert replayed["summary"]["case_count"] == 1
