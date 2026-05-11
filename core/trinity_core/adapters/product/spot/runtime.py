"""Bounded Spot reasoning runtime built on Trinity shared services."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from trinity_core.memory import (
    ReplyMemoryStore,
    SpotMemoryResolver,
    build_runtime_memory_profile,
)
from trinity_core.model_config import load_model_config
from trinity_core.ops.cycle_store import RuntimeCycleStore, dataclass_payload
from trinity_core.ops.runtime_trace import (
    build_runtime_loop_decision_payload,
    build_runtime_memory_context_payload,
    persist_runtime_trace,
)
from trinity_core.ops.spot_policy_store import SpotPolicyStore
from trinity_core.schemas import (
    ConfidenceBundle,
    LoopAction,
    MemoryRecordFamily,
    MemorySummary,
    MinorityReport,
    SpotReasoningCandidate,
    SpotReasoningRequest,
    SpotReasoningResult,
    SpotReviewDisposition,
    SpotReviewOutcome,
    SpotTrainingBundle,
)
from trinity_core.workflow import build_hitl_escalation, decide_loop_action_from_signals

_RISKY_IDENTITY_TERMS = (
    "zionist",
    "jew",
    "globalist",
    "traitor",
    "boycott",
    "parasite",
)
_VIOLENT_THREAT_TERMS = (
    "kill",
    "eliminate",
    "destroy",
    "wipe out",
    "weapon",
    "weapons",
    "shoot",
    "bomb",
    "attack",
    "stab",
    "hunt",
    "make them pay",
)


class SpotRuntime:
    """Minimal Trinity runtime slice for Spot message reasoning."""

    def __init__(
        self,
        *,
        store: RuntimeCycleStore | None = None,
        memory_store: ReplyMemoryStore | None = None,
        policy_store: SpotPolicyStore | None = None,
    ) -> None:
        self.store = store or RuntimeCycleStore(adapter_name="spot")
        self.memory_store = memory_store or ReplyMemoryStore(adapter_name="spot")
        self.memory_resolver = SpotMemoryResolver(self.memory_store)
        self.policy_store = policy_store or SpotPolicyStore()
        self.model_config = load_model_config("spot")
        self.model_provider = None

    @property
    def ollama_client(self) -> Any:
        return self.model_provider

    def reason_spot(self, request: SpotReasoningRequest) -> SpotReasoningResult:
        cycle_id = uuid4()
        generated_at = request.occurred_at or datetime.now(UTC)
        memory_context = self.memory_resolver.resolve_for_request(request)
        memory_profile = build_runtime_memory_profile(memory_context)
        candidates = self._build_candidates(request, memory_context, memory_profile)
        confidence_bundle = self._build_confidence_bundle(candidates)
        minority_report = self._build_minority_report(
            cycle_id=cycle_id,
            request=request,
            candidates=candidates,
            memory_context=memory_context,
        )
        loop_history: list[dict[str, Any]] = []
        loop_decision = decide_loop_action_from_signals(
            confidence_bundle=confidence_bundle,
            minority_report=minority_report,
            loop_count=0,
            max_loop_count=1,
            minimum_combined_confidence=0.62,
            high_risk=self._is_high_risk(request),
        )
        loop_history.append(
            {
                "loop_count": loop_decision.loop_count,
                "action": loop_decision.action.value,
                "reason": loop_decision.reason,
                "combined_confidence": loop_decision.confidence_bundle.combined_confidence,
            }
        )
        if loop_decision.action is LoopAction.REWORK:
            candidates = self._rework_candidates(
                candidates,
                memory_profile=memory_profile,
                minority_report=minority_report,
            )
            confidence_bundle = self._build_confidence_bundle(candidates, reworked=True)
            minority_report = self._build_minority_report(
                cycle_id=cycle_id,
                request=request,
                candidates=candidates,
                memory_context=memory_context,
                reworked=True,
            )
            loop_decision = decide_loop_action_from_signals(
                confidence_bundle=confidence_bundle,
                minority_report=minority_report,
                loop_count=1,
                max_loop_count=1,
                minimum_combined_confidence=0.62,
                high_risk=self._is_high_risk(request),
            )
            loop_history.append(
                {
                    "loop_count": loop_decision.loop_count,
                    "action": loop_decision.action.value,
                    "reason": loop_decision.reason,
                    "combined_confidence": loop_decision.confidence_bundle.combined_confidence,
                }
            )
        selected = candidates[0]
        review_policy = self._review_policy(
            request=request,
            selected=selected,
            confidence_bundle=confidence_bundle,
            loop_decision_action=loop_decision.action,
        )
        hitl_escalation = (
            build_hitl_escalation(
                cycle_id=cycle_id,
                adapter_name="spot",
                company_id=request.company_id,
                majority_result_ref=selected.candidate_key,
                decision_target="spot_row_review_decision",
                loop_decision=loop_decision,
                memory_factors=memory_context.selected_keys[:6],
                created_at=generated_at,
            )
            if loop_decision.action is LoopAction.ESCALATE
            else None
        )
        result = SpotReasoningResult(
            company_id=request.company_id,
            run_id=request.run_id,
            row_ref=request.row_ref,
            generated_at=generated_at,
            candidates=candidates,
            selected_candidate_key=selected.candidate_key,
            confidence_bundle=confidence_bundle,
            review_required=review_policy["review_required"],
            review_reason=review_policy["review_reason"],
            policy_sensitive=review_policy["policy_sensitive"],
            automatic_disposition=review_policy["automatic_disposition"],
            human_override_allowed=True,
            deeper_analysis_available=True,
            escalation_recommended=loop_decision.action is LoopAction.ESCALATE,
            minority_report=minority_report,
            metadata={
                "source_platform": request.source_platform,
                "review_reason": review_policy["review_reason"],
                "policy_sensitive": review_policy["policy_sensitive"],
                "automatic_disposition": review_policy["automatic_disposition"],
                "runtime_memory_context": build_runtime_memory_context_payload(memory_context),
                "runtime_memory_profile": memory_profile.prompt_payload(),
                "runtime_loop_history": loop_history,
                "runtime_loop_decision": build_runtime_loop_decision_payload(
                    {
                        "majority_candidate_key": selected.candidate_key,
                        "majority_reason": selected.rationale,
                        "confidence_bundle": confidence_bundle,
                        "minority_report": minority_report,
                    },
                    loop_decision,
                ),
                "runtime_hitl_escalation": (
                    dataclass_payload(hitl_escalation) if hitl_escalation is not None else {}
                ),
            },
        )
        trace_payload = {
            "cycle_id": str(cycle_id),
            "company_id": str(request.company_id),
            "exported_at": generated_at.isoformat(),
            "spot_reasoning_request": {
                "company_id": str(request.company_id),
                "run_id": request.run_id,
                "row_ref": request.row_ref,
                "language": request.language,
                "message_text": request.message_text,
                "source_platform": request.source_platform,
                "source_handle": request.source_handle,
                "metadata": dict(request.metadata),
            },
            "spot_reasoning_result": {
                "company_id": str(result.company_id),
                "run_id": result.run_id,
                "row_ref": result.row_ref,
                "generated_at": result.generated_at.isoformat(),
                "candidates": [
                    {
                        "candidate_key": candidate.candidate_key,
                        "interpretation": candidate.interpretation,
                        "rationale": candidate.rationale,
                        "threat_label_hint": candidate.threat_label_hint,
                        "review_recommended": candidate.review_recommended,
                    }
                    for candidate in result.candidates
                ],
                "selected_candidate_key": result.selected_candidate_key,
                "review_required": result.review_required,
                "review_reason": result.review_reason,
                "policy_sensitive": result.policy_sensitive,
                "automatic_disposition": result.automatic_disposition,
                "human_override_allowed": result.human_override_allowed,
                "deeper_analysis_available": result.deeper_analysis_available,
                "escalation_recommended": result.escalation_recommended,
                "candidate_count": len(result.candidates),
                "confidence_bundle": {
                    "generator_confidence": result.confidence_bundle.generator_confidence,
                    "refiner_confidence": result.confidence_bundle.refiner_confidence,
                    "evaluator_confidence": result.confidence_bundle.evaluator_confidence,
                    "frontier_confidence": result.confidence_bundle.frontier_confidence,
                    "combined_confidence": result.confidence_bundle.combined_confidence,
                    "disagreement_severity": result.confidence_bundle.disagreement_severity,
                },
                "minority_report": (
                    {
                        "minority_result_ref": result.minority_report.minority_result_ref,
                        "dissent_reason": result.minority_report.dissent_reason,
                    }
                    if result.minority_report is not None
                    else None
                ),
            },
            "runtime_memory_context": build_runtime_memory_context_payload(memory_context),
            "runtime_memory_profile": memory_profile.prompt_payload(),
            "runtime_loop_history": loop_history,
            "runtime_loop_decision": build_runtime_loop_decision_payload(
                {
                    "majority_candidate_key": selected.candidate_key,
                    "majority_reason": selected.rationale,
                    "confidence_bundle": confidence_bundle,
                    "minority_report": minority_report,
                },
                loop_decision,
            ),
            "runtime_hitl_escalation": (
                dataclass_payload(hitl_escalation) if hitl_escalation is not None else {}
            ),
        }
        trace = _PayloadTrace(cycle_id=cycle_id, payload=trace_payload)
        persist_runtime_trace(self.store, trace)
        return SpotReasoningResult(
            company_id=result.company_id,
            run_id=result.run_id,
            row_ref=result.row_ref,
            generated_at=result.generated_at,
            candidates=result.candidates,
            selected_candidate_key=result.selected_candidate_key,
            confidence_bundle=result.confidence_bundle,
            review_required=result.review_required,
            review_reason=result.review_reason,
            policy_sensitive=result.policy_sensitive,
            automatic_disposition=result.automatic_disposition,
            human_override_allowed=result.human_override_allowed,
            deeper_analysis_available=result.deeper_analysis_available,
            escalation_recommended=result.escalation_recommended,
            minority_report=result.minority_report,
            trace_ref=str(self.store.export_path(cycle_id)),
            metadata=result.metadata,
        )

    def export_trace(self, cycle_id: Any) -> dict[str, Any]:
        payload = self.store.load_cycle(cycle_id)
        export_path = self.store.save_export(cycle_id, payload)
        return {"cycle_id": str(cycle_id), "trace_ref": str(export_path), "trace": payload}

    def record_review_outcome(self, outcome: SpotReviewOutcome) -> dict[str, Any]:
        payload = self.store.load_cycle(outcome.cycle_id, outcome.company_id)
        payload.setdefault("spot_review_outcomes", []).append(dataclass_payload(outcome))
        self.store.save_cycle(outcome.cycle_id, payload)
        export_path = self.store.save_export(outcome.cycle_id, payload)
        for summary in _spot_outcome_memory_summaries(outcome, payload):
            self.memory_store.save_summary(summary)
        return {
            "status": "ok",
            "cycle_id": str(outcome.cycle_id),
            "trace_ref": str(export_path),
        }

    def export_training_bundle(
        self,
        cycle_id: UUID,
        *,
        bundle_type: str,
    ) -> dict[str, Any]:
        payload = self.store.load_cycle(cycle_id)
        bundle = spot_training_bundle_from_payload(payload, bundle_type=str(bundle_type))
        bundle_path = self.store.save_bundle(bundle.bundle_id, dataclass_payload(bundle))
        return {
            "bundle_id": str(bundle.bundle_id),
            "bundle_path": str(bundle_path),
            "bundle": dataclass_payload(bundle),
        }

    def _build_candidates(
        self,
        request: SpotReasoningRequest,
        memory_context: Any,
        memory_profile: Any,
    ) -> tuple[SpotReasoningCandidate, ...]:
        text = request.message_text.lower()
        has_risky = any(term in text for term in _RISKY_IDENTITY_TERMS)
        has_hostile = any(term in text for term in _VIOLENT_THREAT_TERMS)
        memory_parts: list[str] = []
        if memory_context.records:
            memory_parts.append(f"Retrieved memory records: {len(memory_context.records)}.")
        if memory_profile.anti_pattern_hints:
            memory_parts.append(
                "Known anti-patterns: " + " | ".join(memory_profile.anti_pattern_hints[:2])
            )
        if memory_profile.successful_pattern_hints:
            memory_parts.append(
                "Successful patterns: "
                + " | ".join(memory_profile.successful_pattern_hints[:2])
            )
        if memory_profile.ranked_memory_lines:
            memory_parts.append(
                "Ranked memory: " + " | ".join(memory_profile.ranked_memory_lines[:2])
            )
        if memory_profile.working_summary:
            memory_parts.append("Working memory: " + memory_profile.working_summary)
        memory_note = (" " + " ".join(memory_parts)) if memory_parts else ""
        primary_label = "Conspiracy Theories" if "globalist" in text else "Structural Antisemitism"
        if has_hostile:
            primary_label = "Classical Antisemitism"
        primary = SpotReasoningCandidate(
            candidate_key="primary",
            interpretation=(
                "Message likely contains antisemitic or threat-relevant rhetoric."
                if has_risky or has_hostile
                else "Message likely falls outside the strongest threat patterns."
            ),
            rationale=(
                "Deterministic heuristic identified hostile or loaded language."
                if has_risky or has_hostile
                else "Deterministic heuristic did not find strong threat-language anchors."
            )
            + memory_note,
            threat_label_hint=primary_label if has_risky or has_hostile else "Not Antisemitic",
            review_recommended=has_hostile,
        )
        review = SpotReasoningCandidate(
            candidate_key="review",
            interpretation="Message remains ambiguous enough to justify human review.",
            rationale=(
                "Borderline phrasing, sarcasm, or context collapse may change classification."
                + memory_note
            ),
            threat_label_hint=primary_label if has_risky else "Not Antisemitic",
            review_recommended=has_risky,
        )
        benign = SpotReasoningCandidate(
            candidate_key="benign",
            interpretation="Message may be non-antisemitic or context-dependent.",
            rationale="No deterministic signal alone is sufficient for a stronger classification.",
            threat_label_hint="Not Antisemitic",
            review_recommended=False,
        )
        if has_hostile:
            return (primary, review, benign)
        if has_risky:
            return (review, primary, benign)
        return (benign, review, primary)

    def _build_confidence_bundle(
        self,
        candidates: tuple[SpotReasoningCandidate, ...],
        *,
        reworked: bool = False,
    ) -> ConfidenceBundle:
        selected = candidates[0]
        if selected.candidate_key == "primary":
            combined = 0.82 if reworked else 0.78
            disagreement = 0.14 if reworked else 0.18
        elif selected.candidate_key == "review":
            combined = 0.61 if reworked else 0.56
            disagreement = 0.32 if reworked else 0.44
        else:
            combined = 0.75 if reworked else 0.72
            disagreement = 0.12 if reworked else 0.16
        return ConfidenceBundle(
            generator_confidence=combined,
            refiner_confidence=min(1.0, combined + 0.04),
            evaluator_confidence=max(0.0, combined - 0.02),
            frontier_confidence=combined,
            combined_confidence=combined,
            disagreement_severity=disagreement,
        )

    def _build_minority_report(
        self,
        *,
        cycle_id,
        request: SpotReasoningRequest,
        candidates: tuple[SpotReasoningCandidate, ...],
        memory_context: Any,
        reworked: bool = False,
    ) -> MinorityReport | None:
        if candidates[0].candidate_key != "review":
            return None
        return MinorityReport(
            cycle_id=cycle_id,
            adapter="spot",
            company_id=request.company_id,
            majority_result_ref=candidates[0].candidate_key,
            minority_result_ref=candidates[1].candidate_key,
            dissent_source="spot_reasoning_rework" if reworked else "spot_reasoning_alternate",
            dissent_reason=(
                "Rework preserved ambiguity after memory-guided review."
                if reworked
                else "Primary deterministic interpretation remains plausible but unresolved."
            ),
            disagreement_severity=0.32 if reworked else 0.44,
            memory_factors=memory_context.selected_keys[:6],
            recommended_action=LoopAction.ESCALATE.value,
            created_at=request.occurred_at or datetime.now(UTC),
        )

    def _rework_candidates(
        self,
        candidates: tuple[SpotReasoningCandidate, ...],
        *,
        memory_profile: Any,
        minority_report: MinorityReport | None,
    ) -> tuple[SpotReasoningCandidate, ...]:
        review = candidates[0]
        review_note_parts: list[str] = [
            "Rework pass checked disagreement and preserved the cautious route.",
        ]
        if minority_report is not None:
            review_note_parts.append(minority_report.dissent_reason)
        if memory_profile.correction_hints:
            review_note_parts.append(
                "Corrections: " + " | ".join(memory_profile.correction_hints[:2])
            )
        if memory_profile.disagreement_hints:
            review_note_parts.append(
                "Past disagreements: " + " | ".join(memory_profile.disagreement_hints[:2])
            )
        if memory_profile.core_summary:
            review_note_parts.append("Core memory: " + memory_profile.core_summary)
        if memory_profile.ranked_memory_lines:
            review_note_parts.append(
                "Ranked memory: " + " | ".join(memory_profile.ranked_memory_lines[:2])
            )
        reworked_review = SpotReasoningCandidate(
            candidate_key=review.candidate_key,
            interpretation=review.interpretation,
            rationale=review.rationale + " " + " ".join(review_note_parts),
            threat_label_hint=review.threat_label_hint,
            review_recommended=True,
        )
        return (reworked_review, *candidates[1:])

    def _is_high_risk(self, request: SpotReasoningRequest) -> bool:
        text = request.message_text.lower()
        return any(term in text for term in _VIOLENT_THREAT_TERMS)

    def _review_policy(
        self,
        *,
        request: SpotReasoningRequest,
        selected: SpotReasoningCandidate,
        confidence_bundle: ConfidenceBundle,
        loop_decision_action: LoopAction,
    ) -> dict[str, Any]:
        high_risk = self._is_high_risk(request)
        positive_detection = (selected.threat_label_hint or "Not Antisemitic") != "Not Antisemitic"
        policy_sensitive = high_risk or positive_detection
        active_policy = self.policy_store.resolve(company_id=request.company_id)
        threshold = (
            active_policy.policy.auto_approve_negative_threshold
            if active_policy is not None
            else 0.72
        )
        positive_review_required = (
            active_policy.policy.positive_review_required
            if active_policy is not None
            else True
        )
        default_review_required = (
            active_policy.policy.default_review_required
            if active_policy is not None
            else True
        )
        if loop_decision_action is LoopAction.ESCALATE:
            return {
                "review_required": True,
                "review_reason": (
                    "Runtime ambiguity or risk exceeded the bounded machine threshold."
                ),
                "policy_sensitive": True,
                "automatic_disposition": "review_required",
            }
        if positive_detection and positive_review_required:
            return {
                "review_required": True,
                "review_reason": (
                    "Positive threat classification stays review-required even at high confidence."
                ),
                "policy_sensitive": True,
                "automatic_disposition": "review_required",
            }
        if (
            selected.candidate_key == "benign"
            and not high_risk
            and confidence_bundle.combined_confidence >= threshold
        ):
            return {
                "review_required": False,
                "review_reason": (
                    "High-confidence negative outcome may auto-pass under Spot policy."
                ),
                "policy_sensitive": policy_sensitive,
                "automatic_disposition": "auto_approve",
            }
        return {
            "review_required": default_review_required,
            "review_reason": (
                "Outcome remains reviewable under Spot policy despite bounded machine"
                " reasoning."
            ),
            "policy_sensitive": policy_sensitive,
            "automatic_disposition": "review_required",
        }


class _PayloadTrace:
    def __init__(self, *, cycle_id, payload) -> None:
        self.cycle_id = cycle_id
        self.payload = payload


def spot_training_bundle_from_payload(
    payload: dict[str, Any],
    *,
    bundle_type: str,
) -> SpotTrainingBundle:
    review_payloads = payload.get("spot_review_outcomes", [])
    if not review_payloads:
        raise ValueError("Cannot export Spot training bundle without spot_review_outcomes.")
    latest_review = sorted(
        review_payloads,
        key=lambda item: (
            str(item.get("occurred_at") or ""),
            str(item.get("disposition") or ""),
        ),
    )[-1]
    request_payload = payload.get("spot_reasoning_request")
    result_payload = payload.get("spot_reasoning_result")
    if not isinstance(request_payload, dict) or not isinstance(result_payload, dict):
        raise ValueError("Spot training bundle export requires request and result payloads.")
    cycle_id = UUID(str(payload["cycle_id"]))
    request = SpotReasoningRequest(
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
        occurred_at=_parse_datetime(str(payload["exported_at"])),
        metadata={str(key): value for key, value in request_payload.get("metadata", {}).items()},
    )
    result = SpotReasoningResult(
        company_id=UUID(str(payload["company_id"])),
        run_id=str(request_payload["run_id"]),
        row_ref=str(request_payload["row_ref"]),
        generated_at=_parse_datetime(str(payload["exported_at"])),
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
            for item in result_payload.get("candidates", [])
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
        automatic_disposition=str(result_payload.get("automatic_disposition") or "review_required"),
        human_override_allowed=bool(result_payload.get("human_override_allowed", True)),
        deeper_analysis_available=bool(result_payload.get("deeper_analysis_available", True)),
        escalation_recommended=bool(result_payload.get("escalation_recommended", False)),
        trace_ref=str(payload.get("trace_ref") or ""),
        metadata={
            "runtime_loop_history": result_payload.get("runtime_loop_history", []),
        },
    )
    review_outcome = SpotReviewOutcome(
        company_id=UUID(str(latest_review["company_id"])),
        cycle_id=UUID(str(latest_review["cycle_id"])),
        run_id=str(latest_review["run_id"]),
        row_ref=str(latest_review["row_ref"]),
        selected_candidate_key=str(latest_review["selected_candidate_key"]),
        disposition=SpotReviewDisposition(str(latest_review["disposition"])),
        final_label=str(latest_review["final_label"]),
        occurred_at=_parse_datetime(str(latest_review["occurred_at"])),
        reviewer_notes=(
            str(latest_review["reviewer_notes"])
            if latest_review.get("reviewer_notes") is not None
            else None
        ),
        metadata={str(key): value for key, value in latest_review.get("metadata", {}).items()},
    )
    return SpotTrainingBundle(
        bundle_id=SpotTrainingBundle.build_bundle_id(cycle_id=cycle_id, bundle_type=bundle_type),
        bundle_type=bundle_type,
        exported_at=_parse_datetime(str(latest_review["occurred_at"])),
        spot_reasoning_request=request,
        spot_reasoning_result=result,
        spot_review_outcome=review_outcome,
        labels={
            "bundle_type": str(bundle_type),
            "cycle_id": str(cycle_id),
            "company_id": str(payload["company_id"]),
            "automatic_disposition": result.automatic_disposition,
            "review_required": "true" if result.review_required else "false",
            "policy_sensitive": "true" if result.policy_sensitive else "false",
            "disposition": review_outcome.disposition.value,
            "final_label": review_outcome.final_label,
        },
    )


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware.")
    return parsed


def _spot_outcome_memory_summaries(
    outcome: SpotReviewOutcome,
    payload: dict[str, Any],
) -> tuple[MemorySummary, ...]:
    company_scope = f"company:{outcome.company_id}"
    human_scope = f"human:row:{outcome.row_ref}"
    cycle_key = str(outcome.cycle_id).replace("-", "")
    summaries: list[MemorySummary] = [
        MemorySummary(
            company_id=outcome.company_id,
            summary_key=f"spot_human_resolution_{cycle_key}",
            scope_ref=human_scope,
            content=_spot_human_resolution_text(outcome),
            updated_at=outcome.occurred_at,
            metadata={
                "family": MemoryRecordFamily.HUMAN_RESOLUTION.value,
                "cycle_id": str(outcome.cycle_id),
                "run_id": outcome.run_id,
                "row_ref": outcome.row_ref,
                "selected_candidate_key": outcome.selected_candidate_key,
                "disposition": outcome.disposition.value,
                "final_label": outcome.final_label,
            },
        )
    ]
    family = _spot_outcome_family(outcome.disposition)
    summaries.append(
        MemorySummary(
            company_id=outcome.company_id,
            summary_key=f"spot_{family.value}_{cycle_key}",
            scope_ref=company_scope,
            content=_spot_family_text(outcome, family=family),
            updated_at=outcome.occurred_at,
            metadata={
                "family": family.value,
                "cycle_id": str(outcome.cycle_id),
                "run_id": outcome.run_id,
                "row_ref": outcome.row_ref,
                "selected_candidate_key": outcome.selected_candidate_key,
                "disposition": outcome.disposition.value,
                "final_label": outcome.final_label,
            },
        )
    )
    minority_report = (
        payload.get("runtime_loop_decision", {}).get("consensus", {}).get("minority_report")
    )
    if minority_report:
        summaries.append(
            MemorySummary(
                company_id=outcome.company_id,
                summary_key=f"spot_disagreement_{cycle_key}",
                scope_ref=company_scope,
                content=_spot_disagreement_text(outcome, minority_report=minority_report),
                updated_at=outcome.occurred_at,
                metadata={
                    "family": MemoryRecordFamily.DISAGREEMENT.value,
                    "cycle_id": str(outcome.cycle_id),
                    "run_id": outcome.run_id,
                    "row_ref": outcome.row_ref,
                    "selected_candidate_key": outcome.selected_candidate_key,
                    "disposition": outcome.disposition.value,
                    "final_label": outcome.final_label,
                    "minority_result_ref": str(
                        minority_report.get("minority_result_ref") or ""
                    ),
                },
            )
        )
    return tuple(summaries)


def _spot_outcome_family(disposition: SpotReviewDisposition) -> MemoryRecordFamily:
    if disposition in {
        SpotReviewDisposition.CONFIRMED_POSITIVE,
        SpotReviewDisposition.CONFIRMED_NEGATIVE,
    }:
        return MemoryRecordFamily.SUCCESSFUL_PATTERN
    if disposition is SpotReviewDisposition.CORRECTED:
        return MemoryRecordFamily.CORRECTION
    return MemoryRecordFamily.ANTI_PATTERN


def _spot_human_resolution_text(outcome: SpotReviewOutcome) -> str:
    notes = " ".join(str(outcome.reviewer_notes or "").split())
    base = (
        f"Human resolved Spot row {outcome.row_ref} as {outcome.disposition.value} "
        f"with label {outcome.final_label}."
    )
    if notes:
        return f"{base} {notes[:180]}"
    return base


def _spot_family_text(
    outcome: SpotReviewOutcome,
    *,
    family: MemoryRecordFamily,
) -> str:
    if family is MemoryRecordFamily.SUCCESSFUL_PATTERN:
        return (
            f"Spot reviewer confirmed {outcome.final_label} for row {outcome.row_ref} "
            f"with disposition {outcome.disposition.value}."
        )
    if family is MemoryRecordFamily.CORRECTION:
        return (
            f"Spot reviewer corrected row {outcome.row_ref} to {outcome.final_label}."
        )
    return (
        f"Spot reviewer suppressed or rejected the machine path for row {outcome.row_ref} "
        f"with final label {outcome.final_label}."
    )


def _spot_disagreement_text(
    outcome: SpotReviewOutcome,
    *,
    minority_report: dict[str, Any],
) -> str:
    reason = str(minority_report.get("dissent_reason") or "").strip()
    if reason:
        return (
            f"Spot disagreement persisted for row {outcome.row_ref} and the reviewer resolved it "
            f"as {outcome.final_label}: {reason[:180]}"
        )
    return (
        f"Spot disagreement persisted for row {outcome.row_ref} and the reviewer resolved it "
        f"as {outcome.final_label}."
    )
