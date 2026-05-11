from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from trinity_core.cli import main
from trinity_core.ops import (
    build_gobii_tracked_entity_enrichment_bundle,
    normalize_gobii_tracked_entity_enrichment_bundle,
    persist_gobii_task_record,
    submit_gobii_tracked_entity_enrichment_bundle,
)
from trinity_core.schemas import (
    GobiiTaskRecord,
    GobiiTaskStatus,
    GobiiTrackedEntityEnrichmentRequest,
)


class _FakeGobiiTaskClient:
    def create_task(self, payload):  # noqa: ANN001
        return GobiiTaskRecord(
            id="task-enrichment-123",
            status=GobiiTaskStatus.COMPLETED,
            created_at=datetime.fromisoformat("2026-05-10T09:00:00+00:00"),
            updated_at=datetime.fromisoformat("2026-05-10T09:05:00+00:00"),
            prompt=payload.prompt,
            agent_id=payload.agent_id,
            raw_payload={
                "id": "task-enrichment-123",
                "status": "completed",
                "result": {
                    "entity_name": "Jane Doe",
                    "profile_url": "https://www.linkedin.com/in/jane-doe",
                    "headline": "VP Revenue Operations",
                    "current_company": "Example Corp",
                    "location": "New York, NY",
                    "summary": "Leads revenue operations and systems programs across GTM teams.",
                    "evidence_points": [
                        "Profile headline names revenue operations leadership.",
                        "Experience section shows ownership of GTM systems programs.",
                    ],
                },
            },
        )


def test_gobii_tracked_entity_enrichment_bundle_roundtrip_and_normalization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    company_id = uuid4()
    request = GobiiTrackedEntityEnrichmentRequest(
        company_id=company_id,
        entity_ref="candidate:jane-doe",
        entity_name="Jane Doe",
        target_profile_url="https://www.linkedin.com/in/jane-doe",
        company_name="Example Corp",
        role_hint="Revenue operations",
        notes=("Focus on current role and systems scope.",),
        metadata={"source_program": "tracked_entities"},
    )

    bundle = build_gobii_tracked_entity_enrichment_bundle(
        "reply",
        request,
        agent_id="agent-123",
        wait_seconds=30,
    )

    assert bundle.task_create_request.output_schema is not None
    assert "Target profile URL" in bundle.task_create_request.prompt

    persisted_bundle, bundle_path, record, record_path = (
        submit_gobii_tracked_entity_enrichment_bundle(
            bundle,
            _FakeGobiiTaskClient(),
        )
    )

    assert bundle_path.exists()
    assert record_path.exists()
    assert persisted_bundle.task_id == "task-enrichment-123"
    assert record.company_id == str(company_id)

    artifact_bundle, artifact_path = normalize_gobii_tracked_entity_enrichment_bundle(
        "reply",
        persisted_bundle,
    )

    assert artifact_path.exists()
    assert artifact_bundle.document.document_ref == "gobii-profile-enrichment:candidate:jane-doe"
    assert artifact_bundle.document.path == "https://www.linkedin.com/in/jane-doe"
    assert (
        artifact_bundle.document.metadata["gobii_workflow_kind"]
        == "tracked_entity_profile_enrichment"
    )
    assert "Evidence points:" in artifact_bundle.document.content_text

    db_path = (
        tmp_path
        / "app_support"
        / "trinity_runtime"
        / "adapters"
        / "reply"
        / "memory"
        / "runtime_memory.sqlite3"
    )
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT document_ref, path, title FROM documents WHERE company_id = ?",
            (str(company_id),),
        ).fetchall()
    assert rows == [
        (
            "gobii-profile-enrichment:candidate:jane-doe",
            "https://www.linkedin.com/in/jane-doe",
            "Gobii profile enrichment: Jane Doe",
        )
    ]


def test_normalize_gobii_profile_enrichment_cli_persists_runtime_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    company_id = uuid4()
    request_payload = {
        "company_id": str(company_id),
        "entity_ref": "candidate:jane-doe",
        "entity_name": "Jane Doe",
        "target_profile_url": "https://www.linkedin.com/in/jane-doe",
        "company_name": "Example Corp",
        "role_hint": "Revenue operations",
        "notes": ["Focus on current role and systems scope."],
        "metadata": {"source_program": "tracked_entities"},
    }
    request_path = tmp_path / "profile-enrichment-request.json"
    request_path.write_text(json.dumps(request_payload), encoding="utf-8")

    exit_code = main(
        [
            "make-gobii-profile-enrichment",
            "--adapter",
            "reply",
            "--input-file",
            str(request_path),
            "--agent-id",
            "agent-123",
        ]
    )
    response = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    bundle_path = Path(response["bundle_path"])
    assert bundle_path.exists()

    task_record = GobiiTaskRecord(
        id="task-enrichment-cli-123",
        status=GobiiTaskStatus.COMPLETED,
        created_at=datetime.fromisoformat("2026-05-10T09:00:00+00:00"),
        updated_at=datetime.fromisoformat("2026-05-10T09:05:00+00:00"),
        prompt="Collect one bounded profile enrichment artifact",
        agent_id="agent-123",
        adapter_name="reply",
        company_id=str(company_id),
        raw_payload={
            "id": "task-enrichment-cli-123",
            "status": "completed",
            "result": {
                "entity_name": "Jane Doe",
                "profile_url": "https://www.linkedin.com/in/jane-doe",
                "summary": "Leads revenue operations and systems programs across GTM teams.",
                "headline": "VP Revenue Operations",
                "current_company": "Example Corp",
                "location": "New York, NY",
                "evidence_points": [
                    "Profile headline names revenue operations leadership.",
                    "Experience section shows ownership of GTM systems programs.",
                ],
            },
        },
    )
    task_record_path = persist_gobii_task_record("reply", task_record)
    bundle_payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle_payload["task_id"] = task_record.id
    bundle_payload["task_record_path"] = str(task_record_path)
    bundle_path.write_text(json.dumps(bundle_payload, indent=2), encoding="utf-8")

    exit_code = main(
        [
            "normalize-gobii-profile-enrichment",
            "--adapter",
            "reply",
            "--bundle-file",
            str(bundle_path),
        ]
    )

    response = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert Path(response["bundle_path"]).exists()
    assert response["bundle"]["document"]["metadata"]["entity_ref"] == "candidate:jane-doe"
    assert response["bundle"]["evidence_unit"]["source_ref"]["external_id"] == "candidate:jane-doe"
