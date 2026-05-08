from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from trinity_core.ops.cycle_store import dataclass_payload
from trinity_core.ops.policy_registry import AcceptedArtifactRegistry, AcceptedArtifactRegistryPaths
from trinity_core.ops.reply_policy_gate import (
    accept_reply_behavior_policy,
    review_reply_behavior_policy,
)
from trinity_core.ops.reply_policy_store import ReplyPolicyStore, ReplyPolicyStorePaths
from trinity_core.schemas import (
    AcceptedArtifactVersion,
    BundleNegativeCandidate,
    CandidateScores,
    DraftOutcomeDisposition,
    DraftOutcomeEvent,
    PolicyResolutionSummary,
    RankedDraftSet,
    ReplyBehaviorPolicy,
    ReplyBehaviorScopeKind,
    ReplyBrevityPreferences,
    ReplyChannelRules,
    ReplyTonePreferences,
    StageEvidenceAnchor,
    ThreadMessageRole,
    ThreadMessageSnapshot,
    ThreadSnapshot,
    TrainingBundle,
    TrainingBundleType,
)


def _registry(tmp_path: Path) -> AcceptedArtifactRegistry:
    paths = AcceptedArtifactRegistryPaths(
        adapter_name="reply",
        root_dir=tmp_path / "accepted_artifacts",
        artifacts_dir=tmp_path / "accepted_artifacts" / "artifacts",
    )
    paths.root_dir.mkdir(parents=True, exist_ok=True)
    paths.artifacts_dir.mkdir(parents=True, exist_ok=True)
    return AcceptedArtifactRegistry(paths=paths)


def _store(tmp_path: Path) -> ReplyPolicyStore:
    paths = ReplyPolicyStorePaths(
        adapter_name="reply",
        root_dir=tmp_path / "accepted_reply_policies",
        scopes_dir=tmp_path / "accepted_reply_policies" / "scopes",
    )
    paths.root_dir.mkdir(parents=True, exist_ok=True)
    paths.scopes_dir.mkdir(parents=True, exist_ok=True)
    return ReplyPolicyStore(paths=paths)


def _policy(
    *,
    version: str,
    opening_style: str,
    scope_kind: ReplyBehaviorScopeKind = ReplyBehaviorScopeKind.COMPANY,
    scope_value: str | None = "00000000-0000-0000-0000-000000000001",
) -> ReplyBehaviorPolicy:
    return ReplyBehaviorPolicy(
        artifact_key="reply_behavior_policy",
        version=version,
        scope_kind=scope_kind,
        scope_value=scope_value,
        created_at=datetime(2026, 5, 3, 12, 0, tzinfo=UTC),
        source_project="train",
        tone_preferences=ReplyTonePreferences(
            target_tone="calm",
            formality="medium",
            warmth="warm",
            directness="direct",
        ),
        brevity_preferences=ReplyBrevityPreferences(
            target_length="compact",
            max_sentences=2,
            max_chars=120,
            prefer_single_paragraph=True,
        ),
        channel_rules=ReplyChannelRules(
            opening_style=opening_style,
            closing_style="no_signoff",
            emoji_policy="none",
            url_policy="avoid_urls",
            attachment_reference_policy="mention_if_used",
            newline_policy="single_paragraph",
        ),
    )


