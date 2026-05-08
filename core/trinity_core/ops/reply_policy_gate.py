"""Explicit acceptance gate for reply behavior policies."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from trinity_core.ops.policy_registry import (
    AcceptedArtifactRegistry,
    ReplyPolicyReviewArtifact,
)
from trinity_core.ops.reply_policy_store import ReplyPolicyStore
from trinity_core.reply_runtime import (
    training_bundle_from_payload,
    training_bundle_type_from_payload,
)
from trinity_core.schemas import (
    AcceptedArtifactVersion,
    ReplyBehaviorPolicy,
    ReplyBehaviorScopeKind,
    TrainingBundle,
)
from trinity_core.schemas.policy import reply_behavior_policy_from_payload


@dataclass(frozen=True, slots=True)
class ReplyPolicyAcceptanceResult:
    """One deterministic acceptance-gate decision."""

    accepted: bool
    artifact: AcceptedArtifactVersion | None
    policy: ReplyBehaviorPolicy
    bundle_count: int
    candidate_score: float
    incumbent_score: float | None
    regression_delta: float | None
    holdout_bundle_count: int
    acceptance_mode: str
    source_train_project_key: str | None
    source_train_run_id: str | None
    review_decision_id: str | None
    skeptical_notes: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class ReplyPolicyReviewResult:
    """Deterministic pre-acceptance review result for one candidate policy."""

    ready_for_acceptance: bool
    policy: ReplyBehaviorPolicy
    proposal_bundle_count: int
    holdout_bundle_count: int
    candidate_score: float
    incumbent_score: float | None
    regression_delta: float | None
    holdout_candidate_score: float | None
    holdout_incumbent_score: float | None
    holdout_regression_delta: float | None
    incumbent_policy_version: str | None
    holdout_required: bool
    acceptance_mode: str
    source_train_project_key: str | None
    source_train_run_id: str | None
    review_decision_id: str | None
    skeptical_notes: tuple[str, ...]
    reason: str


def load_reply_behavior_policy_file(path: str | Path) -> ReplyBehaviorPolicy:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return reply_behavior_policy_from_payload(payload)


def accept_reply_behavior_policy(
    policy_file: str | Path,
    *,
    bundle_files: list[str | Path],
    regression_threshold: float = 0.0,
    reason: str | None = None,
    promoted_at: datetime | None = None,
    registry: AcceptedArtifactRegistry | None = None,
    policy_store: ReplyPolicyStore | None = None,
    holdout_bundle_files: list[str | Path] | None = None,
    require_holdout: bool = False,
    source_train_project_key: str | None = None,
    source_train_run_id: str | None = None,
    skeptical_notes: tuple[str, ...] = (),
) -> ReplyPolicyAcceptanceResult:
    review = review_reply_behavior_policy(
        policy_file,
        bundle_files=bundle_files,
        holdout_bundle_files=holdout_bundle_files or [],
        require_holdout=require_holdout,
        regression_threshold=regression_threshold,
        policy_store=policy_store,
        source_train_project_key=source_train_project_key,
        source_train_run_id=source_train_run_id,
        skeptical_notes=skeptical_notes,
    )
    accepted_registry = registry or AcceptedArtifactRegistry()
    review = persist_reply_policy_review_result(accepted_registry, review)
    if not review.ready_for_acceptance:
        return ReplyPolicyAcceptanceResult(
            accepted=False,
            artifact=None,
            policy=review.policy,
            bundle_count=review.proposal_bundle_count,
            candidate_score=review.candidate_score,
            incumbent_score=review.incumbent_score,
            regression_delta=review.regression_delta,
            holdout_bundle_count=review.holdout_bundle_count,
            acceptance_mode=review.acceptance_mode,
            source_train_project_key=review.source_train_project_key,
            source_train_run_id=review.source_train_run_id,
            review_decision_id=review.review_decision_id,
            skeptical_notes=review.skeptical_notes,
            reason=review.reason,
        )

    store = policy_store or ReplyPolicyStore()
    acceptance_time = promoted_at or datetime.now(UTC)
    artifact = AcceptedArtifactVersion(
        artifact_key=review.policy.artifact_key,
        version=review.policy.version,
        source_project=review.policy.source_project,
        accepted_at=acceptance_time,
    )
    accepted_registry.promote(
        artifact,
        reason=reason or review.reason,
        promoted_at=acceptance_time,
        contract_version=review.policy.contract_version,
        scope_kind=review.policy.scope_kind.value,
        scope_value=review.policy.scope_value,
        source_train_project_key=source_train_project_key,
        source_train_run_id=source_train_run_id,
        source_review_decision_id=review.review_decision_id,
        acceptance_mode=review.acceptance_mode,
        holdout_bundle_count=review.holdout_bundle_count,
        skeptical_notes=review.skeptical_notes,
    )
    store.accept(review.policy, artifact=artifact)
    disposition_reason = "Accepted as initial policy." if review.incumbent_score is None else (
        f"Accepted: candidate score {review.candidate_score:.4f} vs incumbent "
        f"{review.incumbent_score:.4f}."
    )
    return ReplyPolicyAcceptanceResult(
        accepted=True,
        artifact=artifact,
        policy=review.policy,
        bundle_count=review.proposal_bundle_count,
        candidate_score=review.candidate_score,
        incumbent_score=review.incumbent_score,
        regression_delta=review.regression_delta,
        holdout_bundle_count=review.holdout_bundle_count,
        acceptance_mode=review.acceptance_mode,
        source_train_project_key=review.source_train_project_key,
        source_train_run_id=review.source_train_run_id,
        review_decision_id=review.review_decision_id,
        skeptical_notes=review.skeptical_notes,
        reason=reason or disposition_reason,
    )


def review_reply_behavior_policy(
    policy_file: str | Path,
    *,
    bundle_files: list[str | Path],
    holdout_bundle_files: list[str | Path],
    require_holdout: bool,
    regression_threshold: float = 0.0,
    policy_store: ReplyPolicyStore | None = None,
    source_train_project_key: str | None = None,
    source_train_run_id: str | None = None,
    skeptical_notes: tuple[str, ...] = (),
) -> ReplyPolicyReviewResult:
    if regression_threshold < 0:
        raise ValueError("regression_threshold must be greater than or equal to 0.")
    policy = load_reply_behavior_policy_file(policy_file)
    bundles = _load_bundles(bundle_files)
    scope_validation_error = _validate_policy_scope_against_corpus(policy, bundles)
    if scope_validation_error is not None:
        return ReplyPolicyReviewResult(
            ready_for_acceptance=False,
            policy=policy,
            proposal_bundle_count=len(bundles),
            holdout_bundle_count=0,
            candidate_score=0.0,
            incumbent_score=None,
            regression_delta=None,
            holdout_candidate_score=None,
            holdout_incumbent_score=None,
            holdout_regression_delta=None,
            incumbent_policy_version=None,
            holdout_required=require_holdout,
            acceptance_mode="rejected",
            source_train_project_key=source_train_project_key,
            source_train_run_id=source_train_run_id,
            review_decision_id=None,
            skeptical_notes=_normalized_notes(skeptical_notes),
            reason=scope_validation_error,
        )

    matching_bundles = _filter_matching_bundles(policy, bundles)
    if not matching_bundles:
        raise ValueError("No training bundles matched the candidate policy scope.")

    store = policy_store or ReplyPolicyStore()
    incumbent = store.current_for_scope(policy.scope_kind, policy.scope_value)
    incumbent_policy_version = incumbent.policy.version if incumbent is not None else None
    candidate_score = _average_score(policy, matching_bundles)
    incumbent_score = (
        _average_score(incumbent.policy, matching_bundles)
        if incumbent is not None
        else None
    )
    regression_delta = (
        round(candidate_score - incumbent_score, 6)
        if incumbent_score is not None
        else None
    )
    if incumbent_score is not None and candidate_score + regression_threshold < incumbent_score:
        return ReplyPolicyReviewResult(
            ready_for_acceptance=False,
            policy=policy,
            proposal_bundle_count=len(matching_bundles),
            holdout_bundle_count=0,
            candidate_score=candidate_score,
            incumbent_score=incumbent_score,
            regression_delta=regression_delta,
            holdout_candidate_score=None,
            holdout_incumbent_score=None,
            holdout_regression_delta=None,
            incumbent_policy_version=incumbent_policy_version,
            holdout_required=require_holdout,
            acceptance_mode="rejected",
            source_train_project_key=source_train_project_key,
            source_train_run_id=source_train_run_id,
            review_decision_id=None,
            skeptical_notes=_normalized_notes(skeptical_notes),
            reason=(
                f"Rejected: candidate score {candidate_score:.4f} regressed below incumbent "
                f"{incumbent_score:.4f} beyond threshold {regression_threshold:.4f}."
            ),
        )

    holdout_matching_bundles = _load_matching_holdouts(policy, holdout_bundle_files)
    if require_holdout and not holdout_matching_bundles:
        return ReplyPolicyReviewResult(
            ready_for_acceptance=False,
            policy=policy,
            proposal_bundle_count=len(matching_bundles),
            holdout_bundle_count=0,
            candidate_score=candidate_score,
            incumbent_score=incumbent_score,
            regression_delta=regression_delta,
            holdout_candidate_score=None,
            holdout_incumbent_score=None,
            holdout_regression_delta=None,
            incumbent_policy_version=incumbent_policy_version,
            holdout_required=require_holdout,
            acceptance_mode="pending_holdout",
            source_train_project_key=source_train_project_key,
            source_train_run_id=source_train_run_id,
            review_decision_id=None,
            skeptical_notes=_normalized_notes(skeptical_notes),
            reason="Rejected: holdout replay is required before acceptance.",
        )
    holdout_candidate_score = None
    holdout_incumbent_score = None
    holdout_regression_delta = None
    if holdout_matching_bundles:
        holdout_candidate_score = _average_score(policy, holdout_matching_bundles)
        holdout_incumbent_score = (
            _average_score(incumbent.policy, holdout_matching_bundles)
            if incumbent is not None
            else None
        )
        holdout_regression_delta = (
            round(holdout_candidate_score - holdout_incumbent_score, 6)
            if holdout_incumbent_score is not None
            else None
        )
        if (
            holdout_incumbent_score is not None
            and holdout_candidate_score + regression_threshold < holdout_incumbent_score
        ):
            return ReplyPolicyReviewResult(
                ready_for_acceptance=False,
                policy=policy,
                proposal_bundle_count=len(matching_bundles),
                holdout_bundle_count=len(holdout_matching_bundles),
                candidate_score=candidate_score,
                incumbent_score=incumbent_score,
                regression_delta=regression_delta,
                holdout_candidate_score=holdout_candidate_score,
                holdout_incumbent_score=holdout_incumbent_score,
                holdout_regression_delta=holdout_regression_delta,
                incumbent_policy_version=incumbent_policy_version,
                holdout_required=require_holdout,
                acceptance_mode="rejected",
                source_train_project_key=source_train_project_key,
                source_train_run_id=source_train_run_id,
                review_decision_id=None,
                skeptical_notes=_normalized_notes(skeptical_notes),
                reason=(
                    f"Rejected: holdout score {holdout_candidate_score:.4f} regressed below "
                    f"incumbent {holdout_incumbent_score:.4f} beyond threshold "
                    f"{regression_threshold:.4f}."
                ),
            )

    skeptical = list(_normalized_notes(skeptical_notes))
    acceptance_mode = "holdout" if holdout_matching_bundles else "override_no_holdout"
    if not holdout_matching_bundles:
        skeptical.append("Accepted without holdout replay; monitor early live cycles closely.")
    return ReplyPolicyReviewResult(
        ready_for_acceptance=True,
        policy=policy,
        proposal_bundle_count=len(matching_bundles),
        holdout_bundle_count=len(holdout_matching_bundles),
        candidate_score=candidate_score,
        incumbent_score=incumbent_score,
        regression_delta=regression_delta,
        holdout_candidate_score=holdout_candidate_score,
        holdout_incumbent_score=holdout_incumbent_score,
        holdout_regression_delta=holdout_regression_delta,
        incumbent_policy_version=incumbent_policy_version,
        holdout_required=require_holdout,
        acceptance_mode=acceptance_mode,
        source_train_project_key=source_train_project_key,
        source_train_run_id=source_train_run_id,
        review_decision_id=None,
        skeptical_notes=tuple(skeptical),
        reason="Review passed.",
    )


def persist_reply_policy_review_result(
    registry: AcceptedArtifactRegistry,
    review: ReplyPolicyReviewResult,
) -> ReplyPolicyReviewResult:
    if review.review_decision_id is not None:
        return review
    review_decision_id = str(uuid4())
    registry.record_review(
        ReplyPolicyReviewArtifact(
            review_decision_id=review_decision_id,
            reviewed_at=datetime.now(UTC),
            artifact_key=review.policy.artifact_key,
            candidate_version=review.policy.version,
            scope_kind=review.policy.scope_kind.value,
            scope_value=review.policy.scope_value,
            ready_for_acceptance=review.ready_for_acceptance,
            acceptance_mode=review.acceptance_mode,
            proposal_bundle_count=review.proposal_bundle_count,
            holdout_bundle_count=review.holdout_bundle_count,
            candidate_score=review.candidate_score,
            incumbent_score=review.incumbent_score,
            regression_delta=review.regression_delta,
            holdout_candidate_score=review.holdout_candidate_score,
            holdout_incumbent_score=review.holdout_incumbent_score,
            holdout_regression_delta=review.holdout_regression_delta,
            incumbent_policy_version=review.incumbent_policy_version,
            source_train_project_key=review.source_train_project_key,
            source_train_run_id=review.source_train_run_id,
            review_reason=review.reason,
            skeptical_notes=review.skeptical_notes,
        )
    )
    return ReplyPolicyReviewResult(
        ready_for_acceptance=review.ready_for_acceptance,
        policy=review.policy,
        proposal_bundle_count=review.proposal_bundle_count,
        holdout_bundle_count=review.holdout_bundle_count,
        candidate_score=review.candidate_score,
        incumbent_score=review.incumbent_score,
        regression_delta=review.regression_delta,
        holdout_candidate_score=review.holdout_candidate_score,
        holdout_incumbent_score=review.holdout_incumbent_score,
        holdout_regression_delta=review.holdout_regression_delta,
        incumbent_policy_version=review.incumbent_policy_version,
        holdout_required=review.holdout_required,
        acceptance_mode=review.acceptance_mode,
        source_train_project_key=review.source_train_project_key,
        source_train_run_id=review.source_train_run_id,
        review_decision_id=review_decision_id,
        skeptical_notes=review.skeptical_notes,
        reason=review.reason,
    )


def _load_bundles(bundle_files: list[str | Path]) -> list[TrainingBundle]:
    if not bundle_files:
        raise ValueError("At least one bundle file is required.")
    bundles = []
    for path in bundle_files:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        bundles.append(
            training_bundle_from_payload(
                payload,
                bundle_type=training_bundle_type_from_payload(payload["bundle_type"]),
            )
        )
    return bundles


def _filter_matching_bundles(
    policy: ReplyBehaviorPolicy,
    bundles: list[TrainingBundle],
) -> list[TrainingBundle]:
    if policy.scope_kind is ReplyBehaviorScopeKind.GLOBAL:
        return bundles
    if policy.scope_kind is ReplyBehaviorScopeKind.COMPANY:
        return [
            bundle
            for bundle in bundles
            if str(bundle.thread_snapshot.company_id).lower()
            == str(policy.scope_value or "").lower()
        ]
    return [
        bundle
        for bundle in bundles
        if bundle.thread_snapshot.channel.strip().lower() == str(policy.scope_value or "").lower()
    ]


def _load_matching_holdouts(
    policy: ReplyBehaviorPolicy,
    holdout_bundle_files: list[str | Path],
) -> list[TrainingBundle]:
    if not holdout_bundle_files:
        return []
    holdout_bundles = _load_bundles(holdout_bundle_files)
    return _filter_matching_bundles(policy, holdout_bundles)


def _validate_policy_scope_against_corpus(
    policy: ReplyBehaviorPolicy,
    bundles: list[TrainingBundle],
) -> str | None:
    companies = {
        str(bundle.thread_snapshot.company_id).strip().lower()
        for bundle in bundles
        if str(bundle.thread_snapshot.company_id).strip()
    }
    channels = {
        bundle.thread_snapshot.channel.strip().lower()
        for bundle in bundles
        if bundle.thread_snapshot.channel.strip()
    }
    if len(companies) == 1:
        only_company = sorted(companies)[0]
        if policy.scope_kind is not ReplyBehaviorScopeKind.COMPANY:
            return "Rejected: one-company corpus must not promote broader than company scope."
        if str(policy.scope_value or "").strip().lower() != only_company:
            return "Rejected: company-scoped policy must match the one-company corpus."
        return None
    if len(channels) == 1:
        only_channel = sorted(channels)[0]
        if policy.scope_kind is ReplyBehaviorScopeKind.GLOBAL:
            return "Rejected: one-channel corpus must not promote global scope."
        if policy.scope_kind is ReplyBehaviorScopeKind.COMPANY:
            return "Rejected: mixed-company corpus must not promote company scope."
        if str(policy.scope_value or "").strip().lower() != only_channel:
            return "Rejected: channel-scoped policy must match the one-channel corpus."
        return None
    if policy.scope_kind is not ReplyBehaviorScopeKind.GLOBAL:
        return "Rejected: mixed-channel corpus must not promote narrower than global scope."
    return None


def _normalized_notes(notes: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(note).strip() for note in notes if str(note).strip())


def _average_score(policy: ReplyBehaviorPolicy, bundles: list[TrainingBundle]) -> float:
    return round(
        sum(_score_bundle(policy, bundle) for bundle in bundles) / len(bundles),
        6,
    )


def _score_bundle(policy: ReplyBehaviorPolicy, bundle: TrainingBundle) -> float:
    text = _resolved_final_text(bundle)
    components = [
        _score_opening_style(policy, text),
        _score_closing_style(policy, text),
        _score_emoji_policy(policy, text),
        _score_url_policy(policy, text),
        _score_attachment_reference_policy(policy, text, bundle),
        _score_newline_policy(policy, text),
        _score_brevity(policy, text),
        _score_tone(policy, text),
    ]
    return round(sum(components) / len(components), 6)


def _resolved_final_text(bundle: TrainingBundle) -> str:
    final_text = str(bundle.draft_outcome_event.final_text or "").strip()
    if final_text:
        return final_text
    if bundle.selected_candidate_id is not None:
        for draft in bundle.ranked_draft_set.drafts:
            if draft.candidate_id == bundle.selected_candidate_id:
                return draft.draft_text.strip()
    return bundle.thread_snapshot.latest_inbound_text.strip()


def _score_opening_style(policy: ReplyBehaviorPolicy, text: str) -> float:
    opening = policy.channel_rules.opening_style
    lower = text.strip().lower()
    starts_ack = bool(re.match(r"^(thanks|thank you|hi|hello|got it|noted)\b", lower))
    if opening == "brief_acknowledgment":
        return 1.0 if starts_ack else 0.0
    if opening == "no_opening":
        return 1.0 if not starts_ack else 0.0
    return 0.5


def _score_closing_style(policy: ReplyBehaviorPolicy, text: str) -> float:
    closing = policy.channel_rules.closing_style
    lower = text.strip().lower()
    ends_signoff = bool(re.search(r"(best|regards|thanks|thank you)[.!]?$", lower))
    if closing == "no_signoff":
        return 1.0 if not ends_signoff else 0.0
    if closing == "short_signoff":
        return 1.0 if ends_signoff else 0.0
    return 0.5


def _score_emoji_policy(policy: ReplyBehaviorPolicy, text: str) -> float:
    if policy.channel_rules.emoji_policy != "none":
        return 0.5
    return 1.0 if not re.search(r"[\U0001F300-\U0001FAFF]", text) else 0.0


def _score_url_policy(policy: ReplyBehaviorPolicy, text: str) -> float:
    has_url = bool(re.search(r"https?://|www\.", text.lower()))
    if policy.channel_rules.url_policy == "avoid_urls":
        return 1.0 if not has_url else 0.0
    if policy.channel_rules.url_policy == "plain_urls":
        return 1.0 if not re.search(r"\[[^\]]+\]\((https?://[^)]+)\)", text) else 0.0
    return 0.5


def _score_attachment_reference_policy(
    policy: ReplyBehaviorPolicy,
    text: str,
    bundle: TrainingBundle,
) -> float:
    rule = policy.channel_rules.attachment_reference_policy
    if rule == "mention_if_used":
        return 0.5
    lower = text.lower()
    mentions_attachment = any(
        token in lower for token in ("attach", "attachment", "file", "doc", "document")
    )
    if rule == "explicit_attachment_reference":
        evidence_has_attachment = any(
            any(
                token in evidence.content_canonical.lower()
                for token in ("attach", "file", "document")
            )
            for evidence in bundle.evidence_units
        )
        return 1.0 if not evidence_has_attachment or mentions_attachment else 0.0
    return 0.5


def _score_newline_policy(policy: ReplyBehaviorPolicy, text: str) -> float:
    lines = [line for line in text.splitlines() if line.strip()]
    if policy.channel_rules.newline_policy == "single_paragraph":
        return 1.0 if len(lines) <= 1 and "\n\n" not in text else 0.0
    if policy.channel_rules.newline_policy == "compact_blocks":
        return 1.0 if len(lines) >= 1 else 0.0
    return 0.5


def _score_brevity(policy: ReplyBehaviorPolicy, text: str) -> float:
    preferences = policy.brevity_preferences
    sentences = _sentence_count(text)
    checks = []
    if preferences.max_sentences is not None:
        checks.append(1.0 if sentences <= preferences.max_sentences else 0.0)
    if preferences.max_chars is not None:
        checks.append(1.0 if len(text) <= preferences.max_chars else 0.0)
    if preferences.prefer_single_paragraph:
        non_empty_lines = [line for line in text.splitlines() if line.strip()]
        checks.append(1.0 if "\n\n" not in text and len(non_empty_lines) <= 1 else 0.0)
    target_length = preferences.target_length
    if target_length == "compact":
        checks.append(1.0 if len(text) <= 220 else 0.0)
    elif target_length == "short":
        checks.append(1.0 if len(text) <= 120 else 0.0)
    elif target_length == "detailed":
        checks.append(1.0 if len(text) >= 140 else 0.0)
    return round(sum(checks) / len(checks), 6) if checks else 0.5


def _score_tone(policy: ReplyBehaviorPolicy, text: str) -> float:
    lower = text.lower()
    checks = []
    if policy.tone_preferences.warmth == "warm":
        checks.append(
            1.0
            if any(token in lower for token in ("thanks", "thank you", "appreciate"))
            else 0.0
        )
    if policy.tone_preferences.directness == "direct":
        checks.append(
            1.0 if not any(token in lower for token in ("maybe", "perhaps", "might")) else 0.0
        )
    if policy.tone_preferences.formality == "high":
        checks.append(1.0 if not any(token in lower for token in ("hey", "ok", "okay")) else 0.0)
    for forbidden in policy.tone_preferences.forbidden_tones:
        checks.append(1.0 if forbidden.lower() not in lower else 0.0)
    return round(sum(checks) / len(checks), 6) if checks else 0.5


def _sentence_count(text: str) -> int:
    segments = [part for part in re.split(r"[.!?]+\s*", text.strip()) if part.strip()]
    return max(1, len(segments))
