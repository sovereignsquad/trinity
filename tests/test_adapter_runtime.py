from __future__ import annotations

from pathlib import Path

import pytest
from trinity_core.cli import main
from trinity_core.ops import resolve_adapter_runtime_paths
from trinity_core.runtime import TrinityRuntime


def test_resolve_adapter_runtime_paths_uses_namespaced_root_for_new_adapters() -> None:
    repo_root = Path("/Users/Shared/Projects/trinity")
    home = Path("/tmp/trinity-test-home")

    paths = resolve_adapter_runtime_paths(
        "reply",
        home=home,
        platform_name="Darwin",
        repo_root=repo_root,
    )

    assert paths.root_dir == (
        home
        / "Library"
        / "Application Support"
        / "Trinity"
        / "trinity_runtime"
        / "adapters"
        / "reply"
    ).resolve()
    assert paths.using_legacy_reply_root is False


def test_resolve_adapter_runtime_paths_can_fall_back_to_legacy_reply_root(tmp_path: Path) -> None:
    repo_root = Path("/Users/Shared/Projects/trinity")
    app_support_dir = tmp_path / "Library" / "Application Support" / "Trinity"
    legacy_root = app_support_dir / "reply_runtime"
    legacy_root.mkdir(parents=True, exist_ok=True)

    paths = resolve_adapter_runtime_paths(
        "reply",
        env={"TRINITY_APP_SUPPORT_DIR": str(app_support_dir)},
        home=tmp_path,
        platform_name="Darwin",
        repo_root=repo_root,
    )

    assert paths.root_dir == legacy_root
    assert paths.using_legacy_reply_root is True


def test_trinity_runtime_rejects_unknown_adapter() -> None:
    with pytest.raises(ValueError, match="Unsupported Trinity adapter"):
        TrinityRuntime(adapter_name="openmythos")


def test_generic_cli_show_config_supports_adapter_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRINITY_MODEL_CONFIG_PATH", str(tmp_path / "config.json"))

    exit_code = main(["show-config", "--adapter", "reply", "--include-path"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"provider": "deterministic"' in captured.out
    assert '"config_path":' in captured.out
