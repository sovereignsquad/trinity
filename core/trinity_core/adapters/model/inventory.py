"""Provider-neutral shared model inventory for Trinity local asset resolution."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_TRINITY_MODELS_ROOT = Path("/Users/Shared/Models")


class ModelInventoryError(ValueError):
    """Raised when the shared Trinity model inventory is invalid."""


@dataclass(frozen=True, slots=True)
class TrinityModelInventoryEntry:
    """One provider-neutral model asset entry from the shared manifest."""

    model_id: str
    family: str
    capability: str
    format: str
    local_path: Path | None = None
    provider_modes: tuple[str, ...] = ()
    provider_refs: Mapping[str, str] = field(default_factory=dict)
    quantization: str | None = None
    embedding_dimensions: int | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TrinityModelInventory:
    """Loaded shared model inventory metadata and normalized entries."""

    models_root: Path
    manifest_path: Path
    manifest_version: str | None
    entries: tuple[TrinityModelInventoryEntry, ...]

    @property
    def loaded(self) -> bool:
        return self.manifest_version is not None

    def find_by_model_id(self, model_id: str) -> TrinityModelInventoryEntry | None:
        normalized = str(model_id or "").strip()
        if not normalized:
            return None
        for entry in self.entries:
            if entry.model_id == normalized:
                return entry
        return None

    def find_for_route(
        self,
        *,
        provider: str,
        route_model: str,
    ) -> TrinityModelInventoryEntry | None:
        normalized_provider = str(provider or "").strip().lower()
        normalized_route_model = str(route_model or "").strip()
        if not normalized_route_model:
            return None
        for entry in self.entries:
            if entry.model_id == normalized_route_model:
                return entry
            provider_ref = str(entry.provider_refs.get(normalized_provider) or "").strip()
            if provider_ref == normalized_route_model:
                return entry
        return None


def resolve_models_root(*, env: Mapping[str, str] | None = None) -> Path:
    """Resolve the shared machine-local model root."""

    resolved_env = env or os.environ
    raw = resolved_env.get("TRINITY_MODELS_ROOT")
    if raw is None:
        return DEFAULT_TRINITY_MODELS_ROOT.resolve()
    return Path(raw).expanduser().resolve()


def default_manifest_path(
    *,
    env: Mapping[str, str] | None = None,
    models_root: Path | None = None,
) -> Path:
    """Resolve the shared manifest location."""

    resolved_env = env or os.environ
    explicit = resolved_env.get("TRINITY_MODEL_MANIFEST_PATH")
    if explicit:
        return Path(explicit).expanduser().resolve()
    root = (models_root or resolve_models_root(env=resolved_env)).resolve()
    return (root / "manifests" / "trinity-model-manifest.json").resolve()


def load_model_inventory(
    *,
    env: Mapping[str, str] | None = None,
    repo_root: Path | None = None,
) -> TrinityModelInventory:
    """Load and validate the shared Trinity model inventory manifest."""

    resolved_env = env or os.environ
    resolved_repo_root = (repo_root or Path.cwd()).expanduser().resolve()
    models_root = resolve_models_root(env=resolved_env)
    manifest_path = default_manifest_path(env=resolved_env, models_root=models_root)

    _reject_repo_local_path(models_root, resolved_repo_root, "models root")
    _reject_repo_local_path(manifest_path, resolved_repo_root, "model manifest path")

    if not manifest_path.exists():
        return TrinityModelInventory(
            models_root=models_root,
            manifest_path=manifest_path,
            manifest_version=None,
            entries=(),
        )

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ModelInventoryError(
            f"Shared Trinity model manifest is invalid JSON: {manifest_path}"
        ) from exc

    if not isinstance(payload, dict):
        raise ModelInventoryError("Shared Trinity model manifest payload must be a JSON object.")

    manifest_version = str(payload.get("manifest_version") or "").strip()
    if not manifest_version:
        raise ModelInventoryError("Shared Trinity model manifest requires manifest_version.")

    entries_payload = payload.get("entries", [])
    if not isinstance(entries_payload, list):
        raise ModelInventoryError("Shared Trinity model manifest entries must be a list.")

    entries = tuple(
        _inventory_entry_from_payload(
            item,
            models_root=models_root,
            repo_root=resolved_repo_root,
        )
        for item in entries_payload
    )
    return TrinityModelInventory(
        models_root=models_root,
        manifest_path=manifest_path,
        manifest_version=manifest_version,
        entries=entries,
    )


def _inventory_entry_from_payload(
    payload: object,
    *,
    models_root: Path,
    repo_root: Path,
) -> TrinityModelInventoryEntry:
    if not isinstance(payload, dict):
        raise ModelInventoryError("Each model inventory entry must be a JSON object.")

    model_id = _required_string(payload, "model_id")
    family = _required_string(payload, "family")
    capability = _required_string(payload, "capability")
    model_format = _required_string(payload, "format")

    local_path: Path | None = None
    raw_local_path = payload.get("local_path")
    if raw_local_path is not None:
        local_path = _resolve_entry_local_path(
            str(raw_local_path),
            models_root=models_root,
            repo_root=repo_root,
        )

    provider_modes_payload = payload.get("provider_modes", ())
    if not isinstance(provider_modes_payload, (list, tuple)):
        raise ModelInventoryError(f"{model_id} provider_modes must be a list.")
    provider_modes = tuple(
        str(item).strip().lower()
        for item in provider_modes_payload
        if str(item).strip()
    )

    provider_refs_payload = payload.get("provider_refs", {})
    if not isinstance(provider_refs_payload, dict):
        raise ModelInventoryError(f"{model_id} provider_refs must be an object.")
    provider_refs = {
        str(key).strip().lower(): str(value).strip()
        for key, value in provider_refs_payload.items()
        if str(key).strip() and str(value).strip()
    }

    embedding_dimensions = payload.get("embedding_dimensions")
    if embedding_dimensions is not None:
        if not isinstance(embedding_dimensions, int) or embedding_dimensions < 1:
            raise ModelInventoryError(
                f"{model_id} embedding_dimensions must be a positive integer."
            )

    metadata_payload = payload.get("metadata", {})
    if not isinstance(metadata_payload, dict):
        raise ModelInventoryError(f"{model_id} metadata must be an object.")
    metadata = {
        str(key).strip(): str(value).strip()
        for key, value in metadata_payload.items()
        if str(key).strip()
    }

    return TrinityModelInventoryEntry(
        model_id=model_id,
        family=family,
        capability=capability,
        format=model_format,
        local_path=local_path,
        provider_modes=provider_modes,
        provider_refs=provider_refs,
        quantization=_optional_string(payload.get("quantization")),
        embedding_dimensions=embedding_dimensions,
        metadata=metadata,
    )


def _resolve_entry_local_path(
    raw: str,
    *,
    models_root: Path,
    repo_root: Path,
) -> Path:
    candidate = Path(raw).expanduser()
    resolved = (candidate if candidate.is_absolute() else models_root / candidate).resolve()
    _reject_repo_local_path(resolved, repo_root, "model asset path")
    try:
        resolved.relative_to(models_root)
    except ValueError as exc:
        raise ModelInventoryError(
            f"Model asset path must stay within the shared models root: {resolved}"
        ) from exc
    return resolved


def _required_string(payload: Mapping[str, object], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ModelInventoryError(f"Shared Trinity model manifest entry requires {key}.")
    return value


def _optional_string(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _reject_repo_local_path(candidate: Path, repo_root: Path, label: str) -> None:
    try:
        candidate.relative_to(repo_root)
    except ValueError:
        return
    raise ModelInventoryError(
        f"Shared Trinity {label} must live outside the repository working tree: {candidate}"
    )
