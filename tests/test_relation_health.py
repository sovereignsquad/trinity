from __future__ import annotations

import json
import subprocess
from pathlib import Path
from urllib import error

import pytest
from trinity_core.cli import main
from trinity_core.ops.relation_health import (
    TrainClientError,
    check_reply_compatibility,
    probe_gobii_seam,
    probe_train_seam,
    request_train_json,
)


class _FakeResponse:
    def __init__(self, payload: object, *, status: int = 200) -> None:
        self._payload = payload
        self.status = status

    def read(self) -> bytes:
        if isinstance(self._payload, (dict, list)):
            return json.dumps(self._payload).encode("utf-8")
        return str(self._payload).encode("utf-8")

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_request_train_json_surfaces_connection_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        raise error.URLError(ConnectionRefusedError("refused"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(TrainClientError, match="connection was refused"):
        request_train_json(url="http://127.0.0.1:8000/x", payload={"ok": True})


def test_probe_train_seam_reports_api_and_cli_health(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    train_root = tmp_path / "train"
    train_root.mkdir()

    def fake_urlopen(request, timeout=0):  # type: ignore[no-untyped-def]
        return _FakeResponse({"status": "ok"})

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="usage: train",
            stderr="",
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("trinity_core.ops.relation_health.subprocess.run", fake_run)

    payload = probe_train_seam(
        default_train_api_base_url="http://127.0.0.1:8000",
        train_root_dir=train_root,
    )

    assert payload["ready"] is True
    assert payload["recommended_transport"] == "api"
    assert payload["api"]["state"] == "online"
    assert payload["cli"]["state"] == "online"


def test_check_reply_compatibility_reports_required_files(tmp_path: Path) -> None:
    reply_root = tmp_path / "reply"
    for relative_path in (
        "chat/brain-runtime.js",
        "chat/routes/messaging.js",
        "chat/js/api.js",
        "app/reply-app/Sources/NativeSettingsView.swift",
    ):
        path = reply_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("// test", encoding="utf-8")

    payload = check_reply_compatibility(reply_root_dir=reply_root)

    assert payload["repo_present"] is True
    assert payload["required_files_ready"] is True
    assert payload["ready"] is True
    assert payload["trinity_contract_checks"]["payload_parsers_ok"] is True


def test_probe_gobii_seam_reports_missing_api_key() -> None:
    payload = probe_gobii_seam(
        adapter_name="reply",
        base_url="https://gobii.ai",
        api_key_env="MISSING_GOBII_API_KEY",
    )

    assert payload["ready"] is False
    assert payload["state"] == "not_configured"
    assert payload["reason"] == "missing_api_key"


def test_runtime_status_reports_mistral_executable_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRINITY_MODEL_CONFIG_PATH", str(tmp_path / "config.json"))

    write_exit = main(
        [
            "write-config",
            "--adapter",
            "reply",
            "--provider",
            "mistral-cli",
            "--mistral-cli-executable",
            "missing-vibe",
            "--generator-model",
            "mistral-small-latest",
            "--refiner-model",
            "mistral-small-latest",
            "--evaluator-model",
            "mistral-medium-latest",
        ]
    )
    assert write_exit == 0
    capsys.readouterr()

    monkeypatch.setattr(
        "trinity_core.adapters.model.mistral_cli.shutil.which",
        lambda _: None,
    )

    exit_code = main(["runtime-status", "--adapter", "reply"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["provider_status"] == "offline"
    assert payload["provider_error_code"] == "executable_missing"
    assert "provider_error:executable_missing" in payload["readiness"]["reasons"]


def test_provider_smoke_reports_disabled_when_llm_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRINITY_MODEL_CONFIG_PATH", str(tmp_path / "config.json"))

    exit_code = main(["provider-smoke", "--adapter", "reply"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["state"] == "disabled"
    assert payload["roles"]["generator"]["reason"] == "llm_disabled"


def test_check_reply_compatibility_cli_contract(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reply_root = tmp_path / "reply"
    for relative_path in (
        "chat/brain-runtime.js",
        "chat/routes/messaging.js",
        "chat/js/api.js",
        "app/reply-app/Sources/NativeSettingsView.swift",
    ):
        path = reply_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("// test", encoding="utf-8")

    exit_code = main(["check-reply-compatibility", "--reply-root-dir", str(reply_root)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["contract_version"] == "trinity_reply_compat.v1"
    assert payload["ready"] is True


def test_gobii_status_cli_live_check(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("GOBII_API_KEY", "secret-key")
    monkeypatch.setattr(
        "trinity_core.cli.probe_gobii_seam",
        lambda **kwargs: {
            "contract_version": "trinity_gobii_status.v1",
            "adapter": kwargs["adapter_name"],
            "ready": True,
            "state": "online",
        },
    )

    exit_code = main(["gobii-status", "--adapter", "reply", "--check-live"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["state"] == "online"
