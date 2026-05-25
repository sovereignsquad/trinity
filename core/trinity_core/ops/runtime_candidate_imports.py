"""Governed reverse import lane for Train runtime-candidate packs."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from trinity_core.adapters import REPLY_ADAPTER_NAME, normalize_adapter_name
from trinity_core.memory.storage import ReplyMemoryStore
from trinity_core.ops.cycle_store import dataclass_payload, write_json_atomic
from trinity_core.ops.runtime_storage import resolve_adapter_runtime_paths
from trinity_core.schemas import (
    DocumentRecord,
    MemorySummary,
    RuntimeCandidateFamily,
    RuntimeCandidateImportBundle,
    RuntimeCandidateRecord,
    RuntimeCandidateState,
)

RUNTIME_CANDIDATE_IMPORT_SCHEMA_VERSION = "runtime_candidate_import_schema.v1"
TRAIN_RUNTIME_CANDIDATE_BUNDLE_KIND = "runtime-candidate-pack.v1"
TRAIN_RUNTIME_CANDIDATE_FAMILIES = frozenset(item.value for item in RuntimeCandidateFamily)


class RuntimeCandidateImportError(ValueError):
    """Raised when one runtime-candidate pack is malformed or unsafe to stage."""


class RuntimeCandidateAdoptionError(ValueError):
    """Raised when one runtime-candidate import cannot be adopted safely."""


class RuntimeCandidateImportPaths:
    def __init__(self, adapter_name: str, root_dir: Path, companies_dir: Path) -> None:
        self.adapter_name = adapter_name
        self.root_dir = root_dir
        self.companies_dir = companies_dir


def resolve_runtime_candidate_import_paths(
    adapter_name: str = REPLY_ADAPTER_NAME,
) -> RuntimeCandidateImportPaths:
    adapter_paths = resolve_adapter_runtime_paths(
        adapter_name,
        repo_root=Path(__file__).resolve().parents[3],
    )
    root_dir = adapter_paths.root_dir / "runtime_candidate_imports"
    companies_dir = root_dir / "companies"
    companies_dir.mkdir(parents=True, exist_ok=True)
    return RuntimeCandidateImportPaths(
        adapter_name=normalize_adapter_name(adapter_name),
        root_dir=root_dir,
        companies_dir=companies_dir,
    )


class RuntimeCandidateImportStore:
    """Persist staged Train runtime-candidate bundles by company and import ID."""

    def __init__(
        self,
        paths: RuntimeCandidateImportPaths | None = None,
        *,
        adapter_name: str = REPLY_ADAPTER_NAME,
    ) -> None:
        self.paths = paths or resolve_runtime_candidate_import_paths(adapter_name)

    def import_path(self, *, company_id: UUID | str, import_id: str) -> Path:
        company_dir = self.paths.companies_dir / str(company_id).strip().lower() / "imports"
        company_dir.mkdir(parents=True, exist_ok=True)
        return company_dir / f"{import_id}.json"

    def save_import(
        self,
        *,
        company_id: UUID | str,
        import_id: str,
        payload: dict[str, Any],
    ) -> Path:
        return write_json_atomic(
            self.import_path(company_id=company_id, import_id=import_id),
            payload,
        )

    def load_import(
        self,
        *,
        company_id: UUID | str,
        import_id: str,
    ) -> dict[str, Any]:
        return json.loads(
            self.import_path(company_id=company_id, import_id=import_id).read_text(encoding="utf-8")
        )


def import_runtime_candidate_pack(
    *,
    adapter_name: str,
    company_id: UUID | str,
    manifest_path: Path | str,
    import_id: str | None = None,
    import_store: RuntimeCandidateImportStore | None = None,
) -> dict[str, Any]:
    manifest_file = Path(manifest_path).resolve()
    manifest = _load_json_object(manifest_file)
    artifact_kind = str(manifest.get("artifact_kind") or "").strip()
    bundle_kind = str(manifest.get("bundle_kind") or "").strip()
    if artifact_kind != "runtime-candidate-pack":
        raise RuntimeCandidateImportError(
            f"Unsupported artifact_kind '{artifact_kind}' in '{manifest_file}'."
        )
    if bundle_kind != TRAIN_RUNTIME_CANDIDATE_BUNDLE_KIND:
        raise RuntimeCandidateImportError(
            f"Unsupported runtime candidate bundle_kind '{bundle_kind}' in '{manifest_file}'."
        )
    artifact_ref = str(manifest.get("portable_artifact_ref") or "").strip()
    if not artifact_ref:
        raise RuntimeCandidateImportError(
            f"Runtime candidate manifest '{manifest_file}' is missing portable_artifact_ref."
        )
    bundle_root = manifest_file.parent / "runtime-candidate-pack"
    candidates_path = bundle_root / "runtime-candidates.json"
    bundle_metadata_path = bundle_root / "bundle-metadata.json"
    candidates_payload = _load_json_array(candidates_path)
    bundle_metadata = _load_json_object(bundle_metadata_path)
    effective_import_id = _normalize_import_id(import_id or artifact_ref)
    imported_at = datetime.now(UTC)
    typed_candidates = tuple(_candidate_from_payload(item) for item in candidates_payload)
    source_snapshot_ref = str(
        manifest.get("snapshot_ref") or bundle_metadata.get("snapshot_ref") or ""
    ).strip()
    import_bundle = RuntimeCandidateImportBundle(
        import_id=effective_import_id,
        adapter_name=normalize_adapter_name(adapter_name),
        company_id=_as_company_uuid(company_id),
        artifact_ref=artifact_ref,
        imported_at=imported_at,
        manifest_path=str(manifest_file),
        bundle_kind=bundle_kind,
        source_snapshot_ref=source_snapshot_ref,
        candidate_family_counts=dict(bundle_metadata.get("candidate_family_counts") or {}),
        source_stats=dict(bundle_metadata.get("source_stats") or {}),
        lineage=dict(manifest.get("lineage") or {}),
        provenance=dict(manifest.get("provenance") or {}),
        candidates=typed_candidates,
    )
    payload = dataclass_payload(import_bundle)
    payload["schema_version"] = RUNTIME_CANDIDATE_IMPORT_SCHEMA_VERSION
    path = (import_store or RuntimeCandidateImportStore(adapter_name=adapter_name)).save_import(
        company_id=company_id,
        import_id=effective_import_id,
        payload=payload,
    )
    return {
        "status": "ok",
        "company_id": str(company_id),
        "import_id": effective_import_id,
        "import_path": str(path),
        "artifact_ref": artifact_ref,
        "candidate_count": len(typed_candidates),
        "candidate_family_counts": _count_candidate_families(typed_candidates),
        "staged_candidate_count": sum(
            1 for item in typed_candidates if item.candidate_state is RuntimeCandidateState.STAGED
        ),
    }


def inspect_runtime_candidate_import(
    *,
    adapter_name: str,
    company_id: UUID | str,
    import_id: str,
    import_store: RuntimeCandidateImportStore | None = None,
) -> dict[str, Any]:
    payload = (import_store or RuntimeCandidateImportStore(adapter_name=adapter_name)).load_import(
        company_id=company_id,
        import_id=import_id,
    )
    candidates = tuple(_candidate_from_payload(item) for item in payload.get("candidates", []))
    return {
        "status": "ok",
        "company_id": str(company_id),
        "import_id": import_id,
        "artifact_ref": payload.get("artifact_ref"),
        "bundle_kind": payload.get("bundle_kind"),
        "source_snapshot_ref": payload.get("source_snapshot_ref"),
        "candidate_count": len(candidates),
        "candidate_family_counts": _count_candidate_families(candidates),
        "candidate_state_counts": _count_candidate_states(candidates),
        "conflicted_candidate_count": sum(1 for item in candidates if item.conflict_flags),
        "source_stats": payload.get("source_stats", {}),
        "manifest_path": payload.get("manifest_path"),
    }


def adopt_runtime_candidate_import(
    *,
    adapter_name: str,
    company_id: UUID | str,
    import_id: str,
    min_confidence: float = 0.6,
    allow_conflicted: bool = False,
    import_store: RuntimeCandidateImportStore | None = None,
    memory_store: ReplyMemoryStore | None = None,
) -> dict[str, Any]:
    if min_confidence < 0 or min_confidence > 1:
        raise RuntimeCandidateAdoptionError("min_confidence must be between 0 and 1.")
    store = import_store or RuntimeCandidateImportStore(adapter_name=adapter_name)
    payload = store.load_import(company_id=company_id, import_id=import_id)
    runtime_memory = memory_store or ReplyMemoryStore(adapter_name=adapter_name)
    imported_at = _parse_datetime(str(payload.get("imported_at") or "")) or datetime.now(UTC)
    candidates = [_candidate_from_payload(item) for item in payload.get("candidates", [])]

    adopted_count = 0
    skipped_count = 0
    adopted_family_counts: dict[str, int] = {}
    updated_candidates: list[RuntimeCandidateRecord] = []
    for candidate in candidates:
        if candidate.candidate_state is not RuntimeCandidateState.STAGED:
            updated_candidates.append(candidate)
            continue
        skip_reason = _candidate_skip_reason(
            candidate,
            min_confidence=min_confidence,
            allow_conflicted=allow_conflicted,
        )
        if skip_reason is not None:
            updated_candidates.append(
                replace(
                    candidate,
                    candidate_state=RuntimeCandidateState.SKIPPED,
                    adoption_metadata={
                        **dict(candidate.adoption_metadata),
                        "decision": "skipped",
                        "reason": skip_reason,
                        "decided_at": datetime.now(UTC).isoformat(),
                    },
                )
            )
            skipped_count += 1
            continue
        adopted_targets = _adopt_candidate(
            company_id=_as_company_uuid(company_id),
            import_id=import_id,
            artifact_ref=str(payload.get("artifact_ref") or ""),
            candidate=candidate,
            imported_at=imported_at,
            memory_store=runtime_memory,
        )
        updated_candidates.append(
            replace(
                candidate,
                candidate_state=RuntimeCandidateState.ADOPTED,
                adoption_metadata={
                    **dict(candidate.adoption_metadata),
                    "decision": "adopted",
                    "adopted_at": datetime.now(UTC).isoformat(),
                    "adopted_targets": adopted_targets,
                },
            )
        )
        adopted_count += 1
        adopted_family_counts[candidate.candidate_family.value] = (
            adopted_family_counts.get(candidate.candidate_family.value, 0) + 1
        )

    payload["candidates"] = [dataclass_payload(item) for item in updated_candidates]
    payload["last_adoption"] = {
        "adopted_count": adopted_count,
        "skipped_count": skipped_count,
        "min_confidence": min_confidence,
        "allow_conflicted": allow_conflicted,
        "executed_at": datetime.now(UTC).isoformat(),
    }
    path = store.save_import(company_id=company_id, import_id=import_id, payload=payload)
    return {
        "status": "ok",
        "company_id": str(company_id),
        "import_id": import_id,
        "import_path": str(path),
        "adopted_count": adopted_count,
        "skipped_count": skipped_count,
        "adopted_family_counts": adopted_family_counts,
        "candidate_state_counts": _count_candidate_states(tuple(updated_candidates)),
    }


def _adopt_candidate(
    *,
    company_id: UUID,
    import_id: str,
    artifact_ref: str,
    candidate: RuntimeCandidateRecord,
    imported_at: datetime,
    memory_store: ReplyMemoryStore,
) -> tuple[str, ...]:
    adopted_targets: list[str] = []
    metadata = {
        "import_id": import_id,
        "artifact_ref": artifact_ref,
        "candidate_id": candidate.candidate_id,
        "candidate_family": candidate.candidate_family.value,
        "candidate_state": candidate.candidate_state.value,
        "document_class": candidate.document_class,
        "confidence": candidate.confidence,
        "confidence_reason": candidate.confidence_reason,
        "freshness": candidate.freshness,
        "freshness_bucket": candidate.freshness_bucket,
        "conflict_flags": list(candidate.conflict_flags),
        "evidence_refs": list(candidate.evidence_refs),
        "source_snapshot_ref": candidate.source_snapshot_ref,
        "producer_export_ref": candidate.producer_export_ref,
    }
    if candidate.candidate_family in (
        RuntimeCandidateFamily.MEMORY,
        RuntimeCandidateFamily.SUMMARY,
    ):
        memory_store.save_summary(
            MemorySummary(
                company_id=company_id,
                summary_key=_summary_key(import_id, candidate),
                scope_ref=f"company:{company_id}",
                content=candidate.text,
                updated_at=imported_at,
                metadata={
                    **metadata,
                    "family": "preference"
                    if candidate.candidate_family is RuntimeCandidateFamily.MEMORY
                    else "evidence",
                },
            )
        )
        adopted_targets.append("memory_summary")
    if candidate.candidate_family in (
        RuntimeCandidateFamily.SUMMARY,
        RuntimeCandidateFamily.REPLY_SUPPORT,
    ):
        memory_store.register_document(
            DocumentRecord(
                company_id=company_id,
                document_ref=_document_ref(import_id, candidate),
                source="train-runtime-candidate",
                path=(
                    candidate.document_path
                    or f"/train/runtime-candidate/{import_id}/{candidate.candidate_id}.md"
                ),
                title=candidate.document_title or candidate.candidate_id,
                content_text=candidate.text,
                occurred_at=imported_at,
                metadata=metadata,
            )
        )
        adopted_targets.append("retrieval_document")
    return tuple(adopted_targets)


def _candidate_skip_reason(
    candidate: RuntimeCandidateRecord,
    *,
    min_confidence: float,
    allow_conflicted: bool,
) -> str | None:
    if candidate.confidence < min_confidence:
        return f"confidence<{min_confidence:.2f}"
    if candidate.conflict_flags and not allow_conflicted:
        return "conflicted"
    return None


def _candidate_from_payload(payload: dict[str, Any]) -> RuntimeCandidateRecord:
    family = str(payload.get("candidate_family") or "").strip()
    if family not in TRAIN_RUNTIME_CANDIDATE_FAMILIES:
        raise RuntimeCandidateImportError(f"Unsupported runtime candidate family '{family}'.")
    state = str(payload.get("candidate_state") or RuntimeCandidateState.STAGED.value).strip()
    state = state.lower()
    if state not in {item.value for item in RuntimeCandidateState}:
        state = RuntimeCandidateState.STAGED.value
    return RuntimeCandidateRecord(
        candidate_id=str(payload.get("candidate_id") or "").strip(),
        candidate_family=RuntimeCandidateFamily(family),
        source_snapshot_ref=str(payload.get("source_snapshot_ref") or "").strip(),
        producer_export_ref=str(payload.get("producer_export_ref") or "").strip(),
        record_index=int(payload.get("record_index") or 0),
        text=str(payload.get("text") or "").strip(),
        candidate_state=RuntimeCandidateState(state),
        document_title=_optional_text(payload.get("document_title")),
        document_path=_optional_text(payload.get("document_path")),
        document_class=_optional_text(payload.get("document_class")),
        record_chunk_index=payload.get("record_chunk_index"),
        confidence=float(payload.get("confidence") or 0.0),
        confidence_reason=str(payload.get("confidence_reason") or "").strip(),
        freshness=str(payload.get("freshness") or "").strip(),
        freshness_bucket=str(payload.get("freshness_bucket") or "").strip(),
        conflict_flags=tuple(str(item) for item in payload.get("conflict_flags") or ()),
        evidence_refs=tuple(str(item) for item in payload.get("evidence_refs") or ()),
        adoption_metadata=dict(payload.get("adoption_metadata") or {}),
    )


def _summary_key(import_id: str, candidate: RuntimeCandidateRecord) -> str:
    return f"train-import:{import_id}:{candidate.candidate_family.value}:{candidate.candidate_id}"


def _document_ref(import_id: str, candidate: RuntimeCandidateRecord) -> str:
    return f"train-import:{import_id}:{candidate.candidate_id}"


def _count_candidate_families(candidates: tuple[RuntimeCandidateRecord, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in candidates:
        counts[item.candidate_family.value] = counts.get(item.candidate_family.value, 0) + 1
    return counts


def _count_candidate_states(candidates: tuple[RuntimeCandidateRecord, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in candidates:
        counts[item.candidate_state.value] = counts.get(item.candidate_state.value, 0) + 1
    return counts


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeCandidateImportError(f"Expected JSON object in '{path}'.")
    return payload


def _load_json_array(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise RuntimeCandidateImportError(f"Expected JSON object array in '{path}'.")
    return payload


def _normalize_import_id(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip())
    normalized = normalized.strip("-._")
    if not normalized:
        raise RuntimeCandidateImportError("Runtime candidate import_id resolved to empty text.")
    return normalized


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _as_company_uuid(value: UUID | str) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _parse_datetime(value: str) -> datetime | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
