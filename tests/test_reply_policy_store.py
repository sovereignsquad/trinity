from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from trinity_core.ops.reply_policy_store import ReplyPolicyStore, ReplyPolicyStorePaths
from trinity_core.schemas import (
    AcceptedArtifactVersion,
    ReplyBehaviorPolicy,
    ReplyBehaviorScopeKind,
    ReplyBrevityPreferences,
    ReplyChannelRules,
    ReplyTonePreferences,
)


def _store(tmp_path: Path) -> ReplyPolicyStore:
    paths = ReplyPolicyStorePaths(
        adapter_name="reply",
        root_dir=tmp_path / "accepted_reply_policies",
        scopes_dir=tmp_path / "accepted_reply_policies" / "scopes",
    )
    paths.root_dir.mkdir(parents=True, exist_ok=True)
    paths.scopes_dir.mkdir(parents=True, exist_ok=True)
    return ReplyPolicyStore(paths=paths)


def _policy(
    *,
    scope_kind: ReplyBehaviorScopeKind,
    scope_value: str | None,
    version: str,
) -> ReplyBehaviorPolicy:
    return ReplyBehaviorPolicy(
        artifact_key="reply_behavior_policy",
        version=version,
        scope_kind=scope_kind,
        scope_value=scope_value,
        created_at=datetime(2026, 5, 3, 12, 0, tzinfo=UTC),
        source_project="train",
        tone_preferences=ReplyTonePreferences(
            target_tone="calm",
            formality="medium",
            warmth="warm",
            directness="direct",
        ),
        brevity_preferences=ReplyBrevityPreferences(
            target_length="compact",
            max_sentences=3,
            max_chars=240,
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


def _artifact(version: str) -> AcceptedArtifactVersion:
    return AcceptedArtifactVersion(
        artifact_key="reply_behavior_policy",
        version=version,
        source_project="train",
        accepted_at=datetime(2026, 5, 3, 12, 30, tzinfo=UTC),
    )


def test_resolve_prefers_channel_scope_over_global(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.accept(
        _policy(scope_kind=ReplyBehaviorScopeKind.GLOBAL, scope_value=None, version="global-v1"),
        artifact=_artifact("global-v1"),
    )
    store.accept(
        _policy(
            scope_kind=ReplyBehaviorScopeKind.CHANNEL,
            scope_value="whatsapp",
            version="channel-v1",
        ),
        artifact=_artifact("channel-v1"),
    )

    resolved = store.resolve(channel="whatsapp")

    assert resolved is not None
    assert resolved.policy.version == "channel-v1"
    assert resolved.artifact.version == "channel-v1"


def test_resolve_falls_back_to_global_scope(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.accept(
        _policy(scope_kind=ReplyBehaviorScopeKind.GLOBAL, scope_value=None, version="global-v1"),
        artifact=_artifact("global-v1"),
    )

    resolved = store.resolve(channel="email")

    assert resolved is not None
    assert resolved.policy.scope_kind is ReplyBehaviorScopeKind.GLOBAL
    assert resolved.artifact.version == "global-v1"


def test_resolve_prefers_company_scope_over_channel_and_global(tmp_path: Path) -> None:
    store = _store(tmp_path)
    company_id = "11111111-1111-5111-8111-111111111111"
    store.accept(
        _policy(scope_kind=ReplyBehaviorScopeKind.GLOBAL, scope_value=None, version="global-v1"),
        artifact=_artifact("global-v1"),
    )
    store.accept(
        _policy(
            scope_kind=ReplyBehaviorScopeKind.CHANNEL,
            scope_value="email",
            version="channel-v1",
        ),
        artifact=_artifact("channel-v1"),
    )
    store.accept(
        _policy(
            scope_kind=ReplyBehaviorScopeKind.COMPANY,
            scope_value=company_id,
            version="company-v1",
        ),
        artifact=_artifact("company-v1"),
    )

    resolved = store.resolve(company_id=company_id, channel="email")

    assert resolved is not None
    assert resolved.policy.scope_kind is ReplyBehaviorScopeKind.COMPANY
    assert resolved.policy.version == "company-v1"


def test_resolve_with_summary_explains_scope_path(tmp_path: Path) -> None:
    store = _store(tmp_path)
    company_id = "11111111-1111-5111-8111-111111111111"
    store.accept(
        _policy(scope_kind=ReplyBehaviorScopeKind.GLOBAL, scope_value=None, version="global-v1"),
        artifact=_artifact("global-v1"),
    )
    store.accept(
        _policy(
            scope_kind=ReplyBehaviorScopeKind.CHANNEL,
            scope_value="email",
            version="channel-v1",
        ),
        artifact=_artifact("channel-v1"),
    )

    resolved = store.resolve_with_summary(company_id=company_id, channel="email")

    assert resolved.accepted_policy is not None
    assert resolved.accepted_policy.policy.version == "channel-v1"
    assert resolved.summary.matched_scope_kind == "channel"
    assert resolved.summary.matched_policy_version == "channel-v1"
    assert resolved.summary.resolution_path == (
        f"company:{company_id}:miss",
        "channel:email:match",
    )
