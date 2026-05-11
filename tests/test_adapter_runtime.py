from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest
from trinity_core.adapters.product.spot import SpotRuntime
from trinity_core.cli import main
from trinity_core.memory import ReplyMemoryStore
from trinity_core.ops import resolve_adapter_runtime_paths
from trinity_core.ops.cycle_store import RuntimeCyclePaths, RuntimeCycleStore
from trinity_core.ops.spot_policy_store import SpotPolicyStore, SpotPolicyStorePaths
from trinity_core.runtime import TrinityRuntime
from trinity_core.schemas import (
    AcceptedArtifactVersion,
    SpotReasoningRequest,
    SpotReviewDisposition,
    SpotReviewOutcome,
    SpotReviewPolicy,
    SpotReviewScopeKind,
)


def test_resolve_adapter_runtime_paths_uses_namespaced_root_for_new_adapters() -> None:
    repo_root = Path("/Users/Shared/Projects/trinity")
    home = Path("/tmp/trinity-test-home")

    paths = resolve_adapter_runtime_paths(
        "reply",
        home=home,
        platform_name="Darwin",
        repo_root=repo_root,
    )

    assert paths.root_dir == (
        home
        / "Library"
        / "Application Support"
        / "Trinity"
        / "trinity_runtime"
        / "adapters"
        / "reply"
    ).resolve()
    assert paths.using_legacy_reply_root is False


def test_resolve_adapter_runtime_paths_can_fall_back_to_legacy_reply_root(tmp_path: Path) -> None:
    repo_root = Path("/Users/Shared/Projects/trinity")
    app_support_dir = tmp_path / "Library" / "Application Support" / "Trinity"
    legacy_root = app_support_dir / "reply_runtime"
    legacy_root.mkdir(parents=True, exist_ok=True)

    paths = resolve_adapter_runtime_paths(
        "reply",
        env={"TRINITY_APP_SUPPORT_DIR": str(app_support_dir)},
        home=tmp_path,
        platform_name="Darwin",
        repo_root=repo_root,
    )

    assert paths.root_dir == legacy_root
    assert paths.using_legacy_reply_root is True


def test_trinity_runtime_rejects_unknown_adapter() -> None:
    with pytest.raises(ValueError, match="Unsupported Trinity adapter"):
        TrinityRuntime(adapter_name="openmythos")


def test_trinity_runtime_supports_bounded_spot_reasoning(tmp_path: Path) -> None:
    runtime = TrinityRuntime(adapter_name="spot")
    request = SpotReasoningRequest(
        company_id=__import__("uuid").uuid4(),
        run_id="run-1",
        row_ref="sheet1:42",
        language="de",
        message_text="We should boycott the zionists everywhere.",
        occurred_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
    )

    result = runtime.reason_spot(request)

    assert result.run_id == "run-1"
    assert result.trace_ref is not None
    assert result.candidates
    assert "runtime_memory_profile" in result.metadata
    assert "anti_pattern_hints" in result.metadata["runtime_memory_profile"]
    assert "runtime_loop_history" in result.metadata
    assert result.escalation_recommended is True
    assert result.review_required is True
    assert result.automatic_disposition == "review_required"
    assert (
        result.metadata["runtime_hitl_escalation"]["decision_target"]
        == "spot_row_review_decision"
    )


def test_trinity_runtime_allows_high_confidence_benign_spot_auto_approval() -> None:
    runtime = TrinityRuntime(adapter_name="spot")
    request = SpotReasoningRequest(
        company_id=__import__("uuid").uuid4(),
        run_id="run-2",
        row_ref="sheet1:43",
        language="en",
        message_text="Thank you for the update, this looks fine.",
        occurred_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
    )

    result = runtime.reason_spot(request)

    assert result.selected_candidate_key == "benign"
    assert result.review_required is False
    assert result.automatic_disposition == "auto_approve"
    assert result.deeper_analysis_available is True
    assert result.human_override_allowed is True


def test_trinity_runtime_blocks_high_risk_spot_false_negative_auto_approval() -> None:
    runtime = TrinityRuntime(adapter_name="spot")
    request = SpotReasoningRequest(
        company_id=__import__("uuid").uuid4(),
        run_id="run-2c",
        row_ref="sheet1:43c",
        language="en",
        message_text="We should bring weapons to the rally and make them pay tonight.",
        occurred_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
    )

    result = runtime.reason_spot(request)

    assert result.selected_candidate_key != "benign"
    assert result.review_required is True
    assert result.automatic_disposition == "review_required"
    assert result.policy_sensitive is True


