from __future__ import annotations

import json
from pathlib import Path

import pytest
from trinity_core.cli import main
from trinity_core.ops.control_plane import (
    ControlPlanePaths,
    ControlPlaneStore,
    load_control_plane_job,
    make_prepared_draft_refresh_job,
    make_provider_comparison_job,
    run_control_plane_job,
    schedule_prepared_draft_refresh_jobs,
)


class _FakeProvider:
    provider_name = "ollama"
    supports_model_inventory = False

    def __init__(self, config) -> None:
        self.config = config

    def chat_json(self, *, route, system_prompt: str, user_prompt: str):
        payload = json.loads(user_prompt)
        if route.model == "generator-shadow":
            latest = str(payload["latest_inbound_text"]).lower()
            if "updated numbers" in latest:
                return {
                    "candidates": [
                        {
                            "title": "Direct answer",
                            "content": "Thanks Alice, I can send the updated numbers today.",
                            "impact": 8,
                            "confidence": 8,
                            "ease": 8,
                            "tags": ["direct"],
                        },
                        {
                            "title": "Advance",
                            "content": "I can send the numbers and add the client note too.",
                            "impact": 7,
                            "confidence": 6,
                            "ease": 6,
                            "tags": ["advance"],
                        },
                        {
                            "title": "Clarify",
                            "content": "Do you need the updated numbers or the full update note?",
                            "impact": 6,
                            "confidence": 6,
                            "ease": 6,
                            "tags": ["clarify"],
                        },
                    ]
                }
            return {
                "candidates": [
                    {
                        "title": "Clarify scope",
                        "content": (
                            "Thanks Maya, happy to help. Do you want a short intro note "
                            "or the full follow-up message?"
                        ),
                        "impact": 8,
                        "confidence": 8,
                        "ease": 8,
                        "tags": ["clarify"],
                    },
                    {
                        "title": "Direct answer",
                        "content": "I can draft the note now.",
                        "impact": 6,
                        "confidence": 6,
                        "ease": 7,
                        "tags": ["direct"],
                    },
                    {
                        "title": "Advance",
                        "content": "I can draft it and suggest a follow-up step too.",
                        "impact": 7,
                        "confidence": 6,
                        "ease": 6,
                        "tags": ["advance"],
                    },
                ]
            }
        if route.model == "refiner-shadow":
            candidate = payload["candidate"]
            return {
                "title": candidate["title"],
                "content": candidate["content"],
                "impact": 8,
                "confidence": 8,
                "ease": 8,
                "tags": candidate["semantic_tags"],
                "reason": "Kept the draft concise and operator-safe.",
            }
        if route.model == "evaluator-shadow":
            return {
                "evaluations": [
                    {
                        "candidate_id": item["candidate_id"],
                        "disposition": "ELIGIBLE",
                        "impact": 8 if index == 0 else 6,
                        "confidence": 8 if index == 0 else 6,
                        "ease": 8 if index == 0 else 6,
                        "quality_score": 90.0 if index == 0 else 72.0,
                        "urgency_score": 65.0,
                        "freshness_score": 70.0,
                        "feedback_score": 14.0,
                        "reason": "Scored by fake provider benchmark harness.",
                    }
                    for index, item in enumerate(payload["candidates"])
                ]
            }
        raise AssertionError(f"Unexpected model in fake provider: {route.model}")

    def list_models(self):
        return ()


class _FakeRuntime:
    def __init__(self, *, adapter_name: str) -> None:
        self.adapter_name = adapter_name

    def refresh_prepared_draft(
        self,
        *,
        company_id,
        thread_ref: str,
        generation_reason: str = "manual_refresh",
    ):
        return {
            "status": "ok",
            "company_id": str(company_id),
            "thread_ref": thread_ref,
            "generation_reason": generation_reason,
        }

    def inspect_prepared_draft_refresh(
        self,
        *,
        company_id,
        limit: int = 10,
        stale_after_minutes: int = 15,
    ):
        return {
            "status": "ok",
            "company_id": str(company_id),
            "refresh_plan": {
                "company_id": str(company_id),
                "generated_at": "2026-05-10T12:00:00+00:00",
                "stale_before": "2026-05-10T11:45:00+00:00",
                "limit": limit,
                "candidates": [
                    {
                        "company_id": str(company_id),
                        "thread_ref": "reply:email:alice@example.com",
                        "channel": "email",
                        "contact_handle": "alice@example.com",
                        "refresh_reason": "dirty:inbound_message_recorded",
                        "priority_rank": 1,
                        "refresh_recommended": True,
                        "dirty": True,
                        "stale": False,
                        "missing_prepared_draft": False,
                    },
                    {
                        "company_id": str(company_id),
                        "thread_ref": "reply:email:bob@example.com",
                        "channel": "email",
                        "contact_handle": "bob@example.com",
                        "refresh_reason": "stale_prepared_draft",
                        "priority_rank": 2,
                        "refresh_recommended": True,
                        "dirty": False,
                        "stale": True,
                        "missing_prepared_draft": False,
                    },
                ],
            },
        }


