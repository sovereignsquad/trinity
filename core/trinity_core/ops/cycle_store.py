"""Filesystem-backed storage for adapter-scoped Trinity runtime cycles."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from trinity_core.adapters import REPLY_ADAPTER_NAME, normalize_adapter_name
from trinity_core.ops.runtime_storage import resolve_adapter_runtime_paths


@dataclass(frozen=True, slots=True)
class RuntimeCyclePaths:
    """Resolved storage paths for persisted runtime cycles."""

    adapter_name: str
    root_dir: Path
    cycles_dir: Path
    exports_dir: Path
    companies_dir: Path | None = None


def resolve_cycle_storage_paths(adapter_name: str = REPLY_ADAPTER_NAME) -> RuntimeCyclePaths:
    adapter_paths = resolve_adapter_runtime_paths(
        adapter_name,
        repo_root=Path(__file__).resolve().parents[3],
    )
    root_dir = adapter_paths.root_dir
    cycles_dir = root_dir / "cycles"
    exports_dir = root_dir / "exports"
    companies_dir = root_dir / "companies"
    for path in (root_dir, cycles_dir, exports_dir, companies_dir):
        path.mkdir(parents=True, exist_ok=True)
    return RuntimeCyclePaths(
        adapter_name=normalize_adapter_name(adapter_name),
        root_dir=root_dir,
        cycles_dir=cycles_dir,
        exports_dir=exports_dir,
        companies_dir=companies_dir,
    )


class RuntimeCycleStore:
    """Persist runtime cycle payloads as stable JSON documents."""

    def __init__(
        self,
        paths: RuntimeCyclePaths | None = None,
        *,
        adapter_name: str = REPLY_ADAPTER_NAME,
    ) -> None:
        self.paths = paths or resolve_cycle_storage_paths(adapter_name)

    def cycle_path(self, cycle_id: UUID, company_id: UUID | str | None = None) -> Path:
        if company_id is not None:
            return self._company_dir(company_id) / "cycles" / f"{cycle_id}.json"
        legacy_path = self.paths.cycles_dir / f"{cycle_id}.json"
        return legacy_path if legacy_path.exists() else self._discover_path("cycles", cycle_id)

    def export_path(self, cycle_id: UUID, company_id: UUID | str | None = None) -> Path:
        if company_id is not None:
            return self._company_dir(company_id) / "exports" / f"{cycle_id}.json"
        legacy_path = self.paths.exports_dir / f"{cycle_id}.json"
        return legacy_path if legacy_path.exists() else self._discover_path("exports", cycle_id)

    def bundle_path(self, bundle_id: UUID, company_id: UUID | str | None = None) -> Path:
        if company_id is not None:
            bundles_dir = self._company_dir(company_id) / "training_bundles"
            bundles_dir.mkdir(parents=True, exist_ok=True)
            return bundles_dir / f"{bundle_id}.json"
        bundles_dir = self.paths.root_dir / "training_bundles"
        bundles_dir.mkdir(parents=True, exist_ok=True)
        legacy_path = bundles_dir / f"{bundle_id}.json"
        if legacy_path.exists():
            return legacy_path
        return self._discover_path("training_bundles", bundle_id)

    def save_cycle(self, cycle_id: UUID, payload: dict[str, Any]) -> Path:
        path = self.cycle_path(cycle_id, _company_id_from_payload(payload))
        write_json_atomic(path, payload)
        return path

    def load_cycle(self, cycle_id: UUID, company_id: UUID | str | None = None) -> dict[str, Any]:
        path = self.cycle_path(cycle_id, company_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def save_export(self, cycle_id: UUID, payload: dict[str, Any]) -> Path:
        path = self.export_path(cycle_id, _company_id_from_payload(payload))
        write_json_atomic(path, payload)
        return path

    def save_bundle(self, bundle_id: UUID, payload: dict[str, Any]) -> Path:
        path = self.bundle_path(bundle_id, _company_id_from_training_bundle_payload(payload))
        write_json_atomic(path, payload)
        return path

    def _company_dir(self, company_id: UUID | str) -> Path:
        companies_dir = self.paths.companies_dir or (self.paths.root_dir / "companies")
        company_dir = companies_dir / str(company_id).strip().lower()
        company_dir.mkdir(parents=True, exist_ok=True)
        for subdir in ("cycles", "exports", "training_bundles"):
            (company_dir / subdir).mkdir(parents=True, exist_ok=True)
        return company_dir

    def _discover_path(self, category: str, entity_id: UUID) -> Path:
        companies_dir = self.paths.companies_dir or (self.paths.root_dir / "companies")
        pattern = f"*/{category}/{entity_id}.json"
        matches = sorted(companies_dir.glob(pattern))
        if matches:
            return matches[0]
        fallback_root = self.paths.root_dir / category
        fallback_root.mkdir(parents=True, exist_ok=True)
        return fallback_root / f"{entity_id}.json"


def dataclass_payload(value: Any) -> dict[str, Any]:
    """Convert nested dataclasses into JSON-safe payloads."""

    if hasattr(value, "__dataclass_fields__"):
        return _json_ready(asdict(value))
    if isinstance(value, dict):
        return _json_ready(value)
    raise TypeError("Expected dataclass or dict payload.")


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return dt.isoformat()
    return value


def _json_default(value: Any) -> Any:
    return _json_ready(value)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2, sort_keys=True, default=_json_default)
    temp_path = path.with_name(f".{path.name}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        handle.write(serialized)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, path)
    return path


def _company_id_from_payload(payload: dict[str, Any]) -> str | None:
    if "thread_snapshot" in payload:
        return _normalize_company_id(payload["thread_snapshot"].get("company_id"))
    if "ranked_draft_set" in payload and payload["ranked_draft_set"].get("drafts"):
        first_draft = payload["ranked_draft_set"]["drafts"][0]
        if isinstance(first_draft, dict):
            return _normalize_company_id(first_draft.get("company_id"))
    return _normalize_company_id(payload.get("company_id"))


def _company_id_from_training_bundle_payload(payload: dict[str, Any]) -> str | None:
    if "thread_snapshot" in payload:
        return _normalize_company_id(payload["thread_snapshot"].get("company_id"))
    return _company_id_from_payload(payload)


def _normalize_company_id(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    return normalized or None
