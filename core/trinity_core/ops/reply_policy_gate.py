"""Explicit acceptance gate for reply behavior policies."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from trinity_core.ops.policy_registry import AcceptedArtifactRegistry
from trinity_core.ops.reply_policy_store import ReplyPolicyStore
from trinity_core.reply_runtime import (
    training_bundle_from_payload,
    training_bundle_type_from_payload,
)
from trinity_core.schemas import (
    AcceptedArtifactVersion,
    ReplyBehaviorPolicy,
    ReplyBehaviorScopeKind,
    TrainingBundle,
)
from trinity_core.schemas.policy import reply_behavior_policy_from_payload


@dataclass(frozen=True, slots=True)
class ReplyPolicyAcceptanceResult:
    """One deterministic acceptance-gate decision."""

    accepted: bool
    artifact: AcceptedArtifactVersion | None
    policy: ReplyBehaviorPolicy
    bundle_count: int
    candidate_score: float
    incumbent_score: float | None
    regression_delta: float | None
    reason: str


def load_reply_behavior_policy_file(path: str | Path) -> ReplyBehaviorPolicy:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return reply_behavior_policy_from_payload(payload)


def accept_reply_behavior_policy(
    policy_file: str | Path,
    *,
    bundle_files: list[str | Path],
    regression_threshold: float = 0.0,
    reason: str | None = None,
    promoted_at: datetime | None = None,
    registry: AcceptedArtifactRegistry | None = None,
    policy_store: ReplyPolicyStore | None = None,
) -> ReplyPolicyAcceptanceResult:
    if regression_threshold < 0:
        raise ValueError("regression_threshold must be greater than or equal to 0.")
    policy = load_reply_behavior_policy_file(policy_file)
    bundles = _load_bundles(bundle_files)
    matching_bundles = _filter_matching_bundles(policy, bundles)
    if not matching_bundles:
        raise ValueError("No training bundles matched the candidate policy scope.")

    candidate_score = _average_score(policy, matching_bundles)
    store = policy_store or ReplyPolicyStore()
    incumbent = store.current_for_scope(policy.scope_kind, policy.scope_value)
    incumbent_score = (
        _average_score(incumbent.policy, matching_bundles)
        if incumbent is not None
        else None
    )
    regression_delta = (
        round(candidate_score - incumbent_score, 6)
        if incumbent_score is not None
        else None
    )
    if incumbent_score is not None and candidate_score + regression_threshold < incumbent_score:
        return ReplyPolicyAcceptanceResult(
            accepted=False,
            artifact=None,
            policy=policy,
            bundle_count=len(matching_bundles),
            candidate_score=candidate_score,
            incumbent_score=incumbent_score,
            regression_delta=regression_delta,
            reason=(
                f"Rejected: candidate score {candidate_score:.4f} regressed below incumbent "
                f"{incumbent_score:.4f} beyond threshold {regression_threshold:.4f}."
            ),
        )

    acceptance_time = promoted_at or datetime.now(UTC)
    artifact = AcceptedArtifactVersion(
        artifact_key=policy.artifact_key,
        version=policy.version,
        source_project=policy.source_project,
        accepted_at=acceptance_time,
    )
    accepted_registry = registry or AcceptedArtifactRegistry()
    accepted_registry.promote(artifact, reason=reason, promoted_at=acceptance_time)
    store.accept(policy, artifact=artifact)
    disposition_reason = "Accepted as initial policy." if incumbent is None else (
        f"Accepted: candidate score {candidate_score:.4f} vs incumbent {incumbent_score:.4f}."
    )
    return ReplyPolicyAcceptanceResult(
        accepted=True,
        artifact=artifact,
        policy=policy,
        bundle_count=len(matching_bundles),
        candidate_score=candidate_score,
        incumbent_score=incumbent_score,
        regression_delta=regression_delta,
        reason=reason or disposition_reason,
    )


def _load_bundles(bundle_files: list[str | Path]) -> list[TrainingBundle]:
    if not bundle_files:
        raise ValueError("At least one bundle file is required.")
    bundles = []
    for path in bundle_files:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        bundles.append(
            training_bundle_from_payload(
                payload,
                bundle_type=training_bundle_type_from_payload(payload["bundle_type"]),
            )
        )
    return bundles


def _filter_matching_bundles(
    policy: ReplyBehaviorPolicy,
    bundles: list[TrainingBundle],
) -> list[TrainingBundle]:
    if policy.scope_kind is ReplyBehaviorScopeKind.GLOBAL:
        return bundles
    return [
        bundle
        for bundle in bundles
        if bundle.thread_snapshot.channel.strip().lower() == str(policy.scope_value or "").lower()
    ]


def _average_score(policy: ReplyBehaviorPolicy, bundles: list[TrainingBundle]) -> float:
    return round(
        sum(_score_bundle(policy, bundle) for bundle in bundles) / len(bundles),
        6,
    )


def _score_bundle(policy: ReplyBehaviorPolicy, bundle: TrainingBundle) -> float:
    text = _resolved_final_text(bundle)
    components = [
        _score_opening_style(policy, text),
        _score_closing_style(policy, text),
        _score_emoji_policy(policy, text),
        _score_url_policy(policy, text),
        _score_attachment_reference_policy(policy, text, bundle),
        _score_newline_policy(policy, text),
        _score_brevity(policy, text),
        _score_tone(policy, text),
    ]
    return round(sum(components) / len(components), 6)


def _resolved_final_text(bundle: TrainingBundle) -> str:
    final_text = str(bundle.draft_outcome_event.final_text or "").strip()
    if final_text:
        return final_text
    if bundle.selected_candidate_id is not None:
        for draft in bundle.ranked_draft_set.drafts:
            if draft.candidate_id == bundle.selected_candidate_id:
                return draft.draft_text.strip()
    return bundle.thread_snapshot.latest_inbound_text.strip()


def _score_opening_style(policy: ReplyBehaviorPolicy, text: str) -> float:
    opening = policy.channel_rules.opening_style
    lower = text.strip().lower()
    starts_ack = bool(re.match(r"^(thanks|thank you|hi|hello|got it|noted)\b", lower))
    if opening == "brief_acknowledgment":
        return 1.0 if starts_ack else 0.0
    if opening == "no_opening":
        return 1.0 if not starts_ack else 0.0
    return 0.5


def _score_closing_style(policy: ReplyBehaviorPolicy, text: str) -> float:
    closing = policy.channel_rules.closing_style
    lower = text.strip().lower()
    ends_signoff = bool(re.search(r"(best|regards|thanks|thank you)[.!]?$", lower))
    if closing == "no_signoff":
        return 1.0 if not ends_signoff else 0.0
    if closing == "short_signoff":
        return 1.0 if ends_signoff else 0.0
    return 0.5


def _score_emoji_policy(policy: ReplyBehaviorPolicy, text: str) -> float:
    if policy.channel_rules.emoji_policy != "none":
        return 0.5
    return 1.0 if not re.search(r"[\U0001F300-\U0001FAFF]", text) else 0.0


def _score_url_policy(policy: ReplyBehaviorPolicy, text: str) -> float:
    has_url = bool(re.search(r"https?://|www\.", text.lower()))
    if policy.channel_rules.url_policy == "avoid_urls":
        return 1.0 if not has_url else 0.0
    if policy.channel_rules.url_policy == "plain_urls":
        return 1.0 if not re.search(r"\[[^\]]+\]\((https?://[^)]+)\)", text) else 0.0
    return 0.5


def _score_attachment_reference_policy(
    policy: ReplyBehaviorPolicy,
    text: str,
    bundle: TrainingBundle,
) -> float:
    rule = policy.channel_rules.attachment_reference_policy
    if rule == "mention_if_used":
        return 0.5
    lower = text.lower()
    mentions_attachment = any(
        token in lower for token in ("attach", "attachment", "file", "doc", "document")
    )
    if rule == "explicit_attachment_reference":
        evidence_has_attachment = any(
            any(
                token in evidence.content_canonical.lower()
                for token in ("attach", "file", "document")
            )
            for evidence in bundle.evidence_units
        )
        return 1.0 if not evidence_has_attachment or mentions_attachment else 0.0
    return 0.5


def _score_newline_policy(policy: ReplyBehaviorPolicy, text: str) -> float:
    lines = [line for line in text.splitlines() if line.strip()]
    if policy.channel_rules.newline_policy == "single_paragraph":
        return 1.0 if len(lines) <= 1 and "\n\n" not in text else 0.0
    if policy.channel_rules.newline_policy == "compact_blocks":
        return 1.0 if len(lines) >= 1 else 0.0
    return 0.5


def _score_brevity(policy: ReplyBehaviorPolicy, text: str) -> float:
    preferences = policy.brevity_preferences
    sentences = _sentence_count(text)
    checks = []
    if preferences.max_sentences is not None:
        checks.append(1.0 if sentences <= preferences.max_sentences else 0.0)
    if preferences.max_chars is not None:
        checks.append(1.0 if len(text) <= preferences.max_chars else 0.0)
    if preferences.prefer_single_paragraph:
        non_empty_lines = [line for line in text.splitlines() if line.strip()]
        checks.append(1.0 if "\n\n" not in text and len(non_empty_lines) <= 1 else 0.0)
    target_length = preferences.target_length
    if target_length == "compact":
        checks.append(1.0 if len(text) <= 220 else 0.0)
    elif target_length == "short":
        checks.append(1.0 if len(text) <= 120 else 0.0)
    elif target_length == "detailed":
        checks.append(1.0 if len(text) >= 140 else 0.0)
    return round(sum(checks) / len(checks), 6) if checks else 0.5


def _score_tone(policy: ReplyBehaviorPolicy, text: str) -> float:
    lower = text.lower()
    checks = []
    if policy.tone_preferences.warmth == "warm":
        checks.append(
            1.0
            if any(token in lower for token in ("thanks", "thank you", "appreciate"))
            else 0.0
        )
    if policy.tone_preferences.directness == "direct":
        checks.append(
            1.0 if not any(token in lower for token in ("maybe", "perhaps", "might")) else 0.0
        )
    if policy.tone_preferences.formality == "high":
        checks.append(1.0 if not any(token in lower for token in ("hey", "ok", "okay")) else 0.0)
    for forbidden in policy.tone_preferences.forbidden_tones:
        checks.append(1.0 if forbidden.lower() not in lower else 0.0)
    return round(sum(checks) / len(checks), 6) if checks else 0.5


def _sentence_count(text: str) -> int:
    segments = [part for part in re.split(r"[.!?]+\s*", text.strip()) if part.strip()]
    return max(1, len(segments))
