from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from urllib import request
from urllib.error import HTTPError, URLError

import pytest
from trinity_core.cli import main
from trinity_core.ops.gobii_tasks import GobiiTaskClient, GobiiTaskClientError
from trinity_core.schemas import GobiiTaskCreateRequest, GobiiTaskRecord, GobiiTaskStatus


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def close(self) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_gobii_task_client_create_list_get_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_urlopen(req: request.Request, timeout: float):
        calls.append((req.get_method(), req.full_url))
        if req.get_method() == "POST" and req.full_url.endswith("/api/v1/tasks/browser-use/"):
            return _FakeResponse(
                {
                    "id": "task-123",
                    "status": "pending",
                    "created_at": "2026-05-09T12:00:00+00:00",
                    "updated_at": "2026-05-09T12:00:00+00:00",
                    "prompt": "Run nightly benchmark",
                    "agent_id": "agent-123",
                }
            )
        if req.get_method() == "GET" and "/result/" in req.full_url:
            return _FakeResponse(
                {
                    "id": "task-123",
                    "status": "completed",
                    "created_at": "2026-05-09T12:00:00+00:00",
                    "updated_at": "2026-05-09T12:01:00+00:00",
                    "prompt": "Run nightly benchmark",
                    "agent_id": "agent-123",
                }
            )
        if req.get_method() == "GET" and req.full_url.endswith(
            "/api/v1/tasks/browser-use/?page=1&page_size=10"
        ):
            return _FakeResponse(
                {
                    "count": 1,
                    "results": [
                        {
                            "id": "task-123",
                            "status": "completed",
                            "created_at": "2026-05-09T12:00:00+00:00",
                            "updated_at": "2026-05-09T12:01:00+00:00",
                            "prompt": "Run nightly benchmark",
                            "agent_id": "agent-123",
                        }
                    ],
                }
            )
        if req.get_method() == "POST" and req.full_url.endswith(
            "/api/v1/tasks/browser-use/task-123/cancel/"
        ):
            return _FakeResponse(
                {
                    "id": "task-123",
                    "status": "cancelled",
                    "created_at": "2026-05-09T12:00:00+00:00",
                    "updated_at": "2026-05-09T12:02:00+00:00",
                    "prompt": "Run nightly benchmark",
                    "agent_id": "agent-123",
                }
            )
        raise AssertionError((req.get_method(), req.full_url))

    monkeypatch.setattr("trinity_core.ops.gobii_tasks.request.urlopen", fake_urlopen)
    client = GobiiTaskClient(base_url="https://gobii.ai", api_key="secret-key")

    created = client.create_task(
        GobiiTaskCreateRequest(prompt="Run nightly benchmark", agent_id="agent-123")
    )
    listed = client.list_tasks(page=1, page_size=10)
    result = client.get_task_result("task-123")
    cancelled = client.cancel_task("task-123")

    assert created.id == "task-123"
    assert listed[0].status.value == "completed"
    assert result.status.value == "completed"
    assert cancelled.status.value == "cancelled"
    assert len(calls) == 4


def test_submit_gobii_task_cli_persists_record(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    monkeypatch.setenv("GOBII_API_KEY", "secret-key")

    monkeypatch.setattr(
        "trinity_core.cli.GobiiTaskClient.create_task",
        lambda self, payload: GobiiTaskRecord(
            id="task-123",
            status=GobiiTaskStatus.PENDING,
            created_at=datetime.fromisoformat("2026-05-09T12:00:00+00:00"),
            updated_at=datetime.fromisoformat("2026-05-09T12:00:00+00:00"),
            prompt=payload.prompt,
            agent_id=payload.agent_id,
        ),
    )

    exit_code = main(
        [
            "submit-gobii-task",
            "--adapter",
            "reply",
            "--prompt",
            "Run nightly benchmark",
            "--agent-id",
            "agent-123",
            "--company-id",
            "8f6029db-f7d3-4c36-b3ea-f90ef24e0207",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert Path(payload["task_path"]).exists()
    assert payload["task"]["id"] == "task-123"
    assert payload["task"]["company_id"] == "8f6029db-f7d3-4c36-b3ea-f90ef24e0207"


def test_gobii_task_client_rejects_missing_base_url() -> None:
    client = GobiiTaskClient(base_url=" ", api_key="secret-key")

    with pytest.raises(GobiiTaskClientError, match="base_url is required"):
        client.get_task_result("task-123")


def test_gobii_task_client_surfaces_auth_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(req: request.Request, timeout: float):
        raise HTTPError(
            req.full_url,
            403,
            "Forbidden",
            hdrs=None,
            fp=_FakeResponse({"detail": "denied"}),
        )

    monkeypatch.setattr("trinity_core.ops.gobii_tasks.request.urlopen", fake_urlopen)
    client = GobiiTaskClient(base_url="https://gobii.ai", api_key="secret-key")

    with pytest.raises(GobiiTaskClientError, match="authentication failed"):
        client.cancel_task("task-123")


def test_gobii_task_client_surfaces_unreachable_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(req: request.Request, timeout: float):
        raise URLError("connection refused")

    monkeypatch.setattr("trinity_core.ops.gobii_tasks.request.urlopen", fake_urlopen)
    client = GobiiTaskClient(base_url="https://gobii.ai", api_key="secret-key")

    with pytest.raises(GobiiTaskClientError, match="unreachable"):
        client.list_tasks()


def test_gobii_task_client_surfaces_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(req: request.Request, timeout: float):
        raise URLError(TimeoutError("timed out"))

    monkeypatch.setattr("trinity_core.ops.gobii_tasks.request.urlopen", fake_urlopen)
    client = GobiiTaskClient(base_url="https://gobii.ai", api_key="secret-key")

    with pytest.raises(GobiiTaskClientError, match="timed out"):
        client.get_task_result("task-123")


def test_gobii_task_client_rejects_invalid_results_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "trinity_core.ops.gobii_tasks.request.urlopen",
        lambda req, timeout: _FakeResponse({"results": "not-a-list"}),
    )
    client = GobiiTaskClient(base_url="https://gobii.ai", api_key="secret-key")

    with pytest.raises(GobiiTaskClientError, match="invalid results payload"):
        client.list_tasks()
