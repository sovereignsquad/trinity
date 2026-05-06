"""Runtime storage path resolution outside the repository working tree."""

from __future__ import annotations

import os
import platform as platform_module
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from trinity_core.adapters import REPLY_ADAPTER_NAME, normalize_adapter_name


@dataclass(frozen=True, slots=True)
class RuntimeStoragePaths:
    """Resolved local runtime storage locations for Trinity."""

    app_support_dir: Path
    cache_dir: Path
    log_dir: Path


@dataclass(frozen=True, slots=True)
class AdapterRuntimePaths:
    """Resolved storage locations for one adapter within the Trinity runtime root."""

    adapter_name: str
    root_dir: Path
    using_legacy_reply_root: bool = False


def resolve_runtime_storage_paths(
    *,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
    platform_name: str | None = None,
    repo_root: Path | None = None,
) -> RuntimeStoragePaths:
    """Resolve machine-local runtime storage paths and reject repo-local locations."""

    resolved_env = env or os.environ
    resolved_home = (home or Path.home()).expanduser().resolve()
    resolved_platform = platform_name or platform_module.system()
    resolved_repo_root = (repo_root or Path.cwd()).expanduser().resolve()

    if resolved_platform == "Darwin":
        default_app_support = resolved_home / "Library" / "Application Support" / "Trinity"
        default_cache = resolved_home / "Library" / "Caches" / "Trinity"
        default_log = resolved_home / "Library" / "Logs" / "Trinity"
    else:
        default_app_support = resolved_home / ".local" / "share" / "trinity"
        default_cache = resolved_home / ".cache" / "trinity"
        default_log = resolved_home / ".local" / "state" / "trinity" / "logs"

    app_support_dir = _resolve_path(
        resolved_env.get("TRINITY_APP_SUPPORT_DIR"),
        default_app_support,
    )
    cache_dir = _resolve_path(
        resolved_env.get("TRINITY_CACHE_DIR"),
        default_cache,
    )
    log_dir = _resolve_path(
        resolved_env.get("TRINITY_LOG_DIR"),
        default_log,
    )

    for label, path in (
        ("app support", app_support_dir),
        ("cache", cache_dir),
        ("log", log_dir),
    ):
        if _is_within_repo(path, resolved_repo_root):
            raise ValueError(
                f"Trinity {label} directory must live outside the repository working tree: {path}"
            )

    return RuntimeStoragePaths(
        app_support_dir=app_support_dir,
        cache_dir=cache_dir,
        log_dir=log_dir,
    )


def resolve_adapter_runtime_paths(
    adapter_name: str,
    *,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
    platform_name: str | None = None,
    repo_root: Path | None = None,
) -> AdapterRuntimePaths:
    """Resolve the durable storage root for one Trinity adapter."""

    runtime_paths = resolve_runtime_storage_paths(
        env=env,
        home=home,
        platform_name=platform_name,
        repo_root=repo_root,
    )
    normalized_adapter = normalize_adapter_name(adapter_name)
    namespaced_root = (
        runtime_paths.app_support_dir / "trinity_runtime" / "adapters" / normalized_adapter
    )
    legacy_reply_root = runtime_paths.app_support_dir / "reply_runtime"
    use_legacy_reply_root = (
        normalized_adapter == REPLY_ADAPTER_NAME
        and legacy_reply_root.exists()
        and not namespaced_root.exists()
    )
    root_dir = legacy_reply_root if use_legacy_reply_root else namespaced_root
    root_dir.mkdir(parents=True, exist_ok=True)
    return AdapterRuntimePaths(
        adapter_name=normalized_adapter,
        root_dir=root_dir,
        using_legacy_reply_root=use_legacy_reply_root,
    )


def _resolve_path(value: str | None, default: Path) -> Path:
    if value is None:
        return default.resolve()
    return Path(value).expanduser().resolve()


def _is_within_repo(candidate: Path, repo_root: Path) -> bool:
    try:
        candidate.relative_to(repo_root)
        return True
    except ValueError:
        return False
