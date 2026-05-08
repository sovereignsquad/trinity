from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime

import pytest
from trinity_core.ops.cycle_store import dataclass_payload
from trinity_core.schemas import (
    ReplyBehaviorPolicy,
    ReplyBehaviorScopeKind,
    ReplyBrevityPreferences,
    ReplyChannelRules,
    ReplyTonePreferences,
    reply_behavior_policy_from_payload,
    select_reply_behavior_policy,
)


def _base_policy(
    *,
    scope_kind: ReplyBehaviorScopeKind = ReplyBehaviorScopeKind.GLOBAL,
    scope_value: str | None = None,
    version: str = "v1",
    created_at: datetime | None = None,
) -> ReplyBehaviorPolicy:
    return ReplyBehaviorPolicy(
        artifact_key="reply_behavior_policy",
        version=version,
        scope_kind=scope_kind,
        scope_value=scope_value,
        created_at=created_at or datetime(2026, 5, 3, 12, 0, tzinfo=UTC),
        source_project="train",
        tone_preferences=ReplyTonePreferences(
            target_tone="calm",
            formality="medium",
            warmth="warm",
            directness="direct",
            forbidden_tones=("defensive",),
        ),
        brevity_preferences=ReplyBrevityPreferences(
            target_length="compact",
            max_sentences=3,
            max_chars=280,
            prefer_single_paragraph=True,
        ),
        channel_rules=ReplyChannelRules(
            opening_style="brief_acknowledgment",
            closing_style="no_signoff",
            emoji_policy="none",
            url_policy="plain_urls",
            attachment_reference_policy="mention_if_used",
            newline_policy="single_paragraph",
        ),
    )


def test_global_policy_rejects_scope_value() -> None:
    with pytest.raises(ValueError, match="scope_value must be omitted"):
        _base_policy(
            scope_kind=ReplyBehaviorScopeKind.GLOBAL,
            scope_value="email",
        )


def test_channel_policy_requires_scope_value() -> None:
    with pytest.raises(ValueError, match="scope_value is required"):
        _base_policy(scope_kind=ReplyBehaviorScopeKind.CHANNEL)


def test_company_policy_requires_scope_value() -> None:
    with pytest.raises(ValueError, match="scope_value is required"):
        _base_policy(scope_kind=ReplyBehaviorScopeKind.COMPANY)


def test_policy_round_trip_from_payload_preserves_validated_shape() -> None:
    policy = _base_policy(
        scope_kind=ReplyBehaviorScopeKind.CHANNEL,
        scope_value=" Email ",
    )

    payload = dataclass_payload(policy)
    restored = reply_behavior_policy_from_payload(payload)

    assert restored.scope_kind is ReplyBehaviorScopeKind.CHANNEL
    assert restored.scope_value == "email"
    assert restored.contract_version == policy.contract_version
    assert asdict(restored) == asdict(
        _base_policy(
            scope_kind=ReplyBehaviorScopeKind.CHANNEL,
            scope_value="email",
        )
    )


def test_select_reply_behavior_policy_prefers_channel_over_global() -> None:
    global_policy = _base_policy(version="global-v1")
    channel_policy = _base_policy(
        scope_kind=ReplyBehaviorScopeKind.CHANNEL,
        scope_value="whatsapp",
        version="channel-v1",
    )

    selected = select_reply_behavior_policy(
        (global_policy, channel_policy),
        channel="whatsapp",
    )

    assert selected is channel_policy


def test_select_reply_behavior_policy_prefers_company_over_channel() -> None:
    company_id = "11111111-1111-5111-8111-111111111111"
    channel_policy = _base_policy(
        scope_kind=ReplyBehaviorScopeKind.CHANNEL,
        scope_value="linkedin",
        version="channel-v1",
    )
    company_policy = _base_policy(
        scope_kind=ReplyBehaviorScopeKind.COMPANY,
        scope_value=company_id,
        version="company-v1",
    )

    selected = select_reply_behavior_policy(
        (channel_policy, company_policy),
        company_id=company_id,
        channel="linkedin",
    )

    assert selected is company_policy


def test_select_reply_behavior_policy_breaks_same_scope_ties_deterministically() -> None:
    older = _base_policy(
        scope_kind=ReplyBehaviorScopeKind.CHANNEL,
        scope_value="linkedin",
        version="v1",
        created_at=datetime(2026, 5, 3, 11, 0, tzinfo=UTC),
    )
    newer = _base_policy(
        scope_kind=ReplyBehaviorScopeKind.CHANNEL,
        scope_value="linkedin",
        version="v2",
        created_at=datetime(2026, 5, 3, 12, 0, tzinfo=UTC),
    )

    selected = select_reply_behavior_policy((older, newer), channel="linkedin")

    assert selected is newer


def test_tone_preferences_reject_duplicate_forbidden_tones() -> None:
    with pytest.raises(ValueError, match="duplicates"):
        ReplyTonePreferences(
            target_tone="calm",
            formality="medium",
            warmth="warm",
            directness="direct",
            forbidden_tones=("pushy", "pushy"),
        )
