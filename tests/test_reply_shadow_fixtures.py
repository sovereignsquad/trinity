from __future__ import annotations

from pathlib import Path

from trinity_core.ops.cycle_store import RuntimeCyclePaths, RuntimeCycleStore
from trinity_core.ops.reply_shadow_fixtures import (
    load_reply_shadow_fixture,
    load_reply_shadow_fixtures,
    run_reply_shadow_fixture,
    run_reply_shadow_fixtures,
    summarize_reply_shadow_results,
)
from trinity_core.reply_runtime import ReplyRuntime

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "reply_shadow"


def _runtime(tmp_path: Path) -> ReplyRuntime:
    store = RuntimeCycleStore(
        RuntimeCyclePaths(
            adapter_name="reply",
            root_dir=tmp_path / "runtime",
            cycles_dir=tmp_path / "runtime" / "cycles",
            exports_dir=tmp_path / "runtime" / "exports",
        )
    )
    store.paths.cycles_dir.mkdir(parents=True, exist_ok=True)
    store.paths.exports_dir.mkdir(parents=True, exist_ok=True)
    return ReplyRuntime(store=store)


def test_load_reply_shadow_fixture_reads_thread_snapshot() -> None:
    fixture = load_reply_shadow_fixture(FIXTURE_DIR / "email_update_today.json")

    assert fixture.fixture_id == "email_update_today"
    assert fixture.thread_snapshot.channel == "email"
    assert fixture.legacy_suggestion.startswith("Thanks Alice")


def test_run_reply_shadow_fixture_is_deterministic(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    fixture = load_reply_shadow_fixture(FIXTURE_DIR / "linkedin_clarify_scope.json")

    first = run_reply_shadow_fixture(runtime, fixture)
    second = run_reply_shadow_fixture(runtime, fixture)

    assert first.fixture_id == second.fixture_id
    assert first.channel == second.channel
    assert first.trinity_suggestion == second.trinity_suggestion
    assert first.overlap_ratio == second.overlap_ratio
    assert first.edit_distance == second.edit_distance
    assert first.accepted_artifact_version.artifact_key == "reply_ranker_policy"


def test_run_reply_shadow_fixtures_directory_builds_summary(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    fixtures = load_reply_shadow_fixtures(FIXTURE_DIR)

    results = run_reply_shadow_fixtures(runtime, fixtures)
    summary = summarize_reply_shadow_results(results)

    assert len(results) == 2
    assert summary["fixture_count"] == 2
    assert 0.0 <= summary["average_overlap_ratio"] <= 1.0
    assert 0.0 <= summary["average_edit_distance"] <= 1.0
    assert all(result.trinity_suggestion for result in results)
