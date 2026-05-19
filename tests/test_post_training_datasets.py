from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from trinity_core.adapters.product.spot import SpotRuntime
from trinity_core.cli import main
from trinity_core.ops import (
    apply_post_training_curation_decision,
    build_post_training_dataset,
    build_post_training_dataset_split,
    load_post_training_curation_decision,
    load_post_training_dataset,
    make_post_training_curation_decision,
    persist_post_training_curation_decision,
    persist_post_training_dataset,
    promote_post_training_dataset,
)
from trinity_core.ops.cycle_store import RuntimeCyclePaths, RuntimeCycleStore
from trinity_core.reply_runtime import ReplyRuntime
from trinity_core.schemas import (
    DraftOutcomeDisposition,
    DraftOutcomeEvent,
    PostTrainingAnnotationStatus,
    PostTrainingDatasetStatus,
    PostTrainingExampleKind,
    PostTrainingSplitKind,
    SpotReasoningRequest,
    SpotReviewDisposition,
    SpotReviewOutcome,
    ThreadMessageRole,
    ThreadMessageSnapshot,
    ThreadSnapshot,
    TrainingBundleType,
)


def test_build_post_training_dataset_from_reply_bundle_preserves_examples(
    tmp_path: Path,
) -> None:
    runtime = ReplyRuntime(
        store=RuntimeCycleStore(
            RuntimeCyclePaths(
                adapter_name="reply",
                root_dir=tmp_path / "reply_runtime",
                cycles_dir=tmp_path / "reply_runtime" / "cycles",
                exports_dir=tmp_path / "reply_runtime" / "exports",
            )
        )
    )
    runtime.store.paths.cycles_dir.mkdir(parents=True, exist_ok=True)
    runtime.store.paths.exports_dir.mkdir(parents=True, exist_ok=True)
    snapshot = ThreadSnapshot(
        company_id=uuid4(),
        thread_ref="reply:linkedin:alice",
        channel="linkedin",
        contact_handle="linkedin://alice",
        latest_inbound_text="Can you send the updated numbers today?",
        requested_at=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
        messages=(
            ThreadMessageSnapshot(
                message_id="msg-1",
                role=ThreadMessageRole.CONTACT,
                text="Can you send the updated numbers today?",
                occurred_at=datetime(2026, 5, 13, 11, 59, tzinfo=UTC),
                channel="linkedin",
                source="linkedin",
                handle="linkedin://alice",
            ),
        ),
    )
    ranked = runtime.suggest(snapshot)
    runtime.record_outcome(
        DraftOutcomeEvent(
            company_id=snapshot.company_id,
            cycle_id=ranked.cycle_id,
            thread_ref=snapshot.thread_ref,
            channel=snapshot.channel,
            candidate_id=ranked.drafts[0].candidate_id,
            disposition=DraftOutcomeDisposition.EDITED_THEN_SENT,
            occurred_at=datetime(2026, 5, 13, 12, 1, tzinfo=UTC),
            original_draft_text=ranked.drafts[0].draft_text,
            final_text="Here is the corrected human-approved reply.",
            edit_distance=0.2,
            latency_ms=500,
            send_result="ok",
        )
    )
    exported = runtime.export_training_bundle(
        ranked.cycle_id,
        bundle_type=TrainingBundleType.TONE_LEARNING,
    )

    dataset = build_post_training_dataset(
        dataset_name="Reply Local Learning",
        adapter_name="reply",
        bundle_payloads=(exported["bundle"],),
    )

    assert dataset.adapter_name == "reply"
    assert dataset.status == PostTrainingDatasetStatus.CANDIDATE
    assert len(dataset.examples) >= 3
    assert dataset.examples[0].example_kind == PostTrainingExampleKind.CORRECTED
    assert dataset.examples[0].annotation_status == PostTrainingAnnotationStatus.CURATED
    assert dataset.examples[0].target_text == "Here is the corrected human-approved reply."
    assert any(
        example.example_kind == PostTrainingExampleKind.NEGATIVE
        for example in dataset.examples
    )


