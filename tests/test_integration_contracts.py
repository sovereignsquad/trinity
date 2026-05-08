from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from trinity_core.model_config import TrinityReplyModelConfig, TrinityRoleRoute
from trinity_core.ops.cycle_store import RuntimeCyclePaths, RuntimeCycleStore
from trinity_core.ops.reply_policy_store import ReplyPolicyStore, ReplyPolicyStorePaths
from trinity_core.reply_runtime import ReplyRuntime
from trinity_core.schemas import (
    AcceptedArtifactVersion,
    CandidateLineage,
    CandidateRecord,
    CandidateScores,
    CandidateState,
    CandidateType,
    DraftOutcomeDisposition,
    DraftOutcomeEvent,
    RankedDraftSet,
    ReplyBehaviorPolicy,
    ReplyBehaviorScopeKind,
    ReplyBrevityPreferences,
    ReplyChannelRules,
    ReplyDraftCandidate,
    ReplyEvidenceEnvelope,
    ReplyFeedbackDisposition,
    ReplyFeedbackEvent,
    ReplyTonePreferences,
    ThreadContextSnippet,
    ThreadMessageRole,
    ThreadMessageSnapshot,
    ThreadSnapshot,
    TrainingBundleType,
)


def test_reply_draft_candidate_can_be_built_from_runtime_candidate() -> None:
    company_id = uuid4()
    evidence_id = uuid4()
    candidate = CandidateRecord(
        company_id=company_id,
        candidate_id=uuid4(),
        candidate_type=CandidateType.ACTION,
        state=CandidateState.EVALUATED,
        title="Draft recovery note",
        content="Send a concise recovery note to the stakeholder.",
        lineage=CandidateLineage(version_family_id=uuid4(), source_evidence_ids=(evidence_id,)),
        scores=CandidateScores(
            impact=8,
            confidence=7,
            ease=6,
            quality_score=84.0,
            urgency_score=80.0,
            freshness_score=79.0,
            feedback_score=25.0,
        ),
        created_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        evaluated_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        evaluation_reason="Best current action for the conversation.",
    )

    draft = ReplyDraftCandidate.from_candidate_record(
        candidate,
        conversation_ref="reply:linkedin:alice",
        recipient_handle="linkedin://alice",
        channel="linkedin",
    )

    assert draft.conversation_ref == "reply:linkedin:alice"
    assert draft.rationale == "Best current action for the conversation."
    assert draft.source_evidence_ids == (evidence_id,)


def test_reply_evidence_envelope_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ReplyEvidenceEnvelope(
            company_id=uuid4(),
            conversation_ref="reply:imessage:bob",
            channel="imessage",
            sender_handle="+36301234567",
            message_text="Need the updated numbers.",
            occurred_at=datetime(2026, 5, 1, 12, 0),
        )


def test_reply_feedback_event_requires_edited_text_for_edited_disposition() -> None:
    with pytest.raises(ValueError, match="edited_text"):
        ReplyFeedbackEvent(
            company_id=uuid4(),
            candidate_id=uuid4(),
            conversation_ref="reply:whatsapp:carol",
            disposition=ReplyFeedbackDisposition.EDITED,
            occurred_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        )


def test_thread_snapshot_requires_timezone_aware_requested_at() -> None:
    with pytest.raises(ValueError, match="requested_at"):
        ThreadSnapshot(
            company_id=uuid4(),
            thread_ref="reply:linkedin:alice",
            channel="linkedin",
            contact_handle="linkedin://alice",
            latest_inbound_text="Can you send the update?",
            requested_at=datetime(2026, 5, 1, 12, 0),
        )


def test_ranked_draft_set_requires_non_empty_drafts() -> None:
    with pytest.raises(ValueError, match="drafts"):
        RankedDraftSet(
            cycle_id=uuid4(),
            thread_ref="reply:linkedin:alice",
            channel="linkedin",
            generated_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
            drafts=(),
            accepted_artifact_version=AcceptedArtifactVersion(
                artifact_key="reply_ranker_policy",
                version="v0",
                source_project="trinity",
                accepted_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
            ),
        )


