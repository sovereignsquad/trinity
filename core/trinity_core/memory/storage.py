"""SQLite-backed runtime memory and prepared-draft storage."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from trinity_core.ops.cycle_store import dataclass_payload
from trinity_core.ops.runtime_storage import resolve_adapter_runtime_paths
from trinity_core.schemas import (
    ContactProfile,
    DocumentRecord,
    MemoryEvent,
    MemorySummary,
    PreparedDraftRefreshCandidate,
    PreparedDraftRefreshPlan,
    PreparedDraftSet,
    RetrievalChunk,
    ThreadSnapshot,
    ThreadState,
)


class ReplyMemoryStore:
    """Tenant-safe storage for runtime memory, snapshots, and prepared drafts."""

    def __init__(self, db_path: Path | None = None, *, adapter_name: str = "reply") -> None:
        if db_path is None:
            root_dir = resolve_adapter_runtime_paths(
                adapter_name,
                repo_root=Path(__file__).resolve().parents[4],
            ).root_dir
            memory_dir = root_dir / "memory"
            memory_dir.mkdir(parents=True, exist_ok=True)
            db_path = memory_dir / "runtime_memory.sqlite3"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def record_event(self, event: MemoryEvent) -> None:
        payload = json.dumps(_json_ready(dict(event.metadata)), sort_keys=True)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO memory_events (
                    company_id, event_kind, source_ref, occurred_at, thread_ref,
                    channel, contact_handle, content_text, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(event.company_id),
                    event.event_kind.value,
                    event.source_ref,
                    _iso(event.occurred_at),
                    event.thread_ref,
                    event.channel,
                    event.contact_handle,
                    event.content_text,
                    payload,
                ),
            )

    def upsert_contact_profile(self, profile: ContactProfile) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO contact_profiles (
                    company_id, contact_handle, display_name, summary, metadata_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(profile.company_id),
                    profile.contact_handle,
                    profile.display_name,
                    profile.summary,
                    json.dumps(_json_ready(dict(profile.metadata)), sort_keys=True),
                    _iso(profile.updated_at or datetime.now(UTC)),
                ),
            )

    def load_contact_profile(
        self,
        company_id: UUID | str,
        contact_handle: str,
    ) -> ContactProfile | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT display_name, summary, metadata_json, updated_at
                FROM contact_profiles
                WHERE company_id = ? AND contact_handle = ?
                """,
                (str(company_id), contact_handle),
            ).fetchone()
        if row is None:
            return None
        company_uuid = UUID(str(company_id)) if not isinstance(company_id, UUID) else company_id
        return ContactProfile(
            company_id=company_uuid,
            contact_handle=contact_handle,
            display_name=row[0],
            summary=row[1] or "",
            metadata=_json_object(row[2]),
            updated_at=_parse_datetime(row[3]),
        )

    def upsert_thread_state(
        self,
        state: ThreadState,
        *,
        snapshot: ThreadSnapshot | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO thread_states (
                    company_id, thread_ref, channel, contact_handle, latest_inbound_text,
                    last_event_at, last_snapshot_at, metadata_json, latest_snapshot_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(state.company_id),
                    state.thread_ref,
                    state.channel,
                    state.contact_handle,
                    state.latest_inbound_text,
                    _iso(state.last_event_at),
                    _iso(state.last_snapshot_at),
                    json.dumps(_json_ready(dict(state.metadata)), sort_keys=True),
                    json.dumps(dataclass_payload(snapshot), sort_keys=True)
                    if snapshot is not None
                    else self._existing_snapshot_json(conn, state.company_id, state.thread_ref),
                ),
            )

    def load_thread_state(
        self,
        company_id: UUID | str,
        thread_ref: str,
    ) -> ThreadState | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    channel,
                    contact_handle,
                    latest_inbound_text,
                    last_event_at,
                    last_snapshot_at,
                    metadata_json
                FROM thread_states
                WHERE company_id = ? AND thread_ref = ?
                """,
                (str(company_id), thread_ref),
            ).fetchone()
        if row is None:
            return None
        company_uuid = UUID(str(company_id)) if not isinstance(company_id, UUID) else company_id
        return ThreadState(
            company_id=company_uuid,
            thread_ref=thread_ref,
            channel=row[0],
            contact_handle=row[1],
            latest_inbound_text=row[2] or "",
            last_event_at=_parse_datetime(row[3]),
            last_snapshot_at=_parse_datetime(row[4]),
            metadata=_json_object(row[5]),
        )

    def save_summary(self, summary: MemorySummary) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO memory_summaries (
                    company_id, summary_key, scope_ref, content, updated_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(summary.company_id),
                    summary.summary_key,
                    summary.scope_ref,
                    summary.content,
                    _iso(summary.updated_at),
                    json.dumps(_json_ready(dict(summary.metadata)), sort_keys=True),
                ),
            )

    def list_memory_summaries(
        self,
        company_id: UUID | str,
        *,
        scope_refs: tuple[str, ...] = (),
        limit: int = 10,
    ) -> tuple[MemorySummary, ...]:
        query = """
            SELECT summary_key, scope_ref, content, updated_at, metadata_json
            FROM memory_summaries
            WHERE company_id = ?
        """
        params: list[Any] = [str(company_id)]
        if scope_refs:
            placeholders = ", ".join("?" for _ in scope_refs)
            query += f" AND scope_ref IN ({placeholders})"
            params.extend(scope_refs)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        company_uuid = UUID(str(company_id)) if not isinstance(company_id, UUID) else company_id
        return tuple(
            MemorySummary(
                company_id=company_uuid,
                summary_key=row[0],
                scope_ref=row[1],
                content=row[2],
                updated_at=_parse_datetime(row[3]) or datetime.now(UTC),
                metadata=_json_object(row[4]),
            )
            for row in rows
        )

    def register_document(self, document: DocumentRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO documents (
                    company_id, document_ref, source, path,
                    title, content_text, occurred_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(document.company_id),
                    document.document_ref,
                    document.source,
                    document.path,
                    document.title,
                    document.content_text,
                    _iso(document.occurred_at),
                    json.dumps(_json_ready(dict(document.metadata)), sort_keys=True),
                ),
            )
        if document.content_text.strip():
            self.save_retrieval_chunk(
                RetrievalChunk(
                    company_id=document.company_id,
                    chunk_ref=f"{document.document_ref}:0",
                    document_ref=document.document_ref,
                    content=document.content_text.strip(),
                    created_at=document.occurred_at or datetime.now(UTC),
                    metadata=document.metadata,
                )
            )

    def delete_document(self, company_id: UUID | str, document_ref: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM documents WHERE company_id = ? AND document_ref = ?",
                (str(company_id), str(document_ref)),
            )
            conn.execute(
                "DELETE FROM retrieval_chunks WHERE company_id = ? AND document_ref = ?",
                (str(company_id), str(document_ref)),
            )

    def save_retrieval_chunk(self, chunk: RetrievalChunk) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO retrieval_chunks (
                    company_id, chunk_ref, document_ref, content, created_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(chunk.company_id),
                    chunk.chunk_ref,
                    chunk.document_ref,
                    chunk.content,
                    _iso(chunk.created_at),
                    json.dumps(_json_ready(dict(chunk.metadata)), sort_keys=True),
                ),
            )

    def list_retrieval_chunks(
        self,
        company_id: UUID | str,
        *,
        limit: int = 10,
    ) -> tuple[RetrievalChunk, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT chunk_ref, document_ref, content, created_at, metadata_json
                FROM retrieval_chunks
                WHERE company_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (str(company_id), int(limit)),
            ).fetchall()
        company_uuid = UUID(str(company_id)) if not isinstance(company_id, UUID) else company_id
        return tuple(
            RetrievalChunk(
                company_id=company_uuid,
                chunk_ref=row[0],
                document_ref=row[1],
                content=row[2],
                created_at=_parse_datetime(row[3]) or datetime.now(UTC),
                metadata=_json_object(row[4]),
            )
            for row in rows
        )

    def mark_thread_dirty(self, company_id: UUID | str, thread_ref: str, reason: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO dirty_threads (
                    company_id, thread_ref, reason, updated_at
                ) VALUES (?, ?, ?, ?)
                """,
                (str(company_id), thread_ref, reason, _iso(datetime.now(UTC))),
            )

    def clear_thread_dirty(self, company_id: UUID | str, thread_ref: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM dirty_threads WHERE company_id = ? AND thread_ref = ?",
                (str(company_id), thread_ref),
            )

    def load_dirty_thread_payload(
        self,
        company_id: UUID | str,
        thread_ref: str,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT reason, updated_at
                FROM dirty_threads
                WHERE company_id = ? AND thread_ref = ?
                """,
                (str(company_id), thread_ref),
            ).fetchone()
        if row is None:
            return None
        return {
            "reason": str(row[0]),
            "updated_at": row[1],
        }

    def build_prepared_draft_refresh_plan(
        self,
        company_id: UUID | str,
        *,
        limit: int = 10,
        stale_after: timedelta = timedelta(minutes=15),
        now: datetime | None = None,
    ) -> PreparedDraftRefreshPlan:
        if limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")
        generated_at = now or datetime.now(UTC)
        stale_before = generated_at - stale_after
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    ts.thread_ref,
                    ts.channel,
                    ts.contact_handle,
                    ts.last_event_at,
                    ts.last_snapshot_at,
                    dt.reason,
                    dt.updated_at,
                    pd.prepared_at,
                    pd.expires_at
                FROM thread_states ts
                LEFT JOIN dirty_threads dt
                    ON dt.company_id = ts.company_id AND dt.thread_ref = ts.thread_ref
                LEFT JOIN prepared_drafts pd
                    ON pd.company_id = ts.company_id AND pd.thread_ref = ts.thread_ref
                WHERE ts.company_id = ? AND ts.latest_snapshot_json IS NOT NULL
                ORDER BY
                    CASE WHEN dt.thread_ref IS NOT NULL THEN 1 ELSE 0 END DESC,
                    CASE
                        WHEN pd.thread_ref IS NULL THEN 1
                        WHEN pd.expires_at <= ? THEN 1
                        WHEN pd.prepared_at <= ? THEN 1
                        ELSE 0
                    END DESC,
                    COALESCE(ts.last_event_at, ts.last_snapshot_at) DESC
                """,
                (
                    str(company_id),
                    _iso(generated_at),
                    _iso(stale_before),
                ),
            ).fetchall()
        company_uuid = UUID(str(company_id)) if not isinstance(company_id, UUID) else company_id
        candidates: list[PreparedDraftRefreshCandidate] = []
        for row in rows:
            dirty = bool(row[5])
            prepared_at = _parse_datetime(row[7])
            expires_at = _parse_datetime(row[8])
            missing_prepared_draft = prepared_at is None or expires_at is None
            stale = False
            if not missing_prepared_draft:
                stale = bool(expires_at <= generated_at or prepared_at <= stale_before)
            refresh_recommended = dirty or missing_prepared_draft or stale
            if not refresh_recommended:
                continue
            refresh_reason = _refresh_reason(
                dirty=dirty,
                dirty_reason=str(row[5] or "").strip(),
                missing_prepared_draft=missing_prepared_draft,
                stale=stale,
            )
            candidates.append(
                PreparedDraftRefreshCandidate(
                    company_id=company_uuid,
                    thread_ref=str(row[0]),
                    channel=str(row[1]),
                    contact_handle=str(row[2]),
                    refresh_reason=refresh_reason,
                    priority_rank=len(candidates) + 1,
                    refresh_recommended=True,
                    dirty=dirty,
                    stale=stale,
                    missing_prepared_draft=missing_prepared_draft,
                    last_event_at=_parse_datetime(row[3]),
                    last_snapshot_at=_parse_datetime(row[4]),
                    dirty_at=_parse_datetime(row[6]),
                    prepared_at=prepared_at,
                    expires_at=expires_at,
                )
            )
            if len(candidates) >= limit:
                break
        return PreparedDraftRefreshPlan(
            company_id=company_uuid,
            generated_at=generated_at,
            stale_before=stale_before,
            limit=limit,
            candidates=tuple(candidates),
        )

    def save_prepared_draft(self, prepared: PreparedDraftSet) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO prepared_drafts (
                    company_id, thread_ref, prepared_at, expires_at, source_thread_version,
                    retrieval_context_hash, generation_reason, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(prepared.company_id),
                    prepared.thread_ref,
                    _iso(prepared.prepared_at),
                    _iso(prepared.expires_at),
                    prepared.source_thread_version,
                    prepared.retrieval_context_hash,
                    prepared.generation_reason,
                    json.dumps(dataclass_payload(prepared), sort_keys=True),
                ),
            )

    def load_prepared_draft_payload(
        self,
        company_id: UUID | str,
        thread_ref: str,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json FROM prepared_drafts
                WHERE company_id = ? AND thread_ref = ?
                """,
                (str(company_id), thread_ref),
            ).fetchone()
        if row is None or not row[0]:
            return None
        return json.loads(str(row[0]))

    def latest_snapshot_payload(
        self,
        company_id: UUID | str,
        thread_ref: str,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT latest_snapshot_json FROM thread_states
                WHERE company_id = ? AND thread_ref = ?
                """,
                (str(company_id), thread_ref),
            ).fetchone()
        if row is None or not row[0]:
            return None
        return json.loads(str(row[0]))

    def _existing_snapshot_json(
        self,
        conn: sqlite3.Connection,
        company_id: UUID | str,
        thread_ref: str,
    ) -> str | None:
        row = conn.execute(
            """
            SELECT latest_snapshot_json
            FROM thread_states
            WHERE company_id = ? AND thread_ref = ?
            """,
            (str(company_id), thread_ref),
        ).fetchone()
        if row is None:
            return None
        return row[0]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS memory_events (
                    company_id TEXT NOT NULL,
                    event_kind TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    thread_ref TEXT,
                    channel TEXT,
                    contact_handle TEXT,
                    content_text TEXT,
                    metadata_json TEXT NOT NULL,
                    PRIMARY KEY (company_id, event_kind, source_ref)
                );
                CREATE TABLE IF NOT EXISTS contact_profiles (
                    company_id TEXT NOT NULL,
                    contact_handle TEXT NOT NULL,
                    display_name TEXT,
                    summary TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (company_id, contact_handle)
                );
                CREATE TABLE IF NOT EXISTS thread_states (
                    company_id TEXT NOT NULL,
                    thread_ref TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    contact_handle TEXT NOT NULL,
                    latest_inbound_text TEXT NOT NULL,
                    last_event_at TEXT,
                    last_snapshot_at TEXT,
                    metadata_json TEXT NOT NULL,
                    latest_snapshot_json TEXT,
                    PRIMARY KEY (company_id, thread_ref)
                );
                CREATE TABLE IF NOT EXISTS memory_summaries (
                    company_id TEXT NOT NULL,
                    summary_key TEXT NOT NULL,
                    scope_ref TEXT NOT NULL,
                    content TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    PRIMARY KEY (company_id, summary_key, scope_ref)
                );
                CREATE TABLE IF NOT EXISTS documents (
                    company_id TEXT NOT NULL,
                    document_ref TEXT NOT NULL,
                    source TEXT NOT NULL,
                    path TEXT NOT NULL,
                    title TEXT,
                    content_text TEXT NOT NULL,
                    occurred_at TEXT,
                    metadata_json TEXT NOT NULL,
                    PRIMARY KEY (company_id, document_ref)
                );
                CREATE TABLE IF NOT EXISTS retrieval_chunks (
                    company_id TEXT NOT NULL,
                    chunk_ref TEXT NOT NULL,
                    document_ref TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    PRIMARY KEY (company_id, chunk_ref)
                );
                CREATE TABLE IF NOT EXISTS dirty_threads (
                    company_id TEXT NOT NULL,
                    thread_ref TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (company_id, thread_ref)
                );
                CREATE TABLE IF NOT EXISTS prepared_drafts (
                    company_id TEXT NOT NULL,
                    thread_ref TEXT NOT NULL,
                    prepared_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    source_thread_version TEXT NOT NULL,
                    retrieval_context_hash TEXT NOT NULL,
                    generation_reason TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (company_id, thread_ref)
                );
                """
            )


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    dt = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return dt.isoformat()


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return _iso(value)
    if hasattr(value, "__dataclass_fields__"):
        return _json_ready(asdict(value))
    return value


def _json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else {}


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _refresh_reason(
    *,
    dirty: bool,
    dirty_reason: str,
    missing_prepared_draft: bool,
    stale: bool,
) -> str:
    if dirty:
        return f"dirty:{dirty_reason or 'dirty_thread'}"
    if missing_prepared_draft:
        return "missing_prepared_draft"
    if stale:
        return "stale_prepared_draft"
    return "not_recommended"
