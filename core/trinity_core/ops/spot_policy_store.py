"""Filesystem-backed accepted Spot review policy store."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from trinity_core.adapters import SPOT_ADAPTER_NAME, normalize_adapter_name
from trinity_core.ops.cycle_store import dataclass_payload, write_json_atomic
from trinity_core.ops.runtime_storage import resolve_adapter_runtime_paths
from trinity_core.schemas import (
    AcceptedArtifactVersion,
    SpotReviewPolicy,
    SpotReviewScopeKind,
    spot_review_policy_from_payload,
)


@dataclass(frozen=True, slots=True)
class SpotPolicyStorePaths:
    """Resolved storage paths for accepted Spot review policies."""

    adapter_name: str
    root_dir: Path
    scopes_dir: Path


@dataclass(frozen=True, slots=True)
class AcceptedSpotReviewPolicy:
    """One accepted Spot review policy artifact with runtime provenance."""

    artifact: AcceptedArtifactVersion
    policy: SpotReviewPolicy


def resolve_spot_policy_store_paths(
    adapter_name: str = SPOT_ADAPTER_NAME,
) -> SpotPolicyStorePaths:
    adapter_paths = resolve_adapter_runtime_paths(
        adapter_name,
        repo_root=Path(__file__).resolve().parents[3],
    )
    root_dir = adapter_paths.root_dir / "accepted_spot_policies"
    scopes_dir = root_dir / "scopes"
    for path in (root_dir, scopes_dir):
        path.mkdir(parents=True, exist_ok=True)
    return SpotPolicyStorePaths(
        adapter_name=normalize_adapter_name(adapter_name),
        root_dir=root_dir,
        scopes_dir=scopes_dir,
    )


class SpotPolicyStore:
    """Store accepted Spot review policy artifacts deterministically."""

    def __init__(
        self,
        paths: SpotPolicyStorePaths | None = None,
        *,
        adapter_name: str = SPOT_ADAPTER_NAME,
    ) -> None:
        self.paths = paths or resolve_spot_policy_store_paths(adapter_name)

    def accept(
        self,
        policy: SpotReviewPolicy,
        *,
        artifact: AcceptedArtifactVersion,
    ) -> Path:
        if artifact.artifact_key != policy.artifact_key:
            raise ValueError("artifact_key must match policy.artifact_key.")
        if artifact.version != policy.version:
            raise ValueError("artifact.version must match policy.version.")
        version_path = self.version_path(policy.scope_kind, policy.scope_value, policy.version)
        if version_path.exists():
            raise ValueError(f"Accepted Spot review policy already exists: {policy.version}")
        payload = {
            "artifact": dataclass_payload(artifact),
            "policy": dataclass_payload(policy),
        }
        self._write_json(version_path, payload)
        self._write_json(self.current_path(policy.scope_kind, policy.scope_value), payload)
        return version_path

    def resolve(
        self,
        *,
        company_id: UUID | str | None = None,
    ) -> AcceptedSpotReviewPolicy | None:
        normalized_company_id = _normalize_company_id(company_id)
        if normalized_company_id is not None:
            company_policy = self.current_for_scope(
                SpotReviewScopeKind.COMPANY,
                normalized_company_id,
            )
            if company_policy is not None:
                return company_policy
        return self.current_for_scope(SpotReviewScopeKind.GLOBAL, None)

    def current(self) -> AcceptedSpotReviewPolicy | None:
        return self.current_for_scope(SpotReviewScopeKind.GLOBAL, None)

    def current_for_scope(
        self,
        scope_kind: SpotReviewScopeKind,
        scope_value: str | None,
    ) -> AcceptedSpotReviewPolicy | None:
        path = self.current_path(scope_kind, scope_value)
        if not path.exists():
            return None
        return _accepted_policy_from_payload(_read_json(path))

    def load_version(
        self,
        scope_kind: SpotReviewScopeKind,
        scope_value: str | None,
        version: str,
    ) -> AcceptedSpotReviewPolicy:
        path = self.version_path(scope_kind, scope_value, version)
        if not path.exists():
            raise ValueError(f"Unknown accepted Spot review policy version: {version}")
        return _accepted_policy_from_payload(_read_json(path))

    def activate_version(
        self,
        scope_kind: SpotReviewScopeKind,
        scope_value: str | None,
        version: str,
    ) -> Path:
        accepted = self.load_version(scope_kind, scope_value, version)
        payload = {
            "artifact": dataclass_payload(accepted.artifact),
            "policy": dataclass_payload(accepted.policy),
        }
        return self._write_json(self.current_path(scope_kind, scope_value), payload)

    def scope_dir(
        self,
        scope_kind: SpotReviewScopeKind,
        scope_value: str | None,
    ) -> Path:
        path = self.paths.scopes_dir / _scope_key(scope_kind, scope_value)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def version_path(
        self,
        scope_kind: SpotReviewScopeKind,
        scope_value: str | None,
        version: str,
    ) -> Path:
        versions_dir = self.scope_dir(scope_kind, scope_value) / "versions"
        versions_dir.mkdir(parents=True, exist_ok=True)
        return versions_dir / f"{_safe_path_component(version)}.json"

    def current_path(
        self,
        scope_kind: SpotReviewScopeKind,
        scope_value: str | None,
    ) -> Path:
        return self.scope_dir(scope_kind, scope_value) / "current.json"

    def _write_json(self, path: Path, payload: dict[str, Any]) -> Path:
        return write_json_atomic(path, payload)


def _accepted_policy_from_payload(payload: dict[str, Any]) -> AcceptedSpotReviewPolicy:
    return AcceptedSpotReviewPolicy(
        artifact=AcceptedArtifactVersion(
            artifact_key=str(payload["artifact"]["artifact_key"]),
            version=str(payload["artifact"]["version"]),
            source_project=str(payload["artifact"]["source_project"]),
            accepted_at=_parse_datetime(str(payload["artifact"]["accepted_at"])),
        ),
        policy=spot_review_policy_from_payload(payload["policy"]),
    )


def _read_json(path: Path) -> dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def _parse_datetime(value: str):
    from datetime import datetime

    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("accepted_at must be timezone-aware.")
    return parsed


def _safe_path_component(value: str) -> str:
    import re

    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    if not normalized:
        raise ValueError("Path component must not be empty.")
    return normalized


def _scope_key(scope_kind: SpotReviewScopeKind, scope_value: str | None) -> str:
    if scope_kind is SpotReviewScopeKind.GLOBAL:
        return "global"
    normalized_scope = _normalize_company_id(scope_value)
    if not normalized_scope:
        raise ValueError("Company scope requires scope_value.")
    return f"company__{_safe_path_component(normalized_scope)}"


def _normalize_company_id(company_id: UUID | str | None) -> str | None:
    if company_id is None:
        return None
    return str(company_id).strip().lower() or None
