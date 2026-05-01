from __future__ import annotations

from pathlib import Path

import pytest
from trinity_core.ops import resolve_runtime_storage_paths


def test_macos_defaults_resolve_outside_repo() -> None:
    repo_root = Path("/Users/Shared/Projects/trinity")
    home = Path("/Users/tester")

    paths = resolve_runtime_storage_paths(
        home=home,
        platform_name="Darwin",
        repo_root=repo_root,
    )

    assert paths.app_support_dir == home / "Library" / "Application Support" / "Trinity"
    assert paths.cache_dir == home / "Library" / "Caches" / "Trinity"
    assert paths.log_dir == home / "Library" / "Logs" / "Trinity"


def test_override_paths_are_allowed_outside_repo() -> None:
    repo_root = Path("/Users/Shared/Projects/trinity")

    paths = resolve_runtime_storage_paths(
        env={
            "TRINITY_APP_SUPPORT_DIR": "/tmp/trinity-data",
            "TRINITY_CACHE_DIR": "/tmp/trinity-cache",
            "TRINITY_LOG_DIR": "/tmp/trinity-logs",
        },
        home=Path("/Users/tester"),
        platform_name="Darwin",
        repo_root=repo_root,
    )

    assert paths.app_support_dir == Path("/tmp/trinity-data").resolve()
    assert paths.cache_dir == Path("/tmp/trinity-cache").resolve()
    assert paths.log_dir == Path("/tmp/trinity-logs").resolve()


def test_repo_local_runtime_storage_is_rejected() -> None:
    repo_root = Path("/Users/Shared/Projects/trinity")

    with pytest.raises(
        ValueError,
        match="must live outside the repository working tree",
    ):
        resolve_runtime_storage_paths(
            env={"TRINITY_APP_SUPPORT_DIR": "/Users/Shared/Projects/trinity/data"},
            home=Path("/Users/tester"),
            platform_name="Darwin",
            repo_root=repo_root,
        )