def test_trinity_runtime_uses_accepted_spot_review_policy_threshold(tmp_path: Path) -> None:
    store = SpotPolicyStore(
        SpotPolicyStorePaths(
            adapter_name="spot",
            root_dir=tmp_path / "accepted_spot_policies",
            scopes_dir=tmp_path / "accepted_spot_policies" / "scopes",
        )
    )
    store.paths.root_dir.mkdir(parents=True, exist_ok=True)
    store.paths.scopes_dir.mkdir(parents=True, exist_ok=True)
    store.accept(
        SpotReviewPolicy(
            artifact_key="spot_review_policy",
            version="spot.v2",
            scope_kind=SpotReviewScopeKind.COMPANY,
            scope_value="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            source_project="train",
            auto_approve_negative_threshold=0.99,
        ),
        artifact=AcceptedArtifactVersion(
            artifact_key="spot_review_policy",
            version="spot.v2",
            source_project="train",
            accepted_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        ),
    )
    runtime = SpotRuntime(policy_store=store)
    request = SpotReasoningRequest(
        company_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        run_id="run-2b",
        row_ref="sheet1:43b",
        language="en",
        message_text="Thank you for the update, this looks fine.",
        occurred_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
    )

    result = runtime.reason_spot(request)

    assert result.selected_candidate_key == "benign"
    assert result.review_required is True
    assert result.automatic_disposition == "review_required"


def test_trinity_runtime_persists_spot_review_outcome_memory(tmp_path: Path) -> None:
    runtime = SpotRuntime(
        store=RuntimeCycleStore(
            RuntimeCyclePaths(
                adapter_name="spot",
                root_dir=tmp_path / "runtime",
                cycles_dir=tmp_path / "runtime" / "cycles",
                exports_dir=tmp_path / "runtime" / "exports",
            )
        ),
        memory_store=ReplyMemoryStore(
            db_path=tmp_path / "runtime_memory.sqlite3",
            adapter_name="spot",
        ),
    )
    runtime.store.paths.cycles_dir.mkdir(parents=True, exist_ok=True)
    runtime.store.paths.exports_dir.mkdir(parents=True, exist_ok=True)
    request = SpotReasoningRequest(
        company_id=__import__("uuid").uuid4(),
        run_id="run-3",
        row_ref="sheet1:44",
        language="de",
        message_text="We should boycott the zionists everywhere.",
        occurred_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
    )
    result = runtime.reason_spot(request)
    trace_path = Path(str(result.trace_ref))
    payload = json.loads(trace_path.read_text(encoding="utf-8"))
    cycle_id = UUID(str(payload["cycle_id"]))

    outcome = SpotReviewOutcome(
        company_id=request.company_id,
        cycle_id=cycle_id,
        run_id=request.run_id,
        row_ref=request.row_ref,
        selected_candidate_key=result.selected_candidate_key,
        disposition=SpotReviewDisposition.CORRECTED,
        final_label="Structural Antisemitism",
        occurred_at=request.occurred_at,
        reviewer_notes="Human reviewer confirmed the need for corrected classification.",
    )

    recorded = runtime.record_review_outcome(outcome)

    assert recorded["status"] == "ok"
    summaries = runtime.memory_store.list_memory_summaries(
        request.company_id,
        scope_refs=(f"company:{request.company_id}", f"human:row:{request.row_ref}"),
        limit=10,
    )
    families = {summary.metadata.get("family") for summary in summaries}
    assert "correction" in families
    assert "human_resolution" in families
    assert "disagreement" in families


def test_trinity_runtime_exports_spot_training_bundle(tmp_path: Path) -> None:
    runtime = SpotRuntime(
        store=RuntimeCycleStore(
            RuntimeCyclePaths(
                adapter_name="spot",
                root_dir=tmp_path / "runtime",
                cycles_dir=tmp_path / "runtime" / "cycles",
                exports_dir=tmp_path / "runtime" / "exports",
            )
        ),
        memory_store=ReplyMemoryStore(
            db_path=tmp_path / "runtime_memory.sqlite3",
            adapter_name="spot",
        ),
    )
    runtime.store.paths.cycles_dir.mkdir(parents=True, exist_ok=True)
    runtime.store.paths.exports_dir.mkdir(parents=True, exist_ok=True)
    request = SpotReasoningRequest(
        company_id=__import__("uuid").uuid4(),
        run_id="run-4",
        row_ref="sheet1:45",
        language="en",
        message_text="Thank you for the update, this looks fine.",
        occurred_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
    )
    result = runtime.reason_spot(request)
    trace_payload = json.loads(Path(str(result.trace_ref)).read_text(encoding="utf-8"))
    cycle_id = UUID(str(trace_payload["cycle_id"]))
    runtime.record_review_outcome(
        SpotReviewOutcome(
            company_id=request.company_id,
            cycle_id=cycle_id,
            run_id=request.run_id,
            row_ref=request.row_ref,
            selected_candidate_key=result.selected_candidate_key,
            disposition=SpotReviewDisposition.CONFIRMED_NEGATIVE,
            final_label="Not Antisemitic",
            occurred_at=request.occurred_at,
        )
    )

    exported = runtime.export_training_bundle(
        cycle_id,
        bundle_type="spot-review-policy-learning",
    )

    assert exported["bundle"]["bundle_type"] == "spot-review-policy-learning"
    assert exported["bundle"]["spot_review_outcome"]["final_label"] == "Not Antisemitic"
    assert exported["bundle"]["labels"]["automatic_disposition"] == "auto_approve"


