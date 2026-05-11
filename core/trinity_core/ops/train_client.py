"""Autonomous handoff client for invoking the sibling Train optimizer."""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from trinity_core.adapters import REPLY_ADAPTER_NAME, SPOT_ADAPTER_NAME
from trinity_core.ops.runtime_storage import resolve_adapter_runtime_paths

DEFAULT_TRAIN_API_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TRAIN_TRANSPORT = "api"


def propose_reply_policy_with_train(
    *,
    learner_kind: str,
    bundle_files: list[str | Path],
    transport: str = DEFAULT_TRAIN_TRANSPORT,
    train_api_base_url: str | None = None,
    train_root_dir: str | Path | None = None,
    proposal_output_path: str | Path | None = None,
    eval_output_path: str | Path | None = None,
) -> dict[str, Any]:
    if transport == "api":
        return propose_reply_policy_via_train_api(
            learner_kind=learner_kind,
            bundle_files=bundle_files,
            train_api_base_url=train_api_base_url,
            proposal_output_path=proposal_output_path,
            eval_output_path=eval_output_path,
        )
    if transport == "cli":
        return propose_reply_policy_via_train_cli(
            learner_kind=learner_kind,
            bundle_files=bundle_files,
            train_root_dir=train_root_dir,
            proposal_output_path=proposal_output_path,
            eval_output_path=eval_output_path,
        )
    raise ValueError("transport must be 'api' or 'cli'.")


def propose_spot_review_policy_with_train(
    *,
    learner_kind: str,
    bundle_files: list[str | Path],
    transport: str = DEFAULT_TRAIN_TRANSPORT,
    train_api_base_url: str | None = None,
    train_root_dir: str | Path | None = None,
    proposal_output_path: str | Path | None = None,
    eval_output_path: str | Path | None = None,
    comparison_output_path: str | Path | None = None,
) -> dict[str, Any]:
    if transport == "api":
        return propose_spot_review_policy_via_train_api(
            learner_kind=learner_kind,
            bundle_files=bundle_files,
            train_api_base_url=train_api_base_url,
            proposal_output_path=proposal_output_path,
            eval_output_path=eval_output_path,
            comparison_output_path=comparison_output_path,
        )
    if transport == "cli":
        return propose_spot_review_policy_via_train_cli(
            learner_kind=learner_kind,
            bundle_files=bundle_files,
            train_root_dir=train_root_dir,
            proposal_output_path=proposal_output_path,
            eval_output_path=eval_output_path,
            comparison_output_path=comparison_output_path,
        )
    raise ValueError("transport must be 'api' or 'cli'.")


