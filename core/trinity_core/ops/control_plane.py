"""Bounded control-plane seam for recurring Trinity jobs and inspectable run artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from trinity_core.ops.cycle_store import dataclass_payload, write_json_atomic
from trinity_core.ops.provider_comparison import (
    current_config_route_set,
    deterministic_route_set,
    load_provider_route_sets,
    run_reply_provider_comparison_from_fixture_dir,
)
from trinity_core.ops.runtime_storage import resolve_adapter_runtime_paths
from trinity_core.runtime import TrinityRuntime
from trinity_core.schemas import (
    ControlPlaneJob,
    ControlPlaneJobKind,
    ControlPlaneRun,
    ControlPlaneRunStatus,
)


@dataclass(frozen=True, slots=True)
class ControlPlanePaths:
    """Persistent paths for control-plane job and run artifacts."""

    adapter_name: str
    root_dir: Path
    jobs_dir: Path
    runs_dir: Path


class ControlPlaneStore:
    """Persistent storage for bounded control-plane jobs and runs."""

    def __init__(
        self,
        paths: ControlPlanePaths | None = None,
        *,
        adapter_name: str = "reply",
    ) -> None:
        self.paths = paths or resolve_control_plane_paths(adapter_name)

    def save_job(self, job: ControlPlaneJob) -> Path:
        path = self.paths.jobs_dir / f"{job.job_id}.json"
        write_json_atomic(path, dataclass_payload(job))
        return path

    def load_job(self, job_id: str) -> ControlPlaneJob:
        payload = json.loads((self.paths.jobs_dir / f"{job_id}.json").read_text(encoding="utf-8"))
        return control_plane_job_from_payload(payload)

    def save_run(self, run: ControlPlaneRun) -> Path:
        path = self.paths.runs_dir / f"{run.run_id}.json"
        write_json_atomic(path, dataclass_payload(run))
        return path

    def load_run(self, run_id: UUID | str) -> ControlPlaneRun:
        payload = json.loads(
            (self.paths.runs_dir / f"{str(run_id).strip()}.json").read_text(encoding="utf-8")
        )
        return control_plane_run_from_payload(payload)


def resolve_control_plane_paths(adapter_name: str) -> ControlPlanePaths:
    adapter_paths = resolve_adapter_runtime_paths(
        adapter_name,
        repo_root=Path(__file__).resolve().parents[3],
    )
    root_dir = adapter_paths.root_dir / "control_plane"
    jobs_dir = root_dir / "jobs"
    runs_dir = root_dir / "runs"
    for path in (root_dir, jobs_dir, runs_dir):
        path.mkdir(parents=True, exist_ok=True)
    return ControlPlanePaths(
        adapter_name=adapter_paths.adapter_name,
        root_dir=root_dir,
        jobs_dir=jobs_dir,
        runs_dir=runs_dir,
    )


def load_control_plane_job(path: str | Path) -> ControlPlaneJob:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return control_plane_job_from_payload(payload)


def control_plane_job_from_payload(payload: dict[str, Any]) -> ControlPlaneJob:
    return ControlPlaneJob(
        job_id=str(payload["job_id"]),
        adapter_name=str(payload["adapter_name"]),
        job_kind=ControlPlaneJobKind(str(payload["job_kind"])),
        created_at=_parse_datetime(payload["created_at"]),
        payload=dict(payload.get("payload", {})),
        schedule_hint=_optional_text(payload.get("schedule_hint")),
        description=_optional_text(payload.get("description")),
        labels=tuple(str(item) for item in payload.get("labels", [])),
    )


def control_plane_run_from_payload(payload: dict[str, Any]) -> ControlPlaneRun:
    return ControlPlaneRun(
        run_id=UUID(str(payload["run_id"])),
        job_id=str(payload["job_id"]),
        adapter_name=str(payload["adapter_name"]),
        job_kind=ControlPlaneJobKind(str(payload["job_kind"])),
        status=ControlPlaneRunStatus(str(payload["status"])),
        started_at=_parse_datetime(payload["started_at"]),
        completed_at=_parse_datetime(payload["completed_at"]),
        payload=dict(payload.get("payload", {})),
        outputs=dict(payload.get("outputs", {})),
        failure_reason=_optional_text(payload.get("failure_reason")),
    )


def run_control_plane_job(
    job: ControlPlaneJob,
    *,
    runtime_factory=TrinityRuntime,
    store: ControlPlaneStore | None = None,
) -> tuple[ControlPlaneRun, Path]:
    resolved_store = store or ControlPlaneStore(adapter_name=job.adapter_name)
    started_at = datetime.now(UTC)
    try:
        outputs = _execute_control_plane_job(job, runtime_factory=runtime_factory)
        run = ControlPlaneRun(
            run_id=uuid4(),
            job_id=job.job_id,
            adapter_name=job.adapter_name,
            job_kind=job.job_kind,
            status=ControlPlaneRunStatus.SUCCEEDED,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            payload=dict(job.payload),
            outputs=outputs,
        )
    except Exception as exc:
        run = ControlPlaneRun(
            run_id=uuid4(),
            job_id=job.job_id,
            adapter_name=job.adapter_name,
            job_kind=job.job_kind,
            status=ControlPlaneRunStatus.FAILED,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            payload=dict(job.payload),
            outputs={},
            failure_reason=str(exc),
        )
    run_path = resolved_store.save_run(run)
    return run, run_path


def _execute_control_plane_job(
    job: ControlPlaneJob,
    *,
    runtime_factory,
) -> dict[str, Any]:
    if job.job_kind is ControlPlaneJobKind.REPLY_PROVIDER_COMPARISON:
        fixture_dir = str(job.payload["fixture_dir"])
        route_sets = []
        if bool(job.payload.get("include_deterministic_baseline", False)):
            route_sets.append(deterministic_route_set())
        if bool(job.payload.get("include_current_config", False)):
            route_sets.append(current_config_route_set(job.adapter_name))
        for route_set_file in job.payload.get("route_set_files", []):
            route_sets.extend(load_provider_route_sets(str(route_set_file)))
        report, report_path = run_reply_provider_comparison_from_fixture_dir(
            route_sets,
            fixture_dir,
            corpus_id=_optional_text(job.payload.get("corpus_id")),
        )
        return {
            "report_path": str(report_path),
            "report_id": report.report_id,
            "route_summary_count": len(report.route_summaries),
        }

    if job.job_kind is ControlPlaneJobKind.REPLY_PREPARED_DRAFT_REFRESH:
        runtime = runtime_factory(adapter_name=job.adapter_name)
        result = runtime.refresh_prepared_draft(
            company_id=job.payload["company_id"],
            thread_ref=str(job.payload["thread_ref"]),
            generation_reason=str(
                job.payload.get("generation_reason") or "control_plane_refresh"
            ),
        )
        return result

    raise ValueError(f"Unsupported control-plane job kind: {job.job_kind}")


def make_provider_comparison_job(
    *,
    job_id: str,
    fixture_dir: str,
    route_set_files: tuple[str, ...] = (),
    corpus_id: str | None = None,
    include_current_config: bool = True,
    include_deterministic_baseline: bool = True,
    schedule_hint: str | None = None,
    description: str | None = None,
) -> ControlPlaneJob:
    return ControlPlaneJob(
        job_id=job_id,
        adapter_name="reply",
        job_kind=ControlPlaneJobKind.REPLY_PROVIDER_COMPARISON,
        created_at=datetime.now(UTC),
        payload={
            "fixture_dir": fixture_dir,
            "route_set_files": list(route_set_files),
            "corpus_id": corpus_id,
            "include_current_config": include_current_config,
            "include_deterministic_baseline": include_deterministic_baseline,
        },
        schedule_hint=schedule_hint,
        description=description,
    )


def make_prepared_draft_refresh_job(
    *,
    job_id: str,
    company_id: str,
    thread_ref: str,
    generation_reason: str = "control_plane_refresh",
    schedule_hint: str | None = None,
    description: str | None = None,
) -> ControlPlaneJob:
    return ControlPlaneJob(
        job_id=job_id,
        adapter_name="reply",
        job_kind=ControlPlaneJobKind.REPLY_PREPARED_DRAFT_REFRESH,
        created_at=datetime.now(UTC),
        payload={
            "company_id": company_id,
            "thread_ref": thread_ref,
            "generation_reason": generation_reason,
        },
        schedule_hint=schedule_hint,
        description=description,
    )


def schedule_prepared_draft_refresh_jobs(
    *,
    company_id: str,
    limit: int = 10,
    stale_after_minutes: int = 15,
    generation_reason: str = "scheduled_active_thread_refresh",
    schedule_hint: str | None = None,
    description: str | None = None,
    runtime_factory=TrinityRuntime,
    store: ControlPlaneStore | None = None,
) -> tuple[dict[str, Any], tuple[ControlPlaneJob, ...], tuple[Path, ...]]:
    runtime = runtime_factory(adapter_name="reply")
    inspection = runtime.inspect_prepared_draft_refresh(
        company_id=company_id,
        limit=limit,
        stale_after_minutes=stale_after_minutes,
    )
    plan_payload = dict(inspection.get("refresh_plan", {}))
    resolved_store = store or ControlPlaneStore(adapter_name="reply")
    jobs: list[ControlPlaneJob] = []
    job_paths: list[Path] = []
    for candidate in plan_payload.get("candidates", []):
        if not bool(candidate.get("refresh_recommended", False)):
            continue
        thread_ref = str(candidate["thread_ref"])
        job = make_prepared_draft_refresh_job(
            job_id=_prepared_draft_refresh_job_id(company_id, thread_ref),
            company_id=company_id,
            thread_ref=thread_ref,
            generation_reason=generation_reason,
            schedule_hint=schedule_hint,
            description=description
            or f"Refresh prepared draft for active thread {thread_ref}.",
        )
        jobs.append(job)
        job_paths.append(resolved_store.save_job(job))
    return inspection, tuple(jobs), tuple(job_paths)


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _prepared_draft_refresh_job_id(company_id: str, thread_ref: str) -> str:
    normalized_company = str(company_id).strip().lower()
    normalized_thread = "".join(
        character if character.isalnum() else "-"
        for character in str(thread_ref).strip().lower()
    ).strip("-")
    return f"refresh-{normalized_company}-{normalized_thread}"
