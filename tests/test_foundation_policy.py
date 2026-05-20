from __future__ import annotations

import json
import subprocess
from pathlib import Path

from trinity_core.cli import main
from trinity_core.ops.foundation_policy import load_foundation_policy


def test_write_and_show_foundation_policy(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))

    exit_code = main(
        [
            "write-foundation-policy",
            "--train-default-transport",
            "cli",
            "--adapter",
            "reply",
            "--supported-provider",
            "deterministic",
            "--supported-provider",
            "mistral-cli",
            "--preferred-live-provider",
            "mistral-cli",
            "--release-gate-role",
            "generator",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["train"]["default_transport"] == "cli"
    assert payload["reply"]["preferred_live_provider"] == "mistral-cli"
    assert payload["reply"]["release_gate_roles"] == ["generator"]

    exit_code = main(["show-foundation-policy", "--include-path"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["policy_path"].endswith("foundation_policy.json")
    assert payload["reply"]["supported_providers"] == ["deterministic", "mistral-cli"]


def test_foundation_check_passes_for_spot_when_cli_train_is_ready(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    train_root = tmp_path / "train"
    train_root.mkdir()

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="usage: train",
            stderr="",
        )

    monkeypatch.setattr("trinity_core.ops.relation_health.subprocess.run", fake_run)

    exit_code = main(
        [
            "foundation-check",
            "--adapter",
            "spot",
            "--train-root-dir",
            str(train_root),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ready"] is True
    assert payload["state"] == "ready"
    assert payload["provider_smoke"]["state"] == "skipped"


def test_foundation_check_fails_when_reply_is_not_on_preferred_live_path(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    monkeypatch.setenv("TRINITY_MODEL_CONFIG_PATH", str(tmp_path / "config.json"))
    train_root = tmp_path / "train"
    train_root.mkdir()

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="usage: train",
            stderr="",
        )

    monkeypatch.setattr("trinity_core.ops.relation_health.subprocess.run", fake_run)

    write_exit = main(
        [
            "write-config",
            "--adapter",
            "reply",
            "--provider",
            "deterministic",
        ]
    )
    assert write_exit == 0
    capsys.readouterr()

    exit_code = main(
        [
            "foundation-check",
            "--adapter",
            "reply",
            "--train-root-dir",
            str(train_root),
            "--reply-root-dir",
            str(tmp_path / "missing-reply"),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert "provider_not_on_preferred_live_path" in payload["failures"]
    assert load_foundation_policy().train.default_transport == "cli"