def test_generic_cli_show_config_supports_adapter_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRINITY_MODEL_CONFIG_PATH", str(tmp_path / "config.json"))

    exit_code = main(["show-config", "--adapter", "reply", "--include-path"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"provider": "deterministic"' in captured.out
    assert '"config_path":' in captured.out


def test_runtime_status_reports_unsupported_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRINITY_MODEL_CONFIG_PATH", str(tmp_path / "config.json"))

    write_exit = main(
        [
            "write-config",
            "--adapter",
            "reply",
            "--provider",
            "mlx",
            "--generator-model",
            "mlx-gen",
            "--refiner-model",
            "mlx-refine",
            "--evaluator-model",
            "mlx-eval",
        ]
    )
    assert write_exit == 0
    capsys.readouterr()

    status_exit = main(["runtime-status", "--adapter", "reply"])

    captured = capsys.readouterr()
    assert status_exit == 0
    assert '"provider": "mlx"' in captured.out
    assert '"provider_status": "unsupported"' in captured.out


def test_write_config_updates_route_provider_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRINITY_MODEL_CONFIG_PATH", str(tmp_path / "config.json"))

    exit_code = main(
        [
            "write-config",
            "--adapter",
            "reply",
            "--provider",
            "ollama",
            "--generator-model",
            "gen-1",
            "--refiner-model",
            "ref-1",
            "--evaluator-model",
            "eval-1",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"provider": "ollama"' in captured.out
    assert '"generator": {' in captured.out
    assert '"refiner": {' in captured.out
    assert '"evaluator": {' in captured.out
    assert captured.out.count('"provider": "ollama"') == 4


def test_runtime_status_supports_mistral_cli_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRINITY_MODEL_CONFIG_PATH", str(tmp_path / "config.json"))

    write_exit = main(
        [
            "write-config",
            "--adapter",
            "reply",
            "--provider",
            "mistral-cli",
            "--mistral-cli-executable",
            "vibe",
            "--mistral-cli-arg=--agent",
            "--mistral-cli-arg=auto-approve",
            "--generator-model",
            "mistral-small-latest",
            "--refiner-model",
            "mistral-small-latest",
            "--evaluator-model",
            "mistral-medium-latest",
        ]
    )
    assert write_exit == 0
    capsys.readouterr()

    monkeypatch.setattr(
        "trinity_core.adapters.model.mistral_cli.shutil.which",
        lambda _: "/usr/local/bin/vibe",
    )

    status_exit = main(["runtime-status", "--adapter", "reply"])

    captured = capsys.readouterr()
    assert status_exit == 0
    assert '"provider": "mistral-cli"' in captured.out
    assert '"provider_status": "configured"' in captured.out
    assert '"mistral_cli_executable": "vibe"' in captured.out
    assert '"mistral_cli_model_binding": "advisory"' in captured.out


def test_write_config_persists_mistral_cli_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRINITY_MODEL_CONFIG_PATH", str(tmp_path / "config.json"))

    exit_code = main(
        [
            "write-config",
            "--adapter",
            "reply",
            "--provider",
            "mistral-cli",
            "--mistral-cli-executable",
            "/opt/mistral/bin/vibe",
            "--mistral-cli-arg=--agent",
            "--mistral-cli-arg=auto-approve",
            "--mistral-cli-mode",
            "vibe",
            "--mistral-cli-model-binding",
            "advisory",
            "--generator-model",
            "mistral-small-latest",
            "--refiner-model",
            "mistral-small-latest",
            "--evaluator-model",
            "mistral-medium-latest",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"provider": "mistral-cli"' in captured.out
    assert '"mistral_cli_executable": "/opt/mistral/bin/vibe"' in captured.out
    assert '"mistral_cli_args": [' in captured.out
    assert '"mistral_cli_mode": "vibe"' in captured.out
    assert '"mistral_cli_model_binding": "advisory"' in captured.out
