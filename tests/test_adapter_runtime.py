from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest
from trinity_core.adapters import get_adapter_descriptor, list_supported_adapters
from trinity_core.adapters.product.spot import SpotRuntime
from trinity_core.cli import main, run_cli
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


def test_adapter_registry_exposes_runtime_descriptors() -> None:
    descriptors = {descriptor.adapter_name: descriptor for descriptor in list_supported_adapters()}

    assert set(descriptors) == {"reply", "spot"}
    assert descriptors["reply"].runtime_class_name == "ReplyRuntime"
    assert descriptors["spot"].runtime_class_name == "SpotRuntime"
    assert get_adapter_descriptor("spot").runtime_module.endswith(".spot.runtime")


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
    assert result.candidates[0].ice_score > 0
    assert result.candidates[0].priority_score > 0.0


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


def test_spot_trace_persists_score_fields_for_candidates(tmp_path: Path) -> None:
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
        run_id="run-score",
        row_ref="sheet1:45",
        language="de",
        message_text="We should boycott the zionists everywhere.",
        occurred_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
    )

    result = runtime.reason_spot(request)
    payload = json.loads(Path(str(result.trace_ref)).read_text(encoding="utf-8"))
    candidate = payload["spot_reasoning_result"]["candidates"][0]

    assert candidate["impact"] >= 1
    assert candidate["confidence"] >= 1
    assert candidate["ease"] >= 1
    assert candidate["ice_score"] == (
        candidate["impact"] * candidate["confidence"] * candidate["ease"]
    )
    assert candidate["priority_score"] > 0.0


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
    payload = json.loads(captured.out)
    assert status_exit == 0
    assert payload["provider"] == "mlx"
    assert payload["provider_status"] == "unsupported"
    assert payload["contract_version"] == "trinity_cli.v1"
    assert payload["status_schema_version"] == 4
    assert payload["readiness"]["ready"] is False
    assert payload["readiness"]["state"] == "unsupported"
    assert "provider_unsupported" in payload["readiness"]["reasons"]


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
    payload = json.loads(captured.out)
    assert status_exit == 0
    assert payload["provider"] == "mistral-cli"
    assert payload["provider_status"] == "configured"
    assert payload["mistral_cli_executable"] == "vibe"
    assert payload["mistral_cli_model_binding"] == "advisory"
    assert payload["readiness"]["ready"] is True
    assert payload["readiness"]["state"] == "configured"


