"""Deterministic Reply runtime spine owned by Trinity."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any
from uuid import UUID, uuid4

from trinity_core.ops.cycle_store import RuntimeCycleStore, dataclass_payload
from trinity_core.schemas import (
    AcceptedArtifactVersion,
    CandidateDraft,
    CandidateRecord,
    CandidateState,
    CandidateType,
    DraftOutcomeDisposition,
    DraftOutcomeEvent,
    EvidenceProvenance,
    EvidenceSourceRef,
    EvidenceSourceType,
    GoldenExample,
    RankedDraftSet,
    ReplyFeedbackDisposition,
    ReplyFeedbackEvent,
    ReworkRoute,
    RuntimeTraceExport,
    ThreadContextSnippet,
    ThreadMessageRole,
    ThreadMessageSnapshot,
    ThreadSnapshot,
)
from trinity_core.workflow import (
    EvaluationDisposition,
    EvaluatorExecutionInput,
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
    execute_candidate_pipeline,
    ingest_evidence,
)

ARTIFACT_VERSION = "reply_ranker_policy.v0"
ARTIFACT_KEY = "reply_ranker_policy"
ARTIFACT_SOURCE_PROJECT = "trinity"


class ReplyRuntime:
    """Local runtime spine for Reply integration."""

    def __init__(self, store: RuntimeCycleStore | None = None) -> None:
        self.store = store or RuntimeCycleStore()

    def suggest(self, snapshot: ThreadSnapshot) -> RankedDraftSet:
        cycle_id = uuid4()
        cycle_time = snapshot.requested_at
        evidence_units = self._build_evidence(snapshot)
        pipeline = execute_candidate_pipeline(
            GeneratorExecutionInput(
                company_id=snapshot.company_id,
                evidence_units=evidence_units,
                strategic_context={
                    "channel": snapshot.channel,
                    "contact_handle": snapshot.contact_handle,
                },
                topic_anchors=tuple(_topic_anchors(snapshot)),
                freshness_reference=snapshot.requested_at,
            ),
            generator_runner=self._generator_runner(snapshot),
            refiner_runner=self._refiner_runner(snapshot),
            evaluator_runner=self._evaluator_runner(snapshot),
            now=cycle_time,
        )
        frontier = build_frontier(pipeline.evaluated.records, limit=3)
        artifact = AcceptedArtifactVersion(
            artifact_key=ARTIFACT_KEY,
            version=ARTIFACT_VERSION,
            source_project=ARTIFACT_SOURCE_PROJECT,
            accepted_at=cycle_time,
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
                    risk_flags=_risk_flags(entry.candidate, snapshot),
                    delivery_eligible=entry.candidate.state is CandidateState.EVALUATED,
                )
                for entry in frontier
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
            frontier_candidate_ids=tuple(entry.candidate.candidate_id for entry in frontier),
            ranked_draft_set=ranked,
            accepted_artifact_version=artifact,
            model_routes={
                "generator": "deterministic:v0",
                "refiner": "deterministic:v0",
                "evaluator": "deterministic:v0",
            },
        )
        self._persist_cycle(trace)
        return replace(ranked, trace_ref=str(self.store.export_path(cycle_id)))

    def record_outcome(self, event: DraftOutcomeEvent) -> dict[str, Any]:
        payload = self.store.load_cycle(event.cycle_id)
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
        return {"status": "ok", "cycle_id": str(event.cycle_id), "trace_ref": str(export_path)}

    def export_trace(self, cycle_id: UUID) -> dict[str, Any]:
        payload = self.store.load_cycle(cycle_id)
        export_path = self.store.save_export(cycle_id, payload)
        return {"cycle_id": str(cycle_id), "trace_ref": str(export_path), "trace": payload}

    def _build_evidence(self, snapshot: ThreadSnapshot) -> tuple[Any, ...]:
        store = InMemoryEvidenceStore()
        accepted = []
        for raw in _raw_evidence(snapshot):
            result = ingest_evidence(raw, store=store, now=snapshot.requested_at)
            if result.accepted is not None:
                accepted.append(result.accepted)
        return tuple(accepted)

    def _persist_cycle(self, trace: RuntimeTraceExport) -> None:
        payload = dataclass_payload(trace)
        self.store.save_cycle(trace.cycle_id, payload)
        self.store.save_export(trace.cycle_id, payload)

    def _generator_runner(self, snapshot: ThreadSnapshot):
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
                    content=direct,
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
                    content=confirm,
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
                    content=clarify,
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

    def _refiner_runner(self, snapshot: ThreadSnapshot):
        def runner(stage_input: RefinerExecutionInput):
            results = []
            for candidate in stage_input.generated_candidates:
                compact = _truncate(candidate.content.replace("  ", " "))
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

    def _evaluator_runner(self, snapshot: ThreadSnapshot):
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


def thread_snapshot_from_payload(payload: dict[str, Any]) -> ThreadSnapshot:
    return ThreadSnapshot(
        company_id=UUID(payload["company_id"]),
        thread_ref=str(payload["thread_ref"]),
        channel=str(payload["channel"]),
        contact_handle=str(payload["contact_handle"]),
        latest_inbound_text=str(payload["latest_inbound_text"]),
        requested_at=_parse_datetime(payload["requested_at"]),
        messages=tuple(
            ThreadMessageSnapshot(
                message_id=str(item["message_id"]),
                role=ThreadMessageRole(str(item["role"])),
                text=str(item["text"]),
                occurred_at=_parse_datetime(item["occurred_at"]),
                channel=str(item["channel"]),
                source=str(item["source"]),
                handle=str(item["handle"]),
            )
            for item in payload.get("messages", [])
        ),
        context_snippets=tuple(
            ThreadContextSnippet(
                source=str(item["source"]),
                path=str(item["path"]),
                text=str(item["text"]),
            )
            for item in payload.get("context_snippets", [])
        ),
        golden_examples=tuple(
            GoldenExample(path=str(item["path"]), text=str(item["text"]))
            for item in payload.get("golden_examples", [])
        ),
        metadata={str(key): str(value) for key, value in payload.get("metadata", {}).items()},
    )


def outcome_event_from_payload(payload: dict[str, Any]) -> DraftOutcomeEvent:
    return DraftOutcomeEvent(
        company_id=UUID(payload["company_id"]),
        cycle_id=UUID(payload["cycle_id"]),
        thread_ref=str(payload["thread_ref"]),
        channel=str(payload["channel"]),
        disposition=DraftOutcomeDisposition(str(payload["disposition"])),
        occurred_at=_parse_datetime(payload["occurred_at"]),
        candidate_id=UUID(payload["candidate_id"]) if payload.get("candidate_id") else None,
        original_draft_text=payload.get("original_draft_text"),
        final_text=payload.get("final_text"),
        edit_distance=float(payload["edit_distance"])
        if payload.get("edit_distance") is not None
        else None,
        latency_ms=int(payload["latency_ms"]) if payload.get("latency_ms") is not None else None,
        send_result=payload.get("send_result"),
        notes=payload.get("notes"),
    )


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


def _risk_flags(candidate: CandidateRecord, snapshot: ThreadSnapshot) -> tuple[str, ...]:
    flags = []
    if len(candidate.content) > 180:
        flags.append("long_draft")
    if "confirm the exact outcome" in candidate.content.lower():
        flags.append("needs_clarification")
    if len(snapshot.context_snippets) == 0:
        flags.append("low_context")
    return tuple(flags)


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


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def normalized_edit_distance(left: str, right: str) -> float:
    if not left and not right:
        return 0.0
    return 1.0 - SequenceMatcher(a=left, b=right).ratio()
