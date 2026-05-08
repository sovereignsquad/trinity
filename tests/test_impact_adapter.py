from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from trinity_core import cli as trinity_cli
from trinity_core.impact_runtime import ImpactRuntime
from trinity_core.ops.cycle_store import RuntimeCyclePaths, RuntimeCycleStore
from trinity_core.schemas import (
    IMPACT_CONTRACT_VERSION,
    ImpactModelSnapshot,
    ImpactProfileSnapshot,
    ImpactRecommendationDisposition,
    ImpactRecommendationOutcomeEvent,
    ImpactRuntimeSnapshot,
)


def _store(tmp_path: Path) -> RuntimeCycleStore:
    return RuntimeCycleStore(
        RuntimeCyclePaths(
            adapter_name="impact",
            root_dir=tmp_path,
            cycles_dir=tmp_path / "cycles",
            exports_dir=tmp_path / "exports",
        )
    )


def _snapshot() -> ImpactProfileSnapshot:
    return ImpactProfileSnapshot(
        project_ref="impact",
        profile_ref="run-001",
        requested_at=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
        machine_class="apple_silicon_16gb",
        os_name="macOS",
        architecture="arm64",
        readiness_summary=(
            "Ollama is installed but unreachable; local workflow claims are incomplete."
        ),
        runtimes=(
            ImpactRuntimeSnapshot(
                runtime_id="ollama",
                status="installed_unreachable",
                installed=True,
                reachable=False,
                notes="localhost API did not respond",
            ),
        ),
        models=(
            ImpactModelSnapshot(
                model_id="llama3.2:3b",
                runtime_id="ollama",
                locality="local",
                presence="detected",
            ),
        ),
    )


def test_impact_snapshot_requires_timezone() -> None:
    with pytest.raises(ValueError, match="requested_at"):
        ImpactProfileSnapshot(
            project_ref="impact",
            profile_ref="run-001",
            requested_at=datetime(2026, 5, 8, 10, 0),
            machine_class="apple_silicon_16gb",
            os_name="macOS",
            architecture="arm64",
            readiness_summary="Needs review.",
        )


def test_impact_runtime_persists_cycle_and_feedback(tmp_path: Path) -> None:
    runtime = ImpactRuntime(store=_store(tmp_path))
    ranked = runtime.suggest(_snapshot())

    assert len(ranked.recommendations) == 3
    assert runtime.store.cycle_path(ranked.cycle_id).exists()
    assert runtime.store.export_path(ranked.cycle_id).exists()
    assert ranked.contract_version == IMPACT_CONTRACT_VERSION

    outcome = ImpactRecommendationOutcomeEvent(
        profile_ref="run-001",
        cycle_id=ranked.cycle_id,
        disposition=ImpactRecommendationDisposition.APPLIED,
        occurred_at=datetime(2026, 5, 8, 10, 1, tzinfo=UTC),
        candidate_id=ranked.recommendations[0].candidate_id,
        final_note="Started Ollama and queued a re-scan.",
    )

    result = runtime.record_outcome(outcome)

    assert result["status"] == "ok"
    payload = runtime.store.load_cycle(ranked.cycle_id)
    assert payload["profile_snapshot"]["profile_ref"] == "run-001"
    assert payload["feedback_events"][0]["disposition"] == "APPLIED"
    assert payload["frontier_candidate_ids"]


def test_cli_dispatches_impact_snapshot(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}
    snapshot_file = _write_snapshot_file(Path("/tmp"))

    class FakeRuntime:
        def __init__(self, *, adapter_name: str) -> None:
            captured["adapter"] = adapter_name

        def suggest(self, snapshot):  # type: ignore[no-untyped-def]
            captured["snapshot_type"] = type(snapshot).__name__
            return {
                "cycle_id": "11111111-1111-4111-8111-111111111111",
                "profile_ref": snapshot.profile_ref,
                "generated_at": "2026-05-08T10:00:00+00:00",
                "recommendations": [
                    {
                        "candidate_id": "22222222-2222-4222-8222-222222222222",
                        "profile_ref": snapshot.profile_ref,
                        "rank": 1,
                        "headline": "Test",
                        "recommendation_text": "Test recommendation",
                        "rationale": "Test rationale",
                        "risk_flags": [],
                        "scores": {
                            "impact": 8,
                            "confidence": 8,
                            "ease": 7,
                            "quality_score": 80.0,
                            "urgency_score": 60.0,
                            "freshness_score": 70.0,
                            "feedback_score": 10.0,
                        },
                        "source_evidence_ids": ["33333333-3333-4333-8333-333333333333"],
                    }
                ],
                "contract_version": IMPACT_CONTRACT_VERSION,
            }

    monkeypatch.setattr(trinity_cli, "TrinityRuntime", FakeRuntime)
    monkeypatch.setattr(trinity_cli, "AcceptedArtifactRegistry", lambda adapter_name: object())

    exit_code = trinity_cli.main(
        [
            "suggest",
            "--adapter",
            "impact",
            "--input-file",
            str(snapshot_file),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert captured["adapter"] == "impact"
    assert captured["snapshot_type"] == "ImpactProfileSnapshot"
    assert payload["profile_ref"] == "run-001"


def test_cli_rejects_reply_only_policy_commands_for_impact() -> None:
    with pytest.raises(ValueError, match="implemented only for the reply adapter"):
        trinity_cli.main(
            [
                "policy-review",
                "--adapter",
                "impact",
                "--policy-file",
                "/tmp/policy.json",
                "--bundle-file",
                "/tmp/bundle.json",
            ]
        )


def _write_snapshot_file(base: Path) -> Path:
    path = base / "impact_snapshot.json"
    snapshot = _snapshot()
    path.write_text(
        json.dumps(
            {
                "project_ref": snapshot.project_ref,
                "profile_ref": snapshot.profile_ref,
                "requested_at": snapshot.requested_at.isoformat(),
                "machine_class": snapshot.machine_class,
                "os_name": snapshot.os_name,
                "architecture": snapshot.architecture,
                "readiness_summary": snapshot.readiness_summary,
                "runtimes": [
                    {
                        "runtime_id": runtime.runtime_id,
                        "status": runtime.status,
                        "installed": runtime.installed,
                        "reachable": runtime.reachable,
                        "notes": runtime.notes,
                    }
                    for runtime in snapshot.runtimes
                ],
                "models": [
                    {
                        "model_id": model.model_id,
                        "runtime_id": model.runtime_id,
                        "locality": model.locality,
                        "presence": model.presence,
                    }
                    for model in snapshot.models
                ],
                "contract_version": snapshot.contract_version,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path