def propose_reply_policy_via_train_api(
    *,
    learner_kind: str,
    bundle_files: list[str | Path],
    train_api_base_url: str | None = None,
    proposal_output_path: str | Path | None = None,
    eval_output_path: str | Path | None = None,
) -> dict[str, Any]:
    payload = {
        "learner_kind": learner_kind,
        "bundle_files": [str(Path(path)) for path in bundle_files],
        "proposal_output_path": str(proposal_output_path) if proposal_output_path else None,
        "eval_output_path": str(eval_output_path) if eval_output_path else None,
    }
    base_url = str(
        train_api_base_url
        or os.environ.get("TRINITY_TRAIN_API_BASE_URL")
        or DEFAULT_TRAIN_API_BASE_URL
    ).rstrip("/")
    request = urllib.request.Request(
        f"{base_url}/v1/trinity/reply/policies/propose",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Train API request failed with {exc.code}: {body}") from exc


def propose_spot_review_policy_via_train_api(
    *,
    learner_kind: str,
    bundle_files: list[str | Path],
    train_api_base_url: str | None = None,
    proposal_output_path: str | Path | None = None,
    eval_output_path: str | Path | None = None,
    comparison_output_path: str | Path | None = None,
) -> dict[str, Any]:
    payload = {
        "learner_kind": learner_kind,
        "bundle_files": [str(Path(path)) for path in bundle_files],
        "proposal_output_path": str(proposal_output_path) if proposal_output_path else None,
        "eval_output_path": str(eval_output_path) if eval_output_path else None,
        "comparison_output_path": (
            str(comparison_output_path) if comparison_output_path else None
        ),
    }
    base_url = str(
        train_api_base_url
        or os.environ.get("TRINITY_TRAIN_API_BASE_URL")
        or DEFAULT_TRAIN_API_BASE_URL
    ).rstrip("/")
    request = urllib.request.Request(
        f"{base_url}/v1/trinity/spot/policies/propose",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Train API request failed with {exc.code}: {body}") from exc


def propose_reply_policy_via_train_cli(
    *,
    learner_kind: str,
    bundle_files: list[str | Path],
    train_root_dir: str | Path | None = None,
    proposal_output_path: str | Path | None = None,
    eval_output_path: str | Path | None = None,
) -> dict[str, Any]:
    root_dir = _resolve_train_root_dir(train_root_dir)
    command = [
        "uv",
        "run",
        "python",
        "-m",
        "train_core.cli",
        "propose-reply-policy",
        "--learner-kind",
        learner_kind,
    ]
    for path in bundle_files:
        command.extend(["--bundle-file", str(Path(path))])
    if proposal_output_path is not None:
        command.extend(["--proposal-output-path", str(proposal_output_path)])
    if eval_output_path is not None:
        command.extend(["--eval-output-path", str(eval_output_path)])
    completed = subprocess.run(
        command,
        cwd=root_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        error_text = completed.stderr.strip() or completed.stdout.strip() or "Train CLI failed."
        raise RuntimeError(error_text)
    return json.loads(completed.stdout)


def propose_spot_review_policy_via_train_cli(
    *,
    learner_kind: str,
    bundle_files: list[str | Path],
    train_root_dir: str | Path | None = None,
    proposal_output_path: str | Path | None = None,
    eval_output_path: str | Path | None = None,
    comparison_output_path: str | Path | None = None,
) -> dict[str, Any]:
    root_dir = _resolve_train_root_dir(train_root_dir)
    command = [
        "uv",
        "run",
        "python",
        "-m",
        "train_core.cli",
        "propose-spot-review-policy",
        "--learner-kind",
        learner_kind,
    ]
    for path in bundle_files:
        command.extend(["--bundle-file", str(Path(path))])
    if proposal_output_path is not None:
        command.extend(["--proposal-output-path", str(proposal_output_path)])
    if eval_output_path is not None:
        command.extend(["--eval-output-path", str(eval_output_path)])
    if comparison_output_path is not None:
        command.extend(["--comparison-output-path", str(comparison_output_path)])
    completed = subprocess.run(
        command,
        cwd=root_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        error_text = completed.stderr.strip() or completed.stdout.strip() or "Train CLI failed."
        raise RuntimeError(error_text)
    return json.loads(completed.stdout)


def default_train_proposal_paths(
    *,
    adapter_name: str = REPLY_ADAPTER_NAME,
    learner_kind: str,
) -> tuple[Path, Path]:
    adapter_paths = resolve_adapter_runtime_paths(
        adapter_name,
        repo_root=Path(__file__).resolve().parents[3],
    )
    handoff_dir = adapter_paths.root_dir / "train_handoffs" / "reply_policy" / learner_kind
    handoff_dir.mkdir(parents=True, exist_ok=True)
    proposal_path = handoff_dir / "proposal.json"
    eval_path = handoff_dir / "eval_report.json"
    return proposal_path, eval_path


def default_train_spot_proposal_paths(
    *,
    adapter_name: str = SPOT_ADAPTER_NAME,
    learner_kind: str,
) -> tuple[Path, Path, Path]:
    adapter_paths = resolve_adapter_runtime_paths(
        adapter_name,
        repo_root=Path(__file__).resolve().parents[3],
    )
    handoff_dir = adapter_paths.root_dir / "train_handoffs" / "spot_review_policy" / learner_kind
    handoff_dir.mkdir(parents=True, exist_ok=True)
    proposal_path = handoff_dir / "proposal.json"
    eval_path = handoff_dir / "eval_report.json"
    comparison_path = handoff_dir / "comparison_report.json"
    return proposal_path, eval_path, comparison_path


def _resolve_train_root_dir(train_root_dir: str | Path | None) -> Path:
    if train_root_dir is not None:
        return Path(train_root_dir).expanduser().resolve()
    configured = os.environ.get("TRINITY_TRAIN_ROOT_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[4] / "train"
