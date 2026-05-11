"""Gobii-facing workflow and agent contracts used by bounded Trinity ops seams."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


def _require_text(value: str, *, field_name: str) -> None:
    if not str(value or "").strip():
        raise ValueError(f"{field_name} is required.")


def _require_timezone(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


@dataclass(frozen=True, slots=True)
class GobiiAgentCreateRequest:
    """Minimal Gobii agent-create payload used by the recurring workflow proof."""

    name: str
    charter: str
    schedule: str
    whitelist_policy: str = "manual"
    is_active: bool = True
    template_code: str | None = None
    enabled_personal_server_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.name, field_name="name")
        _require_text(self.charter, field_name="charter")
        _require_text(self.schedule, field_name="schedule")


@dataclass(frozen=True, slots=True)
class GobiiAgentRecord:
    """Minimal normalized Gobii agent response used by this repo."""

    id: str
    name: str
    schedule: str | None
    is_active: bool
    life_state: str
    browser_use_agent_id: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.id, field_name="id")
        _require_text(self.name, field_name="name")
        _require_text(self.life_state, field_name="life_state")


@dataclass(frozen=True, slots=True)
class GobiiRecurringWorkflowBundle:
    """Persisted Gobii-ready recurring workflow package for one Trinity job."""

    workflow_id: str
    adapter_name: str
    job_id: str
    created_at: datetime
    schedule: str
    equivalent_trigger_command: str
    agent_create_request: GobiiAgentCreateRequest
    description: str | None = None
    job_path: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _require_text(self.workflow_id, field_name="workflow_id")
        _require_text(self.adapter_name, field_name="adapter_name")
        _require_text(self.job_id, field_name="job_id")
        _require_text(self.schedule, field_name="schedule")
        _require_text(
            self.equivalent_trigger_command,
            field_name="equivalent_trigger_command",
        )
        _require_timezone(self.created_at, field_name="created_at")
