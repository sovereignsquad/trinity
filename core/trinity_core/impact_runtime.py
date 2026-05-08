"""Impact adapter runtime implementation behind the generic Trinity facade."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid5

from trinity_core.model_config import load_model_config_for_adapter
from trinity_core.ollama_client import OllamaChatClient
from trinity_core.ops.cycle_store import RuntimeCycleStore, dataclass_payload
from trinity_core.schemas import (
    CandidateType,
    EvidenceProvenance,
    EvidenceSourceRef,
    EvidenceSourceType,
)
from trinity_core.schemas.impact_integration import (
    IMPACT_CONTRACT_VERSION,
    ImpactModelSnapshot,
    ImpactProfileSnapshot,
    ImpactRankedRecommendationSet,
    ImpactRecommendationCandidate,
    ImpactRecommendationDisposition,
    ImpactRecommendationOutcomeEvent,
    ImpactRuntimeSnapshot,
    ImpactRuntimeTraceExport,
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
    build_frontier,
    execute_candidate_pipeline,
    frontier_score,
    ingest_evidence,
)

_IMPACT_TENANT_NAMESPACE = UUID("761bec12-837c-5928-98b7-c49a91a6bf5a")


class ImpactRuntime:
    """Local runtime spine for the Impact adapter."""

    def __init__(self, store: RuntimeCycleStore | None = None) -> None:
        self.store = store or RuntimeCycleStore(adapter_name="impact")
        self.model_config = load_model_config_for_adapter("impact")
        self.ollama_client = OllamaChatClient(
            base_url=self.model_config.ollama_base_url,
            timeout_seconds=self.model_config.timeout_seconds,
        )

    def suggest(self, snapshot: ImpactProfileSnapshot) -> ImpactRankedRecommendationSet:
        cycle_id = uuid5(
            _IMPACT_TENANT_NAMESPACE,
            f"{snapshot.project_ref}:{snapshot.profile_ref}:{snapshot.requested_at.isoformat()}",
        )
        tenant_id = _tenant_id(snapshot)
        evidence_units = self._build_evidence(snapshot, tenant_id)
        pipeline = execute_candidate_pipeline(
            GeneratorExecutionInput(
                company_id=tenant_id,
                evidence_units=evidence_units,
                strategic_context={
                    "project_ref": snapshot.project_ref,
                    "machine_class": snapshot.machine_class,
                    "os_name": snapshot.os_name,
                    "architecture": snapshot.architecture,
                },
                topic_anchors=tuple(_topic_anchors(snapshot)),
                freshness_reference=snapshot.requested_at,
            ),
            generator_runner=self._generator_runner(snapshot),
            refiner_runner=self._refiner_runner(snapshot),
            evaluator_runner=self._evaluator_runner(snapshot),
            now=snapshot.requested_at,
        )
        frontier = build_frontier(pipeline.evaluated.records, limit=3)
        surfaced_frontier = _build_surfaced_frontier(pipeline.evaluated.records, frontier, limit=3)
        ranked = ImpactRankedRecommendationSet(
            cycle_id=cycle_id,
            profile_ref=snapshot.profile_ref,
            generated_at=snapshot.requested_at,
            recommendations=tuple(
                ImpactRecommendationCandidate.from_candidate_record(
                    entry.candidate,
                    profile_ref=snapshot.profile_ref,
                    rank=entry.rank,
                    risk_flags=_risk_flags(entry.candidate.content),
                )
                for entry in surfaced_frontier
            ),
        )
        trace = ImpactRuntimeTraceExport(
            cycle_id=cycle_id,
            exported_at=snapshot.requested_at,
            snapshot_hash=_snapshot_hash(snapshot),
            profile_snapshot=snapshot,
            evidence_units=evidence_units,
            candidates=pipeline.evaluated.records,
            frontier_candidate_ids=tuple(
                entry.candidate.candidate_id for entry in surfaced_frontier
            ),
            ranked_recommendation_set=ranked,
            model_routes=self._model_routes(),
        )
        self._persist_cycle(trace)
        return replace(ranked, trace_ref=str(self.store.export_path(cycle_id)))

    def record_outcome(self, event: ImpactRecommendationOutcomeEvent) -> dict[str, Any]:
        payload = self.store.load_cycle(event.cycle_id)
        payload.setdefault("feedback_events", []).append(dataclass_payload(event))
        self.store.save_cycle(event.cycle_id, payload)
        export_path = self.store.save_export(event.cycle_id, payload)
        return {"status": "ok", "cycle_id": str(event.cycle_id), "trace_ref": str(export_path)}

    def export_trace(self, cycle_id: UUID) -> dict[str, Any]:
        payload = self.store.load_cycle(cycle_id)
        export_path = self.store.save_export(cycle_id, payload)
        return {"cycle_id": str(cycle_id), "trace_ref": str(export_path), "trace": payload}

    def export_training_bundle(self, cycle_id: UUID, *, bundle_type: Any) -> dict[str, Any]:
        raise ValueError(
            "Impact adapter does not export training bundles yet. "
            "Only the Reply adapter currently supports offline learning bundles."
        )

    def _build_evidence(
        self,
        snapshot: ImpactProfileSnapshot,
        tenant_id: UUID,
    ) -> tuple[Any, ...]:
        store = InMemoryEvidenceStore()
        accepted = []
        for raw in _raw_evidence(snapshot, tenant_id):
            result = ingest_evidence(raw, store=store, now=snapshot.requested_at)
            if result.accepted is not None:
                accepted.append(result.accepted)
        return tuple(accepted)

    def _persist_cycle(self, trace: ImpactRuntimeTraceExport) -> None:
        payload = dataclass_payload(trace)
        self.store.save_cycle(trace.cycle_id, payload)
        self.store.save_export(trace.cycle_id, payload)

    def _generator_runner(self, snapshot: ImpactProfileSnapshot):
        unreachable = [
            runtime for runtime in snapshot.runtimes if runtime.status == "installed_unreachable"
        ]
        reachable = [
            runtime for runtime in snapshot.runtimes if runtime.status == "installed_reachable"
        ]
        local_models = [
            model
            for model in snapshot.models
            if model.locality == "local" and model.presence == "detected"
        ]

        def runner(stage_input: GeneratorExecutionInput):
            primary = _primary_recommendation(
                snapshot, unreachable=unreachable, reachable=reachable, local_models=local_models
            )
            baseline = _baseline_recommendation(
                snapshot, reachable=reachable, local_models=local_models
            )
            audit = _audit_recommendation(snapshot)
            evidence_ids = tuple(str(unit.evidence_id) for unit in stage_input.evidence_units[:4])
            return (
                RawGeneratedCandidate(
                    candidate_type=CandidateType.ACTION,
                    title=primary["title"],
                    content=primary["content"],
                    source_evidence_ids=evidence_ids,
                    impact=8,
                    confidence=8,
                    ease=7,
                    semantic_tags=("impact", "runtime", "next_step"),
                ),
                RawGeneratedCandidate(
                    candidate_type=CandidateType.ACTION,
                    title=baseline["title"],
                    content=baseline["content"],
                    source_evidence_ids=evidence_ids,
                    impact=7,
                    confidence=7,
                    ease=7,
                    semantic_tags=("impact", "baseline", "verification"),
                ),
                RawGeneratedCandidate(
                    candidate_type=CandidateType.ACTION,
                    title=audit["title"],
                    content=audit["content"],
                    source_evidence_ids=evidence_ids,
                    impact=6,
                    confidence=8,
                    ease=8,
                    semantic_tags=("impact", "documentation", "audit"),
                ),
            )

        return runner

    def _refiner_runner(self, snapshot: ImpactProfileSnapshot):
        def runner(stage_input: RefinerExecutionInput):
            return tuple(
                RawRefinerResult(
                    disposition=RefinerDisposition.REFINE,
                    parent_candidate_id=str(candidate.candidate_id),
                    title=candidate.title,
                    content=_trim_recommendation(candidate.content),
                    impact=candidate.scores.impact,
                    confidence=candidate.scores.confidence,
                    ease=candidate.scores.ease,
                    semantic_tags=candidate.semantic_tags,
                    reason="Trimmed to one operator action with explicit verification intent.",
                )
                for candidate in stage_input.generated_candidates
            )

        return runner

    def _evaluator_runner(self, snapshot: ImpactProfileSnapshot):
        unreachable_count = sum(
            1 for runtime in snapshot.runtimes if runtime.status == "installed_unreachable"
        )
        local_model_count = sum(
            1
            for model in snapshot.models
            if model.locality == "local" and model.presence == "detected"
        )

        def runner(stage_input: EvaluatorExecutionInput):
            results = []
            for candidate in stage_input.refined_candidates:
                text = candidate.content.lower()
                quality = 70.0
                urgency = 50.0
                freshness = 72.0 if candidate.lineage.source_evidence_ids else 40.0
                if "start" in text or "re-run" in text:
                    urgency += 18.0 if unreachable_count else 8.0
                if "baseline" in text or "validate" in text:
                    quality += 6.0 if local_model_count else 1.0
                if "archive" in text or "compare" in text:
                    quality += 3.0
                disposition = EvaluationDisposition.ELIGIBLE
                reason = (
                    "Impact recommendation is grounded in profile evidence and "
                    "preserves operator control."
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
                        feedback_score=12.0,
                        reason=reason,
                    )
                )
            return tuple(results)

        return runner

    def _model_routes(self) -> dict[str, str]:
        return {
            "generator": self.model_config.generator.model,
            "refiner": self.model_config.refiner.model,
            "evaluator": self.model_config.evaluator.model,
        }


def impact_profile_snapshot_from_payload(payload: dict[str, Any]) -> ImpactProfileSnapshot:
    return ImpactProfileSnapshot(
        project_ref=str(payload["project_ref"]),
        profile_ref=str(payload["profile_ref"]),
        requested_at=_parse_datetime(payload["requested_at"]),
        machine_class=str(payload["machine_class"]),
        os_name=str(payload["os_name"]),
        architecture=str(payload["architecture"]),
        readiness_summary=str(payload["readiness_summary"]),
        runtimes=tuple(
            ImpactRuntimeSnapshot(
                runtime_id=str(item["runtime_id"]),
                status=str(item["status"]),
                installed=bool(item["installed"]),
                reachable=item.get("reachable"),
                notes=item.get("notes"),
            )
            for item in payload.get("runtimes", [])
        ),
        models=tuple(
            ImpactModelSnapshot(
                model_id=str(item["model_id"]),
                runtime_id=str(item["runtime_id"]),
                locality=str(item["locality"]),
                presence=str(item["presence"]),
            )
            for item in payload.get("models", [])
        ),
        metadata={str(key): str(value) for key, value in dict(payload.get("metadata", {})).items()},
        contract_version=str(payload.get("contract_version") or IMPACT_CONTRACT_VERSION),
    )


def impact_outcome_event_from_payload(payload: dict[str, Any]) -> ImpactRecommendationOutcomeEvent:
    candidate_id = payload.get("candidate_id")
    return ImpactRecommendationOutcomeEvent(
        profile_ref=str(payload["profile_ref"]),
        cycle_id=UUID(str(payload["cycle_id"])),
        disposition=ImpactRecommendationDisposition(str(payload["disposition"])),
        occurred_at=_parse_datetime(payload["occurred_at"]),
        candidate_id=UUID(str(candidate_id)) if candidate_id else None,
        final_note=str(payload["final_note"]) if payload.get("final_note") is not None else None,
        contract_version=str(payload.get("contract_version") or IMPACT_CONTRACT_VERSION),
    )


def _tenant_id(snapshot: ImpactProfileSnapshot) -> UUID:
    return uuid5(_IMPACT_TENANT_NAMESPACE, f"{snapshot.project_ref}:{snapshot.profile_ref}")


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware.")
    return parsed


def _raw_evidence(snapshot: ImpactProfileSnapshot, tenant_id: UUID) -> tuple[RawEvidenceInput, ...]:
    items: list[RawEvidenceInput] = [
        RawEvidenceInput(
            company_id=tenant_id,
            source_type=EvidenceSourceType.OTHER,
            source_ref=EvidenceSourceRef(
                external_id=f"{snapshot.profile_ref}:host",
                locator=snapshot.project_ref,
                version=snapshot.contract_version,
            ),
            content=(
                f"Machine class {snapshot.machine_class}. OS {snapshot.os_name}. "
                f"Architecture {snapshot.architecture}. Readiness: {snapshot.readiness_summary}"
            ),
            metadata={"kind": "host_summary"},
            topic_hints=("host", "readiness"),
            freshness_duration=timedelta(days=14),
            provenance=EvidenceProvenance(
                collected_at=snapshot.requested_at,
                collector="impact_adapter",
                ingestion_channel="profile_snapshot",
            ),
        )
    ]
    for runtime in snapshot.runtimes:
        items.append(
            RawEvidenceInput(
                company_id=tenant_id,
                source_type=EvidenceSourceType.OTHER,
                source_ref=EvidenceSourceRef(
                    external_id=f"{snapshot.profile_ref}:runtime:{runtime.runtime_id}",
                    locator=snapshot.project_ref,
                    version=snapshot.contract_version,
                ),
                content=(
                    f"Runtime {runtime.runtime_id} status {runtime.status}. "
                    f"Installed {runtime.installed}. Reachable {runtime.reachable}. "
                    f"Notes {runtime.notes or 'none'}."
                ),
                metadata={"kind": "runtime_row", "runtime_id": runtime.runtime_id},
                topic_hints=("runtime", runtime.runtime_id, runtime.status),
                freshness_duration=timedelta(days=14),
                provenance=EvidenceProvenance(
                    collected_at=snapshot.requested_at,
                    collector="impact_adapter",
                    ingestion_channel="profile_snapshot",
                ),
            )
        )
    for model in snapshot.models:
        items.append(
            RawEvidenceInput(
                company_id=tenant_id,
                source_type=EvidenceSourceType.OTHER,
                source_ref=EvidenceSourceRef(
                    external_id=f"{snapshot.profile_ref}:model:{model.model_id}",
                    locator=snapshot.project_ref,
                    version=snapshot.contract_version,
                ),
                content=(
                    f"Model {model.model_id} on runtime {model.runtime_id}. "
                    f"Locality {model.locality}. Presence {model.presence}."
                ),
                metadata={"kind": "model_row", "runtime_id": model.runtime_id},
                topic_hints=("model", model.runtime_id, model.locality),
                freshness_duration=timedelta(days=14),
                provenance=EvidenceProvenance(
                    collected_at=snapshot.requested_at,
                    collector="impact_adapter",
                    ingestion_channel="profile_snapshot",
                ),
            )
        )
    return tuple(items)


def _topic_anchors(snapshot: ImpactProfileSnapshot) -> list[str]:
    anchors = [snapshot.machine_class, snapshot.os_name, snapshot.architecture]
    anchors.extend(runtime.runtime_id for runtime in snapshot.runtimes[:3])
    return [anchor for anchor in anchors if anchor]


def _primary_recommendation(
    snapshot: ImpactProfileSnapshot,
    *,
    unreachable: list[ImpactRuntimeSnapshot],
    reachable: list[ImpactRuntimeSnapshot],
    local_models: list[ImpactModelSnapshot],
) -> dict[str, str]:
    if unreachable:
        runtime = unreachable[0]
        return {
            "title": f"Bring {runtime.runtime_id} online and re-run IMPACT",
            "content": (
                f"Start or repair the local {runtime.runtime_id} service, then "
                "run a fresh IMPACT scan. Until the runtime API responds, model "
                "inventory and readiness claims remain incomplete."
            ),
        }
    if reachable and not local_models:
        runtime = reachable[0]
        return {
            "title": f"Install one small model on {runtime.runtime_id}",
            "content": (
                "Keep the current profile as the before-state, pull one "
                f"lightweight local model into {runtime.runtime_id}, then scan "
                "again so IMPACT can prove the machine moved from runtime-only "
                "visibility to model-backed usability."
            ),
        }
    if local_models:
        model = local_models[0]
        return {
            "title": f"Validate one real workflow on {model.runtime_id}",
            "content": (
                "Use this machine as a concrete baseline: run one small "
                f"end-to-end local AI workflow on {model.runtime_id}, keep the "
                "profile and report as evidence, and avoid making broader "
                "capability claims until that workflow is reproducible."
            ),
        }
    return {
        "title": "Establish one reachable local runtime",
        "content": (
            "The current profile is still too thin for confident local-AI "
            "claims. Start one supported runtime, re-run the scan, and use "
            "that second profile as the first real baseline."
        ),
    }


def _baseline_recommendation(
    snapshot: ImpactProfileSnapshot,
    *,
    reachable: list[ImpactRuntimeSnapshot],
    local_models: list[ImpactModelSnapshot],
) -> dict[str, str]:
    if reachable:
        runtime_names = ", ".join(runtime.runtime_id for runtime in reachable[:3])
        return {
            "title": "Freeze a baseline profile before changing the machine",
            "content": (
                "Archive this IMPACT profile and HTML report as the baseline "
                f"for {runtime_names}. After any runtime or model change, run "
                "a second scan and compare the two reports instead of relying "
                "on memory."
            ),
        }
    if local_models:
        return {
            "title": "Capture a before-and-after report pair",
            "content": (
                "Keep the current profile, make one controlled runtime or "
                "model change, and capture a second scan. That gives IMPACT a "
                "verifiable delta instead of a single isolated snapshot."
            ),
        }
    return {
        "title": "Treat the current scan as an inventory checkpoint",
        "content": (
            "Use this profile as an inventory checkpoint only. Do not infer "
            "workload readiness until the next scan shows at least one "
            "reachable runtime or a concrete model inventory."
        ),
    }


def _audit_recommendation(snapshot: ImpactProfileSnapshot) -> dict[str, str]:
    return {
        "title": "Keep the recommendation tied to profile evidence",
        "content": (
            "When you share or act on this IMPACT result, cite the concrete "
            "profile facts behind it: runtime status, model visibility, "
            "machine class, and the exact readiness summary. Do not turn one "
            "scan into a general performance promise."
        ),
    }


def _trim_recommendation(text: str) -> str:
    collapsed = " ".join(str(text).split()).strip()
    return collapsed[:320].rstrip()


def _risk_flags(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    flags = []
    if "do not" in lowered or "avoid" in lowered:
        flags.append("conservative_gate")
    if "re-run" in lowered or "scan again" in lowered:
        flags.append("requires_follow_up_scan")
    return tuple(flags)


def _snapshot_hash(snapshot: ImpactProfileSnapshot) -> str:
    parts = [
        snapshot.project_ref,
        snapshot.profile_ref,
        snapshot.machine_class,
        snapshot.os_name,
        snapshot.architecture,
        snapshot.readiness_summary,
        "|".join(
            f"{runtime.runtime_id}:{runtime.status}:{runtime.installed}:{runtime.reachable}"
            for runtime in snapshot.runtimes
        ),
        "|".join(
            f"{model.model_id}:{model.runtime_id}:{model.locality}:{model.presence}"
            for model in snapshot.models
        ),
    ]
    return hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()


def _build_surfaced_frontier(
    records: tuple[Any, ...],
    frontier: tuple[FrontierEntry, ...],
    *,
    limit: int,
) -> tuple[FrontierEntry, ...]:
    selected = [entry.candidate for entry in frontier[:limit]]
    seen = {candidate.candidate_id for candidate in selected}
    extras = [
        FrontierEntry(candidate=record, rank=0)
        for record in records
        if record.candidate_id not in seen
    ]
    ranked_extras = sorted(
        extras,
        key=lambda entry: (
            entry.candidate.state.name != "EVALUATED",
            -frontier_score(entry.candidate),
            str(entry.candidate.candidate_id),
        ),
    )
    combined = selected + [entry.candidate for entry in ranked_extras]
    return tuple(
        FrontierEntry(candidate=candidate, frontier_score=frontier_score(candidate), rank=index)
        for index, candidate in enumerate(combined[:limit], start=1)
    )
