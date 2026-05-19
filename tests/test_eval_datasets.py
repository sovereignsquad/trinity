from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from trinity_core.cli import main
from trinity_core.ops.cycle_store import RuntimeCyclePaths, RuntimeCycleStore
from trinity_core.ops.eval_datasets import (
    build_cross_adapter_score_report,
    build_eval_dataset,
    build_score_governance_dashboard_report,
    build_score_governance_release_report,
    build_score_governance_status_surface,
    build_score_governance_triage_report,
    build_score_health_report,
    compare_score_health_reports,
    curate_eval_case_from_trace_payload,
    evaluate_score_governance,
    load_eval_dataset,
    load_eval_replay_report,
    load_score_governance_release_decision,
    load_score_governance_release_report,
    load_score_governance_triage_report,
    load_score_governance_triage_resolution,
    load_score_health_report,
    load_score_health_review_decision,
    load_score_health_trend_report,
    make_score_governance_release_decision,
    make_score_governance_triage_resolution,
    make_score_health_review_decision,
    merge_eval_dataset_cases,
    persist_eval_dataset,
    persist_score_governance_release_decision,
    persist_score_governance_release_report,
    persist_score_governance_triage_report,
    persist_score_governance_triage_resolution,
    persist_score_health_report,
    persist_score_health_review_decision,
    persist_score_health_trend_report,
    replay_reply_eval_dataset,
    review_score_health_report,
    summarize_cross_adapter_score_report,
    summarize_eval_replay_report,
    summarize_score_governance_dashboard_report,
    summarize_score_governance_release_report,
    summarize_score_governance_status_surface,
    summarize_score_governance_triage_report,
    summarize_score_health_report,
    summarize_score_health_trend_report,
)
from trinity_core.ops.policy_registry import AcceptedArtifactRegistry, AcceptedArtifactRegistryPaths
from trinity_core.ops.runtime_storage import resolve_adapter_runtime_paths
from trinity_core.reply_runtime import ReplyRuntime
from trinity_core.schemas import (
    AcceptedArtifactVersion,
    DraftOutcomeDisposition,
    DraftOutcomeEvent,
    ScoreGovernancePolicy,
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


def _registry(tmp_path: Path) -> AcceptedArtifactRegistry:
    paths = AcceptedArtifactRegistryPaths(
        adapter_name="reply",
        root_dir=tmp_path / "accepted_artifacts",
        artifacts_dir=tmp_path / "accepted_artifacts" / "artifacts",
    )
    paths.root_dir.mkdir(parents=True, exist_ok=True)
    paths.artifacts_dir.mkdir(parents=True, exist_ok=True)
    return AcceptedArtifactRegistry(paths=paths)


def _write_spot_cycle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    adapter_paths = resolve_adapter_runtime_paths("spot")
    cycles_dir = adapter_paths.root_dir / "cycles"
    cycles_dir.mkdir(parents=True, exist_ok=True)
    cycle_path = cycles_dir / "spot-cycle.json"
    cycle_path.write_text(
        json.dumps(
            {
                "adapter_name": "spot",
                "cycle_id": "spot-cycle",
                "spot_reasoning_result": {
                    "candidates": [
                        {
                            "candidate_key": "spot-primary",
                            "interpretation": "Escalate for manual review",
                            "ice_score": 392,
                            "priority_score": 61.92,
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    return cycle_path


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


def test_build_score_health_report_from_trace_payloads(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    payload_one = _record_outcome(runtime, _thread_snapshot())
    payload_two = _record_outcome(runtime, _thread_snapshot())

    report = build_score_health_report(
        report_name="Reply Score Health",
        adapter_name="reply",
        trace_payloads=(payload_one, payload_two),
        metadata={"selection_reason": "manual review"},
    )
    report_path = persist_score_health_report("reply", report)

    assert report_path.exists()
    assert report.trace_count == 2
    assert report.candidate_count >= 2
    assert report.flagged_candidate_count >= 1
    assert report.flag_counts
    assert report.tuple_clusters
    summary = summarize_score_health_report(report)
    assert summary["trace_count"] == 2
    assert summary["flag_type_count"] >= 1
    assert summary["tuple_cluster_count"] >= 1


def test_review_score_health_report_with_replay_analytics(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    payload_one = _record_outcome(runtime, _thread_snapshot())
    payload_two = _record_outcome(runtime, _thread_snapshot())
    report = build_score_health_report(
        report_name="Reply Score Health",
        adapter_name="reply",
        trace_payloads=(payload_one, payload_two),
    )
    report_path = persist_score_health_report("reply", report)
    loaded_report = load_score_health_report(report_path)

    case = curate_eval_case_from_trace_payload(
        "reply",
        payload_one,
        selection_reason="high-signal production trace",
    )
    dataset = build_eval_dataset(
        dataset_name="Reply Production Trace Goldens",
        adapter_name="reply",
        cases=(case,),
    )
    replay_report, replay_report_path = replay_reply_eval_dataset(
        dataset,
        runtime=_runtime(tmp_path / "replay"),
    )
    loaded_replay_report = load_eval_replay_report(replay_report_path)

    review = review_score_health_report(
        loaded_report,
        replay_report=loaded_replay_report,
    )

    assert review["overview"]["trace_count"] == 2
    assert review["top_flags"]
    assert review["top_tuple_clusters"]
    assert review["triage_recommendations"]
    assert review["replay_analytics"]["case_count"] == len(replay_report.case_results)
    assert review["replay_analytics"]["quality_risk"] in {"low", "medium", "high", "unknown"}


def test_make_and_persist_score_health_review_decision(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    payload = _record_outcome(runtime, _thread_snapshot())
    report = build_score_health_report(
        report_name="Reply Score Health",
        adapter_name="reply",
        trace_payloads=(payload,),
    )
    replay_case = curate_eval_case_from_trace_payload(
        "reply",
        payload,
        selection_reason="high-signal production trace",
    )
    replay_dataset = build_eval_dataset(
        dataset_name="Reply Production Trace Goldens",
        adapter_name="reply",
        cases=(replay_case,),
    )
    replay_report, _ = replay_reply_eval_dataset(
        replay_dataset,
        runtime=_runtime(tmp_path / "replay"),
    )

    decision = make_score_health_review_decision(
        report,
        status="investigate",
        notes="Repeated clustering needs inspection.",
        replay_report=replay_report,
    )
    decision_path = persist_score_health_review_decision("reply", decision)
    loaded_decision = load_score_health_review_decision(decision_path)

    assert decision_path.exists()
    assert loaded_decision.status == "investigate"
    assert loaded_decision.replay_report_dataset_id == replay_report.dataset_id


def test_compare_score_health_reports_builds_trend_report(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    payload_one = _record_outcome(runtime, _thread_snapshot())
    payload_two = _record_outcome(runtime, _thread_snapshot())
    report_one = build_score_health_report(
        report_name="Reply Score Health One",
        adapter_name="reply",
        trace_payloads=(payload_one,),
    )
    report_two = build_score_health_report(
        report_name="Reply Score Health Two",
        adapter_name="reply",
        trace_payloads=(payload_one, payload_two),
    )

    trend_report = compare_score_health_reports(
        (report_one, report_two),
        trend_report_name="Reply Score Health Trend",
    )

    assert trend_report.compared_report_count == 2
    assert trend_report.report_ids == (report_one.report_id, report_two.report_id)
    summary = summarize_score_health_trend_report(trend_report)
    assert summary["compared_report_count"] == 2
    assert summary["recurring_tuple_cluster_count"] >= 0


def test_evaluate_score_governance_blocks_investigate_decision(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    payload = _record_outcome(runtime, _thread_snapshot())
    report = build_score_health_report(
        report_name="Reply Score Health",
        adapter_name="reply",
        trace_payloads=(payload,),
    )
    decision = make_score_health_review_decision(
        report,
        status="investigate",
        notes="Needs follow-up.",
    )

    governance = evaluate_score_governance(report, decision=decision)

    assert governance.allowed is False
    assert governance.override_required is True
    assert governance.decision_status == "investigate"
    assert governance.blocking_reasons


def test_evaluate_score_governance_blocks_threshold_breaches(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    payload_one = _record_outcome(runtime, _thread_snapshot())
    payload_two = _record_outcome(runtime, _thread_snapshot())
    report_one = build_score_health_report(
        report_name="Reply Score Health One",
        adapter_name="reply",
        trace_payloads=(payload_one,),
    )
    report_two = build_score_health_report(
        report_name="Reply Score Health Two",
        adapter_name="reply",
        trace_payloads=(payload_one, payload_two),
    )
    trend_report = compare_score_health_reports(
        (report_one, report_two),
        trend_report_name="Reply Score Health Trend",
    )

    governance = evaluate_score_governance(
        report_two,
        trend_report=trend_report,
        policy=ScoreGovernancePolicy(
            persistent_flag_tolerance=0,
            recurring_tuple_cluster_tolerance=0,
        ),
    )

    assert governance.allowed is False
    assert governance.trend_report_id == trend_report.trend_report_id
    assert governance.blocking_reasons


def test_report_score_health_cli(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    runtime = ReplyRuntime()
    payload_one = _record_outcome(runtime, _thread_snapshot())
    payload_two = _record_outcome(runtime, _thread_snapshot())

    exit_code = main(
        [
            "report-score-health",
            "--adapter",
            "reply",
            "--report-name",
            "Reply Score Health",
            "--cycle-id",
            str(payload_one["cycle_id"]),
            "--cycle-id",
            str(payload_two["cycle_id"]),
            "--selection-reason",
            "manual governance review",
        ]
    )
    reported = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert Path(reported["report_path"]).exists()
    assert reported["summary"]["trace_count"] == 2
    assert reported["summary"]["tuple_cluster_count"] >= 1


def test_review_score_health_cli(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    runtime = ReplyRuntime()
    payload = _record_outcome(runtime, _thread_snapshot())

    exit_code = main(
        [
            "report-score-health",
            "--adapter",
            "reply",
            "--report-name",
            "Reply Score Health",
            "--cycle-id",
            str(payload["cycle_id"]),
        ]
    )
    reported = json.loads(capsys.readouterr().out)
    report_path = Path(reported["report_path"])

    case = curate_eval_case_from_trace_payload(
        "reply",
        payload,
        selection_reason="human-reviewed gold trace",
    )
    dataset = build_eval_dataset(
        dataset_name="Reply Production Trace Goldens",
        adapter_name="reply",
        cases=(case,),
    )
    replay_report, replay_report_path = replay_reply_eval_dataset(
        dataset,
        runtime=_runtime(tmp_path / "replay"),
    )

    assert exit_code == 0
    assert report_path.exists()
    assert replay_report.case_results

    exit_code = main(
        [
            "review-score-health",
            "--report-file",
            str(report_path),
            "--replay-report-file",
            str(replay_report_path),
        ]
    )
    reviewed = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert reviewed["review"]["overview"]["trace_count"] == 1
    assert reviewed["review"]["replay_analytics"]["case_count"] == 1


def test_review_score_health_cli_can_persist_decision(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    runtime = ReplyRuntime()
    payload = _record_outcome(runtime, _thread_snapshot())

    exit_code = main(
        [
            "report-score-health",
            "--adapter",
            "reply",
            "--report-name",
            "Reply Score Health",
            "--cycle-id",
            str(payload["cycle_id"]),
        ]
    )
    reported = json.loads(capsys.readouterr().out)
    report_path = Path(reported["report_path"])

    exit_code = main(
        [
            "review-score-health",
            "--report-file",
            str(report_path),
            "--decision-status",
            "investigate",
            "--decision-notes",
            "Follow up on recurring tuple clusters.",
        ]
    )
    reviewed = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert Path(reviewed["decision_path"]).exists()
    assert reviewed["decision"]["status"] == "investigate"


def test_compare_score_health_cli(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    runtime = ReplyRuntime()
    payload_one = _record_outcome(runtime, _thread_snapshot())
    payload_two = _record_outcome(runtime, _thread_snapshot())

    report_paths: list[str] = []
    for name, cycle_id in (
        ("Reply Score Health One", str(payload_one["cycle_id"])),
        ("Reply Score Health Two", str(payload_two["cycle_id"])),
    ):
        exit_code = main(
            [
                "report-score-health",
                "--adapter",
                "reply",
                "--report-name",
                name,
                "--cycle-id",
                cycle_id,
            ]
        )
        reported = json.loads(capsys.readouterr().out)
        assert exit_code == 0
        report_paths.append(reported["report_path"])

    exit_code = main(
        [
            "compare-score-health",
            "--trend-report-name",
            "Reply Score Health Trend",
            "--report-file",
            report_paths[0],
            "--report-file",
            report_paths[1],
            "--selection-reason",
            "manual trend review",
        ]
    )
    compared = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert Path(compared["trend_report_path"]).exists()
    assert compared["summary"]["compared_report_count"] == 2


def test_check_score_governance_cli(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    runtime = ReplyRuntime()
    payload = _record_outcome(runtime, _thread_snapshot())
    report = build_score_health_report(
        report_name="Reply Score Health",
        adapter_name="reply",
        trace_payloads=(payload,),
    )
    report_path = persist_score_health_report("reply", report)
    decision = make_score_health_review_decision(
        report,
        status="investigate",
        notes="Needs follow-up.",
    )
    decision_path = persist_score_health_review_decision("reply", decision)
    trend_report = compare_score_health_reports(
        (report,),
        trend_report_name="Reply Score Health Trend",
    )
    trend_report_path = persist_score_health_trend_report("reply", trend_report)

    loaded_trend = load_score_health_trend_report(trend_report_path)
    assert loaded_trend.trend_report_id == trend_report.trend_report_id

    exit_code = main(
        [
            "check-score-governance",
            "--report-file",
            str(report_path),
            "--decision-file",
            str(decision_path),
            "--trend-report-file",
            str(trend_report_path),
        ]
    )
    checked = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert checked["allowed"] is False
    assert checked["score_governance"]["decision_status"] == "investigate"


def test_build_and_persist_score_governance_release_report(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    payload = _record_outcome(runtime, _thread_snapshot())
    report = build_score_health_report(
        report_name="Reply Score Health",
        adapter_name="reply",
        trace_payloads=(payload,),
    )
    decision = make_score_health_review_decision(report, status="investigate")
    governance = evaluate_score_governance(report, decision=decision)
    release_report = build_score_governance_release_report(
        release_report_name="Reply Release Governance",
        report=report,
        governance=governance,
        decision=decision,
    )
    release_report_path = persist_score_governance_release_report("reply", release_report)
    loaded_release_report = load_score_governance_release_report(release_report_path)

    assert release_report_path.exists()
    assert loaded_release_report.allowed is False
    assert loaded_release_report.release_risk in {"high", "medium", "low"}
    summary = summarize_score_governance_release_report(loaded_release_report)
    assert summary["blocking_reason_count"] >= 1


def test_build_score_governance_triage_report_includes_decisions_trends_and_overrides(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    payload_one = _record_outcome(runtime, _thread_snapshot())
    payload_two = _record_outcome(runtime, _thread_snapshot())
    report_one = build_score_health_report(
        report_name="Reply Score Health One",
        adapter_name="reply",
        trace_payloads=(payload_one,),
    )
    report_two = build_score_health_report(
        report_name="Reply Score Health Two",
        adapter_name="reply",
        trace_payloads=(payload_one, payload_two),
    )
    decision = make_score_health_review_decision(report_one, status="investigate")
    trend_report = compare_score_health_reports(
        (report_one, report_two),
        trend_report_name="Reply Score Health Trend",
    )
    registry = _registry(tmp_path)
    registry.promote(
        AcceptedArtifactVersion(
            artifact_key="reply_behavior_policy",
            version="v2",
            source_project="train",
            accepted_at=datetime(2026, 5, 12, 9, 0, tzinfo=UTC),
        ),
        score_governance_status="override",
        score_governance_report_id=report_one.report_id,
        score_governance_decision_id=decision.decision_id,
        score_governance_trend_report_id=trend_report.trend_report_id,
        score_governance_override_notes=("approved temporary exception",),
    )
    triage_report = build_score_governance_triage_report(
        triage_report_name="Reply Governance Triage",
        adapter_name="reply",
        decisions=(decision,),
        trend_reports=(trend_report,),
        registry=registry,
    )
    triage_report_path = persist_score_governance_triage_report("reply", triage_report)
    loaded_triage_report = load_score_governance_triage_report(triage_report_path)

    assert triage_report_path.exists()
    assert loaded_triage_report.item_count >= 3
    item_kinds = {item.item_kind for item in loaded_triage_report.items}
    assert {"review_decision", "trend_report", "override_transition"} <= item_kinds
    summary = summarize_score_governance_triage_report(loaded_triage_report)
    assert summary["high_severity_count"] >= 0


def test_triage_resolution_suppresses_resolved_item(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    payload = _record_outcome(runtime, _thread_snapshot())
    report = build_score_health_report(
        report_name="Reply Score Health",
        adapter_name="reply",
        trace_payloads=(payload,),
    )
    decision = make_score_health_review_decision(report, status="investigate")
    item_id = "decision-reply-score-health-investigate"
    resolution = make_score_governance_triage_resolution(
        adapter_name="reply",
        item_id=item_id,
        resolution_status="resolved",
        notes="Reviewed and closed.",
    )
    resolution_path = persist_score_governance_triage_resolution("reply", resolution)
    loaded_resolution = load_score_governance_triage_resolution(resolution_path)

    triage_report = build_score_governance_triage_report(
        triage_report_name="Reply Governance Triage",
        adapter_name="reply",
        decisions=(decision,),
        trend_reports=(),
        resolutions=(loaded_resolution,),
    )

    assert triage_report.item_count == 0


def test_make_and_persist_score_governance_release_decision(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    payload = _record_outcome(runtime, _thread_snapshot())
    report = build_score_health_report(
        report_name="Reply Score Health",
        adapter_name="reply",
        trace_payloads=(payload,),
    )
    decision = make_score_health_review_decision(report, status="investigate")
    governance = evaluate_score_governance(report, decision=decision)
    release_report = build_score_governance_release_report(
        release_report_name="Reply Release Governance",
        report=report,
        governance=governance,
        decision=decision,
    )
    release_decision = make_score_governance_release_decision(
        release_report,
        decision_status="override_release",
        notes="Approved with explicit exception.",
    )
    release_decision_path = persist_score_governance_release_decision(
        "reply",
        release_decision,
    )
    loaded_release_decision = load_score_governance_release_decision(release_decision_path)

    assert loaded_release_decision.release_report_id == release_report.release_report_id
    assert loaded_release_decision.decision_status == "override_release"


def test_build_score_governance_status_surface(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    runtime = _runtime(tmp_path)
    payload = _record_outcome(runtime, _thread_snapshot())
    report = build_score_health_report(
        report_name="Reply Score Health",
        adapter_name="reply",
        trace_payloads=(payload,),
    )
    persist_score_health_report("reply", report)
    decision = make_score_health_review_decision(report, status="investigate")
    persist_score_health_review_decision("reply", decision)
    governance = evaluate_score_governance(report, decision=decision)
    release_report = build_score_governance_release_report(
        release_report_name="Reply Release Governance",
        report=report,
        governance=governance,
        decision=decision,
    )
    persist_score_governance_release_report("reply", release_report)
    release_decision = make_score_governance_release_decision(
        release_report,
        decision_status="override_release",
    )
    persist_score_governance_release_decision("reply", release_decision)
    triage_report = build_score_governance_triage_report(
        triage_report_name="Reply Governance Work",
        adapter_name="reply",
        decisions=(decision,),
        trend_reports=(),
    )
    persist_score_governance_triage_report("reply", triage_report)

    registry = _registry(tmp_path)
    registry.promote(
        AcceptedArtifactVersion(
            artifact_key="reply_behavior_policy",
            version="v1",
            source_project="train",
            accepted_at=datetime(2026, 5, 12, 12, 0, tzinfo=UTC),
        ),
        score_governance_status="override",
        score_governance_report_id=report.report_id,
        score_governance_decision_id=decision.decision_id,
        release_governance_report_id=release_report.release_report_id,
        release_governance_decision_id=release_decision.release_decision_id,
        release_governance_decision_status=release_decision.decision_status,
    )

    surface = build_score_governance_status_surface("reply", registry=registry)

    assert surface.latest_review_decision_status == "investigate"
    assert surface.latest_release_decision_status == "override_release"
    assert surface.open_triage_item_count >= 1
    assert surface.artifact_statuses[0].release_governance_decision_status == "override_release"
    summary = summarize_score_governance_status_surface(surface)
    assert summary["artifact_count"] == 1


def test_build_cross_adapter_score_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    runtime = ReplyRuntime()
    _record_outcome(runtime, _thread_snapshot())
    _write_spot_cycle(monkeypatch, tmp_path)

    report = build_cross_adapter_score_report(
        report_name="Cross Adapter Scores",
        adapter_names=("reply", "spot"),
        top_n=10,
    )

    assert report.candidate_count >= 2
    assert {entry.adapter_name for entry in report.entries} == {"reply", "spot"}
    summary = summarize_cross_adapter_score_report(report)
    assert summary["adapter_count"] == 2
    assert summary["top_ice"]


def test_build_score_governance_dashboard_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    runtime = ReplyRuntime()
    payload = _record_outcome(runtime, _thread_snapshot())
    report = build_score_health_report(
        report_name="Reply Score Health",
        adapter_name="reply",
        trace_payloads=(payload,),
    )
    persist_score_health_report("reply", report)
    trend_report = compare_score_health_reports((report,), trend_report_name="Reply Trend")
    persist_score_health_trend_report("reply", trend_report)
    decision = make_score_health_review_decision(report, status="investigate")
    triage_report = build_score_governance_triage_report(
        triage_report_name="Reply Governance Work",
        adapter_name="reply",
        decisions=(decision,),
        trend_reports=(trend_report,),
    )
    persist_score_governance_triage_report("reply", triage_report)
    release_report = build_score_governance_release_report(
        release_report_name="Reply Release Governance",
        report=report,
        governance=evaluate_score_governance(report, decision=decision, trend_report=trend_report),
        decision=decision,
        trend_report=trend_report,
    )
    persist_score_governance_release_report("reply", release_report)

    dashboard = build_score_governance_dashboard_report(
        report_name="Governance Dashboard",
        adapter_names=("reply",),
    )

    assert dashboard.adapter_summaries[0].adapter_name == "reply"
    assert dashboard.unresolved_triage_item_count >= 1
    summary = summarize_score_governance_dashboard_report(dashboard)
    assert summary["adapter_count"] == 1


def test_governance_status_and_cross_adapter_cli(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    runtime = ReplyRuntime()
    payload = _record_outcome(runtime, _thread_snapshot())
    report = build_score_health_report(
        report_name="Reply Score Health",
        adapter_name="reply",
        trace_payloads=(payload,),
    )
    persist_score_health_report("reply", report)
    _write_spot_cycle(monkeypatch, tmp_path)

    exit_code = main(["governance-status", "--adapter", "reply"])
    status_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert status_payload["summary"]["adapter_name"] == "reply"

    exit_code = main(
        [
            "report-cross-adapter-scores",
            "--report-name",
            "Cross Adapter Scores",
            "--adapter",
            "reply",
            "--adapter",
            "spot",
            "--top-n",
            "10",
        ]
    )
    score_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert score_payload["summary"]["adapter_count"] == 2

    exit_code = main(
        [
            "report-score-governance-dashboard",
            "--report-name",
            "Governance Dashboard",
            "--adapter",
            "reply",
        ]
    )
    dashboard_payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert dashboard_payload["summary"]["adapter_count"] == 1