def _control_plane_store(tmp_path: Path) -> ControlPlaneStore:
    return ControlPlaneStore(
        ControlPlanePaths(
            adapter_name="reply",
            root_dir=tmp_path / "control_plane",
            jobs_dir=tmp_path / "control_plane" / "jobs",
            runs_dir=tmp_path / "control_plane" / "runs",
        )
    )


def test_make_control_job_cli_persists_provider_comparison_job(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))

    exit_code = main(
        [
            "make-control-job",
            "--adapter",
            "reply",
            "--job-kind",
            "reply_provider_comparison",
            "--job-id",
            "nightly-shadow-benchmark",
            "--fixture-dir",
            str(Path("tests/fixtures/reply_shadow").resolve()),
            "--include-current-config",
            "--include-deterministic-baseline",
            "--schedule-hint",
            "0 * * * *",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert Path(payload["job_path"]).exists()
    assert payload["job"]["job_kind"] == "reply_provider_comparison"
    assert payload["job"]["schedule_hint"] == "0 * * * *"


def test_run_control_plane_job_executes_provider_comparison(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    route_file = tmp_path / "route_sets.json"
    route_file.write_text(
        json.dumps(
            {
                "route_sets": [
                    {
                        "route_set_id": "ollama-shadow",
                        "provider": "ollama",
                        "generator": {
                            "provider": "ollama",
                            "model": "generator-shadow",
                            "temperature": 0.2,
                            "keep_alive": "5m",
                        },
                        "refiner": {
                            "provider": "ollama",
                            "model": "refiner-shadow",
                            "temperature": 0.2,
                            "keep_alive": "5m",
                        },
                        "evaluator": {
                            "provider": "ollama",
                            "model": "evaluator-shadow",
                            "temperature": 0.1,
                            "keep_alive": "5m",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    monkeypatch.setattr(
        "trinity_core.ops.provider_comparison.build_model_provider",
        lambda config: _FakeProvider(config),
    )

    job = make_provider_comparison_job(
        job_id="nightly-shadow-benchmark",
        fixture_dir=str(Path("tests/fixtures/reply_shadow").resolve()),
        route_set_files=(str(route_file),),
        corpus_id="reply-shadow-nightly",
        include_deterministic_baseline=True,
        include_current_config=False,
    )
    store = _control_plane_store(tmp_path)

    run, run_path = run_control_plane_job(job, store=store)

    assert run.status.value == "succeeded"
    assert Path(run.outputs["report_path"]).exists()
    assert run.outputs["route_summary_count"] == 2
    assert run_path.exists()


def test_run_control_plane_job_executes_prepared_draft_refresh(tmp_path: Path) -> None:
    job = make_prepared_draft_refresh_job(
        job_id="refresh-acme-thread-1",
        company_id="acme",
        thread_ref="reply:email:alice@example.com",
        generation_reason="dirty_thread_refresh",
    )
    store = _control_plane_store(tmp_path)

    run, run_path = run_control_plane_job(job, runtime_factory=_FakeRuntime, store=store)

    assert run.status.value == "succeeded"
    assert run.outputs["status"] == "ok"
    assert run.outputs["generation_reason"] == "dirty_thread_refresh"
    assert run_path.exists()


def test_load_control_plane_job_roundtrip(tmp_path: Path) -> None:
    store = _control_plane_store(tmp_path)
    job = make_prepared_draft_refresh_job(
        job_id="refresh-acme-thread-1",
        company_id="acme",
        thread_ref="reply:email:alice@example.com",
    )
    job_path = store.save_job(job)

    loaded = load_control_plane_job(job_path)

    assert loaded.job_id == job.job_id
    assert loaded.job_kind == job.job_kind


def test_schedule_prepared_draft_refresh_jobs_persists_active_thread_jobs(
    tmp_path: Path,
) -> None:
    store = _control_plane_store(tmp_path)

    inspection, jobs, job_paths = schedule_prepared_draft_refresh_jobs(
        company_id="acme",
        limit=2,
        stale_after_minutes=15,
        runtime_factory=_FakeRuntime,
        store=store,
    )

    assert inspection["status"] == "ok"
    assert [job.payload["thread_ref"] for job in jobs] == [
        "reply:email:alice@example.com",
        "reply:email:bob@example.com",
    ]
    assert all(path.exists() for path in job_paths)
    assert jobs[0].payload["generation_reason"] == "scheduled_active_thread_refresh"