def test_build_post_training_dataset_from_spot_bundle_preserves_examples(
    tmp_path: Path,
) -> None:
    runtime = SpotRuntime(
        store=RuntimeCycleStore(
            RuntimeCyclePaths(
                adapter_name="spot",
                root_dir=tmp_path / "spot_runtime",
                cycles_dir=tmp_path / "spot_runtime" / "cycles",
                exports_dir=tmp_path / "spot_runtime" / "exports",
            )
        )
    )
    request = SpotReasoningRequest(
        company_id=uuid4(),
        run_id="run-1",
        row_ref="sheet1:42",
        language="en",
        message_text="We should boycott them everywhere.",
        occurred_at=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )
    result = runtime.reason_spot(request)
    assert result.trace_ref is not None
    cycle_payload = json.loads(Path(result.trace_ref).read_text(encoding="utf-8"))
    runtime.record_review_outcome(
        SpotReviewOutcome(
                company_id=request.company_id,
                cycle_id=UUID(str(cycle_payload["cycle_id"])),
                run_id=request.run_id,
                row_ref=request.row_ref,
                selected_candidate_key=result.selected_candidate_key,
                disposition=SpotReviewDisposition.CORRECTED,
                final_label="review_required",
                occurred_at=datetime(2026, 5, 13, 12, 1, tzinfo=UTC),
            )
    )
    exported = runtime.export_training_bundle(
        cycle_payload["cycle_id"],
        bundle_type="spot-review-policy-learning",
    )

    dataset = build_post_training_dataset(
        dataset_name="Spot Local Learning",
        adapter_name="spot",
        bundle_payloads=(exported["bundle"],),
    )

    assert dataset.adapter_name == "spot"
    assert dataset.status == PostTrainingDatasetStatus.CANDIDATE
    assert dataset.examples[0].target_text == "review_required"
    assert dataset.examples[0].annotation_status == PostTrainingAnnotationStatus.CURATED
    assert any(
        example.example_kind == PostTrainingExampleKind.NEGATIVE
        for example in dataset.examples
    )


def test_cli_can_export_post_training_dataset_from_bundle_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime = ReplyRuntime(
        store=RuntimeCycleStore(
            RuntimeCyclePaths(
                adapter_name="reply",
                root_dir=tmp_path / "reply_runtime",
                cycles_dir=tmp_path / "reply_runtime" / "cycles",
                exports_dir=tmp_path / "reply_runtime" / "exports",
            )
        )
    )
    runtime.store.paths.cycles_dir.mkdir(parents=True, exist_ok=True)
    runtime.store.paths.exports_dir.mkdir(parents=True, exist_ok=True)
    snapshot = ThreadSnapshot(
        company_id=uuid4(),
        thread_ref="reply:imessage:bob",
        channel="imessage",
        contact_handle="+36301234567",
        latest_inbound_text="Do you have the file?",
        requested_at=datetime(2026, 5, 13, 13, 0, tzinfo=UTC),
        messages=(
            ThreadMessageSnapshot(
                message_id="msg-1",
                role=ThreadMessageRole.CONTACT,
                text="Do you have the file?",
                occurred_at=datetime(2026, 5, 13, 12, 59, tzinfo=UTC),
                channel="imessage",
                source="imessage",
                handle="+36301234567",
            ),
        ),
    )
    ranked = runtime.suggest(snapshot)
    runtime.record_outcome(
        DraftOutcomeEvent(
            company_id=snapshot.company_id,
            cycle_id=ranked.cycle_id,
            thread_ref=snapshot.thread_ref,
            channel=snapshot.channel,
            candidate_id=ranked.drafts[0].candidate_id,
            disposition=DraftOutcomeDisposition.SENT_AS_IS,
            occurred_at=datetime(2026, 5, 13, 13, 1, tzinfo=UTC),
            original_draft_text=ranked.drafts[0].draft_text,
            final_text=ranked.drafts[0].draft_text,
            edit_distance=0.0,
            latency_ms=300,
            send_result="ok",
        )
    )
    exported = runtime.export_training_bundle(
        ranked.cycle_id,
        bundle_type=TrainingBundleType.TONE_LEARNING,
    )
    bundle_file = tmp_path / "bundle.json"
    bundle_file.write_text(json.dumps(exported["bundle"]), encoding="utf-8")
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))

    assert (
        main(
            [
                "export-post-training-dataset",
                "--adapter",
                "reply",
                "--dataset-name",
                "CLI Reply Learning",
                "--bundle-file",
                str(bundle_file),
            ]
        )
        == 0
    )

    dataset_path = (
        tmp_path
        / "app_support"
        / "trinity_runtime"
        / "adapters"
        / "reply"
        / "post_training_datasets"
        / "datasets"
        / "cli-reply-learning.json"
    )
    dataset = load_post_training_dataset(dataset_path)
    assert dataset.dataset_id == "cli-reply-learning"
    assert dataset.status == PostTrainingDatasetStatus.CANDIDATE
    assert dataset.examples[0].target_text is not None
    persisted = persist_post_training_dataset(dataset)
    assert persisted.exists()


