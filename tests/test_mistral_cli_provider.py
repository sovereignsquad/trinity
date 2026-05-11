from __future__ import annotations

import subprocess

import pytest
from trinity_core.adapters.model.mistral_cli import (
    MistralCLIError,
    MistralCLIModelProvider,
)
from trinity_core.model_config import TrinityRoleRoute


def test_mistral_cli_provider_parses_vibe_json(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = MistralCLIModelProvider(
        executable="vibe",
        extra_args=("--agent", "auto-approve"),
        timeout_seconds=15.0,
    )
    route = TrinityRoleRoute(
        provider="mistral-cli",
        model="mistral-small-latest",
        temperature=0.2,
        keep_alive="10m",
    )

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        command = args[0]
        assert isinstance(command, list)
        assert command[0] == "/usr/local/bin/vibe"
        assert "--prompt" in command
        assert "--output" in command
        assert "--agent" in command
        assert "auto-approve" in command
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=(
                '{"messages":[{"role":"assistant","content":"'
                '{\\"winner\\":\\"candidate_a\\",\\"confidence\\":0.91}'
                '"}]}'
            ),
            stderr="",
        )

    monkeypatch.setattr(
        "trinity_core.adapters.model.mistral_cli.shutil.which",
        lambda _: "/usr/local/bin/vibe",
    )
    monkeypatch.setattr("trinity_core.adapters.model.mistral_cli.subprocess.run", fake_run)

    payload = provider.chat_json(
        route=route,
        system_prompt="Return JSON only.",
        user_prompt="Pick the best candidate.",
    )

    assert payload == {"winner": "candidate_a", "confidence": 0.91}


def test_mistral_cli_provider_reports_missing_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = MistralCLIModelProvider(executable="missing-vibe")

    monkeypatch.setattr("trinity_core.adapters.model.mistral_cli.shutil.which", lambda _: None)

    with pytest.raises(MistralCLIError, match="executable is not available"):
        provider.chat_json(
            route=TrinityRoleRoute(
                provider="mistral-cli",
                model="mistral-small-latest",
                temperature=0.2,
                keep_alive="10m",
            ),
            system_prompt="Return JSON only.",
            user_prompt="Pick the best candidate.",
        )