def _bundle(
    policy_version: str,
    final_text: str,
    *,
    company_id: str = "00000000-0000-0000-0000-000000000001",
) -> TrainingBundle:
    cycle_id = uuid4()
    candidate_id = uuid4()
    artifact = AcceptedArtifactVersion(
        artifact_key="reply_behavior_policy",
        version=policy_version,
        source_project="train",
        accepted_at=datetime(2026, 5, 3, 11, 0, tzinfo=UTC),
    )
    snapshot = ThreadSnapshot(
        company_id=UUID(company_id),
        thread_ref="reply:email:alice@example.com",
        channel="email",
        contact_handle="alice@example.com",
        latest_inbound_text="Can you send the update today?",
        requested_at=datetime(2026, 5, 3, 12, 0, tzinfo=UTC),
        messages=(
            ThreadMessageSnapshot(
                message_id="msg-1",
                role=ThreadMessageRole.CONTACT,
                text="Can you send the update today?",
                occurred_at=datetime(2026, 5, 3, 11, 59, tzinfo=UTC),
                channel="email",
                source="email",
                handle="alice@example.com",
            ),
        ),
    )
    from trinity_core.schemas import CandidateDraft

    ranked = RankedDraftSet(
        cycle_id=cycle_id,
        thread_ref=snapshot.thread_ref,
        channel=snapshot.channel,
        generated_at=datetime(2026, 5, 3, 12, 0, tzinfo=UTC),
        drafts=(
            CandidateDraft(
                company_id=snapshot.company_id,
                candidate_id=candidate_id,
                thread_ref=snapshot.thread_ref,
                recipient_handle=snapshot.contact_handle,
                channel=snapshot.channel,
                rank=1,
                draft_text=final_text,
                rationale="Top draft.",
                risk_flags=(),
                delivery_eligible=True,
                scores=CandidateScores(
                    impact=8,
                    confidence=7,
                    ease=7,
                    quality_score=80.0,
                    urgency_score=70.0,
                    freshness_score=70.0,
                    feedback_score=10.0,
                ),
                source_evidence_ids=(uuid4(),),
            ),
        ),
        accepted_artifact_version=artifact,
    )
    outcome = DraftOutcomeEvent(
        company_id=snapshot.company_id,
        cycle_id=cycle_id,
        thread_ref=snapshot.thread_ref,
        channel=snapshot.channel,
        candidate_id=candidate_id,
        disposition=DraftOutcomeDisposition.SENT_AS_IS,
        occurred_at=datetime(2026, 5, 3, 12, 1, tzinfo=UTC),
        original_draft_text=final_text,
        final_text=final_text,
        edit_distance=0.0,
        latency_ms=1000,
        send_result="ok",
    )
    return TrainingBundle(
        bundle_id=TrainingBundle.build_bundle_id(
            cycle_id=cycle_id,
            bundle_type=TrainingBundleType.TONE_LEARNING,
        ),
        bundle_type=TrainingBundleType.TONE_LEARNING,
        exported_at=datetime(2026, 5, 3, 12, 1, tzinfo=UTC),
        thread_snapshot=snapshot,
        evidence_units=(),
        ranked_draft_set=ranked,
        selected_candidate_id=candidate_id,
        draft_outcome_event=outcome,
        stage_evidence_anchors=(
            StageEvidenceAnchor(
                stage_name="generator",
                anchor_kind="canonical_input_reinjected",
                evidence_ids=(uuid4(),),
                content_hashes=("hash-1",),
            ),
        ),
        policy_resolution=PolicyResolutionSummary(
            requested_company_id=company_id,
            requested_channel="email",
            matched_scope_kind="company",
            matched_scope_value=company_id,
            matched_policy_version=policy_version,
            resolution_path=(f"company:{company_id}:match",),
        ),
        surfaced_negative_candidates=(
            BundleNegativeCandidate(
                candidate_id=uuid4(),
                candidate_kind="ACTION",
                state="SURFACED_NOT_SELECTED",
                rank=2,
                content="Alternative follow-up.",
                rationale="Alternative surfaced draft.",
                source_evidence_ids=(uuid4(),),
            ),
        ),
        labels={"cycle_id": str(cycle_id), "channel": "email"},
    )


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def test_accept_reply_behavior_policy_promotes_candidate(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    store = _store(tmp_path)
    policy_file = _write_json(
        tmp_path / "policy.json",
        dataclass_payload(_policy(version="v2", opening_style="brief_acknowledgment")),
    )
    bundle_file = _write_json(
        tmp_path / "bundle.json",
        dataclass_payload(_bundle("v1", "Thanks, I can send the update today.")),
    )

    result = accept_reply_behavior_policy(
        policy_file,
        bundle_files=[bundle_file],
        registry=registry,
        policy_store=store,
    )

    assert result.accepted is True
    assert result.artifact is not None
    assert result.review_decision_id is not None
    assert result.acceptance_mode == "override_no_holdout"
    assert result.holdout_bundle_count == 0
    assert registry.current("reply_behavior_policy").version == "v2"
    current_pointer = registry.current_pointer("reply_behavior_policy")
    assert current_pointer["scope_kind"] == "company"
    assert current_pointer["scope_value"] == "00000000-0000-0000-0000-000000000001"
    assert "Accepted without holdout replay" in current_pointer["skeptical_notes"][0]
    assert current_pointer["source_review_decision_id"] == result.review_decision_id
    assert current_pointer["acceptance_mode"] == "override_no_holdout"
    assert current_pointer["holdout_bundle_count"] == 0
    review_path = (
        registry.reviews_dir("reply_behavior_policy")
        / f"{result.review_decision_id}.json"
    )
    assert review_path.exists()
    assert (
        store.resolve(
            company_id="00000000-0000-0000-0000-000000000001",
            channel="email",
        ).policy.version
        == "v2"
    )


def test_accept_reply_behavior_policy_rejects_regression(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    store = _store(tmp_path)
    incumbent_policy = _policy(version="v1", opening_style="brief_acknowledgment")
    artifact = AcceptedArtifactVersion(
        artifact_key="reply_behavior_policy",
        version="v1",
        source_project="train",
        accepted_at=datetime(2026, 5, 3, 12, 0, tzinfo=UTC),
    )
    registry.promote(artifact)
    store.accept(incumbent_policy, artifact=artifact)
    policy_file = _write_json(
        tmp_path / "policy.json",
        dataclass_payload(_policy(version="v2", opening_style="no_opening")),
    )
    bundle_file = _write_json(
        tmp_path / "bundle.json",
        dataclass_payload(_bundle("v1", "Thanks, I can send the update today.")),
    )

    result = accept_reply_behavior_policy(
        policy_file,
        bundle_files=[bundle_file],
        registry=registry,
        policy_store=store,
    )

    assert result.accepted is False
    assert registry.current("reply_behavior_policy").version == "v1"
    assert (
        store.resolve(
            company_id="00000000-0000-0000-0000-000000000001",
            channel="email",
        ).policy.version
        == "v1"
    )


def test_review_reply_behavior_policy_rejects_channel_scope_from_one_company_corpus(
    tmp_path: Path,
) -> None:
    policy_file = _write_json(
        tmp_path / "policy.json",
        dataclass_payload(
            _policy(
                version="v2",
                opening_style="brief_acknowledgment",
                scope_kind=ReplyBehaviorScopeKind.CHANNEL,
                scope_value="email",
            )
        ),
    )
    bundle_file = _write_json(
        tmp_path / "bundle.json",
        dataclass_payload(_bundle("v1", "Thanks, I can send the update today.")),
    )

    result = review_reply_behavior_policy(
        policy_file,
        bundle_files=[bundle_file],
        holdout_bundle_files=[],
        require_holdout=False,
        source_train_project_key="reply-tone",
        source_train_run_id="run-22",
    )

    assert result.ready_for_acceptance is False
    assert result.acceptance_mode == "rejected"
    assert result.source_train_project_key == "reply-tone"
    assert result.source_train_run_id == "run-22"
    assert result.review_decision_id is None
    assert "one-company corpus" in result.reason


def test_accept_reply_behavior_policy_requires_holdout_when_requested(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    store = _store(tmp_path)
    policy_file = _write_json(
        tmp_path / "policy.json",
        dataclass_payload(_policy(version="v2", opening_style="brief_acknowledgment")),
    )
    bundle_file = _write_json(
        tmp_path / "bundle.json",
        dataclass_payload(_bundle("v1", "Thanks, I can send the update today.")),
    )

    result = accept_reply_behavior_policy(
        policy_file,
        bundle_files=[bundle_file],
        holdout_bundle_files=[],
        require_holdout=True,
        registry=registry,
        policy_store=store,
    )

    assert result.accepted is False
    assert result.acceptance_mode == "pending_holdout"
    assert "holdout replay is required" in result.reason


def test_review_reply_behavior_policy_uses_holdout_mode_when_present(tmp_path: Path) -> None:
    policy_file = _write_json(
        tmp_path / "policy.json",
        dataclass_payload(_policy(version="v2", opening_style="brief_acknowledgment")),
    )
    bundle_file = _write_json(
        tmp_path / "bundle.json",
        dataclass_payload(_bundle("v1", "Thanks, I can send the update today.")),
    )
    holdout_bundle_file = _write_json(
        tmp_path / "holdout.json",
        dataclass_payload(_bundle("v1", "Thanks, I can send the update today.")),
    )

    result = review_reply_behavior_policy(
        policy_file,
        bundle_files=[bundle_file],
        holdout_bundle_files=[holdout_bundle_file],
        require_holdout=True,
        source_train_project_key="reply-tone",
        source_train_run_id="run-33",
    )

    assert result.ready_for_acceptance is True
    assert result.acceptance_mode == "holdout"
    assert result.holdout_required is True
    assert result.holdout_bundle_count == 1
    assert result.source_train_project_key == "reply-tone"
    assert result.source_train_run_id == "run-33"
