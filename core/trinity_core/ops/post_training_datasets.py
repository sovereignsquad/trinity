"""Build and persist Trinity-owned post-training datasets from bounded bundles."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from trinity_core.adapters import normalize_adapter_name
from trinity_core.adapters.product.spot.runtime import spot_training_bundle_from_payload
from trinity_core.ops.cycle_store import dataclass_payload, write_json_atomic
from trinity_core.ops.runtime_storage import resolve_adapter_runtime_paths
from trinity_core.reply_runtime import (
    training_bundle_from_payload,
    training_bundle_type_from_payload,
)
from trinity_core.schemas import (
    BundleNegativeCandidate,
    ConfidenceBundle,
    DraftOutcomeDisposition,
    PostTrainingAnnotationStatus,
    PostTrainingCurationDecision,
    PostTrainingDataset,
    PostTrainingDatasetSplit,
    PostTrainingDatasetStatus,
    PostTrainingExample,
    PostTrainingExampleKind,
    PostTrainingMessage,
    PostTrainingPurpose,
    PostTrainingSplitAssignment,
    PostTrainingSplitKind,
    SpotReasoningCandidate,
    SpotReasoningRequest,
    SpotReasoningResult,
    SpotReviewDisposition,
    SpotReviewOutcome,
    SpotTrainingBundle,
    TrainingBundle,
)


@dataclass(frozen=True, slots=True)
class PostTrainingDatasetPaths:
    """Persistent storage paths for Trinity-owned post-training datasets."""

    adapter_name: str
    root_dir: Path
    datasets_dir: Path
    splits_dir: Path
    curation_decisions_dir: Path


def resolve_post_training_dataset_paths(adapter_name: str) -> PostTrainingDatasetPaths:
    adapter_paths = resolve_adapter_runtime_paths(
        adapter_name,
        repo_root=Path(__file__).resolve().parents[3],
    )
    root_dir = adapter_paths.root_dir / "post_training_datasets"
    datasets_dir = root_dir / "datasets"
    splits_dir = root_dir / "splits"
    curation_decisions_dir = root_dir / "curation_decisions"
    for path in (root_dir, datasets_dir, splits_dir, curation_decisions_dir):
        path.mkdir(parents=True, exist_ok=True)
    return PostTrainingDatasetPaths(
        adapter_name=adapter_paths.adapter_name,
        root_dir=root_dir,
        datasets_dir=datasets_dir,
        splits_dir=splits_dir,
        curation_decisions_dir=curation_decisions_dir,
    )


def build_post_training_dataset(
    *,
    dataset_name: str,
    adapter_name: str,
    bundle_payloads: tuple[dict[str, Any], ...],
    purposes: tuple[PostTrainingPurpose, ...] = (
        PostTrainingPurpose.SFT,
        PostTrainingPurpose.LORA,
        PostTrainingPurpose.QLORA,
    ),
    metadata: dict[str, Any] | None = None,
) -> PostTrainingDataset:
    normalized_adapter = normalize_adapter_name(adapter_name)
    examples: list[PostTrainingExample] = []
    bundle_ids: list[str] = []
    cycle_ids: list[str] = []
    for payload in bundle_payloads:
        if normalized_adapter == "reply":
            bundle = _load_reply_training_bundle(payload)
            examples.extend(_reply_examples_from_bundle(bundle))
            bundle_ids.append(str(bundle.bundle_id))
            cycle_ids.append(str(bundle.labels.get("cycle_id") or ""))
        elif normalized_adapter == "spot":
            bundle = _load_spot_training_bundle(payload)
            examples.extend(_spot_examples_from_bundle(bundle))
            bundle_ids.append(str(bundle.bundle_id))
            cycle_ids.append(str(bundle.labels.get("cycle_id") or ""))
        else:
            raise ValueError(f"Unsupported post-training dataset adapter: {normalized_adapter}")
    if not examples:
        raise ValueError("Post-training dataset export produced no examples.")
    return PostTrainingDataset(
        dataset_id=_slugify(dataset_name),
        name=dataset_name,
        adapter_name=normalized_adapter,
        created_at=datetime.now(UTC),
        status=PostTrainingDatasetStatus.CANDIDATE,
        purposes=purposes,
        examples=tuple(examples),
        metadata={
            "bundle_count": len(bundle_payloads),
            "bundle_ids": tuple(bundle_ids),
            "cycle_ids": tuple(item for item in cycle_ids if item),
            **(metadata or {}),
        },
    )


def persist_post_training_dataset(dataset: PostTrainingDataset) -> Path:
    paths = resolve_post_training_dataset_paths(dataset.adapter_name)
    path = paths.datasets_dir / f"{dataset.dataset_id}.json"
    write_json_atomic(path, dataclass_payload(dataset))
    return path


def build_post_training_dataset_split(
    dataset: PostTrainingDataset,
    *,
    split_name: str,
    validation_ratio: float = 0.1,
    holdout_ratio: float = 0.1,
    metadata: dict[str, Any] | None = None,
) -> PostTrainingDatasetSplit:
    if dataset.status is PostTrainingDatasetStatus.CANDIDATE:
        raise ValueError("Dataset must be promoted before split generation.")
    assignments: list[PostTrainingSplitAssignment] = []
    for example in dataset.examples:
        if example.annotation_status is PostTrainingAnnotationStatus.EXCLUDED:
            continue
        bucket = _split_bucket(
            example_id=example.example_id,
            validation_ratio=validation_ratio,
            holdout_ratio=holdout_ratio,
        )
        assignments.append(
            PostTrainingSplitAssignment(
                example_id=example.example_id,
                split_kind=bucket,
            )
        )
    if not assignments:
        raise ValueError("No eligible examples remained for split generation.")
    return PostTrainingDatasetSplit(
        split_id=_slugify(split_name),
        dataset_id=dataset.dataset_id,
        adapter_name=dataset.adapter_name,
        created_at=datetime.now(UTC),
        validation_ratio=validation_ratio,
        holdout_ratio=holdout_ratio,
        assignments=tuple(assignments),
        metadata=metadata or {},
    )


def persist_post_training_dataset_split(split: PostTrainingDatasetSplit) -> Path:
    paths = resolve_post_training_dataset_paths(split.adapter_name)
    path = paths.splits_dir / f"{split.split_id}.json"
    write_json_atomic(path, dataclass_payload(split))
    return path


def make_post_training_curation_decision(
    dataset: PostTrainingDataset,
    *,
    example_id: str,
    annotation_status: PostTrainingAnnotationStatus,
    rationale: str,
    metadata: dict[str, Any] | None = None,
) -> PostTrainingCurationDecision:
    if example_id not in {example.example_id for example in dataset.examples}:
        raise ValueError(f"Example not found in dataset: {example_id}")
    return PostTrainingCurationDecision(
        decision_id=f"{dataset.dataset_id}-{_slugify(example_id)}-{annotation_status.value}",
        dataset_id=dataset.dataset_id,
        adapter_name=dataset.adapter_name,
        example_id=example_id,
        annotation_status=annotation_status,
        rationale=rationale,
        reviewed_at=datetime.now(UTC),
        metadata=metadata or {},
    )


def apply_post_training_curation_decision(
    dataset: PostTrainingDataset,
    decision: PostTrainingCurationDecision,
) -> PostTrainingDataset:
    if dataset.dataset_id != decision.dataset_id:
        raise ValueError("Dataset id does not match the curation decision.")
    updated_examples = []
    matched = False
    for example in dataset.examples:
        if example.example_id != decision.example_id:
            updated_examples.append(example)
            continue
        matched = True
        updated_examples.append(
            PostTrainingExample(
                example_id=example.example_id,
                adapter_name=example.adapter_name,
                company_id=example.company_id,
                source_bundle_id=example.source_bundle_id,
                source_cycle_id=example.source_cycle_id,
                source_candidate_id=example.source_candidate_id,
                example_kind=example.example_kind,
                annotation_status=decision.annotation_status,
                task_kind=example.task_kind,
                messages=example.messages,
                target_text=example.target_text,
                annotation_rationale=decision.rationale,
                input_payload=example.input_payload,
                target_payload=example.target_payload,
                metadata=example.metadata,
                contract_version=example.contract_version,
            )
        )
    if not matched:
        raise ValueError(f"Example not found in dataset: {decision.example_id}")
    return PostTrainingDataset(
        dataset_id=dataset.dataset_id,
        name=dataset.name,
        adapter_name=dataset.adapter_name,
        created_at=dataset.created_at,
        status=dataset.status,
        purposes=dataset.purposes,
        examples=tuple(updated_examples),
        metadata=dataset.metadata,
        contract_version=dataset.contract_version,
    )


def persist_post_training_curation_decision(
    adapter_name: str,
    decision: PostTrainingCurationDecision,
) -> Path:
    paths = resolve_post_training_dataset_paths(adapter_name)
    path = paths.curation_decisions_dir / f"{decision.decision_id}.json"
    write_json_atomic(path, dataclass_payload(decision))
    return path


def load_post_training_dataset(path: str | Path) -> PostTrainingDataset:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Post-training dataset payload must be a JSON object.")
    return PostTrainingDataset(
        dataset_id=str(payload["dataset_id"]),
        name=str(payload["name"]),
        adapter_name=str(payload["adapter_name"]),
        created_at=_parse_datetime(str(payload["created_at"])),
        status=PostTrainingDatasetStatus(
            str(payload.get("status") or PostTrainingDatasetStatus.CANDIDATE.value)
        ),
        purposes=tuple(PostTrainingPurpose(str(item)) for item in payload.get("purposes", [])),
        examples=tuple(
            _post_training_example_from_payload(item)
            for item in payload.get("examples", [])
        ),
        metadata=dict(payload.get("metadata", {})),
        contract_version=str(payload.get("contract_version") or ""),
    )


def load_post_training_dataset_split(path: str | Path) -> PostTrainingDatasetSplit:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Post-training split payload must be a JSON object.")
    return PostTrainingDatasetSplit(
        split_id=str(payload["split_id"]),
        dataset_id=str(payload["dataset_id"]),
        adapter_name=str(payload["adapter_name"]),
        created_at=_parse_datetime(str(payload["created_at"])),
        validation_ratio=float(payload["validation_ratio"]),
        holdout_ratio=float(payload["holdout_ratio"]),
        assignments=tuple(
            PostTrainingSplitAssignment(
                example_id=str(item["example_id"]),
                split_kind=PostTrainingSplitKind(str(item["split_kind"])),
            )
            for item in payload.get("assignments", [])
        ),
        metadata=dict(payload.get("metadata", {})),
        contract_version=str(payload.get("contract_version") or ""),
    )


def load_post_training_curation_decision(path: str | Path) -> PostTrainingCurationDecision:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Post-training curation decision payload must be a JSON object.")
    return PostTrainingCurationDecision(
        decision_id=str(payload["decision_id"]),
        dataset_id=str(payload["dataset_id"]),
        adapter_name=str(payload["adapter_name"]),
        example_id=str(payload["example_id"]),
        annotation_status=PostTrainingAnnotationStatus(str(payload["annotation_status"])),
        rationale=str(payload["rationale"]),
        reviewed_at=_parse_datetime(str(payload["reviewed_at"])),
        metadata=dict(payload.get("metadata", {})),
        contract_version=str(payload.get("contract_version") or ""),
    )


def promote_post_training_dataset(
    dataset: PostTrainingDataset,
    *,
    status: PostTrainingDatasetStatus,
    rationale: str,
) -> PostTrainingDataset:
    if status is PostTrainingDatasetStatus.CANDIDATE:
        raise ValueError("Cannot promote a dataset back to candidate.")
    return PostTrainingDataset(
        dataset_id=dataset.dataset_id,
        name=dataset.name,
        adapter_name=dataset.adapter_name,
        created_at=dataset.created_at,
        status=status,
        purposes=dataset.purposes,
        examples=dataset.examples,
        metadata={
            **dict(dataset.metadata),
            "promotion_rationale": rationale,
            "promoted_status": status.value,
        },
        contract_version=dataset.contract_version,
    )


def summarize_post_training_dataset(dataset: PostTrainingDataset) -> dict[str, Any]:
    counts: dict[str, int] = {}
    annotation_counts: dict[str, int] = {}
    for example in dataset.examples:
        key = example.example_kind.value
        counts[key] = counts.get(key, 0) + 1
        annotation_key = example.annotation_status.value
        annotation_counts[annotation_key] = annotation_counts.get(annotation_key, 0) + 1
    return {
        "dataset_id": dataset.dataset_id,
        "adapter_name": dataset.adapter_name,
        "status": dataset.status.value,
        "example_count": len(dataset.examples),
        "purpose_count": len(dataset.purposes),
        "example_kinds": counts,
        "annotation_statuses": annotation_counts,
    }


def summarize_post_training_dataset_split(split: PostTrainingDatasetSplit) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for assignment in split.assignments:
        key = assignment.split_kind.value
        counts[key] = counts.get(key, 0) + 1
    return {
        "split_id": split.split_id,
        "dataset_id": split.dataset_id,
        "assignment_count": len(split.assignments),
        "split_counts": counts,
    }


def _load_reply_training_bundle(payload: dict[str, Any]) -> TrainingBundle:
    bundle_payload = dict(payload.get("bundle") or payload)
    bundle_type = training_bundle_type_from_payload(str(bundle_payload["bundle_type"]))
    return training_bundle_from_payload(bundle_payload, bundle_type=bundle_type)


def _load_spot_training_bundle(payload: dict[str, Any]) -> SpotTrainingBundle:
    bundle_payload = dict(payload.get("bundle") or payload)
    if "spot_review_outcomes" not in bundle_payload:
        request_payload = dict(bundle_payload["spot_reasoning_request"])
        result_payload = dict(bundle_payload["spot_reasoning_result"])
        review_payload = dict(bundle_payload["spot_review_outcome"])
        return SpotTrainingBundle(
            bundle_id=UUID(str(bundle_payload["bundle_id"])),
            bundle_type=str(bundle_payload["bundle_type"]),
            exported_at=_parse_datetime(str(bundle_payload["exported_at"])),
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
                occurred_at=None,
                metadata=dict(request_payload.get("metadata", {})),
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
                        impact=int(item.get("impact", 5)),
                        confidence=int(item.get("confidence", 5)),
                        ease=int(item.get("ease", 5)),
                        quality_score=float(item.get("quality_score", 0.0)),
                        urgency_score=float(item.get("urgency_score", 0.0)),
                        freshness_score=float(item.get("freshness_score", 0.0)),
                        feedback_score=float(item.get("feedback_score", 0.0)),
                    )
                    for item in result_payload.get("candidates", [])
                ),
                selected_candidate_key=str(result_payload["selected_candidate_key"]),
                confidence_bundle=ConfidenceBundle(
                    generator_confidence=float(
                        result_payload["confidence_bundle"]["generator_confidence"]
                    ),
                    refiner_confidence=float(
                        result_payload["confidence_bundle"]["refiner_confidence"]
                    ),
                    evaluator_confidence=float(
                        result_payload["confidence_bundle"]["evaluator_confidence"]
                    ),
                    frontier_confidence=float(
                        result_payload["confidence_bundle"]["frontier_confidence"]
                    ),
                    combined_confidence=float(
                        result_payload["confidence_bundle"]["combined_confidence"]
                    ),
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
                deeper_analysis_available=bool(
                    result_payload.get("deeper_analysis_available", True)
                ),
                escalation_recommended=bool(result_payload.get("escalation_recommended", False)),
                trace_ref=(
                    str(result_payload["trace_ref"])
                    if result_payload.get("trace_ref") is not None
                    else None
                ),
                metadata=dict(result_payload.get("metadata", {})),
            ),
            spot_review_outcome=SpotReviewOutcome(
                company_id=UUID(str(review_payload["company_id"])),
                cycle_id=UUID(str(review_payload["cycle_id"])),
                run_id=str(review_payload["run_id"]),
                row_ref=str(review_payload["row_ref"]),
                selected_candidate_key=str(review_payload["selected_candidate_key"]),
                disposition=SpotReviewDisposition(str(review_payload["disposition"])),
                final_label=str(review_payload["final_label"]),
                occurred_at=_parse_datetime(str(review_payload["occurred_at"])),
                reviewer_notes=(
                    str(review_payload["reviewer_notes"])
                    if review_payload.get("reviewer_notes") is not None
                    else None
                ),
                metadata=dict(review_payload.get("metadata", {})),
            ),
            labels={
                str(key): str(value)
                for key, value in bundle_payload.get("labels", {}).items()
            },
            contract_version=str(bundle_payload.get("contract_version") or ""),
        )
    return spot_training_bundle_from_payload(
        bundle_payload,
        bundle_type=str(bundle_payload["bundle_type"]),
    )


def _reply_examples_from_bundle(bundle: TrainingBundle) -> list[PostTrainingExample]:
    prompt_messages = _reply_messages(bundle)
    selected_draft = next(
        (
            draft
            for draft in bundle.ranked_draft_set.drafts
            if draft.candidate_id == bundle.selected_candidate_id
        ),
        None,
    )
    examples: list[PostTrainingExample] = []
    outcome = bundle.draft_outcome_event
    final_text = str(outcome.final_text or outcome.original_draft_text or "").strip() or None
    if final_text and selected_draft is not None:
        example_kind = (
            PostTrainingExampleKind.CORRECTED
            if outcome.disposition
            in (
                DraftOutcomeDisposition.EDITED_THEN_SENT,
                DraftOutcomeDisposition.MANUAL_REPLACEMENT,
            )
            else PostTrainingExampleKind.POSITIVE
        )
        examples.append(
            PostTrainingExample(
                example_id=f"reply-positive-{bundle.bundle_id}",
                adapter_name="reply",
                company_id=bundle.thread_snapshot.company_id,
                source_bundle_id=bundle.bundle_id,
                source_cycle_id=_uuid_or_none(bundle.labels.get("cycle_id")),
                source_candidate_id=selected_draft.candidate_id,
                example_kind=example_kind,
                annotation_status=PostTrainingAnnotationStatus.CURATED,
                task_kind="reply_draft",
                messages=prompt_messages,
                target_text=final_text,
                annotation_rationale="Derived from accepted runtime bundle outcome.",
                input_payload={
                    "thread_ref": bundle.thread_snapshot.thread_ref,
                    "channel": bundle.thread_snapshot.channel,
                    "latest_inbound_text": bundle.thread_snapshot.latest_inbound_text,
                    "message_count": len(bundle.thread_snapshot.messages),
                },
                target_payload={
                    "disposition": outcome.disposition.value,
                    "selected_candidate_id": str(selected_draft.candidate_id),
                    "selected_draft_text": selected_draft.draft_text,
                },
                metadata={
                    "bundle_type": bundle.bundle_type.value,
                    "channel": bundle.thread_snapshot.channel,
                },
            )
        )
    elif selected_draft is not None:
        examples.append(
            PostTrainingExample(
                example_id=f"reply-abstain-{bundle.bundle_id}",
                adapter_name="reply",
                company_id=bundle.thread_snapshot.company_id,
                source_bundle_id=bundle.bundle_id,
                source_cycle_id=_uuid_or_none(bundle.labels.get("cycle_id")),
                source_candidate_id=selected_draft.candidate_id,
                example_kind=PostTrainingExampleKind.ABSTAIN,
                annotation_status=PostTrainingAnnotationStatus.CURATED,
                task_kind="reply_draft",
                messages=prompt_messages,
                target_text=None,
                annotation_rationale="Derived from abstain or escalation runtime outcome.",
                input_payload={
                    "thread_ref": bundle.thread_snapshot.thread_ref,
                    "channel": bundle.thread_snapshot.channel,
                },
                target_payload={
                    "disposition": outcome.disposition.value,
                    "notes": str(outcome.notes or ""),
                },
                metadata={
                    "bundle_type": bundle.bundle_type.value,
                    "channel": bundle.thread_snapshot.channel,
                },
            )
        )
    for candidate in (*bundle.surfaced_negative_candidates, *bundle.filtered_negative_candidates):
        examples.append(_reply_negative_example(bundle, prompt_messages, candidate))
    return examples


def _reply_negative_example(
    bundle: TrainingBundle,
    messages: tuple[PostTrainingMessage, ...],
    candidate: BundleNegativeCandidate,
) -> PostTrainingExample:
    return PostTrainingExample(
        example_id=f"reply-negative-{bundle.bundle_id}-{candidate.candidate_id}",
        adapter_name="reply",
        company_id=bundle.thread_snapshot.company_id,
        source_bundle_id=bundle.bundle_id,
        source_cycle_id=_uuid_or_none(bundle.labels.get("cycle_id")),
        source_candidate_id=candidate.candidate_id,
        example_kind=PostTrainingExampleKind.NEGATIVE,
        annotation_status=PostTrainingAnnotationStatus.CURATED,
        task_kind="reply_draft",
        messages=messages,
        target_text=None,
        annotation_rationale="Derived from bounded negative candidate preservation.",
        input_payload={
            "thread_ref": bundle.thread_snapshot.thread_ref,
            "channel": bundle.thread_snapshot.channel,
        },
        target_payload={
            "negative_content": candidate.content,
            "negative_rationale": candidate.rationale,
            "negative_state": candidate.state,
            "delivery_eligible": candidate.delivery_eligible,
        },
        metadata={
            "bundle_type": bundle.bundle_type.value,
            "candidate_kind": candidate.candidate_kind,
        },
    )


def _spot_examples_from_bundle(bundle: SpotTrainingBundle) -> list[PostTrainingExample]:
    messages = _spot_messages(bundle)
    selected_candidate = next(
        (
            candidate
            for candidate in bundle.spot_reasoning_result.candidates
            if candidate.candidate_key == bundle.spot_reasoning_result.selected_candidate_key
        ),
        None,
    )
    review = bundle.spot_review_outcome
    selected_hint = (
        str(selected_candidate.threat_label_hint or "").strip().lower()
        if selected_candidate is not None
        else ""
    )
    final_label = review.final_label.strip().lower()
    example_kind = (
        PostTrainingExampleKind.POSITIVE
        if selected_hint and selected_hint == final_label
        else PostTrainingExampleKind.CORRECTED
    )
    examples = [
        PostTrainingExample(
            example_id=f"spot-positive-{bundle.bundle_id}",
            adapter_name="spot",
            company_id=bundle.spot_reasoning_request.company_id,
            source_bundle_id=bundle.bundle_id,
            source_cycle_id=_uuid_or_none(bundle.labels.get("cycle_id")),
            source_candidate_id=None,
            example_kind=example_kind,
            annotation_status=PostTrainingAnnotationStatus.CURATED,
            task_kind="spot_review_decision",
            messages=messages,
            target_text=review.final_label,
            annotation_rationale="Derived from persisted human review outcome.",
            input_payload={
                "row_ref": bundle.spot_reasoning_request.row_ref,
                "language": bundle.spot_reasoning_request.language,
                "message_text": bundle.spot_reasoning_request.message_text,
            },
            target_payload={
                "selected_candidate_key": bundle.spot_reasoning_result.selected_candidate_key,
                "automatic_disposition": bundle.spot_reasoning_result.automatic_disposition,
                "review_disposition": review.disposition.value,
                "reviewer_notes": str(review.reviewer_notes or ""),
            },
            metadata={"bundle_type": bundle.bundle_type},
        )
    ]
    for candidate in bundle.spot_reasoning_result.candidates:
        if candidate.candidate_key == bundle.spot_reasoning_result.selected_candidate_key:
            continue
        examples.append(
            PostTrainingExample(
                example_id=f"spot-negative-{bundle.bundle_id}-{candidate.candidate_key}",
                adapter_name="spot",
                company_id=bundle.spot_reasoning_request.company_id,
                source_bundle_id=bundle.bundle_id,
                source_cycle_id=_uuid_or_none(bundle.labels.get("cycle_id")),
                source_candidate_id=None,
                example_kind=PostTrainingExampleKind.NEGATIVE,
                annotation_status=PostTrainingAnnotationStatus.CURATED,
                task_kind="spot_review_decision",
                messages=messages,
                target_text=None,
                annotation_rationale="Derived from non-selected Spot reasoning candidates.",
                input_payload={
                    "row_ref": bundle.spot_reasoning_request.row_ref,
                    "language": bundle.spot_reasoning_request.language,
                    "message_text": bundle.spot_reasoning_request.message_text,
                },
                target_payload={
                    "rejected_candidate_key": candidate.candidate_key,
                    "rejected_interpretation": candidate.interpretation,
                    "rejected_label_hint": str(candidate.threat_label_hint or ""),
                },
                metadata={"bundle_type": bundle.bundle_type},
            )
        )
    return examples


def _reply_messages(bundle: TrainingBundle) -> tuple[PostTrainingMessage, ...]:
    lines = [
        f"Channel: {bundle.thread_snapshot.channel}",
        f"Thread Ref: {bundle.thread_snapshot.thread_ref}",
        f"Contact Handle: {bundle.thread_snapshot.contact_handle}",
        "Thread Messages:",
    ]
    for message in bundle.thread_snapshot.messages:
        lines.append(
            f"- {message.role.value} [{message.occurred_at.isoformat()}] {message.text}"
        )
    lines.append(f"Latest Inbound: {bundle.thread_snapshot.latest_inbound_text}")
    if bundle.thread_snapshot.context_snippets:
        lines.append("Context Snippets:")
        for snippet in bundle.thread_snapshot.context_snippets:
            lines.append(f"- {snippet.source}::{snippet.path} {snippet.text}")
    return (
        PostTrainingMessage(
            role="system",
            content="Draft the best operator-ready reply for this thread.",
        ),
        PostTrainingMessage(role="user", content="\n".join(lines)),
    )


def _spot_messages(bundle: SpotTrainingBundle) -> tuple[PostTrainingMessage, ...]:
    return (
        PostTrainingMessage(
            role="system",
            content=(
                "Review this content and return the correct moderation or threat label "
                "for the operator workflow."
            ),
        ),
        PostTrainingMessage(
            role="user",
            content=(
                f"Language: {bundle.spot_reasoning_request.language}\n"
                f"Row Ref: {bundle.spot_reasoning_request.row_ref}\n"
                f"Message: {bundle.spot_reasoning_request.message_text}"
            ),
        ),
    )


def _post_training_example_from_payload(payload: dict[str, Any]) -> PostTrainingExample:
    return PostTrainingExample(
        example_id=str(payload["example_id"]),
        adapter_name=str(payload["adapter_name"]),
        company_id=UUID(str(payload["company_id"])),
        source_bundle_id=UUID(str(payload["source_bundle_id"])),
        source_cycle_id=_uuid_or_none(payload.get("source_cycle_id")),
        source_candidate_id=_uuid_or_none(payload.get("source_candidate_id")),
        example_kind=PostTrainingExampleKind(str(payload["example_kind"])),
        annotation_status=PostTrainingAnnotationStatus(
            str(
                payload.get("annotation_status")
                or PostTrainingAnnotationStatus.CURATED.value
            )
        ),
        task_kind=str(payload["task_kind"]),
        messages=tuple(
            PostTrainingMessage(role=str(item["role"]), content=str(item["content"]))
            for item in payload.get("messages", [])
        ),
        target_text=(
            str(payload["target_text"]) if payload.get("target_text") is not None else None
        ),
        annotation_rationale=(
            str(payload["annotation_rationale"])
            if payload.get("annotation_rationale") is not None
            else None
        ),
        input_payload=dict(payload.get("input_payload", {})),
        target_payload=dict(payload.get("target_payload", {})),
        metadata={str(key): str(value) for key, value in payload.get("metadata", {}).items()},
        contract_version=str(payload.get("contract_version") or ""),
    )


def _slugify(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    if not slug:
        raise ValueError("dataset_name must contain at least one alphanumeric character.")
    return slug


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _uuid_or_none(value: Any) -> UUID | None:
    normalized = str(value or "").strip()
    return UUID(normalized) if normalized else None


def _split_bucket(
    *,
    example_id: str,
    validation_ratio: float,
    holdout_ratio: float,
) -> PostTrainingSplitKind:
    digest = hashlib.sha256(example_id.encode("utf-8")).hexdigest()
    normalized = int(digest[:8], 16) / float(0xFFFFFFFF)
    if normalized < holdout_ratio:
        return PostTrainingSplitKind.HOLDOUT
    if normalized < holdout_ratio + validation_ratio:
        return PostTrainingSplitKind.VALIDATION
    return PostTrainingSplitKind.TRAIN
