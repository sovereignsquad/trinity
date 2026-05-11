from __future__ import annotations

import json
from pathlib import Path

import pytest
from trinity_core.cli import main
from trinity_core.ops.provider_comparison import load_provider_route_sets


class _FakeProvider:
    provider_name = "ollama"
    supports_model_inventory = False

    def __init__(self, config) -> None:
        self.config = config

    def chat_json(self, *, route, system_prompt: str, user_prompt: str):
        payload = json.loads(user_prompt)
        if route.model == "generator-shadow":
            latest = str(payload["latest_inbound_text"]).lower()
            if "updated numbers" in latest:
                return {
                    "candidates": [
                        {
                            "title": "Direct answer",
                            "content": "Thanks Alice, I can send the updated numbers today.",
                            "impact": 8,
                            "confidence": 8,
                            "ease": 8,
                            "tags": ["direct"],
                        },
                        {
                            "title": "Advance",
                            "content": "I can send the numbers and add the client note too.",
                            "impact": 7,
                            "confidence": 6,
                            "ease": 6,
                            "tags": ["advance"],
                        },
                        {
                            "title": "Clarify",
                            "content": "Do you need the updated numbers or the full update note?",
                            "impact": 6,
                            "confidence": 6,
                            "ease": 6,
                            "tags": ["clarify"],
                        },
                    ]
                }
            return {
                "candidates": [
                    {
                        "title": "Clarify scope",
                        "content": (
                            "Thanks Maya, happy to help. Do you want a short intro note "
                            "or the full follow-up message?"
                        ),
                        "impact": 8,
                        "confidence": 8,
                        "ease": 8,
                        "tags": ["clarify"],
                    },
                    {
                        "title": "Direct answer",
                        "content": "I can draft the note now.",
                        "impact": 6,
                        "confidence": 6,
                        "ease": 7,
                        "tags": ["direct"],
                    },
                    {
                        "title": "Advance",
                        "content": "I can draft it and suggest a follow-up step too.",
                        "impact": 7,
                        "confidence": 6,
                        "ease": 6,
                        "tags": ["advance"],
                    },
                ]
            }
        if route.model == "refiner-shadow":
            candidate = payload["candidate"]
            return {
                "title": candidate["title"],
                "content": candidate["content"],
                "impact": 8,
                "confidence": 8,
                "ease": 8,
                "tags": candidate["semantic_tags"],
                "reason": "Kept the draft concise and operator-safe.",
            }
        if route.model == "evaluator-failing":
            raise RuntimeError("simulated evaluator failure")
        if route.model == "evaluator-shadow":
            return {
                "evaluations": [
                    {
                        "candidate_id": item["candidate_id"],
                        "disposition": "ELIGIBLE",
                        "impact": 8 if index == 0 else 6,
                        "confidence": 8 if index == 0 else 6,
                        "ease": 8 if index == 0 else 6,
                        "quality_score": 90.0 if index == 0 else 72.0,
                        "urgency_score": 65.0,
                        "freshness_score": 70.0,
                        "feedback_score": 14.0,
                        "reason": "Scored by fake provider benchmark harness.",
                    }
                    for index, item in enumerate(payload["candidates"])
                ]
            }
        raise AssertionError(f"Unexpected model in fake provider: {route.model}")

    def list_models(self):
        return ()


def _route_file_payload() -> dict[str, object]:
    return {
        "route_sets": [
            {
                "route_set_id": "ollama-shadow",
                "description": "Fake high-quality route set.",
                "provider": "ollama",
                "generator": {
                    "provider": "ollama",
                    "model": "generator-shadow",
                    "temperature": 0.2,
                    "keep_alive": "5m",
                },
                "refiner": {
                    "provider": "ollama",
                    "model": "refiner-shadow",
                    "temperature": 0.2,
                    "keep_alive": "5m",
                },
                "evaluator": {
                    "provider": "ollama",
                    "model": "evaluator-shadow",
                    "temperature": 0.1,
                    "keep_alive": "5m",
                },
            },
            {
                "route_set_id": "ollama-fallback",
                "description": "Fake route set that falls back on evaluator.",
                "provider": "ollama",
                "generator": {
                    "provider": "ollama",
                    "model": "generator-shadow",
                    "temperature": 0.2,
                    "keep_alive": "5m",
                },
                "refiner": {
                    "provider": "ollama",
                    "model": "refiner-shadow",
                    "temperature": 0.2,
                    "keep_alive": "5m",
                },
                "evaluator": {
                    "provider": "ollama",
                    "model": "evaluator-failing",
                    "temperature": 0.1,
                    "keep_alive": "5m",
                },
            },
        ]
    }


def test_load_provider_route_sets_accepts_route_set_arrays(tmp_path: Path) -> None:
    route_file = tmp_path / "route_sets.json"
    route_file.write_text(json.dumps(_route_file_payload()), encoding="utf-8")

    route_sets = load_provider_route_sets(route_file)

    assert [route_set.route_set_id for route_set in route_sets] == [
        "ollama-shadow",
        "ollama-fallback",
    ]
    assert route_sets[0].config.generator.model == "generator-shadow"
    assert route_sets[1].config.evaluator.model == "evaluator-failing"


def test_compare_providers_cli_persists_report_and_fallback_metrics(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    route_file = tmp_path / "route_sets.json"
    route_file.write_text(json.dumps(_route_file_payload()), encoding="utf-8")
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))

    def fake_build_model_provider(config):
        return _FakeProvider(config)

    monkeypatch.setattr(
        "trinity_core.ops.provider_comparison.build_model_provider",
        fake_build_model_provider,
    )

    exit_code = main(
        [
            "compare-providers",
            "--adapter",
            "reply",
            "--fixture-dir",
            str(Path("tests/fixtures/reply_shadow").resolve()),
            "--route-set-file",
            str(route_file),
            "--include-deterministic-baseline",
            "--corpus-id",
            "reply-shadow-smoke",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert Path(payload["report_path"]).exists()
    assert payload["report"]["adapter_name"] == "reply"
    assert payload["report"]["corpus_id"] == "reply-shadow-smoke"

    summaries = {
        item["route_set_id"]: item for item in payload["report"]["route_summaries"]
    }
    assert set(summaries) == {
        "deterministic-baseline",
        "ollama-shadow",
        "ollama-fallback",
    }
    assert summaries["ollama-shadow"]["success_count"] == 2
    assert summaries["ollama-fallback"]["fallback_fixture_count"] == 2
    assert summaries["ollama-fallback"]["role_metrics"]["evaluator"]["failed_calls"] == 2
