"""Gobii browser-use task lifecycle helpers for bounded Trinity ops workflows."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from trinity_core.ops.cycle_store import dataclass_payload, write_json_atomic
from trinity_core.ops.runtime_storage import resolve_adapter_runtime_paths
from trinity_core.schemas import GobiiTaskCreateRequest, GobiiTaskRecord, GobiiTaskStatus


class GobiiTaskClientError(RuntimeError):
    """Raised when Gobii browser-use task transport fails for Trinity ops work."""


@dataclass(frozen=True)
class GobiiTaskClient:
    """Narrow Gobii browser-use Tasks API client."""

    base_url: str
    api_key: str
    timeout_seconds: float = 30.0

    def create_task(self, payload: GobiiTaskCreateRequest) -> GobiiTaskRecord:
        body: dict[str, Any] = {"prompt": payload.prompt}
        if payload.agent_id:
            body["agent_id"] = payload.agent_id
        if payload.webhook:
            body["webhook"] = payload.webhook
        if payload.output_schema is not None:
            body["output_schema"] = payload.output_schema
        if payload.wait_seconds is not None:
            body["wait"] = payload.wait_seconds
        response = self._request_json("/api/v1/tasks/browser-use/", method="POST", payload=body)
        return gobii_task_record_from_payload(response)

    def get_task_result(self, task_id: str) -> GobiiTaskRecord:
        response = self._request_json(
            f"/api/v1/tasks/browser-use/{task_id}/result/",
            method="GET",
            payload=None,
        )
        return gobii_task_record_from_payload(response)

    def list_tasks(
        self,
        *,
        page: int | None = None,
        page_size: int | None = None,
    ) -> tuple[GobiiTaskRecord, ...]:
        query = {}
        if page is not None:
            query["page"] = str(page)
        if page_size is not None:
            query["page_size"] = str(page_size)
        suffix = ""
        if query:
            suffix = "?" + parse.urlencode(query)
        response = self._request_json(
            f"/api/v1/tasks/browser-use/{suffix}",
            method="GET",
            payload=None,
        )
        results = response.get("results", [])
        if not isinstance(results, list):
            raise GobiiTaskClientError("Gobii tasks list returned an invalid results payload.")
        return tuple(
            gobii_task_record_from_payload(item)
            for item in results
            if isinstance(item, dict)
        )

    def cancel_task(self, task_id: str) -> GobiiTaskRecord:
        response = self._request_json(
            f"/api/v1/tasks/browser-use/{task_id}/cancel/",
            method="POST",
            payload={},
        )
        return gobii_task_record_from_payload(response)

    def _request_json(
        self,
        path: str,
        *,
        method: str,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not str(self.base_url).strip():
            raise GobiiTaskClientError("Gobii base_url is required.")
        if not str(self.api_key).strip():
            raise GobiiTaskClientError("Gobii API key is required.")
        endpoint = f"{self.base_url.rstrip('/')}{path}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
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
                raise GobiiTaskClientError(
                    f"Gobii authentication failed (HTTP {exc.code})."
                ) from exc
            raise GobiiTaskClientError(f"Gobii HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise GobiiTaskClientError("Gobii request timed out.") from exc
            raise GobiiTaskClientError(f"Gobii is unreachable: {exc.reason}") from exc

        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GobiiTaskClientError("Gobii returned invalid JSON.") from exc
        if not isinstance(decoded, dict):
            raise GobiiTaskClientError("Gobii returned an unexpected JSON payload.")
        return decoded


@dataclass(frozen=True, slots=True)
class GobiiTaskPaths:
    """Persistent paths for Gobii task records under one adapter runtime root."""

    adapter_name: str
    root_dir: Path
    tasks_dir: Path


def resolve_gobii_task_paths(adapter_name: str) -> GobiiTaskPaths:
    adapter_paths = resolve_adapter_runtime_paths(
        adapter_name,
        repo_root=Path(__file__).resolve().parents[3],
    )
    root_dir = adapter_paths.root_dir / "gobii_tasks"
    tasks_dir = root_dir / "records"
    for path in (root_dir, tasks_dir):
        path.mkdir(parents=True, exist_ok=True)
    return GobiiTaskPaths(
        adapter_name=adapter_paths.adapter_name,
        root_dir=root_dir,
        tasks_dir=tasks_dir,
    )


def persist_gobii_task_record(adapter_name: str, record: GobiiTaskRecord) -> Path:
    paths = resolve_gobii_task_paths(adapter_name)
    path = paths.tasks_dir / f"{record.id}.json"
    write_json_atomic(path, dataclass_payload(record))
    return path


def load_gobii_task_record(path: str | Path) -> GobiiTaskRecord:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise GobiiTaskClientError("Gobii task record payload must be a JSON object.")
    return gobii_task_record_from_payload(payload)


def load_persisted_gobii_task_record(
    adapter_name: str,
    task_id: str,
) -> tuple[GobiiTaskRecord, Path]:
    paths = resolve_gobii_task_paths(adapter_name)
    path = paths.tasks_dir / f"{task_id}.json"
    if not path.exists():
        raise GobiiTaskClientError(f"Gobii task record is missing: {path}")
    return load_gobii_task_record(path), path


def merge_gobii_task_context(
    record: GobiiTaskRecord,
    *,
    adapter_name: str | None = None,
    company_id: str | None = None,
) -> GobiiTaskRecord:
    return replace(
        record,
        adapter_name=adapter_name or record.adapter_name,
        company_id=company_id or record.company_id,
    )


def gobii_task_record_from_payload(payload: dict[str, Any]) -> GobiiTaskRecord:
    raw_payload = payload.get("raw_payload")
    if raw_payload is not None and not isinstance(raw_payload, dict):
        raise GobiiTaskClientError("Gobii task raw_payload must be a JSON object when provided.")
    return GobiiTaskRecord(
        id=str(payload["id"]),
        status=GobiiTaskStatus(str(payload["status"])),
        created_at=_parse_datetime(str(payload["created_at"])),
        updated_at=_parse_datetime(str(payload["updated_at"])),
        prompt=(str(payload["prompt"]).strip() if payload.get("prompt") else None),
        agent_id=(str(payload["agent_id"]).strip() if payload.get("agent_id") else None),
        error_message=(
            str(payload["error_message"]).strip()
            if payload.get("error_message")
            else None
        ),
        credits_cost=(
            str(payload["credits_cost"]).strip()
            if payload.get("credits_cost") is not None
            else None
        ),
        webhook=(str(payload["webhook"]).strip() if payload.get("webhook") else None),
        webhook_last_status_code=(
            int(payload["webhook_last_status_code"])
            if payload.get("webhook_last_status_code") is not None
            else None
        ),
        webhook_last_error=(
            str(payload["webhook_last_error"]).strip()
            if payload.get("webhook_last_error")
            else None
        ),
        adapter_name=(
            str(payload["adapter_name"]).strip() if payload.get("adapter_name") else None
        ),
        company_id=(str(payload["company_id"]).strip() if payload.get("company_id") else None),
        raw_payload=raw_payload if isinstance(raw_payload, dict) else payload,
    )


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
