"""Filesystem-backed accepted reply behavior policy store."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from trinity_core.adapters import REPLY_ADAPTER_NAME, normalize_adapter_name
from trinity_core.ops.cycle_store import dataclass_payload, write_json_atomic
from trinity_core.ops.runtime_storage import resolve_adapter_runtime_paths
from trinity_core.schemas import (
    AcceptedArtifactVersion,
    PolicyResolutionCandidate,
    PolicyResolutionSummary,
    ReplyBehaviorPolicy,
    ReplyBehaviorScopeKind,
)
from trinity_core.schemas.policy import reply_behavior_policy_from_payload


@dataclass(frozen=True, slots=True)
class ReplyPolicyStorePaths:
    """Resolved storage paths for accepted reply behavior policies."""

    adapter_name: str
    root_dir: Path
    scopes_dir: Path


@dataclass(frozen=True, slots=True)
class AcceptedReplyBehaviorPolicy:
    """One accepted policy artifact with its runtime provenance."""

    artifact: AcceptedArtifactVersion
    policy: ReplyBehaviorPolicy


@dataclass(frozen=True, slots=True)
class ResolvedReplyPolicy:
    """Accepted policy plus explanation of how scope resolution selected it."""

    accepted_policy: AcceptedReplyBehaviorPolicy | None
    summary: PolicyResolutionSummary


def resolve_reply_policy_store_paths(
    adapter_name: str = REPLY_ADAPTER_NAME,
) -> ReplyPolicyStorePaths:
    adapter_paths = resolve_adapter_runtime_paths(
        adapter_name,
        repo_root=Path(__file__).resolve().parents[3],
    )
    root_dir = adapter_paths.root_dir / "accepted_reply_policies"
    scopes_dir = root_dir / "scopes"
    for path in (root_dir, scopes_dir):
        path.mkdir(parents=True, exist_ok=True)
    return ReplyPolicyStorePaths(
        adapter_name=normalize_adapter_name(adapter_name),
        root_dir=root_dir,
        scopes_dir=scopes_dir,
    )


class ReplyPolicyStore:
    """Store accepted reply behavior policies by scope with deterministic resolution."""

    def __init__(
        self,
        paths: ReplyPolicyStorePaths | None = None,
        *,
        adapter_name: str = REPLY_ADAPTER_NAME,
    ) -> None:
        self.paths = paths or resolve_reply_policy_store_paths(adapter_name)

    def accept(
        self,
        policy: ReplyBehaviorPolicy,
        *,
        artifact: AcceptedArtifactVersion,
    ) -> Path:
        if artifact.artifact_key != policy.artifact_key:
            raise ValueError("artifact_key must match policy.artifact_key.")
        if artifact.version != policy.version:
            raise ValueError("artifact.version must match policy.version.")
        version_path = self.version_path(policy.scope_kind, policy.scope_value, policy.version)
        if version_path.exists():
            raise ValueError(f"Accepted reply behavior policy already exists: {policy.version}")
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
        channel: str | None = None,
    ) -> AcceptedReplyBehaviorPolicy | None:
        return self.resolve_with_summary(company_id=company_id, channel=channel).accepted_policy

    def resolve_with_summary(
        self,
        *,
        company_id: UUID | str | None = None,
        channel: str | None = None,
    ) -> ResolvedReplyPolicy:
        normalized_company_id = _normalize_scope_value(company_id)
        normalized_channel = _normalize_scope_value(channel)
        considered: list[PolicyResolutionCandidate] = []
        resolution_path: list[str] = []
        if normalized_company_id:
            company_policy = self.current_for_scope(
                ReplyBehaviorScopeKind.COMPANY,
                normalized_company_id,
            )
            considered.append(
                PolicyResolutionCandidate(
                    scope_kind=ReplyBehaviorScopeKind.COMPANY.value,
                    scope_value=normalized_company_id,
                    matched=company_policy is not None,
                    policy_version=company_policy.policy.version if company_policy else None,
                )
            )
            resolution_path.append(
                f"company:{normalized_company_id}:{'match' if company_policy else 'miss'}"
            )
            if company_policy is not None:
                return ResolvedReplyPolicy(
                    accepted_policy=company_policy,
                    summary=PolicyResolutionSummary(
                        requested_company_id=normalized_company_id,
                        requested_channel=normalized_channel,
                        matched_scope_kind=ReplyBehaviorScopeKind.COMPANY.value,
                        matched_scope_value=normalized_company_id,
                        matched_policy_version=company_policy.policy.version,
                        resolution_path=tuple(resolution_path),
                        considered_scopes=tuple(considered),
                    ),
                )
        if normalized_channel:
            channel_policy = self.current_for_scope(
                ReplyBehaviorScopeKind.CHANNEL,
                normalized_channel,
            )
            considered.append(
                PolicyResolutionCandidate(
                    scope_kind=ReplyBehaviorScopeKind.CHANNEL.value,
                    scope_value=normalized_channel,
                    matched=channel_policy is not None,
                    policy_version=channel_policy.policy.version if channel_policy else None,
                )
            )
            resolution_path.append(
                f"channel:{normalized_channel}:{'match' if channel_policy else 'miss'}"
            )
            if channel_policy is not None:
                return ResolvedReplyPolicy(
                    accepted_policy=channel_policy,
                    summary=PolicyResolutionSummary(
                        requested_company_id=normalized_company_id,
                        requested_channel=normalized_channel,
                        matched_scope_kind=ReplyBehaviorScopeKind.CHANNEL.value,
                        matched_scope_value=normalized_channel,
                        matched_policy_version=channel_policy.policy.version,
                        resolution_path=tuple(resolution_path),
                        considered_scopes=tuple(considered),
                    ),
                )
        global_policy = self.current_for_scope(ReplyBehaviorScopeKind.GLOBAL, None)
        considered.append(
            PolicyResolutionCandidate(
                scope_kind=ReplyBehaviorScopeKind.GLOBAL.value,
                scope_value=None,
                matched=global_policy is not None,
                policy_version=global_policy.policy.version if global_policy else None,
            )
        )
        resolution_path.append(f"global:{'match' if global_policy else 'miss'}")
        return ResolvedReplyPolicy(
            accepted_policy=global_policy,
            summary=PolicyResolutionSummary(
                requested_company_id=normalized_company_id,
                requested_channel=normalized_channel,
                matched_scope_kind=(
                    ReplyBehaviorScopeKind.GLOBAL.value if global_policy is not None else None
                ),
                matched_scope_value=None,
                matched_policy_version=global_policy.policy.version if global_policy else None,
                resolution_path=tuple(resolution_path),
                considered_scopes=tuple(considered),
            ),
        )

    def load_current_policies(self) -> list[AcceptedReplyBehaviorPolicy]:
        current: list[AcceptedReplyBehaviorPolicy] = []
        for path in sorted(self.paths.scopes_dir.glob("*/current.json")):
            current.append(_accepted_policy_from_payload(_read_json(path)))
        return current

    def current_for_scope(
        self,
        scope_kind: ReplyBehaviorScopeKind,
        scope_value: str | None,
    ) -> AcceptedReplyBehaviorPolicy | None:
        path = self.current_path(scope_kind, scope_value)
        if not path.exists():
            return None
        return _accepted_policy_from_payload(_read_json(path))

    def scope_dir(
        self,
        scope_kind: ReplyBehaviorScopeKind,
        scope_value: str | None,
    ) -> Path:
        scope_key = _scope_key(scope_kind, scope_value)
        path = self.paths.scopes_dir / scope_key
        path.mkdir(parents=True, exist_ok=True)
        return path

    def version_path(
        self,
        scope_kind: ReplyBehaviorScopeKind,
        scope_value: str | None,
        version: str,
    ) -> Path:
        versions_dir = self.scope_dir(scope_kind, scope_value) / "versions"
        versions_dir.mkdir(parents=True, exist_ok=True)
        return versions_dir / f"{_safe_path_component(version)}.json"

    def current_path(
        self,
        scope_kind: ReplyBehaviorScopeKind,
        scope_value: str | None,
    ) -> Path:
        return self.scope_dir(scope_kind, scope_value) / "current.json"

    def _write_json(self, path: Path, payload: dict[str, Any]) -> Path:
        return write_json_atomic(path, payload)


def _scope_key(scope_kind: ReplyBehaviorScopeKind, scope_value: str | None) -> str:
    if scope_kind is ReplyBehaviorScopeKind.GLOBAL:
        return "global"
    if scope_kind is ReplyBehaviorScopeKind.COMPANY:
        normalized_scope = _normalize_scope_value(scope_value)
        if not normalized_scope:
            raise ValueError("Company scope requires scope_value.")
        return f"company__{_safe_path_component(normalized_scope)}"
    normalized_scope = str(scope_value or "").strip().lower()
    if not normalized_scope:
        raise ValueError("Channel scope requires scope_value.")
    return f"channel__{_safe_path_component(normalized_scope)}"


def _safe_path_component(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    if not normalized:
        raise ValueError("Path component is required.")
    return normalized


def _accepted_policy_from_payload(payload: dict[str, Any]) -> AcceptedReplyBehaviorPolicy:
    return AcceptedReplyBehaviorPolicy(
        artifact=AcceptedArtifactVersion(
            artifact_key=str(payload["artifact"]["artifact_key"]),
            version=str(payload["artifact"]["version"]),
            source_project=str(payload["artifact"]["source_project"]),
            accepted_at=_parse_datetime(str(payload["artifact"]["accepted_at"])),
        ),
        policy=reply_behavior_policy_from_payload(payload["policy"]),
    )


def _parse_datetime(value: str):
    from datetime import datetime

    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("accepted_at must be timezone-aware.")
    return parsed


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_scope_value(value: UUID | str | None) -> str | None:
    normalized = str(value or "").strip().lower()
    return normalized or None
