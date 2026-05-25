"""Machine-local foundation policy for release gates and supported runtime seams."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from trinity_core.adapters import REPLY_ADAPTER_NAME, require_supported_adapter
from trinity_core.ops.runtime_storage import resolve_runtime_storage_paths

FOUNDATION_POLICY_CONTRACT_VERSION = "trinity_foundation_policy.v1"


@dataclass(frozen=True, slots=True)
class TrainFoundationPolicy:
    """Policy for the supported Train transport baseline."""

    default_transport: str = "cli"


@dataclass(frozen=True, slots=True)
class AdapterFoundationPolicy:
    """Supported provider contract for one adapter."""

    supported_providers: tuple[str, ...]
    preferred_live_provider: str | None = None
    release_gate_roles: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OptionalSeamPolicy:
    """Optional seam release requirements."""

    gobii_required_for_release: bool = False


@dataclass(frozen=True, slots=True)
class TrinityFoundationPolicy:
    """Full machine-local foundation policy contract for the adapters modeled today."""

    contract_version: str
    train: TrainFoundationPolicy
    reply: AdapterFoundationPolicy
    spot: AdapterFoundationPolicy
    optional_seams: OptionalSeamPolicy

    def adapter_policy(self, adapter_name: str) -> AdapterFoundationPolicy:
        normalized = require_supported_adapter(adapter_name)
        if normalized == REPLY_ADAPTER_NAME:
            return self.reply
        return self.spot


def default_foundation_policy() -> TrinityFoundationPolicy:
    return TrinityFoundationPolicy(
        contract_version=FOUNDATION_POLICY_CONTRACT_VERSION,
        train=TrainFoundationPolicy(default_transport="cli"),
        reply=AdapterFoundationPolicy(
            supported_providers=("deterministic", "mistral-cli"),
            preferred_live_provider="mistral-cli",
            release_gate_roles=("generator", "refiner", "evaluator"),
        ),
        spot=AdapterFoundationPolicy(
            supported_providers=("deterministic",),
            preferred_live_provider=None,
            release_gate_roles=(),
        ),
        optional_seams=OptionalSeamPolicy(gobii_required_for_release=False),
    )


def foundation_policy_path() -> Path:
    runtime_paths = resolve_runtime_storage_paths(repo_root=Path(__file__).resolve().parents[3])
    root_dir = runtime_paths.app_support_dir / "trinity_runtime"
    root_dir.mkdir(parents=True, exist_ok=True)
    return root_dir / "foundation_policy.json"


def load_foundation_policy() -> TrinityFoundationPolicy:
    path = foundation_policy_path()
    if not path.exists():
        return default_foundation_policy()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default_foundation_policy()
    return _foundation_policy_from_payload(payload)


def save_foundation_policy(policy: TrinityFoundationPolicy) -> Path:
    path = foundation_policy_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(policy), indent=2, sort_keys=True), encoding="utf-8")
    return path


def build_foundation_provider_alignment(
    *,
    adapter_name: str,
    provider: str,
    llm_enabled: bool,
    policy: TrinityFoundationPolicy | None = None,
) -> dict[str, object]:
    resolved_policy = policy or load_foundation_policy()
    adapter_policy = resolved_policy.adapter_policy(adapter_name)
    normalized_provider = str(provider or "").strip().lower()
    preferred_live_provider = (
        str(adapter_policy.preferred_live_provider).strip().lower()
        if adapter_policy.preferred_live_provider
        else None
    )
    supported_providers = tuple(
        str(item).strip().lower()
        for item in adapter_policy.supported_providers
        if str(item).strip()
    )
    provider_supported = normalized_provider in supported_providers
    preferred_match = (
        preferred_live_provider == normalized_provider if preferred_live_provider else True
    )
    reasons: list[str] = []
    if not provider_supported:
        reasons.append("provider_not_in_supported_set")
    if preferred_live_provider and normalized_provider != preferred_live_provider:
        reasons.append("provider_not_preferred_live_path")
    if preferred_live_provider and not llm_enabled:
        reasons.append("preferred_live_provider_not_active")
    ready = provider_supported and (
        not preferred_live_provider or normalized_provider == preferred_live_provider
    )
    return {
        "supported_providers": list(supported_providers),
        "preferred_live_provider": preferred_live_provider,
        "provider_supported": provider_supported,
        "provider_matches_preferred_live_provider": preferred_match,
        "llm_enabled": bool(llm_enabled),
        "ready": ready,
        "state": "ready" if ready else "degraded",
        "reasons": reasons,
    }


def _foundation_policy_from_payload(payload: object) -> TrinityFoundationPolicy:
    if not isinstance(payload, dict):
        return default_foundation_policy()
    default = default_foundation_policy()
    train_payload = payload.get("train", {})
    reply_payload = payload.get("reply", {})
    spot_payload = payload.get("spot", {})
    optional_payload = payload.get("optional_seams", {})
    return TrinityFoundationPolicy(
        contract_version=str(
            payload.get("contract_version") or FOUNDATION_POLICY_CONTRACT_VERSION
        ).strip(),
        train=TrainFoundationPolicy(
            default_transport=_normalized_transport(
                train_payload.get("default_transport"),
                default.train.default_transport,
            )
            if isinstance(train_payload, dict)
            else default.train.default_transport
        ),
        reply=_adapter_policy_from_payload(reply_payload, default.reply),
        spot=_adapter_policy_from_payload(spot_payload, default.spot),
        optional_seams=OptionalSeamPolicy(
            gobii_required_for_release=bool(
                optional_payload.get("gobii_required_for_release")
            )
            if isinstance(optional_payload, dict)
            else default.optional_seams.gobii_required_for_release
        ),
    )


def _adapter_policy_from_payload(
    payload: object,
    fallback: AdapterFoundationPolicy,
) -> AdapterFoundationPolicy:
    if not isinstance(payload, dict):
        return fallback
    supported_providers_payload = payload.get("supported_providers", fallback.supported_providers)
    supported_providers = tuple(
        str(item).strip().lower()
        for item in supported_providers_payload
        if str(item).strip()
    ) or fallback.supported_providers
    preferred_live_provider = str(
        payload.get("preferred_live_provider") or fallback.preferred_live_provider or ""
    ).strip().lower() or None
    release_gate_roles_payload = payload.get("release_gate_roles", fallback.release_gate_roles)
    release_gate_roles = tuple(
        str(item).strip().lower()
        for item in release_gate_roles_payload
        if str(item).strip()
    )
    return AdapterFoundationPolicy(
        supported_providers=supported_providers,
        preferred_live_provider=preferred_live_provider,
        release_gate_roles=release_gate_roles,
    )


def _normalized_transport(value: object, fallback: str) -> str:
    normalized = str(value or fallback).strip().lower()
    return normalized if normalized in {"api", "cli"} else fallback
