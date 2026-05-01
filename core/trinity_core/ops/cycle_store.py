"""Filesystem-backed storage for Reply/Trinity runtime cycles."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from trinity_core.ops.runtime_storage import resolve_runtime_storage_paths


@dataclass(frozen=True, slots=True)
class RuntimeCyclePaths:
    """Resolved storage paths for persisted runtime cycles."""

    root_dir: Path
    cycles_dir: Path
    exports_dir: Path


def resolve_cycle_storage_paths() -> RuntimeCyclePaths:
    runtime_paths = resolve_runtime_storage_paths(repo_root=Path(__file__).resolve().parents[3])
    root_dir = runtime_paths.app_support_dir / "reply_runtime"
    cycles_dir = root_dir / "cycles"
    exports_dir = root_dir / "exports"
    for path in (root_dir, cycles_dir, exports_dir):
        path.mkdir(parents=True, exist_ok=True)
    return RuntimeCyclePaths(root_dir=root_dir, cycles_dir=cycles_dir, exports_dir=exports_dir)


class RuntimeCycleStore:
    """Persist runtime cycle payloads as stable JSON documents."""

    def __init__(self, paths: RuntimeCyclePaths | None = None) -> None:
        self.paths = paths or resolve_cycle_storage_paths()

    def cycle_path(self, cycle_id: UUID) -> Path:
        return self.paths.cycles_dir / f"{cycle_id}.json"

    def export_path(self, cycle_id: UUID) -> Path:
        return self.paths.exports_dir / f"{cycle_id}.json"

    def save_cycle(self, cycle_id: UUID, payload: dict[str, Any]) -> Path:
        path = self.cycle_path(cycle_id)
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=_json_default), encoding="utf-8"
        )
        return path

    def load_cycle(self, cycle_id: UUID) -> dict[str, Any]:
        path = self.cycle_path(cycle_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def save_export(self, cycle_id: UUID, payload: dict[str, Any]) -> Path:
        path = self.export_path(cycle_id)
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=_json_default), encoding="utf-8"
        )
        return path


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