def test_reply_runtime_persists_cycle_and_feedback(tmp_path: Path) -> None:
    runtime = ReplyRuntime(
        store=RuntimeCycleStore(
            RuntimeCyclePaths(
                adapter_name="reply",
                root_dir=tmp_path,
                cycles_dir=tmp_path / "cycles",
                exports_dir=tmp_path / "exports",
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
        requested_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        messages=(
            ThreadMessageSnapshot(
                message_id="msg-1",
                role=ThreadMessageRole.CONTACT,
                text="Can you send the updated numbers today?",
                occurred_at=datetime(2026, 5, 1, 11, 59, tzinfo=UTC),
                channel="linkedin",
                source="linkedin",
                handle="linkedin://alice",
            ),
        ),
        context_snippets=(
            ThreadContextSnippet(
                source="vector-store",
                path="snippet://alice/1",
                text="Alice asked for the Q2 pricing table.",
            ),
        ),
    )

    ranked = runtime.suggest(snapshot)

    assert len(ranked.drafts) == 3
    assert runtime.store.cycle_path(ranked.cycle_id).exists()
    assert runtime.store.export_path(ranked.cycle_id).exists()
    assert runtime.store.cycle_path(ranked.cycle_id, snapshot.company_id).exists()
    assert runtime.store.export_path(ranked.cycle_id, snapshot.company_id).exists()

    outcome = DraftOutcomeEvent(
        company_id=snapshot.company_id,
        cycle_id=ranked.cycle_id,
        thread_ref=snapshot.thread_ref,
        channel=snapshot.channel,
        candidate_id=ranked.drafts[0].candidate_id,
        disposition=DraftOutcomeDisposition.SENT_AS_IS,
        occurred_at=datetime(2026, 5, 1, 12, 1, tzinfo=UTC),
        original_draft_text=ranked.drafts[0].draft_text,
        final_text=ranked.drafts[0].draft_text,
        edit_distance=0.0,
        latency_ms=1000,
        send_result="ok",
    )

    result = runtime.record_outcome(outcome)

    assert result["status"] == "ok"
    payload = runtime.store.load_cycle(ranked.cycle_id)
    assert payload["feedback_events"][0]["disposition"] == DraftOutcomeDisposition.SENT_AS_IS.value
    assert payload["frontier_candidate_ids"]
    assert payload["accepted_artifact_version"]["artifact_key"] == "reply_ranker_policy"
    assert payload["policy_resolution"]["matched_policy_version"] == "reply_ranker_policy.v0"
    assert payload["policy_resolution"]["matched_scope_kind"] == "builtin_runtime_default"
    assert [anchor["stage_name"] for anchor in payload["stage_evidence_anchors"]] == [
        "generator",
        "refiner",
        "evaluator",
    ]
    assert all(
        anchor["anchor_kind"] == "canonical_input_reinjected"
        for anchor in payload["stage_evidence_anchors"]
    )


def test_reply_runtime_supports_cold_start_thread_without_history(tmp_path: Path) -> None:
    runtime = ReplyRuntime(
        store=RuntimeCycleStore(
            RuntimeCyclePaths(
                adapter_name="reply",
                root_dir=tmp_path,
                cycles_dir=tmp_path / "cycles",
                exports_dir=tmp_path / "exports",
            )
        )
    )
    runtime.store.paths.cycles_dir.mkdir(parents=True, exist_ok=True)
    runtime.store.paths.exports_dir.mkdir(parents=True, exist_ok=True)
    snapshot = ThreadSnapshot(
        company_id=uuid4(),
        thread_ref="reply:email:alice@example.com",
        channel="email",
        contact_handle="alice@example.com",
        latest_inbound_text="Can you send me the update today?",
        requested_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        messages=(
            ThreadMessageSnapshot(
                message_id="latest-inbound",
                role=ThreadMessageRole.CONTACT,
                text="Can you send me the update today?",
                occurred_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
                channel="email",
                source="email",
                handle="alice@example.com",
            ),
        ),
    )

    ranked = runtime.suggest(snapshot)

    assert len(ranked.drafts) == 3
    assert all(draft.draft_text for draft in ranked.drafts)


def test_reply_runtime_exports_training_bundle_from_terminal_outcome(tmp_path: Path) -> None:
    runtime = ReplyRuntime(
        store=RuntimeCycleStore(
            RuntimeCyclePaths(
                adapter_name="reply",
                root_dir=tmp_path,
                cycles_dir=tmp_path / "cycles",
                exports_dir=tmp_path / "exports",
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
        requested_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        messages=(
            ThreadMessageSnapshot(
                message_id="msg-1",
                role=ThreadMessageRole.CONTACT,
                text="Can you send the updated numbers today?",
                occurred_at=datetime(2026, 5, 1, 11, 59, tzinfo=UTC),
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
            disposition=DraftOutcomeDisposition.SENT_AS_IS,
            occurred_at=datetime(2026, 5, 1, 12, 1, tzinfo=UTC),
            original_draft_text=ranked.drafts[0].draft_text,
            final_text=ranked.drafts[0].draft_text,
            edit_distance=0.0,
            latency_ms=1000,
            send_result="ok",
        )
    )

    exported = runtime.export_training_bundle(
        ranked.cycle_id,
        bundle_type=TrainingBundleType.TONE_LEARNING,
    )

    assert exported["bundle"]["bundle_type"] == TrainingBundleType.TONE_LEARNING.value
    assert exported["bundle"]["draft_outcome_event"]["disposition"] == "SENT_AS_IS"
    assert exported["bundle"]["selected_candidate_id"] == str(ranked.drafts[0].candidate_id)
    assert exported["bundle"]["ranked_draft_set"]["accepted_artifact_version"]["artifact_key"] == (
        "reply_ranker_policy"
    )
    assert exported["bundle"]["stage_evidence_anchors"]
    assert (
        exported["bundle"]["policy_resolution"]["matched_policy_version"]
        == "reply_ranker_policy.v0"
    )
    assert len(exported["bundle"]["surfaced_negative_candidates"]) == 2
    assert "filtered_negative_candidates" in exported["bundle"]
    assert Path(exported["bundle_path"]).exists()


def test_reply_runtime_applies_accepted_channel_policy_and_provenance(tmp_path: Path) -> None:
    cycle_store = RuntimeCycleStore(
        RuntimeCyclePaths(
            adapter_name="reply",
            root_dir=tmp_path / "runtime",
            cycles_dir=tmp_path / "runtime" / "cycles",
            exports_dir=tmp_path / "runtime" / "exports",
        )
    )
    cycle_store.paths.cycles_dir.mkdir(parents=True, exist_ok=True)
    cycle_store.paths.exports_dir.mkdir(parents=True, exist_ok=True)
    policy_store = ReplyPolicyStore(
        ReplyPolicyStorePaths(
            adapter_name="reply",
            root_dir=tmp_path / "accepted_reply_policies",
            scopes_dir=tmp_path / "accepted_reply_policies" / "scopes",
        )
    )
    policy_store.paths.root_dir.mkdir(parents=True, exist_ok=True)
    policy_store.paths.scopes_dir.mkdir(parents=True, exist_ok=True)
    accepted_artifact = AcceptedArtifactVersion(
        artifact_key="reply_behavior_policy",
        version="email.v2",
        source_project="train",
        accepted_at=datetime(2026, 5, 3, 12, 0, tzinfo=UTC),
    )
    policy_store.accept(
        ReplyBehaviorPolicy(
            artifact_key="reply_behavior_policy",
            version="email.v2",
            scope_kind=ReplyBehaviorScopeKind.CHANNEL,
            scope_value="email",
            created_at=datetime(2026, 5, 3, 11, 0, tzinfo=UTC),
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
                max_chars=140,
                prefer_single_paragraph=True,
            ),
            channel_rules=ReplyChannelRules(
                opening_style="no_opening",
                closing_style="no_signoff",
                emoji_policy="none",
                url_policy="plain_urls",
                attachment_reference_policy="mention_if_used",
                newline_policy="single_paragraph",
            ),
        ),
        artifact=accepted_artifact,
    )
    runtime = ReplyRuntime(store=cycle_store, policy_store=policy_store)
    snapshot = ThreadSnapshot(
        company_id=uuid4(),
        thread_ref="reply:email:alice@example.com",
        channel="email",
        contact_handle="alice@example.com",
        latest_inbound_text="Can you send the updated numbers today?",
        requested_at=datetime(2026, 5, 3, 12, 0, tzinfo=UTC),
        messages=(
            ThreadMessageSnapshot(
                message_id="msg-1",
                role=ThreadMessageRole.CONTACT,
                text="Can you send the updated numbers today?",
                occurred_at=datetime(2026, 5, 3, 11, 59, tzinfo=UTC),
                channel="email",
                source="email",
                handle="alice@example.com",
            ),
        ),
    )

    ranked = runtime.suggest(snapshot)

    assert ranked.accepted_artifact_version.artifact_key == "reply_behavior_policy"
    assert ranked.accepted_artifact_version.version == "email.v2"
    assert all(not draft.draft_text.lower().startswith("thanks") for draft in ranked.drafts)


def test_reply_runtime_isolates_company_scoped_policies_and_storage(tmp_path: Path) -> None:
    cycle_store = RuntimeCycleStore(
        RuntimeCyclePaths(
            adapter_name="reply",
            root_dir=tmp_path / "runtime",
            cycles_dir=tmp_path / "runtime" / "cycles",
            exports_dir=tmp_path / "runtime" / "exports",
            companies_dir=tmp_path / "runtime" / "companies",
        )
    )
    policy_store = ReplyPolicyStore(
        ReplyPolicyStorePaths(
            adapter_name="reply",
            root_dir=tmp_path / "accepted_reply_policies",
            scopes_dir=tmp_path / "accepted_reply_policies" / "scopes",
        )
    )
    company_one = UUID("11111111-1111-5111-8111-111111111111")
    company_two = UUID("22222222-2222-5222-8222-222222222222")
    for company_id, version, target_tone in (
        (company_one, "company-one.v1", "precise"),
        (company_two, "company-two.v1", "warm"),
    ):
        policy_store.accept(
            ReplyBehaviorPolicy(
                artifact_key="reply_behavior_policy",
                version=version,
                scope_kind=ReplyBehaviorScopeKind.COMPANY,
                scope_value=str(company_id),
                created_at=datetime(2026, 5, 4, 11, 0, tzinfo=UTC),
                source_project="train",
                tone_preferences=ReplyTonePreferences(
                    target_tone=target_tone,
                    formality="medium",
                    warmth="warm",
                    directness="direct",
                ),
                brevity_preferences=ReplyBrevityPreferences(
                    target_length="compact",
                    max_sentences=2,
                    max_chars=140,
                    prefer_single_paragraph=True,
                ),
                channel_rules=ReplyChannelRules(
                    opening_style="no_opening",
                    closing_style="no_signoff",
                    emoji_policy="none",
                    url_policy="plain_urls",
                    attachment_reference_policy="mention_if_used",
                    newline_policy="single_paragraph",
                ),
            ),
            artifact=AcceptedArtifactVersion(
                artifact_key="reply_behavior_policy",
                version=version,
                source_project="train",
                accepted_at=datetime(2026, 5, 4, 12, 0, tzinfo=UTC),
            ),
        )
    runtime = ReplyRuntime(store=cycle_store, policy_store=policy_store)
    common_kwargs = dict(
        channel="email",
        latest_inbound_text="Can you send the updated numbers today?",
        requested_at=datetime(2026, 5, 4, 12, 0, tzinfo=UTC),
        messages=(
            ThreadMessageSnapshot(
                message_id="msg-1",
                role=ThreadMessageRole.CONTACT,
                text="Can you send the updated numbers today?",
                occurred_at=datetime(2026, 5, 4, 11, 59, tzinfo=UTC),
                channel="email",
                source="email",
                handle="alice@example.com",
            ),
        ),
    )
    snapshot_one = ThreadSnapshot(
        company_id=company_one,
        thread_ref="reply:email:company-one:alice@example.com",
        contact_handle="alice@example.com",
        **common_kwargs,
    )
    snapshot_two = ThreadSnapshot(
        company_id=company_two,
        thread_ref="reply:email:company-two:alice@example.com",
        contact_handle="alice@example.com",
        **common_kwargs,
    )

    ranked_one = runtime.suggest(snapshot_one)
    ranked_two = runtime.suggest(snapshot_two)

    assert ranked_one.accepted_artifact_version.version == "company-one.v1"
    assert ranked_two.accepted_artifact_version.version == "company-two.v1"
    assert runtime.store.cycle_path(ranked_one.cycle_id, company_one).exists()
    assert runtime.store.cycle_path(ranked_two.cycle_id, company_two).exists()
    assert company_one != company_two
    assert (
        runtime.store.cycle_path(ranked_one.cycle_id, company_one)
        != runtime.store.cycle_path(ranked_two.cycle_id, company_two)
    )


def test_reply_runtime_backfills_three_distinct_drafts_when_llm_duplicates(tmp_path: Path) -> None:
    runtime = ReplyRuntime(
        store=RuntimeCycleStore(
            RuntimeCyclePaths(
                adapter_name="reply",
                root_dir=tmp_path,
                cycles_dir=tmp_path / "cycles",
                exports_dir=tmp_path / "exports",
            )
        )
    )
    runtime.store.paths.cycles_dir.mkdir(parents=True, exist_ok=True)
    runtime.store.paths.exports_dir.mkdir(parents=True, exist_ok=True)
    runtime.model_config = TrinityReplyModelConfig(
        provider="ollama",
        ollama_base_url="http://127.0.0.1:11434",
        timeout_seconds=10.0,
        generator=TrinityRoleRoute(
            provider="ollama",
            model="generator-test",
            temperature=0.2,
            keep_alive="5m",
        ),
        refiner=TrinityRoleRoute(
            provider="ollama",
            model="refiner-test",
            temperature=0.2,
            keep_alive="5m",
        ),
        evaluator=TrinityRoleRoute(
            provider="ollama",
            model="evaluator-test",
            temperature=0.1,
            keep_alive="5m",
        ),
    )

    class FakeOllamaClient:
        def chat_json(self, *, route, system_prompt, user_prompt):  # type: ignore[no-untyped-def]
            if route.model == "generator-test":
                return {
                    "candidates": [
                        {
                            "title": "Fast reply",
                            "content": "Thanks, I can send the update today.",
                            "impact": 8,
                            "confidence": 7,
                            "ease": 7,
                            "tags": ["direct"],
                        },
                        {
                            "title": "Another fast reply",
                            "content": "Thanks, I can send the update today.",
                            "impact": 8,
                            "confidence": 7,
                            "ease": 7,
                            "tags": ["direct"],
                        },
                    ]
                }
            if route.model == "refiner-test":
                payload = json.loads(user_prompt)
                return {
                    "title": payload["candidate"]["title"],
                    "content": payload["candidate"]["content"],
                    "impact": 8,
                    "confidence": 7,
                    "ease": 7,
                    "tags": payload["candidate"]["semantic_tags"],
                    "reason": "Refined.",
                }
            return {
                "evaluations": [
                    {
                        "candidate_id": item["candidate_id"],
                        "disposition": "ELIGIBLE",
                        "impact": 8,
                        "confidence": 7,
                        "ease": 7,
                        "quality_score": 78.0,
                        "urgency_score": 72.0,
                        "freshness_score": 70.0,
                        "feedback_score": 15.0,
                        "reason": "Eligible.",
                    }
                    for item in json.loads(user_prompt)["candidates"]
                ]
            }

    runtime.ollama_client = FakeOllamaClient()  # type: ignore[assignment]

    snapshot = ThreadSnapshot(
        company_id=uuid4(),
        thread_ref="reply:linkedin:alice",
        channel="linkedin",
        contact_handle="linkedin://alice",
        latest_inbound_text="Can you send the updated numbers today?",
        requested_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        messages=(
            ThreadMessageSnapshot(
                message_id="msg-1",
                role=ThreadMessageRole.CONTACT,
                text="Can you send the updated numbers today?",
                occurred_at=datetime(2026, 5, 1, 11, 59, tzinfo=UTC),
                channel="linkedin",
                source="linkedin",
                handle="linkedin://alice",
            ),
        ),
    )

    ranked = runtime.suggest(snapshot)

    assert len(ranked.drafts) == 3
    assert len({draft.draft_text for draft in ranked.drafts}) == 3