def test_runtime_status_reports_shared_model_inventory_match(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRINITY_MODEL_CONFIG_PATH", str(tmp_path / "config.json"))
    models_root = tmp_path / "models"
    manifest_path = models_root / "manifests" / "trinity-model-manifest.json"
    model_file = models_root / "llms" / "chat" / "granite" / "model.safetensors"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    model_file.parent.mkdir(parents=True, exist_ok=True)
    model_file.write_text("placeholder", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": "trinity-model-inventory.v1",
                "entries": [
                    {
                        "model_id": "granite-shared",
                        "family": "granite",
                        "capability": "chat",
                        "format": "mlx",
                        "local_path": "llms/chat/granite/model.safetensors",
                        "provider_refs": {"deterministic": "granite4:350m"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TRINITY_MODELS_ROOT", str(models_root))

    status_exit = main(["runtime-status", "--adapter", "reply"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert status_exit == 0
    assert payload["status_schema_version"] == 4
    assert payload["shared_model_inventory"]["enabled"] is True
    assert payload["shared_model_inventory"]["entry_count"] == 1
    assert payload["roles"]["generator"]["inventory_found"] is True
    assert payload["roles"]["generator"]["inventory_model_id"] == "granite-shared"
    assert payload["roles"]["generator"]["inventory_format"] == "mlx"
    assert payload["roles"]["generator"]["inventory_path"] == str(model_file.resolve())
    assert payload["roles"]["generator"]["inventory_status"] == "present"


def test_run_cli_emits_structured_error_payload_for_invalid_request(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = run_cli(["runtime-status", "--adapter", "openmythos"])

    captured = capsys.readouterr()
    payload = json.loads(captured.err)

    assert exit_code == 2
    assert payload["ok"] is False
    assert payload["contract_version"] == "trinity_cli.v1"
    assert payload["error_schema_version"] == 1
    assert payload["error"]["code"] == "invalid_request"
    assert payload["error"]["command"] == "runtime-status"
    assert payload["error"]["adapter"] == "openmythos"


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


def test_write_config_persists_role_model_ids(
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
            "granite4:350m",
            "--generator-model-id",
            "granite-4.0-h-350m-4bit",
            "--refiner-model",
            "mistral:latest",
            "--refiner-model-id",
            "mistral-latest-shared",
            "--evaluator-model",
            "qwen2.5:7b",
            "--evaluator-model-id",
            "qwen2.5-7b-shared",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["generator"]["model_id"] == "granite-4.0-h-350m-4bit"
    assert payload["refiner"]["model_id"] == "mistral-latest-shared"
    assert payload["evaluator"]["model_id"] == "qwen2.5-7b-shared"


def test_runtime_status_reports_missing_shared_model_asset_by_model_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRINITY_MODEL_CONFIG_PATH", str(tmp_path / "config.json"))
    models_root = tmp_path / "models"
    manifest_path = models_root / "manifests" / "trinity-model-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": "trinity-model-inventory.v1",
                "entries": [
                    {
                        "model_id": "granite-missing",
                        "family": "granite",
                        "capability": "chat",
                        "format": "mlx",
                        "local_path": "llms/chat/granite-missing/model.safetensors",
                        "provider_refs": {"deterministic": "some-other-route"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TRINITY_MODELS_ROOT", str(models_root))

    write_exit = main(
        [
            "write-config",
            "--adapter",
            "reply",
            "--provider",
            "deterministic",
            "--generator-model",
            "granite4:350m",
            "--generator-model-id",
            "granite-missing",
        ]
    )
    assert write_exit == 0
    capsys.readouterr()

    status_exit = main(["runtime-status", "--adapter", "reply"])

    payload = json.loads(capsys.readouterr().out)
    assert status_exit == 0
    assert payload["status_schema_version"] == 4
    assert payload["roles"]["generator"]["inventory_found"] is True
    assert payload["roles"]["generator"]["inventory_model_id"] == "granite-missing"
    assert payload["roles"]["generator"]["inventory_status"] == "missing"


def test_runtime_status_reports_provider_managed_inventory_asset(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRINITY_MODEL_CONFIG_PATH", str(tmp_path / "config.json"))
    models_root = tmp_path / "models"
    manifest_path = models_root / "manifests" / "trinity-model-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": "trinity-model-inventory.v1",
                "entries": [
                    {
                        "model_id": "ollama-managed-granite",
                        "family": "granite",
                        "capability": "chat",
                        "format": "ollama",
                        "provider_modes": ["ollama"],
                        "provider_refs": {"ollama": "granite4:350m"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TRINITY_MODELS_ROOT", str(models_root))

    write_exit = main(
        [
            "write-config",
            "--adapter",
            "reply",
            "--provider",
            "ollama",
            "--generator-model",
            "granite4:350m",
            "--generator-model-id",
            "ollama-managed-granite",
        ]
    )
    assert write_exit == 0
    capsys.readouterr()

    status_exit = main(["runtime-status", "--adapter", "reply"])

    payload = json.loads(capsys.readouterr().out)
    assert status_exit == 0
    assert payload["status_schema_version"] == 4
    assert payload["roles"]["generator"]["inventory_found"] is True
    assert payload["roles"]["generator"]["inventory_model_id"] == "ollama-managed-granite"
    assert payload["roles"]["generator"]["inventory_status"] == "provider_managed"
