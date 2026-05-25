from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from trinity_core.cli import main
from trinity_core.memory.storage import ReplyMemoryStore
from trinity_core.reply_runtime import ReplyRuntime
from trinity_core.schemas import ThreadMessageRole, ThreadMessageSnapshot, ThreadSnapshot


def _write_train_runtime_candidate_bundle(root: Path) -> Path:
    artifact_root = root / "runtime-candidate-pack"
    artifact_root.mkdir(parents=True, exist_ok=True)
    candidates = [
        {
            "candidate_id": "pack@2026-05-24.1:0:summary",
            "candidate_family": "runtime-summary-candidate",
            "source_snapshot_ref": "google-drive-markdown-snapshot@2026-05-24.1",
            "producer_export_ref": "google-drive-markdown-source@2026-05-24.1",
            "record_index": 0,
            "document_title": "Meeting Notes",
            "document_path": "/docs/meeting-notes.md",
            "document_class": "project",
            "candidate_state": "staged",
            "text": "The team agreed to send direct updates every Friday.",
            "confidence": 0.88,
            "confidence_reason": "heuristic-project-summary",
            "freshness": "2026-05-24T07:00:00+00:00",
            "freshness_bucket": "fresh",
            "conflict_flags": [],
            "evidence_refs": ["google-drive-markdown-source@2026-05-24.1:0"],
        },
        {
            "candidate_id": "pack@2026-05-24.1:1:memory",
            "candidate_family": "runtime-memory-candidate",
            "source_snapshot_ref": "google-drive-markdown-snapshot@2026-05-24.1",
            "producer_export_ref": "google-drive-markdown-source@2026-05-24.1",
            "record_index": 1,
            "document_title": "Client Preferences",
            "document_path": "/docs/client-preferences.md",
            "document_class": "person",
            "candidate_state": "staged",
            "text": "The client prefers short replies with explicit next steps.",
            "confidence": 0.91,
            "confidence_reason": "heuristic-person-memory",
            "freshness": "2026-05-24T06:00:00+00:00",
            "freshness_bucket": "fresh",
            "conflict_flags": [],
            "evidence_refs": ["google-drive-markdown-source@2026-05-24.1:1"],
        },
        {
            "candidate_id": "pack@2026-05-24.1:2:reply-support:0",
            "candidate_family": "runtime-reply-support-candidate",
            "source_snapshot_ref": "google-drive-markdown-snapshot@2026-05-24.1",
            "producer_export_ref": "google-drive-markdown-source@2026-05-24.1",
            "record_index": 2,
            "record_chunk_index": 0,
            "document_title": "Launch Checklist",
            "document_path": "/docs/launch-checklist.md",
            "document_class": "process",
            "candidate_state": "staged",
            "text": "Confirm the owner, delivery date, and dependency status before replying.",
            "confidence": 0.84,
            "confidence_reason": "heuristic-process-reply-support",
            "freshness": "2026-05-23T12:00:00+00:00",
            "freshness_bucket": "recent",
            "conflict_flags": [],
            "evidence_refs": ["google-drive-markdown-source@2026-05-24.1:2"],
        },
        {
            "candidate_id": "pack@2026-05-24.1:3:memory",
            "candidate_family": "runtime-memory-candidate",
            "source_snapshot_ref": "google-drive-markdown-snapshot@2026-05-24.1",
            "producer_export_ref": "google-drive-markdown-source@2026-05-24.1",
            "record_index": 3,
            "document_title": "Conflicted Preferences",
            "document_path": "/docs/conflicted-preferences.md",
            "document_class": "person",
            "candidate_state": "staged",
            "text": "The client prefers long exploratory responses.",
            "confidence": 0.52,
            "confidence_reason": "heuristic-person-memory+duplicate-subject",
            "freshness": "2026-05-22T12:00:00+00:00",
            "freshness_bucket": "stale",
            "conflict_flags": ["duplicate-subject"],
            "evidence_refs": ["google-drive-markdown-source@2026-05-24.1:3"],
        },
    ]
    (artifact_root / "runtime-candidates.json").write_text(
        json.dumps(candidates, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (artifact_root / "bundle-metadata.json").write_text(
        json.dumps(
            {
                "snapshot_ref": "google-drive-markdown-snapshot@2026-05-24.1",
                "candidate_count": len(candidates),
                "candidate_family_counts": {
                    "runtime-summary-candidate": 1,
                    "runtime-memory-candidate": 2,
                    "runtime-reply-support-candidate": 1,
                },
                "source_stats": {
                    "scanned_record_count": 4,
                    "accepted_record_count": 4,
                    "skipped_record_count": 0,
                },
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    manifest_path = root / "runtime-candidate-pack.manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "portable_artifact_ref": "runtime-candidate-pack@2026-05-24.1",
                "artifact_kind": "runtime-candidate-pack",
                "snapshot_ref": "google-drive-markdown-snapshot@2026-05-24.1",
                "producer_export_refs": ["google-drive-markdown-source@2026-05-24.1"],
                "serving_refs": ["trinity://runtime-candidate-pack"],
                "generated_at": "2026-05-24T08:00:00+00:00",
                "bundle_kind": "runtime-candidate-pack.v1",
                "candidate_family_counts": {
                    "runtime-summary-candidate": 1,
                    "runtime-memory-candidate": 2,
                    "runtime-reply-support-candidate": 1,
                },
                "source_stats": {
                    "scanned_record_count": 4,
                    "accepted_record_count": 4,
                    "skipped_record_count": 0,
                },
                "lineage": {
                    "snapshot_ref": "google-drive-markdown-snapshot@2026-05-24.1",
                    "source_exports": ["google-drive-markdown-source@2026-05-24.1"],
                },
                "provenance": {
                    "extractor": "train-runtime-candidate-pack",
                    "extractor_version": "v1",
                },
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return manifest_path


def test_import_runtime_candidate_pack_stages_train_bundle(
    monkeypatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    company_id = str(uuid4())
    manifest_path = _write_train_runtime_candidate_bundle(tmp_path / "train_bundle")

    exit_code = main(
        [
            "import-runtime-candidate-pack",
            "--adapter",
            "reply",
            "--company-id",
            company_id,
            "--manifest-file",
            str(manifest_path),
        ]
    )
    assert exit_code == 0
    import_payload = json.loads(capsys.readouterr().out)
    assert import_payload["candidate_count"] == 4
    assert import_payload["staged_candidate_count"] == 4

    exit_code = main(
        [
            "inspect-runtime-candidate-import",
            "--adapter",
            "reply",
            "--company-id",
            company_id,
            "--import-id",
            "runtime-candidate-pack-2026-05-24.1",
        ]
    )
    assert exit_code == 0
    inspect_payload = json.loads(capsys.readouterr().out)
    assert inspect_payload["candidate_state_counts"]["staged"] == 4
    assert inspect_payload["candidate_family_counts"]["runtime-memory-candidate"] == 2


def test_adopt_runtime_candidate_import_promotes_safe_candidates_only(
    monkeypatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    company_id = str(uuid4())
    manifest_path = _write_train_runtime_candidate_bundle(tmp_path / "train_bundle")
    main(
        [
            "import-runtime-candidate-pack",
            "--adapter",
            "reply",
            "--company-id",
            company_id,
            "--manifest-file",
            str(manifest_path),
        ]
    )
    capsys.readouterr()

    exit_code = main(
        [
            "adopt-runtime-candidate-import",
            "--adapter",
            "reply",
            "--company-id",
            company_id,
            "--import-id",
            "runtime-candidate-pack-2026-05-24.1",
            "--min-confidence",
            "0.60",
        ]
    )
    assert exit_code == 0
    adopt_payload = json.loads(capsys.readouterr().out)
    assert adopt_payload["adopted_count"] == 3
    assert adopt_payload["skipped_count"] == 1
    assert adopt_payload["candidate_state_counts"]["adopted"] == 3
    assert adopt_payload["candidate_state_counts"]["skipped"] == 1

    memory_store = ReplyMemoryStore(adapter_name="reply")
    summaries = memory_store.list_memory_summaries(company_id)
    chunks = memory_store.list_retrieval_chunks(company_id, limit=10)

    assert any("short replies with explicit next steps" in item.content for item in summaries)
    assert any("direct updates every Friday" in item.content for item in summaries)
    assert any("Confirm the owner" in item.content for item in chunks)
    assert all("long exploratory responses" not in item.content for item in summaries)


def test_reply_runtime_reports_imported_runtime_knowledge_usage(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    company_id = str(uuid4())
    manifest_path = _write_train_runtime_candidate_bundle(tmp_path / "train_bundle")
    main(
        [
            "import-runtime-candidate-pack",
            "--adapter",
            "reply",
            "--company-id",
            company_id,
            "--manifest-file",
            str(manifest_path),
        ]
    )
    main(
        [
            "adopt-runtime-candidate-import",
            "--adapter",
            "reply",
            "--company-id",
            company_id,
            "--import-id",
            "runtime-candidate-pack-2026-05-24.1",
            "--min-confidence",
            "0.60",
        ]
    )

    runtime = ReplyRuntime()
    ranked = runtime.suggest(
        ThreadSnapshot(
            company_id=UUID(company_id),
            thread_ref="reply:email:alice@example.com",
            channel="email",
            contact_handle="alice@example.com",
            latest_inbound_text="Can you send the latest update?",
            requested_at=_dt("2026-05-24T10:00:00+00:00"),
            messages=(
                ThreadMessageSnapshot(
                    message_id="msg-1",
                    role=ThreadMessageRole.CONTACT,
                    text="Can you send the latest update?",
                    occurred_at=_dt("2026-05-24T10:00:00+00:00"),
                    channel="email",
                    source="reply",
                    handle="alice@example.com",
                ),
            ),
        )
    )

    imported = ranked.runtime_diagnostics.get("imported_runtime_knowledge")
    assert imported is not None
    assert imported["imported_record_count"] >= 3
    assert imported["family_counts"]["runtime-summary-candidate"] >= 1
    assert imported["family_counts"]["runtime-reply-support-candidate"] >= 1


def _dt(value: str):
    from datetime import datetime
    return datetime.fromisoformat(value)
