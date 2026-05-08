from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from trinity_core import cli as trinity_cli
from trinity_core.ops.train_client import propose_reply_policy_via_train_api


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
