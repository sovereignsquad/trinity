from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from trinity_core import cli as trinity_cli
from trinity_core.ops.eval_datasets import (
    build_score_governance_release_report,
    evaluate_score_governance,
    make_score_health_review_decision,
    persist_score_governance_release_report,
    persist_score_health_report,
    persist_score_health_review_decision,
)
from trinity_core.ops.train_client import (
    propose_reply_policy_via_train_api,
    propose_spot_review_policy_via_train_api,
)
from trinity_core.schemas import AcceptedArtifactVersion, ScoreHealthReport


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_propose_reply_policy_via_train_api_posts_expected_payload(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request):  # type: ignore[no-untyped-def]
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(
            {
                "learner_kind": "tone",
                "bundle_count": 1,
                "proposal": {"artifact_key": "reply_behavior_policy"},
                "eval_report": {"summary": "ok"},
                "proposal_path": "/tmp/proposal.json",
                "eval_output_path": "/tmp/eval.json",
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = propose_reply_policy_via_train_api(
        learner_kind="tone",
        bundle_files=["/tmp/bundle.json"],
        train_api_base_url="http://127.0.0.1:8013",
        proposal_output_path="/tmp/proposal.json",
        eval_output_path="/tmp/eval.json",
    )

    assert captured["url"] == "http://127.0.0.1:8013/v1/trinity/reply/policies/propose"
    assert captured["payload"] == {
        "learner_kind": "tone",
        "bundle_files": ["/tmp/bundle.json"],
        "proposal_output_path": "/tmp/proposal.json",
        "eval_output_path": "/tmp/eval.json",
    }
    assert result["bundle_count"] == 1


def test_propose_spot_review_policy_via_train_api_posts_expected_payload(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request):  # type: ignore[no-untyped-def]
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(
            {
                "learner_kind": "review-policy",
                "bundle_count": 1,
                "proposal": {"artifact_key": "spot_review_policy"},
                "eval_report": {"summary": "ok"},
                "comparison_report": {"summary": "ok"},
                "proposal_path": "/tmp/proposal.json",
                "eval_output_path": "/tmp/eval.json",
                "comparison_output_path": "/tmp/comparison.json",
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = propose_spot_review_policy_via_train_api(
        learner_kind="review-policy",
        bundle_files=["/tmp/spot-bundle.json"],
        train_api_base_url="http://127.0.0.1:8014",
        proposal_output_path="/tmp/proposal.json",
        eval_output_path="/tmp/eval.json",
        comparison_output_path="/tmp/comparison.json",
    )

    assert captured["url"] == "http://127.0.0.1:8014/v1/trinity/spot/policies/propose"
    assert captured["payload"] == {
        "learner_kind": "review-policy",
        "bundle_files": ["/tmp/spot-bundle.json"],
        "proposal_output_path": "/tmp/proposal.json",
        "eval_output_path": "/tmp/eval.json",
        "comparison_output_path": "/tmp/comparison.json",
    }
    assert result["bundle_count"] == 1


def test_cli_train_propose_policy_exports_bundles_and_accepts(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    cycle_id = uuid4()
    bundle_path = tmp_path / "bundle.json"
    proposal_path = tmp_path / "proposal.json"
    eval_path = tmp_path / "eval.json"

    class FakeRuntime:
        def __init__(self, *, adapter_name: str) -> None:
            self.adapter_name = adapter_name

        def export_training_bundle(self, cycle_id_value, *, bundle_type):  # type: ignore[no-untyped-def]
            assert cycle_id_value == cycle_id
            assert bundle_type.value == "tone-learning"
            return {"bundle_path": str(bundle_path)}

    class FakeRegistry:
        def __init__(self, adapter_name: str) -> None:
            self.adapter_name = adapter_name

    @dataclass
    class FakeAcceptance:
        accepted: bool = True
        artifact: object | None = None
        policy: object | None = None
        bundle_count: int = 1
        candidate_score: float = 1.0
        incumbent_score: float | None = None
        regression_delta: float | None = None
        holdout_bundle_count: int = 1
        acceptance_mode: str = "holdout"
        source_train_project_key: str | None = "reply-tone"
        source_train_run_id: str | None = "run-123"
        review_decision_id: str | None = "review-123"
        skeptical_notes: tuple[str, ...] = ()
        reason: str = "accepted"

    monkeypatch.setattr(trinity_cli, "TrinityRuntime", FakeRuntime)
    monkeypatch.setattr(trinity_cli, "AcceptedArtifactRegistry", FakeRegistry)
    monkeypatch.setattr(
        trinity_cli,
        "default_train_proposal_paths",
        lambda **_: (proposal_path, eval_path),
    )
    monkeypatch.setattr(
        trinity_cli,
        "propose_reply_policy_with_train",
        lambda **kwargs: {
            "learner_kind": kwargs["learner_kind"],
            "bundle_count": 1,
            "proposal": {"artifact_key": "reply_behavior_policy"},
            "eval_report": {"summary": "ok"},
            "proposal_path": str(proposal_path),
            "eval_output_path": str(eval_path),
        },
    )
    monkeypatch.setattr(
        trinity_cli,
        "accept_reply_behavior_policy",
        lambda *args, **kwargs: FakeAcceptance(),
    )

    exit_code = trinity_cli.main(
        [
            "train-propose-policy",
            "--adapter",
            "reply",
            "--cycle-id",
            str(cycle_id),
            "--bundle-type",
            "tone-learning",
            "--learner-kind",
            "tone",
            "--transport",
            "cli",
            "--accept",
            "--holdout-bundle-file",
            str(bundle_path),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["bundle_files"] == [str(bundle_path)]
    assert payload["train_result"]["proposal_path"] == str(proposal_path)
    assert payload["acceptance_result"]["accepted"] is True


def test_cli_policy_accept_requires_explicit_override_without_holdout(
    monkeypatch,
    capsys,
) -> None:
    captured: dict[str, object] = {}

    class FakeRuntime:
        def __init__(self, *, adapter_name: str) -> None:
            self.adapter_name = adapter_name

    class FakeRegistry:
        def __init__(self, adapter_name: str) -> None:
            self.adapter_name = adapter_name

    @dataclass
    class FakeAcceptance:
        accepted: bool = False
        artifact: object | None = None
        policy: object | None = None
        bundle_count: int = 1
        candidate_score: float = 0.0
        incumbent_score: float | None = None
        regression_delta: float | None = None
        holdout_bundle_count: int = 0
        acceptance_mode: str = "pending_holdout"
        source_train_project_key: str | None = None
        source_train_run_id: str | None = None
        review_decision_id: str | None = None
        skeptical_notes: tuple[str, ...] = ()
        reason: str = "Rejected: holdout replay is required before acceptance."

    monkeypatch.setattr(trinity_cli, "TrinityRuntime", FakeRuntime)
    monkeypatch.setattr(trinity_cli, "AcceptedArtifactRegistry", FakeRegistry)

    def fake_accept(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["require_holdout"] = kwargs["require_holdout"]
        return FakeAcceptance()

    monkeypatch.setattr(trinity_cli, "accept_reply_behavior_policy", fake_accept)

    exit_code = trinity_cli.main(
        [
            "policy-accept",
            "--adapter",
            "reply",
            "--policy-file",
            "/tmp/proposal.json",
            "--bundle-file",
            "/tmp/bundle.json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert captured["require_holdout"] is True
    assert payload["acceptance_mode"] == "pending_holdout"


def test_cli_policy_accept_allows_explicit_no_holdout_override(
    monkeypatch,
    capsys,
) -> None:
    captured: dict[str, object] = {}

    class FakeRuntime:
        def __init__(self, *, adapter_name: str) -> None:
            self.adapter_name = adapter_name

    class FakeRegistry:
        def __init__(self, adapter_name: str) -> None:
            self.adapter_name = adapter_name

    @dataclass
    class FakeAcceptance:
        accepted: bool = True
        artifact: object | None = None
        policy: object | None = None
        bundle_count: int = 1
        candidate_score: float = 1.0
        incumbent_score: float | None = None
        regression_delta: float | None = None
        holdout_bundle_count: int = 0
        acceptance_mode: str = "override_no_holdout"
        source_train_project_key: str | None = None
        source_train_run_id: str | None = None
        review_decision_id: str | None = None
        skeptical_notes: tuple[str, ...] = (
            "Accepted without holdout replay; monitor early live cycles closely.",
        )
        reason: str = "accepted"

    monkeypatch.setattr(trinity_cli, "TrinityRuntime", FakeRuntime)
    monkeypatch.setattr(trinity_cli, "AcceptedArtifactRegistry", FakeRegistry)

    def fake_accept(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["require_holdout"] = kwargs["require_holdout"]
        return FakeAcceptance()

    monkeypatch.setattr(trinity_cli, "accept_reply_behavior_policy", fake_accept)

    exit_code = trinity_cli.main(
        [
            "policy-accept",
            "--adapter",
            "reply",
            "--policy-file",
            "/tmp/proposal.json",
            "--bundle-file",
            "/tmp/bundle.json",
            "--allow-no-holdout",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert captured["require_holdout"] is False
    assert payload["acceptance_mode"] == "override_no_holdout"


def test_cli_policy_accept_blocks_without_score_governance_override(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))

    report = ScoreHealthReport(
        report_id="reply-score-health",
        adapter_name="reply",
        created_at=datetime(2026, 5, 12, 10, 0, tzinfo=UTC),
        trace_count=1,
        candidate_count=2,
        flagged_candidate_count=1,
    )
    report_path = persist_score_health_report("reply", report)
    decision = make_score_health_review_decision(report, status="investigate")
    decision_path = persist_score_health_review_decision("reply", decision)

    def fail_accept(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("accept_reply_behavior_policy should not be called")

    monkeypatch.setattr(trinity_cli, "accept_reply_behavior_policy", fail_accept)

    exit_code = trinity_cli.main(
        [
            "policy-accept",
            "--adapter",
            "reply",
            "--policy-file",
            "/tmp/proposal.json",
            "--bundle-file",
            "/tmp/bundle.json",
            "--score-health-report-file",
            str(report_path),
            "--score-health-decision-file",
            str(decision_path),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["accepted"] is False
    assert payload["score_governance"]["decision_status"] == "investigate"


def test_cli_policy_accept_allows_score_governance_override(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    captured: dict[str, object] = {}

    report = ScoreHealthReport(
        report_id="reply-score-health",
        adapter_name="reply",
        created_at=datetime(2026, 5, 12, 10, 0, tzinfo=UTC),
        trace_count=1,
        candidate_count=2,
        flagged_candidate_count=1,
    )
    report_path = persist_score_health_report("reply", report)
    decision = make_score_health_review_decision(report, status="investigate")
    decision_path = persist_score_health_review_decision("reply", decision)
    governance = evaluate_score_governance(report, decision=decision)
    release_report = build_score_governance_release_report(
        release_report_name="Reply Release Governance",
        report=report,
        governance=governance,
        decision=decision,
    )
    release_report_path = persist_score_governance_release_report("reply", release_report)

    @dataclass
    class FakeAcceptance:
        accepted: bool = True
        artifact: object | None = None
        policy: object | None = None
        bundle_count: int = 1
        candidate_score: float = 1.0
        incumbent_score: float | None = None
        regression_delta: float | None = None
        holdout_bundle_count: int = 0
        acceptance_mode: str = "override_no_holdout"
        source_train_project_key: str | None = None
        source_train_run_id: str | None = None
        review_decision_id: str | None = None
        skeptical_notes: tuple[str, ...] = ()
        reason: str = "accepted"

    def fake_accept(*args, **kwargs):  # type: ignore[no-untyped-def]
        captured["score_governance_status"] = kwargs["score_governance_status"]
        captured["score_governance_decision_id"] = kwargs["score_governance_decision_id"]
        captured["score_governance_override_notes"] = kwargs["score_governance_override_notes"]
        captured["release_governance_report_id"] = kwargs["release_governance_report_id"]
        captured["release_governance_decision_status"] = kwargs[
            "release_governance_decision_status"
        ]
        captured["skeptical_notes"] = kwargs["skeptical_notes"]
        return FakeAcceptance()

    monkeypatch.setattr(trinity_cli, "accept_reply_behavior_policy", fake_accept)

    exit_code = trinity_cli.main(
        [
            "policy-accept",
            "--adapter",
            "reply",
            "--policy-file",
            "/tmp/proposal.json",
            "--bundle-file",
            "/tmp/bundle.json",
            "--score-health-report-file",
            str(report_path),
            "--score-health-decision-file",
            str(decision_path),
            "--release-governance-report-file",
            str(release_report_path),
            "--release-governance-decision-status",
            "override_release",
            "--allow-score-governance-override",
            "--score-governance-override-note",
            "Release lead approved temporary exception.",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["accepted"] is True
    assert payload["score_governance"]["decision_status"] == "investigate"
    assert captured["score_governance_status"] == "override"
    assert captured["score_governance_decision_id"] == decision.decision_id
    assert captured["score_governance_override_notes"] == (
        "Release lead approved temporary exception.",
    )
    assert captured["release_governance_report_id"] == release_report.release_report_id
    assert captured["release_governance_decision_status"] == "override_release"
    assert any("Score governance override" in note for note in captured["skeptical_notes"])


def test_cli_check_release_governance_and_list_work(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    report = ScoreHealthReport(
        report_id="reply-score-health",
        adapter_name="reply",
        created_at=datetime(2026, 5, 12, 10, 0, tzinfo=UTC),
        trace_count=1,
        candidate_count=2,
        flagged_candidate_count=1,
    )
    report_path = persist_score_health_report("reply", report)
    decision = make_score_health_review_decision(report, status="investigate")
    decision_path = persist_score_health_review_decision("reply", decision)

    exit_code = trinity_cli.main(
        [
            "check-release-governance",
            "--report-file",
            str(report_path),
            "--decision-file",
            str(decision_path),
            "--release-report-name",
            "Reply Release Governance",
        ]
    )
    release_payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert release_payload["release_report"]["release_risk"] in {"high", "medium", "low"}

    registry = trinity_cli.AcceptedArtifactRegistry(adapter_name="reply")
    registry.promote(
        AcceptedArtifactVersion(
            artifact_key="reply_behavior_policy",
            version="v2",
            source_project="train",
            accepted_at=datetime(2026, 5, 12, 11, 0, tzinfo=UTC),
        ),
        score_governance_status="override",
        score_governance_report_id=report.report_id,
        score_governance_decision_id=decision.decision_id,
        score_governance_override_notes=("release exception",),
    )

    exit_code = trinity_cli.main(
        [
            "list-score-governance-work",
            "--adapter",
            "reply",
            "--triage-report-name",
            "Reply Governance Work",
        ]
    )
    triage_payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert triage_payload["summary"]["item_count"] >= 2

    decision_report_path = Path(release_payload["release_report_path"])
    exit_code = trinity_cli.main(
        [
            "record-release-governance-decision",
            "--release-report-file",
            str(decision_report_path),
            "--decision-status",
            "override_release",
            "--notes",
            "Approved with explicit exception.",
        ]
    )
    release_decision_payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert (
        release_decision_payload["release_decision"]["release_report_id"]
        == release_payload["release_report"]["release_report_id"]
    )

    first_item_id = triage_payload["triage_report"]["items"][0]["item_id"]
    exit_code = trinity_cli.main(
        [
            "resolve-score-governance-item",
            "--adapter",
            "reply",
            "--item-id",
            first_item_id,
            "--resolution-status",
            "resolved",
            "--notes",
            "Operator handled this item.",
        ]
    )
    resolution_payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert resolution_payload["resolution"]["item_id"] == first_item_id