def test_curation_decision_and_promotion_update_dataset_lifecycle(
    tmp_path: Path,
) -> None:
    runtime = ReplyRuntime(
        store=RuntimeCycleStore(
            RuntimeCyclePaths(
                adapter_name="reply",
                root_dir=tmp_path / "reply_runtime",
                cycles_dir=tmp_path / "reply_runtime" / "cycles",
                exports_dir=tmp_path / "reply_runtime" / "exports",
            )
        )
    )
    runtime.store.paths.cycles_dir.mkdir(parents=True, exist_ok=True)
    runtime.store.paths.exports_dir.mkdir(parents=True, exist_ok=True)
    snapshot = ThreadSnapshot(
        company_id=uuid4(),
        thread_ref="reply:slack:ops",
        channel="slack",
        contact_handle="slack://ops",
        latest_inbound_text="Please send the recap.",
        requested_at=datetime(2026, 5, 13, 14, 0, tzinfo=UTC),
        messages=(
            ThreadMessageSnapshot(
                message_id="msg-1",
                role=ThreadMessageRole.CONTACT,
                text="Please send the recap.",
                occurred_at=datetime(2026, 5, 13, 13, 59, tzinfo=UTC),
                channel="slack",
                source="slack",
                handle="slack://ops",
            ),
        ),
    )
    ranked = runtime.suggest(snapshot)
    runtime.record_outcome(
        DraftOutcomeEvent(
            company_id=snapshot.company_id,
            cycle_id=ranked.cycle_id,
            thread_ref=snapshot.thread_ref,
            channel=snapshot.channel,
            candidate_id=ranked.drafts[0].candidate_id,
            disposition=DraftOutcomeDisposition.SENT_AS_IS,
            occurred_at=datetime(2026, 5, 13, 14, 1, tzinfo=UTC),
            original_draft_text=ranked.drafts[0].draft_text,
            final_text=ranked.drafts[0].draft_text,
            edit_distance=0.0,
            latency_ms=250,
            send_result="ok",
        )
    )
    exported = runtime.export_training_bundle(
        ranked.cycle_id,
        bundle_type=TrainingBundleType.TONE_LEARNING,
    )
    dataset = build_post_training_dataset(
        dataset_name="Reply Curation Lifecycle",
        adapter_name="reply",
        bundle_payloads=(exported["bundle"],),
    )
    negative_example = next(
        example
        for example in dataset.examples
        if example.example_kind == PostTrainingExampleKind.NEGATIVE
    )
    decision = make_post_training_curation_decision(
        dataset,
        example_id=negative_example.example_id,
        annotation_status=PostTrainingAnnotationStatus.EXCLUDED,
        rationale="Operator excluded this negative sample from the first training cut.",
    )
    updated_dataset = apply_post_training_curation_decision(dataset, decision)
    decision_path = persist_post_training_curation_decision("reply", decision)
    loaded_decision = load_post_training_curation_decision(decision_path)
    promoted = promote_post_training_dataset(
        updated_dataset,
        status=PostTrainingDatasetStatus.CURATED,
        rationale="Operator approved the current dataset for split generation.",
    )

    assert loaded_decision.annotation_status == PostTrainingAnnotationStatus.EXCLUDED
    excluded_example = next(
        example
        for example in promoted.examples
        if example.example_id == negative_example.example_id
    )
    assert excluded_example.annotation_status == PostTrainingAnnotationStatus.EXCLUDED
    assert promoted.status == PostTrainingDatasetStatus.CURATED


