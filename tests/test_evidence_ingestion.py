from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from trinity_core.schemas import (
    EvidenceProvenance,
    EvidenceSourceRef,
    EvidenceSourceType,
)
from trinity_core.workflow import InMemoryEvidenceStore, RawEvidenceInput, ingest_evidence


def test_ingestion_canonicalizes_and_hashes_stably() -> None:
    company_id = uuid4()
    store = InMemoryEvidenceStore()
    ingested_at = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)

    result = ingest_evidence(
        RawEvidenceInput(
            company_id=company_id,
            source_type=EvidenceSourceType.EMAIL,
            source_ref=EvidenceSourceRef(external_id="msg-1", locator="imap://inbox/msg-1"),
            content="  Hello&nbsp;&nbsp;<b>world</b>\r\n\r\n  from   Trinity  ",
            metadata={"language": "en"},
            topic_hints=("reply", "customer"),
            freshness_duration=timedelta(hours=12),
            provenance=EvidenceProvenance(
                collected_at=datetime(2026, 5, 1, 11, 59, tzinfo=UTC),
                collector="unit-test",
                ingestion_channel="manual-import",
                raw_origin_uri="imap://inbox/msg-1",
            ),
        ),
        store=store,
        now=ingested_at,
    )

    assert result.accepted is not None
    evidence = result.accepted
    assert evidence.content_canonical == "Hello world from Trinity"
    assert evidence.content_hash == (
        "1bd395efe27b344a51ca885138521bd4061cdc4cad3acfdebe10e43d4fb24709"
    )
    assert evidence.metadata["language"] == "en"
    assert evidence.topic_hints == ("reply", "customer")
    assert evidence.freshness_window is not None
    assert evidence.freshness_window.expires_at == ingested_at + timedelta(hours=12)


def test_ingestion_suppresses_exact_duplicates_per_company() -> None:
    company_id = uuid4()
    store = InMemoryEvidenceStore()
    first = RawEvidenceInput(
        company_id=company_id,
        source_type=EvidenceSourceType.NOTE,
        source_ref=EvidenceSourceRef(external_id="note-1"),
        content="Customer requested a faster reply loop.",
    )
    second = RawEvidenceInput(
        company_id=company_id,
        source_type=EvidenceSourceType.CRM,
        source_ref=EvidenceSourceRef(external_id="crm-77"),
        content="  Customer requested a faster reply loop.  ",
    )

    accepted = ingest_evidence(first, store=store, now=datetime(2026, 5, 1, 12, 0, tzinfo=UTC))
    duplicate = ingest_evidence(second, store=store, now=datetime(2026, 5, 1, 12, 5, tzinfo=UTC))

    assert accepted.accepted is not None
    assert duplicate.accepted is None
    assert duplicate.suppressed_duplicate is not None
    assert duplicate.suppressed_duplicate.company_id == company_id
    assert duplicate.suppressed_duplicate.existing_evidence_id == accepted.accepted.evidence_id
    assert (
        duplicate.suppressed_duplicate.duplicate_content_hash == accepted.accepted.content_hash
    )


def test_ingestion_keeps_tenants_isolated_for_identical_content() -> None:
    store = InMemoryEvidenceStore()
    first_company = uuid4()
    second_company = uuid4()
    shared_content = "Same evidence body across tenants."

    first = ingest_evidence(
        RawEvidenceInput(
            company_id=first_company,
            source_type=EvidenceSourceType.DOCUMENT,
            source_ref=EvidenceSourceRef(external_id="doc-1"),
            content=shared_content,
        ),
        store=store,
        now=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
    )
    second = ingest_evidence(
        RawEvidenceInput(
            company_id=second_company,
            source_type=EvidenceSourceType.DOCUMENT,
            source_ref=EvidenceSourceRef(external_id="doc-2"),
            content=shared_content,
        ),
        store=store,
        now=datetime(2026, 5, 1, 12, 1, tzinfo=UTC),
    )

    assert first.accepted is not None
    assert second.accepted is not None
    assert first.accepted.content_hash == second.accepted.content_hash
    assert first.accepted.company_id != second.accepted.company_id


def test_source_metadata_must_be_explicit() -> None:
    with pytest.raises(ValueError, match="Provenance ingestion channel is required."):
        EvidenceProvenance(
            collected_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
            collector="unit-test",
            ingestion_channel="",
        )
