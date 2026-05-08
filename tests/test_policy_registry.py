from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from trinity_core.ops import (
    AcceptedArtifactRegistry,
    AcceptedArtifactRegistryPaths,
    ReplyPolicyReviewArtifact,
)
from trinity_core.schemas import AcceptedArtifactVersion


def _registry(tmp_path: Path) -> AcceptedArtifactRegistry:
    paths = AcceptedArtifactRegistryPaths(
        adapter_name="reply",
        root_dir=tmp_path / "accepted_artifacts",
        artifacts_dir=tmp_path / "accepted_artifacts" / "artifacts",
    )
    paths.root_dir.mkdir(parents=True, exist_ok=True)
    paths.artifacts_dir.mkdir(parents=True, exist_ok=True)
    return AcceptedArtifactRegistry(paths=paths)


def _artifact(*, version: str) -> AcceptedArtifactVersion:
    return AcceptedArtifactVersion(
        artifact_key="reply_behavior_policy",
        version=version,
        source_project="train",
        accepted_at=datetime(2026, 5, 3, 12, 0, tzinfo=UTC),
    )


def test_promote_persists_immutable_version_and_current_pointer(tmp_path: Path) -> None:
    registry = _registry(tmp_path)

    transition = registry.promote(
        _artifact(version="v1"),
        reason="initial promotion",
        contract_version="trinity.reply.v1alpha1",
        scope_kind="company",
        scope_value="company-1",
        source_train_project_key="reply-tone",
        source_train_run_id="run-123",
        source_review_decision_id="review-123",
        acceptance_mode="holdout",
        holdout_bundle_count=2,
        skeptical_notes=("monitor first 20 sends",),
    )

    assert transition.action == "PROMOTE"
    assert transition.previous_version is None
    assert transition.scope_kind == "company"
    assert transition.scope_value == "company-1"
    assert transition.source_train_project_key == "reply-tone"
    assert transition.source_train_run_id == "run-123"
    assert transition.source_review_decision_id == "review-123"
    assert transition.acceptance_mode == "holdout"
    assert transition.holdout_bundle_count == 2
    assert registry.current("reply_behavior_policy").version == "v1"
    assert registry.version_path("reply_behavior_policy", "v1").exists()
    assert registry.current_path("reply_behavior_policy").exists()
    pointer = registry.current_pointer("reply_behavior_policy")
    assert pointer["contract_version"] == "trinity.reply.v1alpha1"
    assert pointer["source_review_decision_id"] == "review-123"
    assert pointer["acceptance_mode"] == "holdout"
    assert pointer["holdout_bundle_count"] == 2
    assert pointer["skeptical_notes"] == ["monitor first 20 sends"]


def test_record_review_persists_review_artifact(tmp_path: Path) -> None:
    registry = _registry(tmp_path)

    path = registry.record_review(
        ReplyPolicyReviewArtifact(
            review_decision_id="review-abc",
            reviewed_at=datetime(2026, 5, 3, 12, 0, tzinfo=UTC),
            artifact_key="reply_behavior_policy",
            candidate_version="v2",
            scope_kind="company",
            scope_value="company-1",
            ready_for_acceptance=True,
            acceptance_mode="holdout",
            proposal_bundle_count=3,
            holdout_bundle_count=1,
            candidate_score=0.9,
            incumbent_score=0.8,
            regression_delta=0.1,
            incumbent_policy_version="v1",
            source_train_project_key="reply-tone",
            source_train_run_id="run-1",
            review_reason="Review passed.",
        )
    )

    assert path.exists()


def test_promote_rejects_duplicate_version_rewrites(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.promote(_artifact(version="v1"))

    with pytest.raises(ValueError, match="already exists"):
        registry.promote(_artifact(version="v1"))


def test_rollback_restores_previous_version_in_one_step(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.promote(_artifact(version="v1"))
    registry.promote(
        AcceptedArtifactVersion(
            artifact_key="reply_behavior_policy",
            version="v2",
            source_project="train",
            accepted_at=datetime(2026, 5, 3, 13, 0, tzinfo=UTC),
        ),
        reason="new candidate accepted",
    )

    transition = registry.rollback("reply_behavior_policy", reason="regression")

    assert transition.action == "ROLLBACK"
    assert transition.artifact.version == "v1"
    assert transition.previous_version == "v2"
    assert registry.current("reply_behavior_policy").version == "v1"
    assert [record.action for record in registry.history("reply_behavior_policy")] == [
        "PROMOTE",
        "PROMOTE",
        "ROLLBACK",
    ]


def test_rollback_requires_known_target_when_no_previous_version_exists(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    registry.promote(_artifact(version="v1"))

    with pytest.raises(ValueError, match="No rollback target"):
        registry.rollback("reply_behavior_policy")
