from __future__ import annotations

import json
from urllib import request
from urllib.error import HTTPError, URLError

import pytest
from trinity_core.ops.gobii_client import GobiiAgentClient, GobiiClientError
from trinity_core.schemas import GobiiAgentCreateRequest


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


def test_gobii_agent_client_create_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(req: request.Request, timeout: float):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["headers"] = dict(req.header_items())
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse(
            {
                "id": "agent-123",
                "name": "Trinity Maintenance: nightly-shadow-benchmark",
                "schedule": "@daily",
                "is_active": True,
                "life_state": "active",
                "browser_use_agent_id": "browser-use-123",
            }
        )

    monkeypatch.setattr("trinity_core.ops.gobii_client.request.urlopen", fake_urlopen)
    client = GobiiAgentClient(base_url="https://gobii.ai", api_key="secret-key")

    agent = client.create_agent(
        GobiiAgentCreateRequest(
            name="Trinity Maintenance: nightly-shadow-benchmark",
            charter="Run the scheduled Trinity maintenance job.",
            schedule="@daily",
        )
    )

    assert captured["url"] == "https://gobii.ai/api/v1/agents/"
    assert captured["method"] == "POST"
    assert captured["body"]["schedule"] == "@daily"
    assert agent.id == "agent-123"


def test_gobii_agent_client_rejects_missing_api_key() -> None:
    client = GobiiAgentClient(base_url="https://gobii.ai", api_key="  ")

    with pytest.raises(GobiiClientError, match="API key is required"):
        client.create_agent(
            GobiiAgentCreateRequest(
                name="Trinity Maintenance",
                charter="Run maintenance.",
                schedule="@daily",
            )
        )


def test_gobii_agent_client_surfaces_auth_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(req: request.Request, timeout: float):
        raise HTTPError(
            req.full_url,
            401,
            "Unauthorized",
            hdrs=None,
            fp=_FakeResponse({"detail": "bad key"}),
        )

    monkeypatch.setattr("trinity_core.ops.gobii_client.request.urlopen", fake_urlopen)
    client = GobiiAgentClient(base_url="https://gobii.ai", api_key="secret-key")

    with pytest.raises(GobiiClientError, match="authentication failed"):
        client.create_agent(
            GobiiAgentCreateRequest(
                name="Trinity Maintenance",
                charter="Run maintenance.",
                schedule="@daily",
            )
        )


def test_gobii_agent_client_surfaces_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(req: request.Request, timeout: float):
        raise URLError(TimeoutError("timed out"))

    monkeypatch.setattr("trinity_core.ops.gobii_client.request.urlopen", fake_urlopen)
    client = GobiiAgentClient(base_url="https://gobii.ai", api_key="secret-key")

    with pytest.raises(GobiiClientError, match="timed out"):
        client.create_agent(
            GobiiAgentCreateRequest(
                name="Trinity Maintenance",
                charter="Run maintenance.",
                schedule="@daily",
            )
        )


def test_gobii_agent_client_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    class _InvalidJsonResponse:
        def read(self) -> bytes:
            return b"not-json"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "trinity_core.ops.gobii_client.request.urlopen",
        lambda req, timeout: _InvalidJsonResponse(),
    )
    client = GobiiAgentClient(base_url="https://gobii.ai", api_key="secret-key")

    with pytest.raises(GobiiClientError, match="invalid JSON"):
        client.create_agent(
            GobiiAgentCreateRequest(
                name="Trinity Maintenance",
                charter="Run maintenance.",
                schedule="@daily",
            )
        )
