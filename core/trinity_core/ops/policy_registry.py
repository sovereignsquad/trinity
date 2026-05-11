"""Filesystem-backed accepted artifact registry for adapter-scoped policy promotion."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trinity_core.adapters import REPLY_ADAPTER_NAME, normalize_adapter_name
from trinity_core.ops.cycle_store import dataclass_payload, write_json_atomic
from trinity_core.ops.runtime_storage import resolve_adapter_runtime_paths
from trinity_core.schemas import AcceptedArtifactVersion


@dataclass(frozen=True, slots=True)
class AcceptedArtifactRegistryPaths:
    """Resolved storage paths for accepted artifact registry state."""

    adapter_name: str
    root_dir: Path
    artifacts_dir: Path


@dataclass(frozen=True, slots=True)
class AcceptedArtifactTransitionRecord:
    """Immutable promotion or rollback event for one artifact key."""

    artifact: AcceptedArtifactVersion
    action: str
    promoted_at: datetime
    previous_version: str | None = None
    reason: str | None = None
    contract_version: str | None = None
    scope_kind: str | None = None
    scope_value: str | None = None
    source_train_project_key: str | None = None
    source_train_run_id: str | None = None
    source_review_decision_id: str | None = None
    acceptance_mode: str | None = None
    holdout_bundle_count: int = 0
    skeptical_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.action not in {"PROMOTE", "ROLLBACK"}:
            raise ValueError("action must be PROMOTE or ROLLBACK.")
        if self.promoted_at.tzinfo is None:
            raise ValueError("promoted_at must be timezone-aware.")


@dataclass(frozen=True, slots=True)
class ReplyPolicyReviewArtifact:
    """Persisted review decision with lineage into later promotion."""

    review_decision_id: str
    reviewed_at: datetime
    artifact_key: str
    candidate_version: str
    scope_kind: str
    scope_value: str | None
    ready_for_acceptance: bool
    acceptance_mode: str
    proposal_bundle_count: int
    holdout_bundle_count: int
    candidate_score: float
    incumbent_score: float | None
    regression_delta: float | None
    holdout_candidate_score: float | None = None
    holdout_incumbent_score: float | None = None
    holdout_regression_delta: float | None = None
    incumbent_policy_version: str | None = None
    source_train_project_key: str | None = None
    source_train_run_id: str | None = None
    review_reason: str | None = None
    skeptical_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.review_decision_id.strip():
            raise ValueError("review_decision_id is required.")
        if self.reviewed_at.tzinfo is None:
            raise ValueError("reviewed_at must be timezone-aware.")
        if not self.artifact_key.strip():
            raise ValueError("artifact_key is required.")
        if not self.candidate_version.strip():
            raise ValueError("candidate_version is required.")
        if not self.scope_kind.strip():
            raise ValueError("scope_kind is required.")


def resolve_accepted_artifact_registry_paths(
    adapter_name: str = REPLY_ADAPTER_NAME,
) -> AcceptedArtifactRegistryPaths:
    adapter_paths = resolve_adapter_runtime_paths(
        adapter_name,
        repo_root=Path(__file__).resolve().parents[3],
    )
    root_dir = adapter_paths.root_dir / "accepted_artifacts"
    artifacts_dir = root_dir / "artifacts"
    for path in (root_dir, artifacts_dir):
        path.mkdir(parents=True, exist_ok=True)
    return AcceptedArtifactRegistryPaths(
        adapter_name=normalize_adapter_name(adapter_name),
        root_dir=root_dir,
        artifacts_dir=artifacts_dir,
    )


class AcceptedArtifactRegistry:
    """Track immutable accepted artifact versions plus explicit current state."""

    def __init__(
        self,
        paths: AcceptedArtifactRegistryPaths | None = None,
        *,
        adapter_name: str = REPLY_ADAPTER_NAME,
    ) -> None:
        self.paths = paths or resolve_accepted_artifact_registry_paths(adapter_name)

    def promote(
        self,
        artifact: AcceptedArtifactVersion,
        *,
        reason: str | None = None,
        promoted_at: datetime | None = None,
        contract_version: str | None = None,
        scope_kind: str | None = None,
        scope_value: str | None = None,
        source_train_project_key: str | None = None,
        source_train_run_id: str | None = None,
        source_review_decision_id: str | None = None,
        acceptance_mode: str | None = None,
        holdout_bundle_count: int = 0,
        skeptical_notes: tuple[str, ...] = (),
    ) -> AcceptedArtifactTransitionRecord:
        action_time = promoted_at or artifact.accepted_at
        if action_time.tzinfo is None:
            raise ValueError("promoted_at must be timezone-aware.")
        previous = self.current(artifact.artifact_key)
        version_path = self.version_path(artifact.artifact_key, artifact.version)
        if version_path.exists():
            detail = f"{artifact.artifact_key}:{artifact.version}"
            raise ValueError(
                f"Accepted artifact version already exists for {detail}"
            )
        self._write_json(version_path, dataclass_payload(artifact))
        transition = AcceptedArtifactTransitionRecord(
            artifact=artifact,
            action="PROMOTE",
            promoted_at=action_time,
            previous_version=previous.version if previous else None,
            reason=reason,
            contract_version=contract_version,
            scope_kind=scope_kind,
            scope_value=scope_value,
            source_train_project_key=source_train_project_key,
            source_train_run_id=source_train_run_id,
            source_review_decision_id=source_review_decision_id,
            acceptance_mode=acceptance_mode,
            holdout_bundle_count=int(holdout_bundle_count),
            skeptical_notes=tuple(str(note) for note in skeptical_notes if str(note).strip()),
        )
        self._write_transition(transition)
        self._write_current_pointer(transition)
        return transition

    def rollback(
        self,
        artifact_key: str,
        *,
        target_version: str | None = None,
        reason: str | None = None,
        promoted_at: datetime | None = None,
    ) -> AcceptedArtifactTransitionRecord:
        current_pointer = self.current_pointer(artifact_key)
        if current_pointer is None:
            raise ValueError(f"No current accepted artifact exists for {artifact_key}")
        fallback_target = current_pointer.get("previous_version")
        resolved_target = str(target_version or fallback_target or "").strip()
        if not resolved_target:
            raise ValueError(f"No rollback target is available for {artifact_key}")
        artifact = self.load_version(artifact_key, resolved_target)
        action_time = promoted_at or datetime.now(UTC)
        transition = AcceptedArtifactTransitionRecord(
            artifact=artifact,
            action="ROLLBACK",
            promoted_at=action_time,
            previous_version=str(current_pointer["artifact"]["version"]),
            reason=reason,
            contract_version=current_pointer.get("contract_version"),
            scope_kind=current_pointer.get("scope_kind"),
            scope_value=current_pointer.get("scope_value"),
            source_train_project_key=current_pointer.get("source_train_project_key"),
            source_train_run_id=current_pointer.get("source_train_run_id"),
            source_review_decision_id=current_pointer.get("source_review_decision_id"),
            acceptance_mode=current_pointer.get("acceptance_mode"),
            holdout_bundle_count=int(current_pointer.get("holdout_bundle_count") or 0),
            skeptical_notes=tuple(current_pointer.get("skeptical_notes") or ()),
        )
        self._write_transition(transition)
        self._write_current_pointer(transition)
        return transition

    def current(self, artifact_key: str) -> AcceptedArtifactVersion | None:
        pointer = self.current_pointer(artifact_key)
        if pointer is None:
            return None
        return _artifact_from_payload(pointer["artifact"])

    def current_pointer(self, artifact_key: str) -> dict[str, Any] | None:
        path = self.current_path(artifact_key)
        if not path.exists():
            return None
        return _read_json(path)

    def load_version(self, artifact_key: str, version: str) -> AcceptedArtifactVersion:
        path = self.version_path(artifact_key, version)
        if not path.exists():
            raise ValueError(f"Unknown accepted artifact version for {artifact_key}:{version}")
        return _artifact_from_payload(_read_json(path))

    def history(self, artifact_key: str) -> list[AcceptedArtifactTransitionRecord]:
        transitions_dir = self.transitions_dir(artifact_key)
        if not transitions_dir.exists():
            return []
        records = [
            _transition_from_payload(_read_json(path))
            for path in sorted(transitions_dir.glob("*.json"))
        ]
        return records

    def artifact_dir(self, artifact_key: str) -> Path:
        safe_key = _safe_path_component(artifact_key)
        path = self.paths.artifacts_dir / safe_key
        path.mkdir(parents=True, exist_ok=True)
        return path

    def versions_dir(self, artifact_key: str) -> Path:
        path = self.artifact_dir(artifact_key) / "versions"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def transitions_dir(self, artifact_key: str) -> Path:
        path = self.artifact_dir(artifact_key) / "transitions"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def reviews_dir(self, artifact_key: str) -> Path:
        path = self.artifact_dir(artifact_key) / "reviews"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def version_path(self, artifact_key: str, version: str) -> Path:
        return self.versions_dir(artifact_key) / f"{_safe_path_component(version)}.json"

    def current_path(self, artifact_key: str) -> Path:
        return self.artifact_dir(artifact_key) / "current.json"

    def record_review(self, review: ReplyPolicyReviewArtifact) -> Path:
        path = self.reviews_dir(review.artifact_key) / (
            f"{_safe_path_component(review.review_decision_id)}.json"
        )
        self._write_json(path, dataclass_payload(review))
        return path

    def _write_transition(self, transition: AcceptedArtifactTransitionRecord) -> Path:
        timestamp = transition.promoted_at.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
        filename = (
            f"{timestamp}_{transition.action.lower()}_{_safe_path_component(transition.artifact.version)}.json"
        )
        path = self.transitions_dir(transition.artifact.artifact_key) / filename
        self._write_json(path, dataclass_payload(transition))
        return path

    def _write_current_pointer(self, transition: AcceptedArtifactTransitionRecord) -> Path:
        payload = {
            "artifact": dataclass_payload(transition.artifact),
            "action": transition.action,
            "promoted_at": transition.promoted_at,
            "previous_version": transition.previous_version,
            "reason": transition.reason,
            "contract_version": transition.contract_version,
            "scope_kind": transition.scope_kind,
            "scope_value": transition.scope_value,
            "source_train_project_key": transition.source_train_project_key,
            "source_train_run_id": transition.source_train_run_id,
            "source_review_decision_id": transition.source_review_decision_id,
            "acceptance_mode": transition.acceptance_mode,
            "holdout_bundle_count": transition.holdout_bundle_count,
            "skeptical_notes": transition.skeptical_notes,
        }
        path = self.current_path(transition.artifact.artifact_key)
        self._write_json(path, dataclass_payload(payload))
        return path

    def _write_json(self, path: Path, payload: dict[str, Any]) -> Path:
        return write_json_atomic(path, payload)


def _safe_path_component(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip())
    if not normalized:
        raise ValueError("Path component is required.")
    return normalized


def _artifact_from_payload(payload: dict[str, Any]) -> AcceptedArtifactVersion:
    return AcceptedArtifactVersion(
        artifact_key=str(payload["artifact_key"]),
        version=str(payload["version"]),
        source_project=str(payload["source_project"]),
        accepted_at=_parse_datetime(str(payload["accepted_at"])),
    )


def _transition_from_payload(payload: dict[str, Any]) -> AcceptedArtifactTransitionRecord:
    return AcceptedArtifactTransitionRecord(
        artifact=_artifact_from_payload(payload["artifact"]),
        action=str(payload["action"]),
        promoted_at=_parse_datetime(str(payload["promoted_at"])),
        previous_version=payload.get("previous_version"),
        reason=payload.get("reason"),
        contract_version=payload.get("contract_version"),
        scope_kind=payload.get("scope_kind"),
        scope_value=payload.get("scope_value"),
        source_train_project_key=payload.get("source_train_project_key"),
        source_train_run_id=payload.get("source_train_run_id"),
        source_review_decision_id=payload.get("source_review_decision_id"),
        acceptance_mode=payload.get("acceptance_mode"),
        holdout_bundle_count=int(payload.get("holdout_bundle_count", 0)),
        skeptical_notes=tuple(str(item) for item in payload.get("skeptical_notes", ())),
    )


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Registry timestamps must be timezone-aware.")
    return parsed


def _read_json(path: Path) -> dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))
