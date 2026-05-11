"""Minimal Gobii agent API client for bounded recurring Trinity workflow proofs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from trinity_core.schemas import GobiiAgentCreateRequest, GobiiAgentRecord


class GobiiClientError(RuntimeError):
    """Raised when Gobii agent transport cannot satisfy a bounded Trinity request."""


@dataclass(frozen=True)
class GobiiAgentClient:
    """Narrow Gobii Agent API client for create/update operations."""

    base_url: str
    api_key: str
    timeout_seconds: float = 30.0

    def create_agent(self, payload: GobiiAgentCreateRequest) -> GobiiAgentRecord:
        response = self._request_json(
            "/api/v1/agents/",
            method="POST",
            payload={
                "name": payload.name,
                "charter": payload.charter,
                "schedule": payload.schedule,
                "whitelist_policy": payload.whitelist_policy,
                "is_active": payload.is_active,
                "template_code": payload.template_code,
                "enabled_personal_server_ids": list(payload.enabled_personal_server_ids),
            },
        )
        return _agent_record_from_payload(response)

    def update_agent_schedule(self, agent_id: str, schedule: str) -> GobiiAgentRecord:
        response = self._request_json(
            f"/api/v1/agents/{agent_id}/",
            method="PATCH",
            payload={"schedule": schedule},
        )
        return _agent_record_from_payload(response)

    def _request_json(
        self,
        path: str,
        *,
        method: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not str(self.base_url).strip():
            raise GobiiClientError("Gobii base_url is required.")
        if not str(self.api_key).strip():
            raise GobiiClientError("Gobii API key is required.")
        endpoint = f"{self.base_url.rstrip('/')}{path}"
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Api-Key": self.api_key,
            },
            method=method,
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code in {401, 403}:
                raise GobiiClientError(f"Gobii authentication failed (HTTP {exc.code}).") from exc
            raise GobiiClientError(f"Gobii HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise GobiiClientError("Gobii request timed out.") from exc
            raise GobiiClientError(f"Gobii is unreachable: {exc.reason}") from exc

        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GobiiClientError("Gobii returned invalid JSON.") from exc
        if not isinstance(decoded, dict):
            raise GobiiClientError("Gobii returned an unexpected JSON payload.")
        return decoded


def _agent_record_from_payload(payload: dict[str, Any]) -> GobiiAgentRecord:
    return GobiiAgentRecord(
        id=str(payload["id"]),
        name=str(payload["name"]),
        schedule=(str(payload["schedule"]).strip() if payload.get("schedule") else None),
        is_active=bool(payload["is_active"]),
        life_state=str(payload["life_state"]),
        browser_use_agent_id=(
            str(payload["browser_use_agent_id"]).strip()
            if payload.get("browser_use_agent_id")
            else None
        ),
    )
