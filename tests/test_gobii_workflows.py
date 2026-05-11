from __future__ import annotations

import json
from pathlib import Path

import pytest
from trinity_core.cli import main
from trinity_core.ops.control_plane import make_provider_comparison_job
from trinity_core.ops.gobii_workflows import (
    build_gobii_workflow_bundle,
    gobii_workflow_bundle_from_payload,
    load_gobii_workflow_bundle,
    persist_gobii_workflow_bundle,
    register_gobii_workflow_bundle,
)
from trinity_core.schemas import GobiiAgentCreateRequest, GobiiAgentRecord


class _FakeGobiiClient:
    def create_agent(self, payload: GobiiAgentCreateRequest) -> GobiiAgentRecord:
        return GobiiAgentRecord(
            id="agent-123",
            name=payload.name,
            schedule=payload.schedule,
            is_active=True,
            life_state="active",
            browser_use_agent_id="browser-use-123",
        )


def test_build_gobii_workflow_bundle_for_provider_comparison_job(tmp_path: Path) -> None:
    job = make_provider_comparison_job(
        job_id="nightly-shadow-benchmark",
        fixture_dir=str(Path("tests/fixtures/reply_shadow").resolve()),
        include_current_config=True,
        include_deterministic_baseline=True,
    )

    bundle = build_gobii_workflow_bundle(
        job,
        schedule="@daily",
        job_path=str(tmp_path / "nightly-shadow-benchmark.json"),
    )

    assert bundle.workflow_id == "gobii-nightly-shadow-benchmark"
    assert bundle.agent_create_request.schedule == "@daily"
    assert "run-control-job" in bundle.equivalent_trigger_command
    assert bundle.job_path == str(tmp_path / "nightly-shadow-benchmark.json")


def test_persist_and_load_gobii_workflow_bundle_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    job = make_provider_comparison_job(
        job_id="nightly-shadow-benchmark",
        fixture_dir=str(Path("tests/fixtures/reply_shadow").resolve()),
    )
    bundle = build_gobii_workflow_bundle(
        job,
        schedule="@daily",
        job_path=str(tmp_path / "nightly-shadow-benchmark.json"),
    )

    bundle_path = persist_gobii_workflow_bundle(bundle)
    loaded = load_gobii_workflow_bundle(bundle_path)

    assert loaded.workflow_id == bundle.workflow_id
    assert loaded.agent_create_request.name == bundle.agent_create_request.name


def test_register_gobii_workflow_bundle_persists_registration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    job = make_provider_comparison_job(
        job_id="nightly-shadow-benchmark",
        fixture_dir=str(Path("tests/fixtures/reply_shadow").resolve()),
    )
    bundle = build_gobii_workflow_bundle(
        job,
        schedule="@daily",
        job_path=str(tmp_path / "nightly-shadow-benchmark.json"),
    )

    agent, registration_path = register_gobii_workflow_bundle(bundle, _FakeGobiiClient())

    assert agent.id == "agent-123"
    assert registration_path.exists()


def test_gobii_workflow_bundle_from_payload_roundtrip() -> None:
    payload = {
        "workflow_id": "gobii-nightly-shadow-benchmark",
        "adapter_name": "reply",
        "job_id": "nightly-shadow-benchmark",
        "created_at": "2026-05-09T12:00:00+00:00",
        "schedule": "@daily",
        "equivalent_trigger_command": (
            "PYTHONPATH=core uv run python -m trinity_core.cli "
            "run-control-job --job-file /tmp/job.json"
        ),
        "agent_create_request": {
            "name": "Trinity Maintenance: nightly-shadow-benchmark",
            "charter": "Run the scheduled Trinity reply provider-comparison maintenance job.",
            "schedule": "@daily",
            "whitelist_policy": "manual",
            "is_active": True,
            "template_code": None,
            "enabled_personal_server_ids": [],
        },
        "job_path": "/tmp/job.json",
        "notes": ["note-1"],
    }

    bundle = gobii_workflow_bundle_from_payload(payload)

    assert bundle.workflow_id == "gobii-nightly-shadow-benchmark"
    assert bundle.agent_create_request.schedule == "@daily"


def test_register_gobii_workflow_cli_uses_env_api_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    monkeypatch.setenv("GOBII_API_KEY", "secret-key")
    job = make_provider_comparison_job(
        job_id="nightly-shadow-benchmark",
        fixture_dir=str(Path("tests/fixtures/reply_shadow").resolve()),
    )
    bundle = build_gobii_workflow_bundle(
        job,
        schedule="@daily",
        job_path=str(tmp_path / "nightly-shadow-benchmark.json"),
    )
    bundle_path = persist_gobii_workflow_bundle(bundle)

    monkeypatch.setattr(
        "trinity_core.cli.register_gobii_workflow_bundle",
        lambda bundle, client: (
            GobiiAgentRecord(
                id="agent-123",
                name=bundle.agent_create_request.name,
                schedule=bundle.schedule,
                is_active=True,
                life_state="active",
                browser_use_agent_id="browser-use-123",
            ),
            tmp_path / "registration.json",
        ),
    )

    exit_code = main(
        [
            "register-gobii-workflow",
            "--bundle-file",
            str(bundle_path),
            "--gobii-api-base-url",
            "https://gobii.ai",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["agent"]["id"] == "agent-123"
