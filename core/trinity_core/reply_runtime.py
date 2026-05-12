"""Reply adapter runtime implementation behind the generic Trinity facade."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any
from uuid import UUID, uuid4

from trinity_core.adapters.model import build_model_provider
from trinity_core.adapters.product.reply.payloads import (
    document_record_from_payload as adapter_document_record_from_payload,
)
from trinity_core.adapters.product.reply.payloads import (
    memory_event_from_payload as adapter_memory_event_from_payload,
)
from trinity_core.adapters.product.reply.payloads import (
    outcome_event_from_payload as adapter_outcome_event_from_payload,
)
from trinity_core.adapters.product.reply.payloads import (
    thread_snapshot_from_payload as adapter_thread_snapshot_from_payload,
)
from trinity_core.memory import (
    ReplyMemoryResolver,
    ReplyMemoryStore,
    apply_memory_similarity_signals,
    build_runtime_memory_profile,
)
from trinity_core.model_config import load_model_config
from trinity_core.ops.cycle_store import RuntimeCycleStore, dataclass_payload
from trinity_core.ops.reply_policy_store import ReplyPolicyStore
from trinity_core.ops.runtime_trace import (
    build_runtime_loop_decision_payload,
    build_runtime_memory_context_payload,
    persist_runtime_trace,
)
from trinity_core.schemas import (
    REPLY_CONTRACT_VERSION,
    AcceptedArtifactVersion,
    BundleNegativeCandidate,
    CandidateDraft,
    CandidateRecord,
    CandidateState,
    CandidateType,
    ContactProfile,
    DocumentRecord,
    DraftOutcomeDisposition,
    DraftOutcomeEvent,
    EvidenceProvenance,
    EvidenceSourceRef,
    EvidenceSourceType,
    EvidenceUnit,
    LoopAction,
    MemoryEvent,
    MemoryRecordFamily,
    MemorySummary,
    PolicyResolutionCandidate,
    PolicyResolutionSummary,
    PreparedDraftSet,
    RankedDraftSet,
    ReplyBehaviorPolicy,
    ReplyFeedbackDisposition,
    ReplyFeedbackEvent,
    ReworkRoute,
    RuntimeTraceExport,
    StageEvidenceAnchor,
    ThreadContextSnippet,
    ThreadSnapshot,
    ThreadState,
    TrainingBundle,
    TrainingBundleType,
)
from trinity_core.workflow import (
    EvaluationDisposition,
    EvaluatorExecutionInput,
    FrontierEntry,
    GeneratorExecutionInput,
    InMemoryEvidenceStore,
    RawEvaluationResult,
    RawEvidenceInput,
    RawGeneratedCandidate,
    RawRefinerResult,
    RefinerDisposition,
    RefinerExecutionInput,
    apply_reply_feedback,
    build_frontier,
    build_hitl_escalation,
    calibrate_candidate_scores,
    decide_loop_action,
    execute_candidate_pipeline,
    frontier_score,
    ingest_evidence,
    synthesize_consensus_decision,
)
from trinity_core.workflow.prepared_drafts import build_prepared_draft_set

ARTIFACT_VERSION = "reply_ranker_policy.v0"
ARTIFACT_KEY = "reply_ranker_policy"
ARTIFACT_SOURCE_PROJECT = "trinity"

GENERATOR_SYSTEM_PROMPT = """
You are Trinity's fast draft generator.
Return strict JSON with a `candidates` array of exactly 3 concise reply options.
The 3 options must be materially different strategies:
1. direct answer
2. advance with next step
3. clarify or risk-manage
Each candidate must contain: title, content, impact, confidence, ease, tags.
Interpret `ease` as delivery difficulty: lower means harder to realize in the real world,
not merely shorter to write.
Use one of these tags in every candidate: direct, advance, clarify.
Keep content plain text, no markdown, no surrounding commentary.
""".strip()

REFINER_SYSTEM_PROMPT = """
You are Trinity's writing refiner.
Rewrite the provided draft into a polished final candidate while preserving intent.
Return strict JSON with: title, content, impact, confidence, ease, tags, reason.
Interpret `ease` as delivery difficulty, not textual convenience.
Keep content plain text, concise, natural, and operator-safe.
""".strip()

EVALUATOR_SYSTEM_PROMPT = """
You are Trinity's final judge.
Score each candidate for delivery quality and decide whether it is ELIGIBLE or REVISE.
Return strict JSON with an `evaluations` array.
Each evaluation must contain:
candidate_id, disposition, impact, confidence, ease, quality_score, urgency_score,
freshness_score, feedback_score, reason.
Interpret `ease` as delivery difficulty: dependency burden, coordination load, and
execution complexity.
Use only dispositions ELIGIBLE or REVISE.
""".strip()


class ReplyRuntime:
    """Local runtime spine for Reply integration."""

    def __init__(
        self,
        store: RuntimeCycleStore | None = None,
        policy_store: ReplyPolicyStore | None = None,
        memory_store: ReplyMemoryStore | None = None,
    ) -> None:
        self.store = store or RuntimeCycleStore()
        self.policy_store = policy_store or ReplyPolicyStore()
        self.memory_store = memory_store or ReplyMemoryStore()
        self.memory_resolver = ReplyMemoryResolver(self.memory_store)
        self.model_config = load_model_config("reply")
        self.model_provider = build_model_provider(self.model_config)

    @property
    def ollama_client(self) -> Any:
        return self.model_provider

    @ollama_client.setter
    def ollama_client(self, value: Any) -> None:
        self.model_provider = value

    def suggest(self, snapshot: ThreadSnapshot) -> RankedDraftSet:
        cycle_id = uuid4()
        cycle_time = snapshot.requested_at
        resolved_policy = self.policy_store.resolve_with_summary(
            company_id=snapshot.company_id,
            channel=snapshot.channel,
        )
        active_policy_record = resolved_policy.accepted_policy
        active_policy = active_policy_record.policy if active_policy_record else None
        memory_context = self.memory_resolver.resolve_for_snapshot(snapshot)
        memory_profile = build_runtime_memory_profile(memory_context)
        evidence_units = self._build_evidence(snapshot)
        pipeline = execute_candidate_pipeline(
            GeneratorExecutionInput(
                company_id=snapshot.company_id,
                evidence_units=evidence_units,
                strategic_context=self._pipeline_strategic_context(
                    snapshot,
                    memory_context,
                    memory_profile,
                ),
                memory_constraints=self._generator_memory_constraints(
                    memory_context,
                    memory_profile,
                ),
                topic_anchors=tuple(_topic_anchors(snapshot)),
                freshness_reference=snapshot.requested_at,
            ),
            generator_runner=self._generator_runner(snapshot, active_policy),
            refiner_runner=self._refiner_runner(snapshot, active_policy),
            evaluator_runner=self._evaluator_runner(snapshot, active_policy),
            strategic_context=self._pipeline_strategic_context(
                snapshot,
                memory_context,
                memory_profile,
            ),
            feedback_memory=self._pipeline_feedback_memory(memory_context, memory_profile),
            ranking_context=self._pipeline_ranking_context(memory_context, memory_profile),
            strategic_policy=self._pipeline_strategic_policy(
                active_policy,
                memory_context,
                memory_profile,
            ),
            now=cycle_time,
        )
        pipeline = replace(
            pipeline,
            evaluated=replace(
                pipeline.evaluated,
                records=tuple(
                    apply_memory_similarity_signals(candidate, memory_context)
                    for candidate in pipeline.evaluated.records
                ),
            ),
        )
        pipeline = replace(
            pipeline,
            evaluated=replace(
                pipeline.evaluated,
                records=calibrate_candidate_scores(pipeline.evaluated.records),
            ),
        )
        frontier = build_frontier(pipeline.evaluated.records, limit=3)
        surfaced_frontier = _build_surfaced_frontier(
            pipeline.evaluated.records,
            frontier,
            limit=3,
        )
        consensus = synthesize_consensus_decision(
            cycle_id=cycle_id,
            adapter_name="reply",
            majority_candidate=surfaced_frontier[0].candidate if surfaced_frontier else None,
            frontier_entries=tuple(surfaced_frontier),
            generated_candidates=pipeline.generated.records,
            refined_candidates=pipeline.refined.records,
            evaluated_candidates=pipeline.evaluated.records,
            memory_factors=memory_context.selected_keys[:6],
        )
        loop_decision = decide_loop_action(
            consensus,
            loop_count=0,
            max_loop_count=0,
        )
        hitl_escalation = (
            build_hitl_escalation(
                cycle_id=cycle_id,
                adapter_name="reply",
                company_id=snapshot.company_id,
                majority_result_ref=(
                    str(consensus.majority_candidate_id)
                    if consensus.majority_candidate_id is not None
                    else snapshot.thread_ref
                ),
                decision_target="reply_send_decision",
                loop_decision=loop_decision,
                evidence_anchors=_candidate_evidence_anchors(surfaced_frontier[0].candidate)
                if surfaced_frontier
                else (),
                memory_factors=memory_context.selected_keys[:6],
                created_at=cycle_time,
            )
            if loop_decision.action is LoopAction.ESCALATE
            else None
        )
        artifact = _resolved_artifact_version(
            cycle_time,
            active_policy_record=active_policy_record,
        )
        ranked = RankedDraftSet(
            cycle_id=cycle_id,
            thread_ref=snapshot.thread_ref,
            channel=snapshot.channel,
            generated_at=cycle_time,
            drafts=tuple(
                CandidateDraft.from_candidate_record(
                    entry.candidate,
                    thread_ref=snapshot.thread_ref,
                    recipient_handle=snapshot.contact_handle,
                    channel=snapshot.channel,
                    rank=entry.rank,
                    risk_flags=_runtime_controlled_risk_flags(
                        entry.candidate,
                        snapshot,
                        loop_decision=loop_decision,
                    ),
                    delivery_eligible=_delivery_eligible(
                        entry.candidate,
                        loop_decision=loop_decision,
                    ),
                )
                for entry in surfaced_frontier
            ),
            accepted_artifact_version=artifact,
        )
        trace = RuntimeTraceExport(
            cycle_id=cycle_id,
            exported_at=cycle_time,
            snapshot_hash=_snapshot_hash(snapshot),
            thread_snapshot=snapshot,
            evidence_units=evidence_units,
            candidates=pipeline.evaluated.records,
            frontier_candidate_ids=tuple(
                entry.candidate.candidate_id for entry in surfaced_frontier
            ),
            ranked_draft_set=ranked,
            accepted_artifact_version=artifact,
            policy_resolution=_resolved_policy_summary(
                resolved_policy.summary,
                artifact=artifact,
            ),
            stage_evidence_anchors=_build_stage_evidence_anchors(evidence_units),
            model_routes=self._model_routes(),
            runtime_memory_context=build_runtime_memory_context_payload(memory_context),
            runtime_memory_profile=memory_profile.prompt_payload(),
            runtime_loop_decision=build_runtime_loop_decision_payload(
                consensus,
                loop_decision,
            ),
            runtime_hitl_escalation=dataclass_payload(hitl_escalation)
            if hitl_escalation is not None
            else {},
        )
        self._persist_cycle(trace)
        ranked_with_trace = replace(ranked, trace_ref=str(self.store.export_path(cycle_id)))
        self._remember_thread_snapshot(snapshot)
        self._remember_prepared_draft(snapshot, ranked_with_trace, generation_reason="suggest")
        return ranked_with_trace

    def record_outcome(self, event: DraftOutcomeEvent) -> dict[str, Any]:
        payload = self.store.load_cycle(event.cycle_id, event.company_id)
        payload.setdefault("feedback_events", []).append(dataclass_payload(event))
        candidate_id = str(event.candidate_id) if event.candidate_id else None
        if candidate_id:
            updated_candidates = []
            for candidate_payload in payload.get("candidates", []):
                if str(candidate_payload.get("candidate_id")) != candidate_id:
                    updated_candidates.append(candidate_payload)
                    continue
                candidate = _candidate_from_payload(candidate_payload)
                feedback = _reply_feedback_from_outcome(event)
                if feedback is not None:
                    candidate = apply_reply_feedback(candidate, feedback)
                updated_candidates.append(dataclass_payload(candidate))
            payload["candidates"] = updated_candidates
        self.store.save_cycle(event.cycle_id, payload)
        export_path = self.store.save_export(event.cycle_id, payload)
        self._remember_outcome_memory(event, payload)
        return {"status": "ok", "cycle_id": str(event.cycle_id), "trace_ref": str(export_path)}

    def export_trace(self, cycle_id: UUID) -> dict[str, Any]:
        payload = self.store.load_cycle(cycle_id)
        export_path = self.store.save_export(cycle_id, payload)
        return {"cycle_id": str(cycle_id), "trace_ref": str(export_path), "trace": payload}

    def export_training_bundle(
        self,
        cycle_id: UUID,
        *,
        bundle_type: TrainingBundleType,
    ) -> dict[str, Any]:
        payload = self.store.load_cycle(cycle_id)
        bundle = training_bundle_from_payload(payload, bundle_type=bundle_type)
        bundle_path = self.store.save_bundle(bundle.bundle_id, dataclass_payload(bundle))
        return {
            "bundle_id": str(bundle.bundle_id),
            "bundle_path": str(bundle_path),
            "bundle": dataclass_payload(bundle),
        }

    def ingest_memory_event(self, event: MemoryEvent) -> dict[str, Any]:
        self.memory_store.record_event(event)
        if event.event_kind.value == "document_deleted":
            document_ref = str(event.metadata.get("document_ref") or "").strip()
            if document_ref:
                self.memory_store.delete_document(event.company_id, document_ref)
        if event.contact_handle:
            self.memory_store.upsert_contact_profile(
                ContactProfile(
                    company_id=event.company_id,
                    contact_handle=event.contact_handle,
                    display_name=str(event.metadata.get("display_name") or "").strip() or None,
                    summary=str(event.metadata.get("summary") or "").strip(),
                    metadata=event.metadata,
                    updated_at=event.occurred_at,
                )
            )
        if event.thread_ref and event.channel and event.contact_handle:
            self.memory_store.upsert_thread_state(
                ThreadState(
                    company_id=event.company_id,
                    thread_ref=event.thread_ref,
                    channel=event.channel,
                    contact_handle=event.contact_handle,
                    latest_inbound_text=event.content_text or "",
                    last_event_at=event.occurred_at,
                    metadata={
                        "last_event_kind": event.event_kind.value,
                        "source_ref": event.source_ref,
                    },
                )
            )
            self.memory_store.mark_thread_dirty(
                event.company_id,
                event.thread_ref,
                reason=event.event_kind.value,
            )
        return {
            "status": "ok",
            "company_id": str(event.company_id),
            "event_kind": event.event_kind.value,
            "thread_ref": event.thread_ref,
            "source_ref": event.source_ref,
        }

    def register_document(self, document: DocumentRecord) -> dict[str, Any]:
        self.memory_store.register_document(document)
        thread_ref = str(document.metadata.get("thread_ref") or "").strip()
        if thread_ref:
            self.memory_store.mark_thread_dirty(
                document.company_id,
                thread_ref,
                reason="document_registered",
            )
        return {
            "status": "ok",
            "company_id": str(document.company_id),
            "document_ref": document.document_ref,
            "path": document.path,
        }

    def get_prepared_draft(
        self,
        *,
        company_id: UUID | str,
        thread_ref: str,
    ) -> dict[str, Any]:
        payload = self.memory_store.load_prepared_draft_payload(company_id, thread_ref)
        if payload is None:
            return {"status": "missing", "company_id": str(company_id), "thread_ref": thread_ref}
        expires_at = _parse_datetime(payload["expires_at"])
        stale = expires_at <= datetime.now(UTC)
        return {
            "status": "ok",
            "company_id": str(company_id),
            "thread_ref": thread_ref,
            "stale": stale,
            "prepared_draft_set": payload,
        }

    def refresh_prepared_draft(
        self,
        *,
        company_id: UUID | str,
        thread_ref: str,
        generation_reason: str = "manual_refresh",
        overwrite_mode: str = "if_stale_or_dirty",
    ) -> dict[str, Any]:
        existing_payload = self.memory_store.load_prepared_draft_payload(company_id, thread_ref)
        dirty_payload = self.memory_store.load_dirty_thread_payload(company_id, thread_ref)
        if overwrite_mode != "always":
            if overwrite_mode != "if_stale_or_dirty":
                raise ValueError(f"Unsupported overwrite_mode: {overwrite_mode}")
            if existing_payload is not None:
                expires_at = _parse_datetime(existing_payload["expires_at"])
                stale = expires_at <= datetime.now(UTC)
                if not stale and dirty_payload is None:
                    return {
                        "status": "skipped_fresh",
                        "company_id": str(company_id),
                        "thread_ref": thread_ref,
                        "stale": False,
                        "dirty": False,
                        "overwrite_mode": overwrite_mode,
                        "prepared_draft_set": existing_payload,
                    }
        snapshot_payload = self.memory_store.latest_snapshot_payload(company_id, thread_ref)
        if snapshot_payload is None:
            return {
                "status": "missing_snapshot",
                "company_id": str(company_id),
                "thread_ref": thread_ref,
            }
        snapshot = replace(
            adapter_thread_snapshot_from_payload(snapshot_payload),
            requested_at=datetime.now(UTC),
        )
        ranked = self.suggest(snapshot)
        prepared = self._remember_prepared_draft(
            snapshot,
            ranked,
            generation_reason=generation_reason,
        )
        self.memory_store.clear_thread_dirty(company_id, thread_ref)
        overwrite_reason = (
            "forced_refresh"
            if overwrite_mode == "always"
            else "freshen_prepared_draft"
        )
        if dirty_payload is not None:
            overwrite_reason = str(dirty_payload["reason"]).strip() or "dirty_thread"
        elif existing_payload is None:
            overwrite_reason = "missing_prepared_draft"
        elif _parse_datetime(existing_payload["expires_at"]) <= datetime.now(UTC):
            overwrite_reason = "stale_prepared_draft"
        return {
            "status": "ok",
            "company_id": str(company_id),
            "thread_ref": thread_ref,
            "overwrite_mode": overwrite_mode,
            "overwrite_reason": overwrite_reason,
            "prepared_draft_set": dataclass_payload(prepared),
        }

    def inspect_prepared_draft_refresh(
        self,
        *,
        company_id: UUID | str,
        limit: int = 10,
        stale_after_minutes: int = 15,
    ) -> dict[str, Any]:
        plan = self.memory_store.build_prepared_draft_refresh_plan(
            company_id,
            limit=limit,
            stale_after=timedelta(minutes=stale_after_minutes),
            now=datetime.now(UTC),
        )
        return {
            "status": "ok",
            "company_id": str(company_id),
            "refresh_plan": dataclass_payload(plan),
        }

    def _build_evidence(self, snapshot: ThreadSnapshot) -> tuple[Any, ...]:
        store = InMemoryEvidenceStore()
        accepted = []
        for raw in _raw_evidence(snapshot):
            result = ingest_evidence(raw, store=store, now=snapshot.requested_at)
            if result.accepted is not None:
                accepted.append(result.accepted)
        return tuple(accepted)

    def _persist_cycle(self, trace: RuntimeTraceExport) -> None:
        persist_runtime_trace(self.store, trace)

    def _generator_memory_constraints(
        self,
        memory_context: Any,
        memory_profile: Any,
    ) -> dict[str, str]:
        return {
            "retrieval_context_hash": memory_context.retrieval_context_hash,
            "memory_record_count": str(len(memory_context.records)),
            "selected_keys": ",".join(memory_context.selected_keys[:6]),
            "preference_hints": " | ".join(memory_profile.preference_hints[:2]),
            "anti_pattern_hints": " | ".join(memory_profile.anti_pattern_hints[:2]),
            "core_memory_summary": memory_profile.core_summary,
            "retrieval_summary": memory_profile.retrieval_summary,
            "ranked_memory_lines": " | ".join(memory_profile.ranked_memory_lines[:2]),
        }

    def _pipeline_strategic_context(
        self,
        snapshot: ThreadSnapshot,
        memory_context: Any,
        memory_profile: Any,
    ) -> dict[str, str]:
        return {
            "channel": snapshot.channel,
            "contact_handle": snapshot.contact_handle,
            "retrieval_context_hash": memory_context.retrieval_context_hash,
            "memory_preferences": " | ".join(memory_profile.preference_hints[:2]),
            "memory_successes": " | ".join(memory_profile.successful_pattern_hints[:2]),
            "working_memory_summary": memory_profile.working_summary,
            "ranked_memory_lines": " | ".join(memory_profile.ranked_memory_lines[:2]),
        }

    def _pipeline_feedback_memory(self, memory_context: Any, memory_profile: Any) -> dict[str, str]:
        feedback_keys = tuple(
            record.record_key
            for record in memory_context.records
            if str(record.family.value) in {"correction", "human_resolution", "disagreement"}
        )
        return {
            "retrieval_context_hash": memory_context.retrieval_context_hash,
            "feedback_record_count": str(len(feedback_keys)),
            "feedback_keys": ",".join(feedback_keys[:6]),
            "correction_hints": " | ".join(memory_profile.correction_hints[:2]),
            "disagreement_hints": " | ".join(memory_profile.disagreement_hints[:2]),
            "core_memory_summary": memory_profile.core_summary,
            "ranked_memory_lines": " | ".join(memory_profile.ranked_memory_lines[:2]),
        }

    def _pipeline_ranking_context(self, memory_context: Any, memory_profile: Any) -> dict[str, str]:
        return {
            "retrieval_context_hash": memory_context.retrieval_context_hash,
            "memory_record_count": str(len(memory_context.records)),
            "selected_keys": ",".join(memory_context.selected_keys[:6]),
            "anti_pattern_hints": " | ".join(memory_profile.anti_pattern_hints[:2]),
            "successful_pattern_hints": " | ".join(memory_profile.successful_pattern_hints[:2]),
            "archival_memory_summary": memory_profile.archival_summary,
            "ranked_memory_lines": " | ".join(memory_profile.ranked_memory_lines[:2]),
        }

    def _pipeline_strategic_policy(
        self,
        active_policy: ReplyBehaviorPolicy | None,
        memory_context: Any,
        memory_profile: Any,
    ) -> dict[str, str]:
        return {
            "policy_version": active_policy.version if active_policy is not None else "",
            "retrieval_context_hash": memory_context.retrieval_context_hash,
            "memory_record_count": str(len(memory_context.records)),
            "memory_preference_count": str(len(memory_profile.preference_hints)),
            "retrieval_summary": memory_profile.retrieval_summary,
            "ranked_memory_lines": " | ".join(memory_profile.ranked_memory_lines[:2]),
        }

    def _remember_thread_snapshot(self, snapshot: ThreadSnapshot) -> None:
        self.memory_store.upsert_contact_profile(
            ContactProfile(
                company_id=snapshot.company_id,
                contact_handle=snapshot.contact_handle,
                summary="",
                metadata={"channel": snapshot.channel},
                updated_at=snapshot.requested_at,
            )
        )
        self.memory_store.upsert_thread_state(
            ThreadState(
                company_id=snapshot.company_id,
                thread_ref=snapshot.thread_ref,
                channel=snapshot.channel,
                contact_handle=snapshot.contact_handle,
                latest_inbound_text=snapshot.latest_inbound_text,
                last_event_at=snapshot.requested_at,
                last_snapshot_at=snapshot.requested_at,
                metadata={"message_count": len(snapshot.messages)},
            ),
            snapshot=snapshot,
        )

    def _remember_prepared_draft(
        self,
        snapshot: ThreadSnapshot,
        ranked: RankedDraftSet,
        *,
        generation_reason: str,
    ) -> PreparedDraftSet:
        prepared = build_prepared_draft_set(
            snapshot,
            ranked,
            generation_reason=generation_reason,
            now=datetime.now(UTC),
        )
        self.memory_store.save_prepared_draft(prepared)
        return prepared

    def _remember_outcome_memory(
        self,
        event: DraftOutcomeEvent,
        payload: dict[str, Any],
    ) -> None:
        for summary in _outcome_memory_summaries(event, payload):
            self.memory_store.save_summary(summary)

    def _generator_runner(
        self,
        snapshot: ThreadSnapshot,
        active_policy: ReplyBehaviorPolicy | None,
    ):
        deterministic_runner = self._deterministic_generator_runner(snapshot, active_policy)
        if self.model_config.llm_enabled:
            return self._llm_generator_runner(snapshot, deterministic_runner, active_policy)
        return deterministic_runner

    def _deterministic_generator_runner(
        self,
        snapshot: ThreadSnapshot,
        active_policy: ReplyBehaviorPolicy | None,
    ):
        def runner(stage_input: GeneratorExecutionInput):
            last_contact_name = _display_handle(snapshot.contact_handle)
            snippets = _top_snippet_lines(snapshot.context_snippets)
            anchors = (
                ", ".join(stage_input.topic_anchors[:3])
                if stage_input.topic_anchors
                else "the thread"
            )
            direct = _truncate(
                f"Thanks {last_contact_name}, I saw this. {snippets or 'I can move this forward.'}"
            )
            confirm = _truncate(
                "Thanks "
                f"{last_contact_name}. My read is {anchors}. "
                "If that matches what you need, I can send the next step today."
            )
            clarify = _truncate(
                "Thanks "
                f"{last_contact_name}. I want to answer this cleanly. "
                "Can you confirm the exact outcome you want from me here?"
            )
            drafts = (
                RawGeneratedCandidate(
                    candidate_type=CandidateType.ACTION,
                    title="Direct reply",
                    content=_apply_behavior_policy(direct, active_policy),
                    source_evidence_ids=tuple(
                        str(unit.evidence_id) for unit in stage_input.evidence_units[:3]
                    ),
                    impact=8,
                    confidence=7,
                    ease=7,
                    semantic_tags=("direct", snapshot.channel),
                ),
                RawGeneratedCandidate(
                    candidate_type=CandidateType.ACTION,
                    title="Confirm and advance",
                    content=_apply_behavior_policy(confirm, active_policy),
                    source_evidence_ids=tuple(
                        str(unit.evidence_id) for unit in stage_input.evidence_units[:3]
                    ),
                    impact=7,
                    confidence=7,
                    ease=6,
                    semantic_tags=("confirm", "next_step", snapshot.channel),
                ),
                RawGeneratedCandidate(
                    candidate_type=CandidateType.ACTION,
                    title="Clarify requirement",
                    content=_apply_behavior_policy(clarify, active_policy),
                    source_evidence_ids=tuple(
                        str(unit.evidence_id) for unit in stage_input.evidence_units[:2]
                    ),
                    impact=6,
                    confidence=8,
                    ease=8,
                    semantic_tags=("clarify", snapshot.channel),
                ),
            )
            return drafts

        return runner

    def _refiner_runner(
        self,
        snapshot: ThreadSnapshot,
        active_policy: ReplyBehaviorPolicy | None,
    ):
        deterministic_runner = self._deterministic_refiner_runner(snapshot, active_policy)
        if self.model_config.llm_enabled:
            return self._llm_refiner_runner(snapshot, deterministic_runner, active_policy)
        return deterministic_runner

    def _deterministic_refiner_runner(
        self,
        snapshot: ThreadSnapshot,
        active_policy: ReplyBehaviorPolicy | None,
    ):
        def runner(stage_input: RefinerExecutionInput):
            results = []
            for candidate in stage_input.generated_candidates:
                compact = _apply_behavior_policy(
                    _truncate(candidate.content.replace("  ", " ")),
                    active_policy,
                )
                results.append(
                    RawRefinerResult(
                        disposition=RefinerDisposition.REFINE,
                        parent_candidate_id=str(candidate.candidate_id),
                        title=candidate.title,
                        content=compact,
                        impact=candidate.scores.impact,
                        confidence=candidate.scores.confidence,
                        ease=candidate.scores.ease,
                        semantic_tags=candidate.semantic_tags,
                        reason="Trimmed to operator-safe delivery length.",
                    )
                )
            return results

        return runner

    def _evaluator_runner(
        self,
        snapshot: ThreadSnapshot,
        active_policy: ReplyBehaviorPolicy | None,
    ):
        deterministic_runner = self._deterministic_evaluator_runner(snapshot)
        if self.model_config.llm_enabled:
            return self._llm_evaluator_runner(snapshot, deterministic_runner, active_policy)
        return deterministic_runner

    def _deterministic_evaluator_runner(self, snapshot: ThreadSnapshot):
        latest = snapshot.latest_inbound_text
        asks_question = "?" in latest
        snippet_bonus = min(len(snapshot.context_snippets) * 4.0, 12.0)
        example_bonus = min(len(snapshot.golden_examples) * 2.0, 8.0)

        def runner(stage_input: EvaluatorExecutionInput):
            results = []
            for candidate in stage_input.refined_candidates:
                text = candidate.content.lower()
                quality = 62.0 + snippet_bonus + example_bonus
                urgency = 68.0 if asks_question else 54.0
                freshness = 72.0 if candidate.lineage.source_evidence_ids else 45.0
                feedback = 14.0
                if "can you confirm" in text or "confirm the exact outcome" in text:
                    quality -= 6.0
                    urgency += 6.0
                if "thanks" in text:
                    quality += 4.0
                if len(candidate.content) > 220:
                    quality -= 8.0
                disposition = EvaluationDisposition.ELIGIBLE
                reason = "Operator-safe deterministic baseline draft."
                if "confirm the exact outcome" in text and not asks_question:
                    disposition = EvaluationDisposition.REVISE
                    reason = (
                        "Clarification prompt is only useful when the inbound message is ambiguous."
                    )
                results.append(
                    RawEvaluationResult(
                        candidate_id=str(candidate.candidate_id),
                        disposition=disposition,
                        impact=candidate.scores.impact,
                        confidence=candidate.scores.confidence,
                        ease=candidate.scores.ease,
                        quality_score=max(0.0, min(100.0, quality)),
                        urgency_score=max(0.0, min(100.0, urgency)),
                        freshness_score=max(0.0, min(100.0, freshness)),
                        feedback_score=feedback,
                        reason=reason,
                        rework_route=ReworkRoute.REVISE
                        if disposition is EvaluationDisposition.REVISE
                        else None,
                    )
                )
            return results

        return runner

    def _llm_generator_runner(
        self,
        snapshot: ThreadSnapshot,
        fallback_runner,
        active_policy: ReplyBehaviorPolicy | None,
    ):
        def runner(stage_input: GeneratorExecutionInput):
            try:
                prompt = _build_generator_prompt(snapshot, stage_input, active_policy)
                payload = self.model_provider.chat_json(
                    route=self.model_config.generator,
                    system_prompt=GENERATOR_SYSTEM_PROMPT,
                    user_prompt=prompt,
                )
                candidates = payload.get("candidates", [])
                if not isinstance(candidates, list) or not candidates:
                    raise ValueError("Generator returned no candidates.")
                drafts = []
                evidence_refs = tuple(
                    str(unit.evidence_id) for unit in stage_input.evidence_units[:4]
                )
                for index, item in enumerate(candidates[:3], start=1):
                    content = _normalize_llm_text(item.get("content"))
                    if not content:
                        continue
                    tags = tuple(_normalize_llm_tags(item.get("tags")))
                    strategy = _primary_strategy(tags, fallback_index=index)
                    drafts.append(
                        RawGeneratedCandidate(
                            candidate_type=CandidateType.ACTION,
                            title=_normalize_llm_text(item.get("title"))
                            or _strategy_title(strategy, index),
                            content=_apply_behavior_policy(content, active_policy),
                            source_evidence_ids=evidence_refs or tuple(
                                str(unit.evidence_id) for unit in stage_input.evidence_units[:1]
                            ),
                            impact=_bounded_int(item.get("impact"), 7),
                            confidence=_bounded_int(item.get("confidence"), 7),
                            ease=_bounded_int(item.get("ease"), 6),
                            semantic_tags=_ensure_strategy_tags(tags, strategy),
                        )
                    )
                if not drafts:
                    raise ValueError("Generator produced empty candidate content.")
                fallback_candidates = tuple(fallback_runner(stage_input))
                return _ensure_distinct_generated_candidates(drafts, fallback_candidates)
            except Exception:
                return fallback_runner(stage_input)

        return runner

    def _llm_refiner_runner(
        self,
        snapshot: ThreadSnapshot,
        fallback_runner,
        active_policy: ReplyBehaviorPolicy | None,
    ):
        def runner(stage_input: RefinerExecutionInput):
            try:
                results = []
                for candidate in stage_input.generated_candidates:
                    prompt = _build_refiner_prompt(
                        snapshot,
                        stage_input,
                        candidate,
                        active_policy,
                    )
                    payload = self.model_provider.chat_json(
                        route=self.model_config.refiner,
                        system_prompt=REFINER_SYSTEM_PROMPT,
                        user_prompt=prompt,
                    )
                    refined_text = _normalize_llm_text(payload.get("content"))
                    if not refined_text:
                        raise ValueError("Refiner returned empty content.")
                    results.append(
                        RawRefinerResult(
                            disposition=RefinerDisposition.REFINE,
                            parent_candidate_id=str(candidate.candidate_id),
                            title=_normalize_llm_text(payload.get("title")) or candidate.title,
                            content=_apply_behavior_policy(refined_text, active_policy),
                            impact=_bounded_int(payload.get("impact"), candidate.scores.impact),
                            confidence=_bounded_int(
                                payload.get("confidence"), candidate.scores.confidence
                            ),
                            ease=_bounded_int(payload.get("ease"), candidate.scores.ease),
                            semantic_tags=tuple(_normalize_llm_tags(payload.get("tags")))
                            or candidate.semantic_tags,
                            reason=_normalize_llm_text(payload.get("reason"))
                            or "Refined by LLM writing route.",
                        )
                    )
                if not results:
                    raise ValueError("Refiner produced no usable candidates.")
                if len(results) < len(stage_input.generated_candidates):
                    fallback_results = fallback_runner(stage_input)
                    seen = {result.parent_candidate_id for result in results}
                    for fallback in fallback_results:
                        if fallback.parent_candidate_id in seen:
                            continue
                        results.append(fallback)
                        seen.add(fallback.parent_candidate_id)
                return tuple(results)
            except Exception:
                return fallback_runner(stage_input)

        return runner

    def _llm_evaluator_runner(
        self,
        snapshot: ThreadSnapshot,
        fallback_runner,
        active_policy: ReplyBehaviorPolicy | None,
    ):
        def runner(stage_input: EvaluatorExecutionInput):
            try:
                prompt = _build_evaluator_prompt(snapshot, stage_input, active_policy)
                payload = self.model_provider.chat_json(
                    route=self.model_config.evaluator,
                    system_prompt=EVALUATOR_SYSTEM_PROMPT,
                    user_prompt=prompt,
                )
                evaluations = payload.get("evaluations", [])
                if not isinstance(evaluations, list) or not evaluations:
                    raise ValueError("Evaluator returned no evaluations.")
                by_id = {
                    str(candidate.candidate_id): candidate
                    for candidate in stage_input.refined_candidates
                }
                results = []
                for item in evaluations:
                    candidate_id = str(item.get("candidate_id") or "").strip()
                    if candidate_id not in by_id:
                        continue
                    disposition = _normalize_disposition(item.get("disposition"))
                    results.append(
                        RawEvaluationResult(
                            candidate_id=candidate_id,
                            disposition=disposition,
                            impact=_bounded_int(
                                item.get("impact"), by_id[candidate_id].scores.impact
                            ),
                            confidence=_bounded_int(
                                item.get("confidence"), by_id[candidate_id].scores.confidence
                            ),
                            ease=_bounded_int(item.get("ease"), by_id[candidate_id].scores.ease),
                            quality_score=_bounded_float(item.get("quality_score"), 70.0),
                            urgency_score=_bounded_float(item.get("urgency_score"), 60.0),
                            freshness_score=_bounded_float(item.get("freshness_score"), 60.0),
                            feedback_score=_bounded_float(item.get("feedback_score"), 12.0),
                            reason=_normalize_llm_text(item.get("reason"))
                            or "Evaluated by LLM judge route.",
                            rework_route=ReworkRoute.REVISE
                            if disposition is EvaluationDisposition.REVISE
                            else None,
                        )
                    )
                if not results:
                    raise ValueError("Evaluator produced no usable decisions.")
                if len(results) < len(stage_input.refined_candidates):
                    fallback_results = fallback_runner(stage_input)
                    seen = {result.candidate_id for result in results}
                    for fallback in fallback_results:
                        if fallback.candidate_id in seen:
                            continue
                        results.append(fallback)
                        seen.add(fallback.candidate_id)
                return tuple(results)
            except Exception:
                return fallback_runner(stage_input)

        return runner

    def _model_routes(self) -> dict[str, str]:
        if not self.model_config.llm_enabled:
            return {
                "generator": "deterministic:v0",
                "refiner": "deterministic:v0",
                "evaluator": "deterministic:v0",
            }
        return {
            "generator": (
                f"{self.model_config.generator.provider}:{self.model_config.generator.model}"
            ),
            "refiner": f"{self.model_config.refiner.provider}:{self.model_config.refiner.model}",
            "evaluator": (
                f"{self.model_config.evaluator.provider}:{self.model_config.evaluator.model}"
            ),
        }


def thread_snapshot_from_payload(payload: dict[str, Any]) -> ThreadSnapshot:
    return adapter_thread_snapshot_from_payload(payload)


def outcome_event_from_payload(payload: dict[str, Any]) -> DraftOutcomeEvent:
    return adapter_outcome_event_from_payload(payload)


def memory_event_from_payload(payload: dict[str, Any]) -> MemoryEvent:
    return adapter_memory_event_from_payload(payload)


def document_record_from_payload(payload: dict[str, Any]) -> DocumentRecord:
    return adapter_document_record_from_payload(payload)


def training_bundle_type_from_payload(value: str) -> TrainingBundleType:
    return TrainingBundleType(str(value))


def _reply_feedback_from_outcome(event: DraftOutcomeEvent) -> ReplyFeedbackEvent | None:
    if event.candidate_id is None:
        return None
    disposition_map = {
        DraftOutcomeDisposition.SENT_AS_IS: ReplyFeedbackDisposition.SENT,
        DraftOutcomeDisposition.EDITED_THEN_SENT: ReplyFeedbackDisposition.EDITED,
        DraftOutcomeDisposition.REJECTED: ReplyFeedbackDisposition.REJECTED,
        DraftOutcomeDisposition.MANUAL_REPLACEMENT: ReplyFeedbackDisposition.REJECTED,
        DraftOutcomeDisposition.REWORK_REQUESTED: ReplyFeedbackDisposition.REJECTED,
        DraftOutcomeDisposition.SELECTED: ReplyFeedbackDisposition.ACCEPTED,
    }
    feedback_disposition = disposition_map.get(event.disposition)
    if feedback_disposition is None:
        return None
    return ReplyFeedbackEvent(
        company_id=event.company_id,
        candidate_id=event.candidate_id,
        conversation_ref=event.thread_ref,
        disposition=feedback_disposition,
        occurred_at=event.occurred_at,
        notes=event.notes,
        edited_text=event.final_text
        if feedback_disposition is ReplyFeedbackDisposition.EDITED
        else None,
    )


def training_bundle_from_payload(
    payload: dict[str, Any],
    *,
    bundle_type: TrainingBundleType,
) -> TrainingBundle:
    ranked_draft_set = _ranked_draft_set_from_payload(payload["ranked_draft_set"])
    if "draft_outcome_event" in payload:
        outcome_event = outcome_event_from_payload(payload["draft_outcome_event"])
    else:
        outcome_event = _bundle_outcome_event(payload)
    cycle_id = UUID(
        payload.get("cycle_id")
        or payload.get("labels", {}).get("cycle_id")
        or payload["ranked_draft_set"]["cycle_id"]
    )
    policy_resolution = _policy_resolution_from_payload(payload.get("policy_resolution"))
    stage_evidence_anchors = tuple(
        _stage_evidence_anchor_from_payload(item)
        for item in payload.get("stage_evidence_anchors", [])
    )
    surfaced_negative_candidates = tuple(
        _bundle_negative_candidate_from_payload(item)
        for item in payload.get(
            "surfaced_negative_candidates",
            _derived_surfaced_negative_candidates(payload),
        )
    )
    filtered_negative_candidates = tuple(
        _bundle_negative_candidate_from_payload(item)
        for item in payload.get(
            "filtered_negative_candidates",
            _derived_filtered_negative_candidates(payload),
        )
    )
    runtime_loop_action = str(
        payload.get("runtime_loop_decision", {}).get("loop_decision", {}).get("action") or ""
    )
    runtime_hitl = payload.get("runtime_hitl_escalation") or {}
    runtime_minority = (
        payload.get("runtime_loop_decision", {}).get("consensus", {}).get("minority_report")
        or {}
    )
    return TrainingBundle(
        bundle_id=TrainingBundle.build_bundle_id(cycle_id=cycle_id, bundle_type=bundle_type),
        bundle_type=bundle_type,
        exported_at=_parse_datetime(
            payload.get("exported_at") or payload["ranked_draft_set"]["generated_at"]
        ),
        thread_snapshot=thread_snapshot_from_payload(payload["thread_snapshot"]),
        evidence_units=tuple(
            _evidence_unit_from_payload(item) for item in payload.get("evidence_units", [])
        ),
        ranked_draft_set=ranked_draft_set,
        selected_candidate_id=UUID(payload["selected_candidate_id"])
        if payload.get("selected_candidate_id")
        else outcome_event.candidate_id,
        draft_outcome_event=outcome_event,
        stage_evidence_anchors=stage_evidence_anchors,
        model_routes={
            str(key): str(value)
            for key, value in payload.get("model_routes", {}).items()
        },
        policy_resolution=policy_resolution,
        surfaced_negative_candidates=surfaced_negative_candidates,
        filtered_negative_candidates=filtered_negative_candidates,
        labels={
            **{str(key): str(value) for key, value in payload.get("labels", {}).items()},
            "bundle_type": bundle_type.value,
            "cycle_id": str(cycle_id),
            "company_id": str(payload["thread_snapshot"]["company_id"]),
            "trace_ref": str(payload["ranked_draft_set"].get("trace_ref") or ""),
            "channel": ranked_draft_set.channel,
            "runtime_loop_action": runtime_loop_action,
            "had_hitl_escalation": "true" if runtime_hitl else "false",
            "hitl_decision_target": str(runtime_hitl.get("decision_target") or ""),
            "had_minority_report": "true" if runtime_minority else "false",
        },
        contract_version=str(payload.get("contract_version") or REPLY_CONTRACT_VERSION),
    )


def _bundle_outcome_event(payload: dict[str, Any]) -> DraftOutcomeEvent:
    feedback_payloads = payload.get("feedback_events", [])
    if not feedback_payloads:
        raise ValueError("Cannot export training bundle without feedback_events.")
    eligible = [
        outcome_event_from_payload(item)
        for item in feedback_payloads
        if str(item.get("disposition")) != DraftOutcomeDisposition.SHOWN.value
    ]
    if not eligible:
        raise ValueError("Cannot export training bundle with only SHOWN feedback events.")
    return sorted(
        eligible,
        key=lambda event: (
            event.occurred_at.timestamp(),
            event.disposition.value,
            str(event.candidate_id or ""),
        ),
    )[-1]


def _derived_surfaced_negative_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    selected_candidate_id = str(payload.get("selected_candidate_id") or "")
    if not selected_candidate_id and payload.get("draft_outcome_event"):
        selected_candidate_id = str(payload["draft_outcome_event"].get("candidate_id") or "")
    if not selected_candidate_id and payload.get("feedback_events"):
        try:
            selected_candidate_id = str(_bundle_outcome_event(payload).candidate_id or "")
        except ValueError:
            selected_candidate_id = ""
    negatives = []
    for item in payload.get("ranked_draft_set", {}).get("drafts", []):
        if str(item.get("candidate_id")) == selected_candidate_id:
            continue
        negatives.append(
            {
                "candidate_id": item["candidate_id"],
                "candidate_kind": str(item.get("candidate_type") or CandidateType.ACTION.value),
                "state": "SURFACED_NOT_SELECTED",
                "rank": item.get("rank"),
                "content": item["draft_text"],
                "rationale": item["rationale"],
                "source_evidence_ids": item.get("source_evidence_ids", []),
                "source_candidate_ids": [],
                "delivery_eligible": bool(item.get("delivery_eligible", False)),
            }
        )
    return negatives


def _derived_filtered_negative_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    surfaced_ids = {
        str(item["candidate_id"])
        for item in payload.get("ranked_draft_set", {}).get("drafts", [])
    }
    negatives = []
    for item in payload.get("candidates", []):
        if str(item.get("candidate_id")) in surfaced_ids:
            continue
        negatives.append(
            {
                "candidate_id": item["candidate_id"],
                "candidate_kind": item["candidate_type"],
                "state": item["state"],
                "rank": None,
                "content": item["content"],
                "rationale": item.get("evaluation_reason") or item["title"],
                "source_evidence_ids": item.get("lineage", {}).get("source_evidence_ids", []),
                "source_candidate_ids": item.get("lineage", {}).get("source_candidate_ids", []),
                "delivery_eligible": str(item.get("state")) == CandidateState.EVALUATED.value,
            }
        )
    return negatives


def _ranked_draft_set_from_payload(payload: dict[str, Any]) -> RankedDraftSet:
    return RankedDraftSet(
        cycle_id=UUID(payload["cycle_id"]),
        thread_ref=str(payload["thread_ref"]),
        channel=str(payload["channel"]),
        generated_at=_parse_datetime(payload["generated_at"]),
        drafts=tuple(_candidate_draft_from_payload(item) for item in payload["drafts"]),
        accepted_artifact_version=_artifact_version_from_payload(payload["accepted_artifact_version"]),
        trace_ref=payload.get("trace_ref"),
        contract_version=str(payload.get("contract_version") or REPLY_CONTRACT_VERSION),
    )


def _candidate_draft_from_payload(payload: dict[str, Any]) -> CandidateDraft:
    from trinity_core.schemas import CandidateScores

    return CandidateDraft(
        company_id=UUID(payload["company_id"]),
        candidate_id=UUID(payload["candidate_id"]),
        thread_ref=str(payload["thread_ref"]),
        recipient_handle=str(payload["recipient_handle"]),
        channel=str(payload["channel"]),
        rank=int(payload["rank"]),
        draft_text=str(payload["draft_text"]),
        rationale=str(payload["rationale"]),
        risk_flags=tuple(str(item) for item in payload.get("risk_flags", [])),
        delivery_eligible=bool(payload["delivery_eligible"]),
        scores=CandidateScores(**payload["scores"]),
        source_evidence_ids=tuple(UUID(item) for item in payload["source_evidence_ids"]),
        candidate_type=CandidateType(
            str(payload.get("candidate_type") or CandidateType.ACTION.value)
        ),
        contract_version=str(payload.get("contract_version") or REPLY_CONTRACT_VERSION),
    )


def _artifact_version_from_payload(payload: dict[str, Any]) -> AcceptedArtifactVersion:
    return AcceptedArtifactVersion(
        artifact_key=str(payload["artifact_key"]),
        version=str(payload["version"]),
        source_project=str(payload["source_project"]),
        accepted_at=_parse_datetime(payload["accepted_at"]),
    )


def _policy_resolution_from_payload(
    payload: dict[str, Any] | None,
) -> PolicyResolutionSummary | None:
    if payload is None:
        return None
    return PolicyResolutionSummary(
        requested_company_id=payload.get("requested_company_id"),
        requested_channel=payload.get("requested_channel"),
        matched_scope_kind=payload.get("matched_scope_kind"),
        matched_scope_value=payload.get("matched_scope_value"),
        matched_policy_version=payload.get("matched_policy_version"),
        resolution_path=tuple(str(item) for item in payload.get("resolution_path", [])),
        considered_scopes=tuple(
            PolicyResolutionCandidate(
                scope_kind=str(item["scope_kind"]),
                scope_value=item.get("scope_value"),
                matched=bool(item["matched"]),
                policy_version=item.get("policy_version"),
            )
            for item in payload.get("considered_scopes", [])
        ),
    )


def _stage_evidence_anchor_from_payload(payload: dict[str, Any]) -> StageEvidenceAnchor:
    return StageEvidenceAnchor(
        stage_name=str(payload["stage_name"]),
        anchor_kind=str(payload["anchor_kind"]),
        evidence_ids=tuple(UUID(item) for item in payload["evidence_ids"]),
        content_hashes=tuple(str(item) for item in payload["content_hashes"]),
    )


def _bundle_negative_candidate_from_payload(payload: dict[str, Any]) -> BundleNegativeCandidate:
    return BundleNegativeCandidate(
        candidate_id=UUID(payload["candidate_id"]),
        candidate_kind=str(payload["candidate_kind"]),
        state=str(payload["state"]),
        rank=int(payload["rank"]) if payload.get("rank") is not None else None,
        content=str(payload["content"]),
        rationale=str(payload["rationale"]),
        source_evidence_ids=tuple(UUID(item) for item in payload.get("source_evidence_ids", [])),
        source_candidate_ids=tuple(
            UUID(item) for item in payload.get("source_candidate_ids", [])
        ),
        delivery_eligible=bool(payload.get("delivery_eligible", False)),
    )


def _resolved_artifact_version(
    cycle_time: datetime,
    *,
    active_policy_record,
) -> AcceptedArtifactVersion:
    if active_policy_record is not None:
        return active_policy_record.artifact
    return AcceptedArtifactVersion(
        artifact_key=ARTIFACT_KEY,
        version=ARTIFACT_VERSION,
        source_project=ARTIFACT_SOURCE_PROJECT,
        accepted_at=cycle_time,
    )


def _resolved_policy_summary(
    summary: PolicyResolutionSummary,
    *,
    artifact: AcceptedArtifactVersion,
) -> PolicyResolutionSummary:
    if summary.matched_policy_version is not None:
        return summary
    return PolicyResolutionSummary(
        requested_company_id=summary.requested_company_id,
        requested_channel=summary.requested_channel,
        matched_scope_kind="builtin_runtime_default",
        matched_scope_value=None,
        matched_policy_version=artifact.version,
        resolution_path=tuple(summary.resolution_path) + ("builtin_runtime_default:match",),
        considered_scopes=summary.considered_scopes,
    )


def _evidence_unit_from_payload(payload: dict[str, Any]) -> EvidenceUnit:
    return EvidenceUnit(
        company_id=UUID(payload["company_id"]),
        evidence_id=UUID(payload["evidence_id"]),
        source_type=EvidenceSourceType(str(payload["source_type"])),
        source_ref=EvidenceSourceRef(
            external_id=str(payload["source_ref"]["external_id"]),
            locator=payload["source_ref"].get("locator"),
            version=payload["source_ref"].get("version"),
        ),
        content_raw=str(payload["content_raw"]),
        content_canonical=str(payload["content_canonical"]),
        content_hash=str(payload["content_hash"]),
        metadata={str(key): str(value) for key, value in payload.get("metadata", {}).items()},
        topic_hints=tuple(str(item) for item in payload.get("topic_hints", [])),
        created_at=_parse_datetime(payload["created_at"]),
        updated_at=_parse_datetime(payload["updated_at"]),
    )


def _raw_evidence(snapshot: ThreadSnapshot) -> tuple[RawEvidenceInput, ...]:
    evidence = []
    for message in snapshot.messages:
        source_type = (
            EvidenceSourceType.EMAIL
            if snapshot.channel == "email"
            else EvidenceSourceType.TRANSCRIPT
        )
        evidence.append(
            RawEvidenceInput(
                company_id=snapshot.company_id,
                source_type=source_type,
                source_ref=EvidenceSourceRef(
                    external_id=message.message_id,
                    locator=message.handle,
                    version=message.occurred_at.isoformat(),
                ),
                content=message.text,
                metadata={
                    "role": message.role.value,
                    "channel": message.channel,
                    "source": message.source,
                    "thread_ref": snapshot.thread_ref,
                },
                topic_hints=tuple(_topic_anchors(snapshot)),
                freshness_duration=timedelta(days=14),
                provenance=EvidenceProvenance(
                    collected_at=message.occurred_at,
                    collector="reply",
                    ingestion_channel="thread_snapshot",
                    raw_origin_uri=message.handle,
                ),
            )
        )
    for index, snippet in enumerate(snapshot.context_snippets):
        evidence.append(
            RawEvidenceInput(
                company_id=snapshot.company_id,
                source_type=EvidenceSourceType.DOCUMENT,
                source_ref=EvidenceSourceRef(external_id=f"snippet-{index}", locator=snippet.path),
                content=snippet.text,
                metadata={
                    "channel": snapshot.channel,
                    "source": snippet.source,
                    "thread_ref": snapshot.thread_ref,
                },
                topic_hints=tuple(_topic_anchors(snapshot)),
                freshness_duration=timedelta(days=30),
            )
        )
    for index, example in enumerate(snapshot.golden_examples):
        evidence.append(
            RawEvidenceInput(
                company_id=snapshot.company_id,
                source_type=EvidenceSourceType.NOTE,
                source_ref=EvidenceSourceRef(external_id=f"golden-{index}", locator=example.path),
                content=example.text,
                metadata={"kind": "golden_example", "thread_ref": snapshot.thread_ref},
                topic_hints=tuple(_topic_anchors(snapshot)),
                freshness_duration=timedelta(days=90),
            )
        )
    return tuple(evidence)


def _candidate_from_payload(payload: dict[str, Any]) -> CandidateRecord:
    from trinity_core.schemas import CandidateLineage, CandidateScores

    return CandidateRecord(
        company_id=UUID(payload["company_id"]),
        candidate_id=UUID(payload["candidate_id"]),
        candidate_type=CandidateType(str(payload["candidate_type"])),
        state=CandidateState(str(payload["state"])),
        title=str(payload["title"]),
        content=str(payload["content"]),
        lineage=CandidateLineage(
            version_family_id=UUID(payload["lineage"]["version_family_id"]),
            parent_candidate_id=UUID(payload["lineage"]["parent_candidate_id"])
            if payload["lineage"].get("parent_candidate_id")
            else None,
            source_evidence_ids=tuple(
                UUID(value) for value in payload["lineage"].get("source_evidence_ids", [])
            ),
            source_candidate_ids=tuple(
                UUID(value) for value in payload["lineage"].get("source_candidate_ids", [])
            ),
        ),
        scores=CandidateScores(**payload["scores"]),
        semantic_tags=tuple(str(value) for value in payload.get("semantic_tags", [])),
        duplicate_cluster_id=UUID(payload["duplicate_cluster_id"])
        if payload.get("duplicate_cluster_id")
        else None,
        created_at=_parse_datetime(payload["created_at"]),
        updated_at=_parse_datetime(payload["updated_at"]),
        last_presented_at=_parse_datetime(payload["last_presented_at"])
        if payload.get("last_presented_at")
        else None,
        last_feedback_at=_parse_datetime(payload["last_feedback_at"])
        if payload.get("last_feedback_at")
        else None,
        last_reworked_at=_parse_datetime(payload["last_reworked_at"])
        if payload.get("last_reworked_at")
        else None,
        last_delivered_at=_parse_datetime(payload["last_delivered_at"])
        if payload.get("last_delivered_at")
        else None,
        evaluated_at=_parse_datetime(payload["evaluated_at"])
        if payload.get("evaluated_at")
        else None,
        rework_route=ReworkRoute(str(payload["rework_route"]))
        if payload.get("rework_route")
        else None,
        evaluation_reason=payload.get("evaluation_reason"),
        delivery_target_ref=payload.get("delivery_target_ref"),
    )


def _snapshot_hash(snapshot: ThreadSnapshot) -> str:
    return hashlib.sha256(repr(dataclass_payload(snapshot)).encode("utf-8")).hexdigest()


def _build_generator_prompt(
    snapshot: ThreadSnapshot,
    stage_input: GeneratorExecutionInput,
    active_policy: ReplyBehaviorPolicy | None,
) -> str:
    payload = {
        "thread_ref": snapshot.thread_ref,
        "channel": snapshot.channel,
        "contact_handle": snapshot.contact_handle,
        "latest_inbound_text": snapshot.latest_inbound_text,
        "topic_anchors": list(stage_input.topic_anchors[:6]),
        "recent_messages": [
            {
                "role": message.role.value,
                "text": message.text,
                "occurred_at": message.occurred_at.isoformat(),
            }
            for message in snapshot.messages[-8:]
        ],
        "context_snippets": [snippet.text for snippet in snapshot.context_snippets[:6]],
        "golden_examples": [example.text for example in snapshot.golden_examples[:3]],
        "memory_constraints": dict(stage_input.memory_constraints),
        "strategic_context": dict(stage_input.strategic_context),
        "active_policy": dataclass_payload(active_policy) if active_policy is not None else None,
    }
    return json.dumps(payload, ensure_ascii=True, indent=2)


def _build_refiner_prompt(
    snapshot: ThreadSnapshot,
    stage_input: RefinerExecutionInput,
    candidate: CandidateRecord,
    active_policy: ReplyBehaviorPolicy | None,
) -> str:
    payload = {
        "thread_ref": snapshot.thread_ref,
        "channel": snapshot.channel,
        "contact_handle": snapshot.contact_handle,
        "latest_inbound_text": snapshot.latest_inbound_text,
        "candidate": {
            "candidate_id": str(candidate.candidate_id),
            "title": candidate.title,
            "content": candidate.content,
            "semantic_tags": list(candidate.semantic_tags),
        },
        "anchored_evidence": [
            {
                "evidence_id": str(evidence.evidence_id),
                "content": evidence.content_canonical,
                "source_type": evidence.source_type.value,
            }
            for evidence in _evidence_for_candidate(stage_input.evidence_units, candidate)
        ],
        "context_snippets": [snippet.text for snippet in snapshot.context_snippets[:4]],
        "golden_examples": [example.text for example in snapshot.golden_examples[:2]],
        "feedback_memory": dict(stage_input.feedback_memory),
        "ranking_context": dict(stage_input.ranking_context),
        "active_policy": dataclass_payload(active_policy) if active_policy is not None else None,
    }
    return json.dumps(payload, ensure_ascii=True, indent=2)


def _build_evaluator_prompt(
    snapshot: ThreadSnapshot,
    stage_input: EvaluatorExecutionInput,
    active_policy: ReplyBehaviorPolicy | None,
) -> str:
    payload = {
        "thread_ref": snapshot.thread_ref,
        "channel": snapshot.channel,
        "contact_handle": snapshot.contact_handle,
        "latest_inbound_text": snapshot.latest_inbound_text,
        "asks_question": "?" in snapshot.latest_inbound_text,
        "anchored_evidence": [
            {
                "evidence_id": str(evidence.evidence_id),
                "content": evidence.content_canonical,
                "source_type": evidence.source_type.value,
            }
            for evidence in stage_input.evidence_units[:6]
        ],
        "candidates": [
            {
                "candidate_id": str(candidate.candidate_id),
                "title": candidate.title,
                "content": candidate.content,
                "semantic_tags": list(candidate.semantic_tags),
            }
            for candidate in stage_input.refined_candidates
        ],
        "feedback_memory": dict(stage_input.feedback_memory),
        "ranking_context": dict(stage_input.ranking_context),
        "strategic_policy": dict(stage_input.strategic_policy),
        "active_policy": dataclass_payload(active_policy) if active_policy is not None else None,
    }
    return json.dumps(payload, ensure_ascii=True, indent=2)


def _risk_flags(candidate: CandidateRecord, snapshot: ThreadSnapshot) -> tuple[str, ...]:
    flags = []
    if len(candidate.content) > 180:
        flags.append("long_draft")
    if "confirm the exact outcome" in candidate.content.lower():
        flags.append("needs_clarification")
    if len(snapshot.context_snippets) == 0:
        flags.append("low_context")
    if candidate.state is not CandidateState.EVALUATED:
        flags.append("needs_operator_review")
    return tuple(flags)


def _runtime_controlled_risk_flags(
    candidate: CandidateRecord,
    snapshot: ThreadSnapshot,
    *,
    loop_decision: Any,
) -> tuple[str, ...]:
    flags = list(_risk_flags(candidate, snapshot))
    if loop_decision.minority_report is not None:
        flags.append("minority_report_present")
    if loop_decision.confidence_bundle.combined_confidence < 0.6:
        flags.append("low_confidence")
    if loop_decision.action is LoopAction.REWORK:
        flags.append("runtime_rework_required")
    if loop_decision.action is LoopAction.ESCALATE:
        flags.append("human_review_required")
    return tuple(dict.fromkeys(flags))


def _delivery_eligible(candidate: CandidateRecord, *, loop_decision: Any) -> bool:
    if candidate.state is not CandidateState.EVALUATED:
        return False
    return loop_decision.action is LoopAction.ACCEPT


def _candidate_evidence_anchors(candidate: CandidateRecord) -> tuple[str, ...]:
    return tuple(str(evidence_id) for evidence_id in candidate.lineage.source_evidence_ids)


def _outcome_memory_summaries(
    event: DraftOutcomeEvent,
    payload: dict[str, Any],
) -> tuple[MemorySummary, ...]:
    updated_at = event.occurred_at
    company_scope = f"company:{event.company_id}"
    human_scope = f"human:thread:{event.thread_ref}"
    cycle_key = str(event.cycle_id).replace("-", "")
    loop_action = str(
        payload.get("runtime_loop_decision", {}).get("loop_decision", {}).get("action") or ""
    )
    summaries: list[MemorySummary] = [
        MemorySummary(
            company_id=event.company_id,
            summary_key=f"human_resolution_{cycle_key}",
            scope_ref=human_scope,
            content=_human_resolution_summary_text(event, loop_action=loop_action),
            updated_at=updated_at,
            metadata={
                "family": MemoryRecordFamily.HUMAN_RESOLUTION.value,
                "cycle_id": str(event.cycle_id),
                "candidate_id": str(event.candidate_id or ""),
                "disposition": event.disposition.value,
                "loop_action": loop_action,
                "channel": event.channel,
            },
        )
    ]
    family = _outcome_memory_family(event.disposition)
    if family is not None:
        summaries.append(
            MemorySummary(
                company_id=event.company_id,
                summary_key=f"{family.value}_{cycle_key}",
                scope_ref=company_scope,
                content=_family_summary_text(event, family=family),
                updated_at=updated_at,
                metadata={
                    "family": family.value,
                    "cycle_id": str(event.cycle_id),
                    "candidate_id": str(event.candidate_id or ""),
                    "disposition": event.disposition.value,
                    "channel": event.channel,
                },
            )
        )
    minority_report = (
        payload.get("runtime_loop_decision", {}).get("consensus", {}).get("minority_report")
    )
    if minority_report:
        summaries.append(
            MemorySummary(
                company_id=event.company_id,
                summary_key=f"disagreement_{cycle_key}",
                scope_ref=company_scope,
                content=_disagreement_summary_text(event, minority_report=minority_report),
                updated_at=updated_at,
                metadata={
                    "family": MemoryRecordFamily.DISAGREEMENT.value,
                    "cycle_id": str(event.cycle_id),
                    "candidate_id": str(event.candidate_id or ""),
                    "disposition": event.disposition.value,
                    "channel": event.channel,
                    "minority_result_ref": str(
                        minority_report.get("minority_result_ref") or ""
                    ),
                    "dissent_source": str(minority_report.get("dissent_source") or ""),
                },
            )
        )
    return tuple(summaries)


def _outcome_memory_family(
    disposition: DraftOutcomeDisposition,
) -> MemoryRecordFamily | None:
    if disposition in {
        DraftOutcomeDisposition.SENT_AS_IS,
        DraftOutcomeDisposition.SELECTED,
    }:
        return MemoryRecordFamily.SUCCESSFUL_PATTERN
    if disposition in {
        DraftOutcomeDisposition.EDITED_THEN_SENT,
        DraftOutcomeDisposition.MANUAL_REPLACEMENT,
    }:
        return MemoryRecordFamily.CORRECTION
    if disposition in {
        DraftOutcomeDisposition.REJECTED,
        DraftOutcomeDisposition.IGNORED,
        DraftOutcomeDisposition.REWORK_REQUESTED,
    }:
        return MemoryRecordFamily.ANTI_PATTERN
    return None


def _human_resolution_summary_text(
    event: DraftOutcomeEvent,
    *,
    loop_action: str,
) -> str:
    final_text = (event.final_text or event.original_draft_text or "").strip()
    final_text = " ".join(final_text.split())
    prefix = (
        f"Human resolved reply cycle {event.cycle_id} as {event.disposition.value}"
        f" on {event.channel}"
    )
    if loop_action:
        prefix += f" after runtime action {loop_action}"
    if final_text:
        return f"{prefix}: {final_text[:180]}"
    return prefix


def _family_summary_text(
    event: DraftOutcomeEvent,
    *,
    family: MemoryRecordFamily,
) -> str:
    original_text = " ".join((event.original_draft_text or "").split())
    final_text = " ".join((event.final_text or "").split())
    if family is MemoryRecordFamily.SUCCESSFUL_PATTERN:
        return (
            f"Reply outcome {event.disposition.value} succeeded on {event.channel}: "
            f"{final_text[:180] or original_text[:180]}"
        )
    if family is MemoryRecordFamily.CORRECTION:
        return (
            f"Human corrected reply before send on {event.channel}. "
            f"Original: {original_text[:120]}. Final: {final_text[:120]}."
        )
    return (
        f"Avoid reply pattern that led to {event.disposition.value} on {event.channel}: "
        f"{original_text[:180]}"
    )


def _disagreement_summary_text(
    event: DraftOutcomeEvent,
    *,
    minority_report: dict[str, Any],
) -> str:
    reason = str(minority_report.get("dissent_reason") or "").strip()
    if reason:
        return (
            f"Runtime disagreement persisted for cycle {event.cycle_id} and human resolved it "
            f"with {event.disposition.value}: {reason[:180]}"
        )
    return (
        f"Runtime disagreement persisted for cycle {event.cycle_id} and human resolved it "
        f"with {event.disposition.value}."
    )


def _normalize_llm_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_llm_tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(tag.strip().lower() for tag in value if str(tag).strip()))


def _bounded_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(10, parsed))


def _bounded_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(0.0, min(100.0, parsed))


def _normalize_disposition(value: Any) -> EvaluationDisposition:
    raw = str(value or "").strip().upper()
    if raw == EvaluationDisposition.REVISE.value:
        return EvaluationDisposition.REVISE
    return EvaluationDisposition.ELIGIBLE


def _top_snippet_lines(snippets: tuple[ThreadContextSnippet, ...]) -> str:
    if not snippets:
        return ""
    line = snippets[0].text.splitlines()[0].strip()
    return line[:96].rstrip(" ,.;:")


def _display_handle(handle: str) -> str:
    raw = handle.strip()
    if "://" in raw:
        raw = raw.split("://", 1)[1]
    if "@" in raw:
        return raw.split("@", 1)[0]
    return raw.split("/")[-1]


def _topic_anchors(snapshot: ThreadSnapshot) -> list[str]:
    text = f"{snapshot.latest_inbound_text} " + " ".join(
        snippet.text for snippet in snapshot.context_snippets[:2]
    )
    words = [part.strip(".,:;!?()[]{}").lower() for part in text.split()]
    filtered = [word for word in words if len(word) > 4 and word.isalpha()]
    anchors = []
    for word in filtered:
        if word not in anchors:
            anchors.append(word)
        if len(anchors) == 4:
            break
    return anchors or ["followup"]


def _truncate(text: str, limit: int = 240) -> str:
    normalized = " ".join(text.split()).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def _apply_behavior_policy(text: str, policy: ReplyBehaviorPolicy | None) -> str:
    shaped = _truncate(text)
    if policy is None:
        return shaped
    if policy.channel_rules.opening_style == "no_opening":
        shaped = re.sub(
            r"^(thanks|thank you|hi|hello|got it|noted)\s+[^,]*,?\s*",
            "",
            shaped,
            flags=re.IGNORECASE,
        )
    elif policy.channel_rules.opening_style == "brief_acknowledgment" and not re.match(
        r"^(thanks|thank you|hi|hello|got it|noted)\b",
        shaped,
        flags=re.IGNORECASE,
    ):
        shaped = f"Thanks, {shaped[:1].lower() + shaped[1:] if shaped else ''}".strip()
    if policy.channel_rules.emoji_policy == "none":
        shaped = re.sub(r"[\U0001F300-\U0001FAFF]", "", shaped)
    if (
        policy.channel_rules.newline_policy == "single_paragraph"
        or policy.brevity_preferences.prefer_single_paragraph
    ):
        shaped = " ".join(line.strip() for line in shaped.splitlines() if line.strip())
    if policy.brevity_preferences.max_sentences is not None:
        shaped = _truncate_sentences(shaped, policy.brevity_preferences.max_sentences)
    if (
        policy.brevity_preferences.max_chars is not None
        and len(shaped) > policy.brevity_preferences.max_chars
    ):
        shaped = _truncate(shaped, limit=policy.brevity_preferences.max_chars)
    return _truncate(shaped)


def _truncate_sentences(text: str, max_sentences: int) -> str:
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]
    if len(parts) <= max_sentences:
        return text.strip()
    return " ".join(parts[:max_sentences]).strip()


def _evidence_for_candidate(
    evidence_units: tuple[EvidenceUnit, ...],
    candidate: CandidateRecord,
) -> tuple[EvidenceUnit, ...]:
    source_ids = set(candidate.lineage.source_evidence_ids)
    matched = tuple(evidence for evidence in evidence_units if evidence.evidence_id in source_ids)
    return matched or evidence_units[:3]


def _build_stage_evidence_anchors(
    evidence_units: tuple[EvidenceUnit, ...],
) -> tuple[StageEvidenceAnchor, ...]:
    evidence_ids = tuple(evidence.evidence_id for evidence in evidence_units)
    content_hashes = tuple(evidence.content_hash for evidence in evidence_units)
    return tuple(
        StageEvidenceAnchor(
            stage_name=stage_name,
            anchor_kind="canonical_input_reinjected",
            evidence_ids=evidence_ids,
            content_hashes=content_hashes,
        )
        for stage_name in ("generator", "refiner", "evaluator")
    )


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def normalized_edit_distance(left: str, right: str) -> float:
    if not left and not right:
        return 0.0
    return 1.0 - SequenceMatcher(a=left, b=right).ratio()


def _build_surfaced_frontier(
    candidates: tuple[CandidateRecord, ...],
    frontier: tuple[FrontierEntry, ...],
    *,
    limit: int,
) -> tuple[FrontierEntry, ...]:
    selected: list[CandidateRecord] = []
    selected_ids: set[UUID] = set()
    for entry in frontier:
        if _is_materially_distinct_from_selected(entry.candidate, selected):
            selected.append(entry.candidate)
            selected_ids.add(entry.candidate.candidate_id)
        if len(selected) == limit:
            break

    if len(selected) < limit:
        ranked_candidates = sorted(
            candidates,
            key=lambda candidate: (
                candidate.state is not CandidateState.EVALUATED,
                -frontier_score(candidate),
                str(candidate.candidate_id),
            ),
        )
        for candidate in ranked_candidates:
            if candidate.candidate_id in selected_ids:
                continue
            if not _is_materially_distinct_from_selected(candidate, selected):
                continue
            selected.append(candidate)
            selected_ids.add(candidate.candidate_id)
            if len(selected) == limit:
                break

    return tuple(
        FrontierEntry(candidate=candidate, frontier_score=frontier_score(candidate), rank=index)
        for index, candidate in enumerate(selected[:limit], start=1)
    )


def _ensure_distinct_generated_candidates(
    drafts: list[RawGeneratedCandidate],
    fallback_candidates: tuple[RawGeneratedCandidate, ...],
) -> tuple[RawGeneratedCandidate, ...]:
    selected: list[RawGeneratedCandidate] = []
    used_strategies: set[str] = set()

    for draft in drafts:
        strategy = _primary_strategy(draft.semantic_tags)
        if strategy in used_strategies:
            continue
        if any(not _raw_candidates_materially_distinct(draft, existing) for existing in selected):
            continue
        selected.append(
            RawGeneratedCandidate(
                candidate_type=draft.candidate_type,
                title=draft.title or _strategy_title(strategy, len(selected) + 1),
                content=_truncate(draft.content),
                source_evidence_ids=draft.source_evidence_ids,
                impact=draft.impact,
                confidence=draft.confidence,
                ease=draft.ease,
                semantic_tags=_ensure_strategy_tags(draft.semantic_tags, strategy),
            )
        )
        used_strategies.add(strategy)
        if len(selected) == 3:
            return tuple(selected)

    for fallback in fallback_candidates:
        strategy = _primary_strategy(fallback.semantic_tags)
        if strategy in used_strategies and len(used_strategies) < 3:
            continue
        if any(
            not _raw_candidates_materially_distinct(fallback, existing)
            for existing in selected
        ):
            continue
        selected.append(fallback)
        used_strategies.add(strategy)
        if len(selected) == 3:
            return tuple(selected)

    return tuple(selected[:3] or fallback_candidates[:3])


def _is_materially_distinct_from_selected(
    candidate: CandidateRecord,
    selected: list[CandidateRecord],
) -> bool:
    for existing in selected:
        if _primary_strategy(candidate.semantic_tags) == _primary_strategy(existing.semantic_tags):
            return False
        if normalized_edit_distance(candidate.content.lower(), existing.content.lower()) < 0.22:
            return False
    return True


def _raw_candidates_materially_distinct(
    candidate: RawGeneratedCandidate,
    existing: RawGeneratedCandidate,
) -> bool:
    if _primary_strategy(candidate.semantic_tags) == _primary_strategy(existing.semantic_tags):
        return False
    return normalized_edit_distance(candidate.content.lower(), existing.content.lower()) >= 0.22


def _primary_strategy(tags: tuple[str, ...] | list[str], fallback_index: int | None = None) -> str:
    normalized = [str(tag).strip().lower() for tag in tags if str(tag).strip()]
    if "advance" in normalized or "next_step" in normalized or "confirm" in normalized:
        return "advance"
    if "clarify" in normalized or "risk_manage" in normalized or "risk" in normalized:
        return "clarify"
    for strategy in ("direct", "advance", "clarify"):
        if strategy in normalized:
            return strategy
    if fallback_index == 2:
        return "advance"
    if fallback_index == 3:
        return "clarify"
    return "direct"


def _ensure_strategy_tags(tags: tuple[str, ...] | list[str], strategy: str) -> tuple[str, ...]:
    normalized = [str(tag).strip().lower() for tag in tags if str(tag).strip()]
    if strategy not in normalized:
        normalized.insert(0, strategy)
    return tuple(dict.fromkeys(normalized))


def _strategy_title(strategy: str, index: int) -> str:
    mapping = {
        "direct": "Direct reply",
        "advance": "Advance with next step",
        "clarify": "Clarify or risk-manage",
    }
    return mapping.get(strategy, f"Draft option {index}")
