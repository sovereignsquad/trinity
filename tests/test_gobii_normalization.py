from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from trinity_core.cli import main
from trinity_core.ops import (
    GobiiNormalizationError,
    normalize_gobii_task_output,
    persist_gobii_task_record,
)
from trinity_core.schemas import (
    EvidenceSourceType,
    GobiiTaskNormalizationRequest,
    GobiiTaskRecord,
    GobiiTaskStatus,
)


def test_normalize_gobii_task_cli_persists_runtime_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    company_id = uuid4()
    task_record = GobiiTaskRecord(
        id="task-123",
        status=GobiiTaskStatus.COMPLETED,
        created_at=datetime.fromisoformat("2026-05-09T12:00:00+00:00"),
        updated_at=datetime.fromisoformat("2026-05-09T12:05:00+00:00"),
        prompt="Collect message evidence",
        agent_id="agent-123",
        adapter_name="reply",
        company_id=str(company_id),
        raw_payload={"id": "task-123", "result": {"content": "Escalate this threat"}},
    )
    persist_gobii_task_record("reply", task_record)

    payload_path = tmp_path / "normalize.json"
    payload_path.write_text(
        json.dumps(
            {
                "company_id": str(company_id),
                "task_id": "task-123",
                "document_ref": "gobii-doc-123",
                "path": "https://x.example/post/123",
                "title": "Threat signal",
                "content_text": "Escalate this threat for human review.",
                "source_type": "WEB",
                "thread_ref": "thread-123",
                "channel": "email",
                "contact_handle": "analyst@example.com",
                "metadata": {"project": "spot"},
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "normalize-gobii-task",
            "--adapter",
            "reply",
            "--input-file",
            str(payload_path),
        ]
    )

    captured = capsys.readouterr()
    response = json.loads(captured.out)
    assert exit_code == 0
    assert Path(response["bundle_path"]).exists()
    assert response["bundle"]["task_record"]["id"] == "task-123"
    assert response["bundle"]["document"]["metadata"]["gobii_task_id"] == "task-123"

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
        document_rows = conn.execute(
            "SELECT document_ref, source, path FROM documents WHERE company_id = ?",
            (str(company_id),),
        ).fetchall()
        event_rows = conn.execute(
            "SELECT event_kind, source_ref FROM memory_events WHERE company_id = ?",
            (str(company_id),),
        ).fetchall()
        retrieval_rows = conn.execute(
            "SELECT document_ref, content FROM retrieval_chunks WHERE company_id = ?",
            (str(company_id),),
        ).fetchall()
    assert document_rows == [("gobii-doc-123", "gobii", "https://x.example/post/123")]
    assert event_rows == [("document_registered", "gobii-doc-123")]
    assert retrieval_rows == [("gobii-doc-123", "Escalate this threat for human review.")]


def test_normalize_gobii_task_rejects_missing_tenant_binding(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    company_id = uuid4()
    task_record = GobiiTaskRecord(
        id="task-999",
        status=GobiiTaskStatus.COMPLETED,
        created_at=datetime.fromisoformat("2026-05-09T12:00:00+00:00"),
        updated_at=datetime.fromisoformat("2026-05-09T12:05:00+00:00"),
        prompt="Collect message evidence",
        agent_id="agent-123",
        raw_payload={"id": "task-999", "result": {"content": "Escalate this threat"}},
    )
    persist_gobii_task_record("reply", task_record)

    request = GobiiTaskNormalizationRequest(
        company_id=company_id,
        task_id="task-999",
        document_ref="gobii-doc-999",
        path="https://x.example/post/999",
        content_text="Escalate this threat for human review.",
        source_type=EvidenceSourceType.WEB,
    )

    with pytest.raises(GobiiNormalizationError):
        normalize_gobii_task_output("reply", request)