def test_build_post_training_split_is_deterministic_and_skips_excluded_examples(
    tmp_path: Path,
) -> None:
    runtime = ReplyRuntime(
        store=RuntimeCycleStore(
            RuntimeCyclePaths(
                adapter_name="reply",
                root_dir=tmp_path / "reply_runtime",
                cycles_dir=tmp_path / "reply_runtime" / "cycles",
                exports_dir=tmp_path / "reply_runtime" / "exports",
            )
        )
    )
    runtime.store.paths.cycles_dir.mkdir(parents=True, exist_ok=True)
    runtime.store.paths.exports_dir.mkdir(parents=True, exist_ok=True)
    snapshot = ThreadSnapshot(
        company_id=uuid4(),
        thread_ref="reply:email:delta",
        channel="email",
        contact_handle="delta@example.com",
        latest_inbound_text="Please confirm the timeline.",
        requested_at=datetime(2026, 5, 13, 15, 0, tzinfo=UTC),
        messages=(
            ThreadMessageSnapshot(
                message_id="msg-1",
                role=ThreadMessageRole.CONTACT,
                text="Please confirm the timeline.",
                occurred_at=datetime(2026, 5, 13, 14, 59, tzinfo=UTC),
                channel="email",
                source="email",
                handle="delta@example.com",
            ),
        ),
    )
    ranked = runtime.suggest(snapshot)
    runtime.record_outcome(
        DraftOutcomeEvent(
            company_id=snapshot.company_id,
            cycle_id=ranked.cycle_id,
            thread_ref=snapshot.thread_ref,
            channel=snapshot.channel,
            candidate_id=ranked.drafts[0].candidate_id,
            disposition=DraftOutcomeDisposition.SENT_AS_IS,
            occurred_at=datetime(2026, 5, 13, 15, 1, tzinfo=UTC),
            original_draft_text=ranked.drafts[0].draft_text,
            final_text=ranked.drafts[0].draft_text,
            edit_distance=0.0,
            latency_ms=350,
            send_result="ok",
        )
    )
    exported = runtime.export_training_bundle(
        ranked.cycle_id,
        bundle_type=TrainingBundleType.TONE_LEARNING,
    )
    dataset = build_post_training_dataset(
        dataset_name="Reply Split Learning",
        adapter_name="reply",
        bundle_payloads=(exported["bundle"],),
    )
    first_example = dataset.examples[0]
    excluded_dataset = type(dataset)(
        dataset_id=dataset.dataset_id,
        name=dataset.name,
        adapter_name=dataset.adapter_name,
        created_at=dataset.created_at,
        status=dataset.status,
        purposes=dataset.purposes,
        examples=tuple(
            type(example)(
                example_id=example.example_id,
                adapter_name=example.adapter_name,
                company_id=example.company_id,
                source_bundle_id=example.source_bundle_id,
                source_cycle_id=example.source_cycle_id,
                source_candidate_id=example.source_candidate_id,
                example_kind=example.example_kind,
                annotation_status=(
                    PostTrainingAnnotationStatus.EXCLUDED
                    if example.example_id == first_example.example_id
                    else example.annotation_status
                ),
                task_kind=example.task_kind,
                messages=example.messages,
                target_text=example.target_text,
                annotation_rationale=example.annotation_rationale,
                input_payload=example.input_payload,
                target_payload=example.target_payload,
                metadata=example.metadata,
                contract_version=example.contract_version,
            )
            for example in dataset.examples
        ),
        metadata=dataset.metadata,
        contract_version=dataset.contract_version,
    )
    curated_dataset = promote_post_training_dataset(
        excluded_dataset,
        status=PostTrainingDatasetStatus.CURATED,
        rationale="Approved for split generation.",
    )
    split_a = build_post_training_dataset_split(
        curated_dataset,
        split_name="Reply Split A",
        validation_ratio=0.2,
        holdout_ratio=0.2,
    )
    split_b = build_post_training_dataset_split(
        curated_dataset,
        split_name="Reply Split B",
        validation_ratio=0.2,
        holdout_ratio=0.2,
    )
    assert split_a.assignments == split_b.assignments
    assert all(
        assignment.example_id != first_example.example_id for assignment in split_a.assignments
    )
    assert all(
        assignment.split_kind
        in (
            PostTrainingSplitKind.TRAIN,
            PostTrainingSplitKind.VALIDATION,
            PostTrainingSplitKind.HOLDOUT,
        )
        for assignment in split_a.assignments
    )
