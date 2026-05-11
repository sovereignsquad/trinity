"""Explicit acceptance gate for Spot review policies."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from trinity_core.ops.policy_registry import AcceptedArtifactRegistry
from trinity_core.ops.spot_policy_store import SpotPolicyStore
from trinity_core.schemas import (
    AcceptedArtifactVersion,
    ConfidenceBundle,
    SpotReasoningCandidate,
    SpotReasoningRequest,
    SpotReasoningResult,
    SpotReviewDisposition,
    SpotReviewOutcome,
    SpotReviewPolicy,
    SpotReviewScopeKind,
    SpotTrainingBundle,
)
from trinity_core.schemas.spot_policy import spot_review_policy_from_payload

NEGATIVE_LABEL = "Not Antisemitic"


@dataclass(frozen=True, slots=True)
class SpotPolicyAcceptanceResult:
    accepted: bool
    artifact: AcceptedArtifactVersion | None
    policy: SpotReviewPolicy
    bundle_count: int
    candidate_score: float
    incumbent_score: float | None
    regression_delta: float | None
    holdout_bundle_count: int
    acceptance_mode: str
    source_train_project_key: str | None
    source_train_run_id: str | None
    skeptical_notes: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class SpotPolicyReviewResult:
    ready_for_acceptance: bool
    policy: SpotReviewPolicy
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
    skeptical_notes: tuple[str, ...]
    reason: str


def load_spot_review_policy_file(path: str | Path) -> SpotReviewPolicy:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return spot_review_policy_from_payload(payload)


def accept_spot_review_policy(
    policy_file: str | Path,
    *,
    bundle_files: list[str | Path],
    regression_threshold: float = 0.0,
    reason: str | None = None,
    promoted_at: datetime | None = None,
    registry: AcceptedArtifactRegistry | None = None,
    policy_store: SpotPolicyStore | None = None,
    holdout_bundle_files: list[str | Path] | None = None,
    require_holdout: bool = False,
    source_train_project_key: str | None = None,
    source_train_run_id: str | None = None,
    skeptical_notes: tuple[str, ...] = (),
) -> SpotPolicyAcceptanceResult:
    review = review_spot_review_policy(
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
    if not review.ready_for_acceptance:
        return SpotPolicyAcceptanceResult(
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
            skeptical_notes=review.skeptical_notes,
            reason=review.reason,
        )

    accepted_registry = registry or AcceptedArtifactRegistry(adapter_name="spot")
    store = policy_store or SpotPolicyStore()
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
        acceptance_mode=review.acceptance_mode,
        holdout_bundle_count=review.holdout_bundle_count,
        skeptical_notes=review.skeptical_notes,
        source_train_project_key=source_train_project_key,
        source_train_run_id=source_train_run_id,
    )
    store.accept(review.policy, artifact=artifact)
    if review.incumbent_score is None:
        disposition_reason = "Accepted as initial Spot review policy."
    else:
        disposition_reason = (
            f"Accepted: candidate score {review.candidate_score:.4f} vs incumbent "
            f"{review.incumbent_score:.4f}."
        )
    return SpotPolicyAcceptanceResult(
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
        skeptical_notes=review.skeptical_notes,
        reason=reason or disposition_reason,
    )


def review_spot_review_policy(
    policy_file: str | Path,
    *,
    bundle_files: list[str | Path],
    holdout_bundle_files: list[str | Path],
    require_holdout: bool,
    regression_threshold: float = 0.0,
    policy_store: SpotPolicyStore | None = None,
    source_train_project_key: str | None = None,
    source_train_run_id: str | None = None,
    skeptical_notes: tuple[str, ...] = (),
) -> SpotPolicyReviewResult:
    if regression_threshold < 0:
        raise ValueError("regression_threshold must be greater than or equal to 0.")
    policy = load_spot_review_policy_file(policy_file)
    bundles = _load_bundles(bundle_files)
    if not bundles:
        raise ValueError("At least one Spot training bundle is required.")
    scope_validation_error = _validate_policy_scope_against_corpus(policy, bundles)
    if scope_validation_error is not None:
        return SpotPolicyReviewResult(
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
            skeptical_notes=_normalized_notes(skeptical_notes),
            reason=scope_validation_error,
        )

    store = policy_store or SpotPolicyStore()
    incumbent = store.current_for_scope(policy.scope_kind, policy.scope_value)
    incumbent_policy_version = incumbent.policy.version if incumbent is not None else None
    candidate_score = _average_score(policy, bundles)
    incumbent_score = _average_score(incumbent.policy, bundles) if incumbent is not None else None
    regression_delta = (
        round(candidate_score - incumbent_score, 6) if incumbent_score is not None else None
    )
    if incumbent_score is not None and candidate_score + regression_threshold < incumbent_score:
        return SpotPolicyReviewResult(
            ready_for_acceptance=False,
            policy=policy,
            proposal_bundle_count=len(bundles),
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
            skeptical_notes=_normalized_notes(skeptical_notes),
            reason=(
                f"Rejected: candidate score {candidate_score:.4f} regressed below incumbent "
                f"{incumbent_score:.4f} beyond threshold {regression_threshold:.4f}."
            ),
        )

    holdout_bundles = _load_bundles(holdout_bundle_files)
    if require_holdout and not holdout_bundles:
        return SpotPolicyReviewResult(
            ready_for_acceptance=False,
            policy=policy,
            proposal_bundle_count=len(bundles),
            holdout_bundle_count=0,
            candidate_score=candidate_score,
            incumbent_score=incumbent_score,
            regression_delta=regression_delta,
            holdout_candidate_score=None,
            holdout_incumbent_score=None,
            holdout_regression_delta=None,
            incumbent_policy_version=incumbent_policy_version,
            holdout_required=True,
            acceptance_mode="pending_holdout",
            source_train_project_key=source_train_project_key,
            source_train_run_id=source_train_run_id,
            skeptical_notes=_normalized_notes(skeptical_notes),
            reason="Rejected: holdout replay is required before acceptance.",
        )

    holdout_candidate_score = None
    holdout_incumbent_score = None
    holdout_regression_delta = None
    acceptance_mode = "proposal_only"
    if holdout_bundles:
        holdout_candidate_score = _average_score(policy, holdout_bundles)
        holdout_incumbent_score = (
            _average_score(incumbent.policy, holdout_bundles) if incumbent is not None else None
        )
        holdout_regression_delta = (
            round(holdout_candidate_score - holdout_incumbent_score, 6)
            if holdout_incumbent_score is not None
            else None
        )
        acceptance_mode = "holdout"
        if (
            holdout_incumbent_score is not None
            and holdout_candidate_score + regression_threshold < holdout_incumbent_score
        ):
            return SpotPolicyReviewResult(
                ready_for_acceptance=False,
                policy=policy,
                proposal_bundle_count=len(bundles),
                holdout_bundle_count=len(holdout_bundles),
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
                skeptical_notes=_normalized_notes(skeptical_notes),
                reason=(
                    f"Rejected on holdout: candidate score {holdout_candidate_score:.4f} "
                    f"regressed below incumbent {holdout_incumbent_score:.4f}."
                ),
            )
    elif require_holdout:
        acceptance_mode = "pending_holdout"
    elif not require_holdout:
        acceptance_mode = "override_no_holdout"

    return SpotPolicyReviewResult(
        ready_for_acceptance=not require_holdout or bool(holdout_bundles),
        policy=policy,
        proposal_bundle_count=len(bundles),
        holdout_bundle_count=len(holdout_bundles),
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
        skeptical_notes=_normalized_notes(skeptical_notes),
        reason="Spot review policy passed bounded replay review.",
    )


def _load_bundles(paths: list[str | Path]) -> list[SpotTrainingBundle]:
    bundles: list[SpotTrainingBundle] = []
    for path in paths:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        bundles.append(_bundle_from_payload(payload))
    return bundles


def _average_score(policy: SpotReviewPolicy, bundles: list[SpotTrainingBundle]) -> float:
    return round(sum(_score_bundle(policy, bundle) for bundle in bundles) / len(bundles), 6)


def _score_bundle(policy: SpotReviewPolicy, bundle: SpotTrainingBundle) -> float:
    auto_approve = _would_auto_approve_negative(policy, bundle)
    outcome = bundle.spot_review_outcome
    confirmed_negative = (
        outcome.disposition.value == "CONFIRMED_NEGATIVE" and outcome.final_label == NEGATIVE_LABEL
    )
    if confirmed_negative:
        return 1.0 if auto_approve else 0.65
    return 0.0 if auto_approve else 1.0


def _would_auto_approve_negative(policy: SpotReviewPolicy, bundle: SpotTrainingBundle) -> bool:
    result = bundle.spot_reasoning_result
    if result.escalation_recommended:
        return False
    selected = next(
        candidate
        for candidate in result.candidates
        if candidate.candidate_key == result.selected_candidate_key
    )
    positive_detection = (selected.threat_label_hint or NEGATIVE_LABEL) != NEGATIVE_LABEL
    if positive_detection and policy.positive_review_required:
        return False
    if selected.candidate_key != "benign":
        return False
    return (
        result.confidence_bundle.combined_confidence >= policy.auto_approve_negative_threshold
    )


def _normalized_notes(notes: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(note).strip() for note in notes if str(note).strip())


def _validate_policy_scope_against_corpus(
    policy: SpotReviewPolicy,
    bundles: list[SpotTrainingBundle],
) -> str | None:
    company_ids = {
        str(bundle.spot_reasoning_request.company_id).strip().lower() for bundle in bundles
    }
    if len(company_ids) == 1:
        only_company = next(iter(company_ids))
        if policy.scope_kind is not SpotReviewScopeKind.COMPANY:
            return "Rejected: one-company Spot corpus must produce a company-scoped policy."
        if str(policy.scope_value or "").strip().lower() != only_company:
            return "Rejected: company-scoped Spot policy must match the one-company corpus."
        return None
    if policy.scope_kind is not SpotReviewScopeKind.GLOBAL:
        return "Rejected: multi-company Spot corpus must produce a global policy."
    return None


def _bundle_from_payload(payload: dict[str, Any]) -> SpotTrainingBundle:
    request_payload = payload["spot_reasoning_request"]
    result_payload = payload["spot_reasoning_result"]
    outcome_payload = payload["spot_review_outcome"]
    return SpotTrainingBundle(
        bundle_id=UUID(str(payload["bundle_id"])),
        bundle_type=str(payload["bundle_type"]),
        exported_at=_parse_datetime(str(payload["exported_at"])),
        spot_reasoning_request=SpotReasoningRequest(
            company_id=UUID(str(request_payload["company_id"])),
            run_id=str(request_payload["run_id"]),
            row_ref=str(request_payload["row_ref"]),
            language=str(request_payload["language"]),
            message_text=str(request_payload["message_text"]),
            source_platform=(
                str(request_payload["source_platform"])
                if request_payload.get("source_platform") is not None
                else None
            ),
            source_handle=(
                str(request_payload["source_handle"])
                if request_payload.get("source_handle") is not None
                else None
            ),
            occurred_at=_parse_datetime(
                str(request_payload.get("occurred_at") or payload["exported_at"])
            ),
            metadata={
                str(key): value
                for key, value in request_payload.get("metadata", {}).items()
            },
        ),
        spot_reasoning_result=SpotReasoningResult(
            company_id=UUID(str(result_payload["company_id"])),
            run_id=str(result_payload["run_id"]),
            row_ref=str(result_payload["row_ref"]),
            generated_at=_parse_datetime(str(result_payload["generated_at"])),
            candidates=tuple(
                SpotReasoningCandidate(
                    candidate_key=str(item["candidate_key"]),
                    interpretation=str(item["interpretation"]),
                    rationale=str(item["rationale"]),
                    threat_label_hint=(
                        str(item["threat_label_hint"])
                        if item.get("threat_label_hint") is not None
                        else None
                    ),
                    review_recommended=bool(item.get("review_recommended", False)),
                )
                for item in result_payload["candidates"]
            ),
            selected_candidate_key=str(result_payload["selected_candidate_key"]),
            confidence_bundle=ConfidenceBundle(
                generator_confidence=float(result_payload["confidence_bundle"]["generator_confidence"]),
                refiner_confidence=float(result_payload["confidence_bundle"]["refiner_confidence"]),
                evaluator_confidence=float(result_payload["confidence_bundle"]["evaluator_confidence"]),
                frontier_confidence=float(result_payload["confidence_bundle"]["frontier_confidence"]),
                combined_confidence=float(result_payload["confidence_bundle"]["combined_confidence"]),
                disagreement_severity=float(
                    result_payload["confidence_bundle"].get("disagreement_severity", 0.0)
                ),
            ),
            review_required=bool(result_payload.get("review_required", False)),
            review_reason=str(result_payload.get("review_reason") or ""),
            policy_sensitive=bool(result_payload.get("policy_sensitive", False)),
            automatic_disposition=str(
                result_payload.get("automatic_disposition") or "review_required"
            ),
            human_override_allowed=bool(result_payload.get("human_override_allowed", True)),
            deeper_analysis_available=bool(result_payload.get("deeper_analysis_available", True)),
            escalation_recommended=bool(result_payload.get("escalation_recommended", False)),
            metadata={str(key): value for key, value in result_payload.get("metadata", {}).items()},
            contract_version=str(result_payload.get("contract_version") or "trinity.spot.v1alpha1"),
        ),
        spot_review_outcome=SpotReviewOutcome(
            company_id=UUID(str(outcome_payload["company_id"])),
            cycle_id=UUID(str(outcome_payload["cycle_id"])),
            run_id=str(outcome_payload["run_id"]),
            row_ref=str(outcome_payload["row_ref"]),
            selected_candidate_key=str(outcome_payload["selected_candidate_key"]),
            disposition=SpotReviewDisposition(str(outcome_payload["disposition"])),
            final_label=str(outcome_payload["final_label"]),
            occurred_at=_parse_datetime(str(outcome_payload["occurred_at"])),
            reviewer_notes=(
                str(outcome_payload["reviewer_notes"])
                if outcome_payload.get("reviewer_notes") is not None
                else None
            ),
            metadata={
                str(key): value
                for key, value in outcome_payload.get("metadata", {}).items()
            },
            contract_version=str(
                outcome_payload.get("contract_version") or "trinity.spot.v1alpha1"
            ),
        ),
        labels={str(key): str(value) for key, value in payload.get("labels", {}).items()},
        contract_version=str(payload.get("contract_version") or "trinity.spot.v1alpha1"),
    )


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware.")
    return parsed
