from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from trinity_core.adapters.product import spot_reasoning_request_from_payload
from trinity_core.schemas import (
    ConfidenceBundle,
    LoopAction,
    MinorityReport,
    SpotReasoningCandidate,
    SpotReasoningRequest,
    SpotReasoningResult,
    SpotReviewDisposition,
    SpotReviewOutcome,
)


def test_spot_reasoning_request_requires_message_text() -> None:
    with pytest.raises(ValueError, match="message_text"):
        SpotReasoningRequest(
            company_id=uuid4(),
            run_id="run-1",
            row_ref="row-1",
            language="de",
            message_text="",
        )


def test_spot_reasoning_request_from_payload_parses_optional_fields() -> None:
    payload = {
        "company_id": str(uuid4()),
        "run_id": "run-1",
        "row_ref": "sheet1:42",
        "language": "de",
        "message_text": "Some hostile post",
        "source_platform": "x",
        "source_handle": "@example",
        "occurred_at": datetime(2026, 5, 9, 12, 0, tzinfo=UTC).isoformat(),
        "metadata": {"campaign": "sample"},
    }

    request = spot_reasoning_request_from_payload(payload)

    assert request.run_id == "run-1"
    assert request.row_ref == "sheet1:42"
    assert request.source_platform == "x"
    assert request.metadata["campaign"] == "sample"


def test_spot_reasoning_result_requires_selected_candidate() -> None:
    bundle = ConfidenceBundle(
        generator_confidence=0.7,
        refiner_confidence=0.8,
        evaluator_confidence=0.75,
        frontier_confidence=0.8,
        combined_confidence=0.7625,
    )
    candidate = SpotReasoningCandidate(
        candidate_key="c1",
        interpretation="Likely explicit threat rhetoric.",
        rationale="Contains direct hostile framing.",
        threat_label_hint="Structural Antisemitism",
        review_recommended=True,
    )
    minority = MinorityReport(
        cycle_id=uuid4(),
        adapter="spot",
        company_id=uuid4(),
        majority_result_ref="c1",
        minority_result_ref="c2",
        dissent_source="evaluator",
        dissent_reason="Alternate benign reading remains plausible.",
        disagreement_severity=0.4,
        recommended_action=LoopAction.REWORK.value,
        created_at=datetime(2026, 5, 9, 12, 0, tzinfo=UTC),
    )

    result = SpotReasoningResult(
        company_id=uuid4(),
        run_id="run-1",
        row_ref="sheet1:42",
        generated_at=datetime(2026, 5, 9, 12, 0, tzinfo=UTC),
        candidates=(candidate,),
        selected_candidate_key="c1",
        confidence_bundle=bundle,
        review_required=True,
        review_reason="Positive classification requires review.",
        policy_sensitive=True,
        automatic_disposition="review_required",
        escalation_recommended=True,
        minority_report=minority,
    )

    assert result.selected_candidate_key == "c1"
    assert result.minority_report is not None
    assert result.review_required is True


def test_spot_review_outcome_requires_final_label() -> None:
    with pytest.raises(ValueError, match="final_label"):
        SpotReviewOutcome(
            company_id=uuid4(),
            cycle_id=uuid4(),
            run_id="run-1",
            row_ref="sheet1:42",
            selected_candidate_key="review",
            disposition=SpotReviewDisposition.CORRECTED,
            final_label="",
            occurred_at=datetime(2026, 5, 9, 12, 0, tzinfo=UTC),
        )
