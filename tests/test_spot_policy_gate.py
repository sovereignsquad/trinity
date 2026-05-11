from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from trinity_core.adapters.product.spot.runtime import SpotRuntime
from trinity_core.memory import ReplyMemoryStore
from trinity_core.ops.cycle_store import RuntimeCyclePaths, RuntimeCycleStore
from trinity_core.ops.policy_registry import AcceptedArtifactRegistry, AcceptedArtifactRegistryPaths
from trinity_core.ops.spot_policy_gate import accept_spot_review_policy, review_spot_review_policy
from trinity_core.ops.spot_policy_store import SpotPolicyStore, SpotPolicyStorePaths
from trinity_core.schemas import (
    SpotReasoningRequest,
    SpotReviewDisposition,
    SpotReviewOutcome,
    SpotReviewScopeKind,
)


def _runtime(tmp_path: Path) -> SpotRuntime:
    return SpotRuntime(
        store=RuntimeCycleStore(
            RuntimeCyclePaths(
                adapter_name="spot",
                root_dir=tmp_path / "runtime",
                cycles_dir=tmp_path / "runtime" / "cycles",
                exports_dir=tmp_path / "runtime" / "exports",
            )
        ),
        memory_store=ReplyMemoryStore(
            db_path=tmp_path / "runtime_memory.sqlite3",
            adapter_name="spot",
        ),
        policy_store=SpotPolicyStore(
            SpotPolicyStorePaths(
                adapter_name="spot",
                root_dir=tmp_path / "accepted_spot_policies",
                scopes_dir=tmp_path / "accepted_spot_policies" / "scopes",
            )
        ),
    )


def _policy_file(tmp_path: Path, *, version: str, threshold: float) -> Path:
    path = tmp_path / f"{version}.json"
    path.write_text(
        json.dumps(
            {
                "artifact_key": "spot_review_policy",
                "version": version,
                "scope_kind": "company",
                "scope_value": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "created_at": datetime(2026, 5, 9, 13, 0, tzinfo=UTC).isoformat(),
                "source_project": "train",
                "auto_approve_negative_threshold": threshold,
                "positive_review_required": True,
                "default_review_required": True,
                "contract_version": "trinity.spot.v1alpha1",
            }
        ),
        encoding="utf-8",
    )
    return path


def _review_bundle(
    tmp_path: Path,
    *,
    row_ref: str,
    message_text: str,
    disposition: SpotReviewDisposition,
    final_label: str,
) -> Path:
    runtime = _runtime(tmp_path / row_ref.replace(":", "_"))
    runtime.store.paths.cycles_dir.mkdir(parents=True, exist_ok=True)
    runtime.store.paths.exports_dir.mkdir(parents=True, exist_ok=True)
    request = SpotReasoningRequest(
        company_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        run_id=f"run-{row_ref}",
        row_ref=row_ref,
        language="en",
        message_text=message_text,
        occurred_at=datetime(2026, 5, 9, 12, 0, tzinfo=UTC),
    )
    result = runtime.reason_spot(request)
    trace_payload = json.loads(Path(str(result.trace_ref)).read_text(encoding="utf-8"))
    cycle_id = UUID(str(trace_payload["cycle_id"]))
    runtime.record_review_outcome(
        SpotReviewOutcome(
            company_id=request.company_id,
            cycle_id=cycle_id,
            run_id=request.run_id,
            row_ref=row_ref,
            selected_candidate_key=result.selected_candidate_key,
            disposition=disposition,
            final_label=final_label,
            occurred_at=request.occurred_at,
        )
    )
    exported = runtime.export_training_bundle(cycle_id, bundle_type="spot-review-policy-learning")
    return Path(str(exported["bundle_path"]))


def test_review_spot_review_policy_rejects_regression(tmp_path: Path) -> None:
    bundle = _review_bundle(
        tmp_path,
        row_ref="sheet1:1",
        message_text="Thank you for the update, this looks fine.",
        disposition=SpotReviewDisposition.CONFIRMED_NEGATIVE,
        final_label="Not Antisemitic",
    )
    store = SpotPolicyStore(
        SpotPolicyStorePaths(
            adapter_name="spot",
            root_dir=tmp_path / "accepted_spot_policies",
            scopes_dir=tmp_path / "accepted_spot_policies" / "scopes",
        )
    )
    store.paths.root_dir.mkdir(parents=True, exist_ok=True)
    store.paths.scopes_dir.mkdir(parents=True, exist_ok=True)
    from trinity_core.schemas import AcceptedArtifactVersion, SpotReviewPolicy

    incumbent = SpotReviewPolicy(
        artifact_key="spot_review_policy",
        version="spot.v1",
        scope_kind=SpotReviewScopeKind.COMPANY,
        scope_value="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        created_at=datetime(2026, 5, 9, 12, 30, tzinfo=UTC),
        source_project="train",
        auto_approve_negative_threshold=0.7,
    )
    store.accept(
        incumbent,
        artifact=AcceptedArtifactVersion(
            artifact_key="spot_review_policy",
            version="spot.v1",
            source_project="train",
            accepted_at=datetime(2026, 5, 9, 12, 31, tzinfo=UTC),
        ),
    )

    result = review_spot_review_policy(
        _policy_file(tmp_path, version="spot.v2", threshold=0.99),
        bundle_files=[bundle],
        holdout_bundle_files=[],
        require_holdout=False,
        policy_store=store,
    )

    assert result.ready_for_acceptance is False
    assert result.reason.startswith("Rejected:")


def test_accept_spot_review_policy_promotes_candidate(tmp_path: Path) -> None:
    bundle = _review_bundle(
        tmp_path,
        row_ref="sheet1:2",
        message_text="Thank you for the update, this looks fine.",
        disposition=SpotReviewDisposition.CONFIRMED_NEGATIVE,
        final_label="Not Antisemitic",
    )
    store = SpotPolicyStore(
        SpotPolicyStorePaths(
            adapter_name="spot",
            root_dir=tmp_path / "accepted_spot_policies",
            scopes_dir=tmp_path / "accepted_spot_policies" / "scopes",
        )
    )
    store.paths.root_dir.mkdir(parents=True, exist_ok=True)
    store.paths.scopes_dir.mkdir(parents=True, exist_ok=True)
    registry = AcceptedArtifactRegistry(
        paths=AcceptedArtifactRegistryPaths(
            adapter_name="spot",
            root_dir=tmp_path / "accepted_artifacts",
            artifacts_dir=tmp_path / "accepted_artifacts" / "artifacts",
        )
    )
    registry.paths.root_dir.mkdir(parents=True, exist_ok=True)
    registry.paths.artifacts_dir.mkdir(parents=True, exist_ok=True)

    result = accept_spot_review_policy(
        _policy_file(tmp_path, version="spot.v2", threshold=0.7),
        bundle_files=[bundle],
        holdout_bundle_files=[bundle],
        require_holdout=True,
        registry=registry,
        policy_store=store,
    )

    assert result.accepted is True
    assert result.artifact is not None
    assert registry.current("spot_review_policy").version == "spot.v2"
    resolved = store.resolve(company_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert resolved is not None
    assert resolved.policy.version == "spot.v2"
