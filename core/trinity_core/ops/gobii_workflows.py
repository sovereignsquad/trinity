"""Gobii-ready recurring workflow bundles for bounded Trinity maintenance jobs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from trinity_core.ops.cycle_store import dataclass_payload, write_json_atomic
from trinity_core.ops.gobii_client import GobiiAgentClient
from trinity_core.ops.runtime_storage import resolve_adapter_runtime_paths
from trinity_core.schemas import (
    ControlPlaneJob,
    ControlPlaneJobKind,
    GobiiAgentCreateRequest,
    GobiiAgentRecord,
    GobiiRecurringWorkflowBundle,
)


@dataclass(frozen=True, slots=True)
class GobiiWorkflowPaths:
    """Persistent paths for Gobii recurring workflow bundles."""

    adapter_name: str
    root_dir: Path
    bundles_dir: Path
    registrations_dir: Path


def resolve_gobii_workflow_paths(adapter_name: str) -> GobiiWorkflowPaths:
    adapter_paths = resolve_adapter_runtime_paths(
        adapter_name,
        repo_root=Path(__file__).resolve().parents[3],
    )
    root_dir = adapter_paths.root_dir / "gobii_workflows"
    bundles_dir = root_dir / "bundles"
    registrations_dir = root_dir / "registrations"
    for path in (root_dir, bundles_dir, registrations_dir):
        path.mkdir(parents=True, exist_ok=True)
    return GobiiWorkflowPaths(
        adapter_name=adapter_paths.adapter_name,
        root_dir=root_dir,
        bundles_dir=bundles_dir,
        registrations_dir=registrations_dir,
    )


def build_gobii_workflow_bundle(
    job: ControlPlaneJob,
    *,
    schedule: str,
    job_path: str | None = None,
    repo_root: str | Path | None = None,
) -> GobiiRecurringWorkflowBundle:
    if job.job_kind is not ControlPlaneJobKind.REPLY_PROVIDER_COMPARISON:
        raise ValueError(
            "The first Gobii recurring workflow proof is limited to "
            "`reply_provider_comparison` jobs."
        )
    resolved_repo_root = Path(repo_root or Path(__file__).resolve().parents[3]).resolve()
    resolved_job_path = str(job_path).strip() if job_path else "<persisted job file path>"
    command = (
        f"cd {resolved_repo_root} && "
        "PYTHONPATH=core uv run python -m trinity_core.cli "
        f"run-control-job --job-file {resolved_job_path}"
    )
    charter = (
        "Run the scheduled Trinity reply provider-comparison maintenance job. "
        "This agent is an orchestration substrate only: it must not change Trinity "
        "runtime policy directly. Each run should trigger the persisted control-plane "
        "job, capture the resulting comparison-report path, and surface failures "
        "clearly for operator recovery."
    )
    return GobiiRecurringWorkflowBundle(
        workflow_id=f"gobii-{job.job_id}",
        adapter_name=job.adapter_name,
        job_id=job.job_id,
        created_at=datetime.now(UTC),
        schedule=schedule,
        equivalent_trigger_command=command,
        agent_create_request=GobiiAgentCreateRequest(
            name=f"Trinity Maintenance: {job.job_id}",
            charter=charter,
            schedule=schedule,
            whitelist_policy="manual",
            is_active=True,
            template_code=None,
            enabled_personal_server_ids=(),
        ),
        description=job.description,
        job_path=resolved_job_path,
        notes=(
            "Gobii owns recurrence and agent lifecycle only.",
            "Trinity retains runtime, memory, trace, and promotion ownership.",
            "Equivalent local trigger command is included for deterministic local replay.",
        ),
    )


def persist_gobii_workflow_bundle(bundle: GobiiRecurringWorkflowBundle) -> Path:
    paths = resolve_gobii_workflow_paths(bundle.adapter_name)
    path = paths.bundles_dir / f"{bundle.workflow_id}.json"
    write_json_atomic(path, dataclass_payload(bundle))
    return path


def load_gobii_workflow_bundle(path: str | Path) -> GobiiRecurringWorkflowBundle:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return gobii_workflow_bundle_from_payload(payload)


def register_gobii_workflow_bundle(
    bundle: GobiiRecurringWorkflowBundle,
    client: GobiiAgentClient,
) -> tuple[GobiiAgentRecord, Path]:
    agent = client.create_agent(bundle.agent_create_request)
    paths = resolve_gobii_workflow_paths(bundle.adapter_name)
    payload = {
        "workflow_id": bundle.workflow_id,
        "registered_at": datetime.now(UTC).isoformat(),
        "agent": dataclass_payload(agent),
    }
    path = paths.registrations_dir / f"{bundle.workflow_id}.json"
    write_json_atomic(path, payload)
    return agent, path


def gobii_workflow_bundle_from_payload(payload: dict[str, object]) -> GobiiRecurringWorkflowBundle:
    agent_payload = payload["agent_create_request"]
    if not isinstance(agent_payload, dict):
        raise ValueError("Gobii workflow bundle is missing agent_create_request.")
    return GobiiRecurringWorkflowBundle(
        workflow_id=str(payload["workflow_id"]),
        adapter_name=str(payload["adapter_name"]),
        job_id=str(payload["job_id"]),
        created_at=_parse_datetime(str(payload["created_at"])),
        schedule=str(payload["schedule"]),
        equivalent_trigger_command=str(payload["equivalent_trigger_command"]),
        agent_create_request=GobiiAgentCreateRequest(
            name=str(agent_payload["name"]),
            charter=str(agent_payload["charter"]),
            schedule=str(agent_payload["schedule"]),
            whitelist_policy=str(agent_payload.get("whitelist_policy") or "manual"),
            is_active=bool(agent_payload.get("is_active", True)),
            template_code=(
                str(agent_payload["template_code"])
                if agent_payload.get("template_code") is not None
                else None
            ),
            enabled_personal_server_ids=tuple(
                str(item) for item in agent_payload.get("enabled_personal_server_ids", [])
            ),
        ),
        description=(str(payload["description"]).strip() if payload.get("description") else None),
        job_path=(str(payload["job_path"]).strip() if payload.get("job_path") else None),
        notes=tuple(str(item) for item in payload.get("notes", [])),
    )


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
