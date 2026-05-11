from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from trinity_core.ops.spot_policy_store import SpotPolicyStore, SpotPolicyStorePaths
from trinity_core.schemas import (
    AcceptedArtifactVersion,
    SpotReviewPolicy,
    SpotReviewScopeKind,
)


def _store(tmp_path: Path) -> SpotPolicyStore:
    paths = SpotPolicyStorePaths(
        adapter_name="spot",
        root_dir=tmp_path / "accepted_spot_policies",
        scopes_dir=tmp_path / "accepted_spot_policies" / "scopes",
    )
    paths.root_dir.mkdir(parents=True, exist_ok=True)
    paths.scopes_dir.mkdir(parents=True, exist_ok=True)
    return SpotPolicyStore(paths=paths)


def _policy(*, version: str, threshold: float) -> SpotReviewPolicy:
    return SpotReviewPolicy(
        artifact_key="spot_review_policy",
        version=version,
        scope_kind=SpotReviewScopeKind.COMPANY,
        scope_value="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        created_at=datetime(2026, 5, 9, 12, 0, tzinfo=UTC),
        source_project="train",
        auto_approve_negative_threshold=threshold,
        positive_review_required=True,
        default_review_required=True,
    )


def test_spot_policy_store_accepts_and_loads_current_policy(tmp_path: Path) -> None:
    store = _store(tmp_path)
    policy = _policy(version="spot.v1", threshold=0.72)
    artifact = AcceptedArtifactVersion(
        artifact_key="spot_review_policy",
        version="spot.v1",
        source_project="train",
        accepted_at=datetime(2026, 5, 9, 12, 5, tzinfo=UTC),
    )

    store.accept(policy, artifact=artifact)

    current = store.current()
    assert current is None
    resolved = store.resolve(company_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert resolved is not None
    assert resolved.policy.version == "spot.v1"
    assert resolved.policy.auto_approve_negative_threshold == 0.72


def test_spot_policy_store_can_activate_previous_version(tmp_path: Path) -> None:
    store = _store(tmp_path)
    artifact_v1 = AcceptedArtifactVersion(
        artifact_key="spot_review_policy",
        version="spot.v1",
        source_project="train",
        accepted_at=datetime(2026, 5, 9, 12, 5, tzinfo=UTC),
    )
    artifact_v2 = AcceptedArtifactVersion(
        artifact_key="spot_review_policy",
        version="spot.v2",
        source_project="train",
        accepted_at=datetime(2026, 5, 9, 12, 10, tzinfo=UTC),
    )
    store.accept(_policy(version="spot.v1", threshold=0.72), artifact=artifact_v1)
    store.accept(_policy(version="spot.v2", threshold=0.9), artifact=artifact_v2)

    store.activate_version(
        SpotReviewScopeKind.COMPANY,
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "spot.v1",
    )

    resolved = store.resolve(company_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert resolved is not None
    assert resolved.policy.version == "spot.v1"
    assert resolved.policy.auto_approve_negative_threshold == 0.72
