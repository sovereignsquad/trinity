"""Bounded reply behavior policy artifacts owned by Trinity."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from .integration import REPLY_CONTRACT_VERSION


def _require_timezone(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


def _require_text(value: str, *, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required.")


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


class ReplyBehaviorScopeKind(StrEnum):
    """Allowed initial scopes for reply behavior policy artifacts."""

    GLOBAL = "global"
    COMPANY = "company"
    CHANNEL = "channel"


@dataclass(frozen=True, slots=True)
class ReplyTonePreferences:
    """Tone controls for reply generation and refinement."""

    target_tone: str
    formality: str
    warmth: str
    directness: str
    forbidden_tones: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.target_tone, field_name="target_tone")
        _require_text(self.formality, field_name="formality")
        _require_text(self.warmth, field_name="warmth")
        _require_text(self.directness, field_name="directness")
        normalized = tuple(
            tone.strip() for tone in self.forbidden_tones if str(tone).strip()
        )
        if len(normalized) != len(set(normalized)):
            raise ValueError("forbidden_tones must not contain duplicates.")
        object.__setattr__(self, "forbidden_tones", normalized)


@dataclass(frozen=True, slots=True)
class ReplyBrevityPreferences:
    """Brevity controls for reply shaping."""

    target_length: str
    max_sentences: int | None = None
    max_chars: int | None = None
    prefer_single_paragraph: bool = True

    def __post_init__(self) -> None:
        _require_text(self.target_length, field_name="target_length")
        if self.max_sentences is not None and self.max_sentences < 1:
            raise ValueError("max_sentences must be greater than or equal to 1.")
        if self.max_chars is not None and self.max_chars < 1:
            raise ValueError("max_chars must be greater than or equal to 1.")


@dataclass(frozen=True, slots=True)
class ReplyChannelRules:
    """Per-channel presentation rules for reply output."""

    opening_style: str
    closing_style: str
    emoji_policy: str
    url_policy: str
    attachment_reference_policy: str
    newline_policy: str

    def __post_init__(self) -> None:
        _require_text(self.opening_style, field_name="opening_style")
        _require_text(self.closing_style, field_name="closing_style")
        _require_text(self.emoji_policy, field_name="emoji_policy")
        _require_text(self.url_policy, field_name="url_policy")
        _require_text(
            self.attachment_reference_policy,
            field_name="attachment_reference_policy",
        )
        _require_text(self.newline_policy, field_name="newline_policy")


@dataclass(frozen=True, slots=True)
class ReplyBehaviorPolicy:
    """First bounded behavior artifact family for reply drafting."""

    artifact_key: str
    version: str
    scope_kind: ReplyBehaviorScopeKind
    scope_value: str | None
    created_at: datetime
    source_project: str
    tone_preferences: ReplyTonePreferences
    brevity_preferences: ReplyBrevityPreferences
    channel_rules: ReplyChannelRules
    notes: str | None = None
    contract_version: str = REPLY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.artifact_key, field_name="artifact_key")
        _require_text(self.version, field_name="version")
        _require_timezone(self.created_at, field_name="created_at")
        _require_text(self.source_project, field_name="source_project")
        scope_value = _normalize_optional_text(self.scope_value)
        notes = _normalize_optional_text(self.notes)
        if self.scope_kind is ReplyBehaviorScopeKind.GLOBAL and scope_value is not None:
            raise ValueError("scope_value must be omitted for global policies.")
        if (
            self.scope_kind in {ReplyBehaviorScopeKind.COMPANY, ReplyBehaviorScopeKind.CHANNEL}
            and scope_value is None
        ):
            raise ValueError("scope_value is required for company and channel policies.")
        if scope_value is not None:
            scope_value = scope_value.lower()
        object.__setattr__(self, "scope_value", scope_value)
        object.__setattr__(self, "notes", notes)

    def matches_channel(self, channel: str) -> bool:
        return self.matches_scope(channel=channel)

    def matches_scope(
        self,
        *,
        company_id: UUID | str | None = None,
        channel: str | None = None,
    ) -> bool:
        normalized_company_id = _normalize_company_id(company_id)
        normalized_channel = _normalize_channel(channel)
        if self.scope_kind is ReplyBehaviorScopeKind.GLOBAL:
            return True
        if self.scope_kind is ReplyBehaviorScopeKind.COMPANY:
            if normalized_company_id is None:
                raise ValueError("company_id is required for company-scoped policies.")
            return self.scope_value == normalized_company_id
        if normalized_channel is None:
            raise ValueError("channel is required.")
        return self.scope_value == normalized_channel

    def matches_company(self, company_id: UUID | str) -> bool:
        if self.scope_kind is ReplyBehaviorScopeKind.GLOBAL:
            return True
        if self.scope_kind is not ReplyBehaviorScopeKind.COMPANY:
            return False
        return self.scope_value == _normalize_company_id(company_id)


def _normalize_company_id(company_id: UUID | str | None) -> str | None:
    if company_id is None:
        return None
    return str(company_id).strip().lower() or None


def _normalize_channel(channel: str | None) -> str | None:
    if channel is None:
        return None
    normalized_channel = channel.strip().lower()
    return normalized_channel or None


def reply_behavior_policy_from_payload(payload: Mapping[str, Any]) -> ReplyBehaviorPolicy:
    """Parse one persisted payload back into a validated policy artifact."""

    return ReplyBehaviorPolicy(
        artifact_key=str(payload["artifact_key"]),
        version=str(payload["version"]),
        scope_kind=ReplyBehaviorScopeKind(str(payload["scope_kind"])),
        scope_value=payload.get("scope_value"),
        created_at=_parse_datetime(payload["created_at"]),
        source_project=str(payload["source_project"]),
        tone_preferences=ReplyTonePreferences(
            target_tone=str(payload["tone_preferences"]["target_tone"]),
            formality=str(payload["tone_preferences"]["formality"]),
            warmth=str(payload["tone_preferences"]["warmth"]),
            directness=str(payload["tone_preferences"]["directness"]),
            forbidden_tones=tuple(payload["tone_preferences"].get("forbidden_tones", ())),
        ),
        brevity_preferences=ReplyBrevityPreferences(
            target_length=str(payload["brevity_preferences"]["target_length"]),
            max_sentences=payload["brevity_preferences"].get("max_sentences"),
            max_chars=payload["brevity_preferences"].get("max_chars"),
            prefer_single_paragraph=bool(
                payload["brevity_preferences"].get("prefer_single_paragraph", True)
            ),
        ),
        channel_rules=ReplyChannelRules(
            opening_style=str(payload["channel_rules"]["opening_style"]),
            closing_style=str(payload["channel_rules"]["closing_style"]),
            emoji_policy=str(payload["channel_rules"]["emoji_policy"]),
            url_policy=str(payload["channel_rules"]["url_policy"]),
            attachment_reference_policy=str(
                payload["channel_rules"]["attachment_reference_policy"]
            ),
            newline_policy=str(payload["channel_rules"]["newline_policy"]),
        ),
        notes=payload.get("notes"),
        contract_version=str(payload.get("contract_version", REPLY_CONTRACT_VERSION)),
    )


def select_reply_behavior_policy(
    policies: Sequence[ReplyBehaviorPolicy],
    *,
    channel: str | None = None,
    company_id: UUID | str | None = None,
) -> ReplyBehaviorPolicy | None:
    """Select the most specific applicable policy for one runtime scope."""

    matching = [
        policy
        for policy in policies
        if policy.matches_scope(company_id=company_id, channel=channel)
    ]
    if not matching:
        return None
    return sorted(
        matching,
        key=lambda policy: (
            _scope_precedence(policy),
            -policy.created_at.timestamp(),
            policy.artifact_key,
            policy.version,
        ),
    )[0]


def _scope_precedence(policy: ReplyBehaviorPolicy) -> int:
    if policy.scope_kind is ReplyBehaviorScopeKind.COMPANY:
        return 0
    if policy.scope_kind is ReplyBehaviorScopeKind.CHANNEL:
        return 1
    return 2


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("created_at must be timezone-aware.")
    return parsed
