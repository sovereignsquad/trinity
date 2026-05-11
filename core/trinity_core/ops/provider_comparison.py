"""Bounded provider comparison harness for replayable Trinity route evaluation."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from trinity_core.adapters import REPLY_ADAPTER_NAME, normalize_adapter_name
from trinity_core.adapters.model import TrinityModelProvider, build_model_provider
from trinity_core.model_config import TrinityModelConfig, TrinityRoleRoute, load_model_config
from trinity_core.ops.cycle_store import dataclass_payload, write_json_atomic
from trinity_core.ops.reply_shadow_fixtures import (
    ReplyShadowFixture,
    load_reply_shadow_fixtures,
)
from trinity_core.ops.runtime_storage import resolve_adapter_runtime_paths
from trinity_core.reply_runtime import ReplyRuntime

DETERMINISTIC_PROVIDER_MODEL = "deterministic:v0"


@dataclass(frozen=True, slots=True)
class ProviderRouteSet:
    """One replayable route-set candidate for provider comparison."""

    route_set_id: str
    config: TrinityModelConfig
    description: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderRoleCallMetrics:
    """Role-scoped provider call metrics for one fixture or summary."""

    attempted_calls: int = 0
    failed_calls: int = 0


@dataclass(frozen=True, slots=True)
class ProviderComparisonFixtureResult:
    """One fixture replay result under one route set."""

    route_set_id: str
    fixture_id: str
    channel: str
    cycle_id: str | None
    trace_ref: str | None
    latency_ms: float
    success: bool
    provider_error: str | None
    fallback_roles: tuple[str, ...] = ()
    quality_fit_score: float = 0.0
    overlap_ratio: float = 0.0
    edit_distance: float = 1.0
    suggestion: str | None = None
    model_routes: Mapping[str, str] = field(default_factory=dict)
    role_metrics: Mapping[str, ProviderRoleCallMetrics] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProviderComparisonRouteSummary:
    """Aggregate summary for one route set across a bounded corpus."""

    route_set_id: str
    description: str | None
    fixture_count: int
    success_count: int
    failure_count: int
    average_latency_ms: float
    average_quality_fit_score: float
    average_overlap_ratio: float
    average_edit_distance: float
    fallback_fixture_count: int
    routes: Mapping[str, str]
    role_metrics: Mapping[str, ProviderRoleCallMetrics]


@dataclass(frozen=True, slots=True)
class ProviderComparisonReport:
    """Machine-readable comparison report artifact."""

    report_id: str
    adapter_name: str
    corpus_id: str
    created_at: datetime
    route_summaries: tuple[ProviderComparisonRouteSummary, ...]
    fixture_results: tuple[ProviderComparisonFixtureResult, ...]


@dataclass(frozen=True, slots=True)
class ProviderComparisonStorePaths:
    """Persistent artifact paths for provider comparison reports."""

    adapter_name: str
    root_dir: Path
    reports_dir: Path


@dataclass(frozen=True, slots=True)
class _ProviderTrackerSnapshot:
    attempted: Mapping[str, int]
    failed: Mapping[str, int]


class TrackingModelProvider:
    """Provider wrapper that tracks per-role attempts and failures."""

    def __init__(
        self,
        inner: TrinityModelProvider,
        role_route_map: Mapping[TrinityRoleRoute, str],
    ) -> None:
        self._inner = inner
        self._role_route_map = dict(role_route_map)
        self._attempted = {role: 0 for role in ("generator", "refiner", "evaluator")}
        self._failed = {role: 0 for role in ("generator", "refiner", "evaluator")}
        self.provider_name = inner.provider_name
        self.supports_model_inventory = inner.supports_model_inventory

    def chat_json(
        self,
        *,
        route: TrinityRoleRoute,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, object]:
        role = self._role_route_map.get(route, "unknown")
        if role in self._attempted:
            self._attempted[role] += 1
        try:
            return self._inner.chat_json(
                route=route,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        except Exception:
            if role in self._failed:
                self._failed[role] += 1
            raise

    def list_models(self) -> tuple[dict[str, object], ...]:
        return self._inner.list_models()

    def snapshot(self) -> _ProviderTrackerSnapshot:
        return _ProviderTrackerSnapshot(
            attempted=dict(self._attempted),
            failed=dict(self._failed),
        )

    def diff(self, previous: _ProviderTrackerSnapshot) -> dict[str, ProviderRoleCallMetrics]:
        metrics: dict[str, ProviderRoleCallMetrics] = {}
        for role in ("generator", "refiner", "evaluator"):
            metrics[role] = ProviderRoleCallMetrics(
                attempted_calls=self._attempted[role] - previous.attempted.get(role, 0),
                failed_calls=self._failed[role] - previous.failed.get(role, 0),
            )
        return metrics


def resolve_provider_comparison_store_paths(
    adapter_name: str,
) -> ProviderComparisonStorePaths:
    adapter_paths = resolve_adapter_runtime_paths(
        normalize_adapter_name(adapter_name),
        repo_root=Path(__file__).resolve().parents[3],
    )
    root_dir = adapter_paths.root_dir / "provider_comparisons"
    reports_dir = root_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return ProviderComparisonStorePaths(
        adapter_name=normalize_adapter_name(adapter_name),
        root_dir=root_dir,
        reports_dir=reports_dir,
    )


def persist_provider_comparison_report(
    adapter_name: str,
    report: ProviderComparisonReport,
) -> Path:
    paths = resolve_provider_comparison_store_paths(adapter_name)
    report_path = paths.reports_dir / f"{report.report_id}.json"
    write_json_atomic(report_path, dataclass_payload(report))
    return report_path


def load_provider_route_sets(path: str | Path) -> tuple[ProviderRouteSet, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("route_sets"), list):
        items = payload["route_sets"]
    else:
        items = [payload]
    route_sets: list[ProviderRouteSet] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        route_set_id = str(item.get("route_set_id") or "").strip()
        if not route_set_id:
            raise ValueError("Provider route set payload is missing route_set_id.")
        route_sets.append(
            ProviderRouteSet(
                route_set_id=route_set_id,
                description=_optional_text(item.get("description")),
                config=_model_config_from_payload(item),
            )
        )
    return tuple(route_sets)


def deterministic_route_set(route_set_id: str = "deterministic-baseline") -> ProviderRouteSet:
    route = TrinityRoleRoute(
        provider="deterministic",
        model=DETERMINISTIC_PROVIDER_MODEL,
        temperature=0.0,
        keep_alive="0m",
    )
    return ProviderRouteSet(
        route_set_id=route_set_id,
        description="Deterministic fallback baseline.",
        config=TrinityModelConfig(
            provider="deterministic",
            ollama_base_url="http://127.0.0.1:11434",
            timeout_seconds=45.0,
            generator=route,
            refiner=route,
            evaluator=route,
        ),
    )


def current_config_route_set(adapter_name: str) -> ProviderRouteSet:
    normalized_adapter = normalize_adapter_name(adapter_name)
    return ProviderRouteSet(
        route_set_id=f"{normalized_adapter}-current-config",
        description="Current active adapter runtime config.",
        config=load_model_config(normalized_adapter),
    )


def run_reply_provider_comparison(
    route_sets: Sequence[ProviderRouteSet],
    fixtures: Sequence[ReplyShadowFixture],
    *,
    corpus_id: str,
) -> ProviderComparisonReport:
    if len(route_sets) < 2:
        raise ValueError("Provider comparison requires at least two route sets.")
    fixture_results: list[ProviderComparisonFixtureResult] = []
    route_summaries: list[ProviderComparisonRouteSummary] = []
    for route_set in route_sets:
        route_fixture_results = _run_route_set_against_reply_fixtures(route_set, fixtures)
        fixture_results.extend(route_fixture_results)
        route_summaries.append(_summarize_route_set(route_set, route_fixture_results))
    return ProviderComparisonReport(
        report_id=str(uuid4()),
        adapter_name=REPLY_ADAPTER_NAME,
        corpus_id=corpus_id,
        created_at=datetime.now(UTC),
        route_summaries=tuple(route_summaries),
        fixture_results=tuple(fixture_results),
    )


def run_reply_provider_comparison_from_fixture_dir(
    route_sets: Sequence[ProviderRouteSet],
    fixture_dir: str | Path,
    *,
    corpus_id: str | None = None,
) -> tuple[ProviderComparisonReport, Path]:
    fixtures = load_reply_shadow_fixtures(fixture_dir)
    resolved_corpus_id = corpus_id or Path(fixture_dir).resolve().name
    report = run_reply_provider_comparison(
        route_sets,
        fixtures,
        corpus_id=resolved_corpus_id,
    )
    report_path = persist_provider_comparison_report(REPLY_ADAPTER_NAME, report)
    return report, report_path


def _run_route_set_against_reply_fixtures(
    route_set: ProviderRouteSet,
    fixtures: Sequence[ReplyShadowFixture],
) -> tuple[ProviderComparisonFixtureResult, ...]:
    runtime = ReplyRuntime()
    runtime.model_config = route_set.config
    provider = build_model_provider(route_set.config)
    tracker = TrackingModelProvider(
        provider,
        {
            route_set.config.generator: "generator",
            route_set.config.refiner: "refiner",
            route_set.config.evaluator: "evaluator",
        },
    )
    runtime.model_provider = tracker

    results: list[ProviderComparisonFixtureResult] = []
    for fixture in fixtures:
        before = tracker.snapshot()
        started = perf_counter()
        try:
            ranked = runtime.suggest(fixture.thread_snapshot)
            latency_ms = round((perf_counter() - started) * 1000.0, 2)
            role_metrics = tracker.diff(before)
            suggestion = ranked.drafts[0].draft_text.strip() if ranked.drafts else ""
            overlap_ratio = _best_reference_overlap(fixture, suggestion)
            edit_distance = _best_reference_edit_distance(fixture, suggestion)
            quality_fit_score = _quality_fit_score(fixture, suggestion)
            results.append(
                ProviderComparisonFixtureResult(
                    route_set_id=route_set.route_set_id,
                    fixture_id=fixture.fixture_id,
                    channel=fixture.thread_snapshot.channel,
                    cycle_id=str(ranked.cycle_id),
                    trace_ref=ranked.trace_ref,
                    latency_ms=latency_ms,
                    success=True,
                    provider_error=None,
                    fallback_roles=tuple(
                        role
                        for role, metrics in role_metrics.items()
                        if metrics.failed_calls > 0
                    ),
                    quality_fit_score=quality_fit_score,
                    overlap_ratio=overlap_ratio,
                    edit_distance=edit_distance,
                    suggestion=suggestion,
                    model_routes=_route_identity(route_set.config),
                    role_metrics=role_metrics,
                )
            )
        except Exception as exc:
            latency_ms = round((perf_counter() - started) * 1000.0, 2)
            role_metrics = tracker.diff(before)
            results.append(
                ProviderComparisonFixtureResult(
                    route_set_id=route_set.route_set_id,
                    fixture_id=fixture.fixture_id,
                    channel=fixture.thread_snapshot.channel,
                    cycle_id=None,
                    trace_ref=None,
                    latency_ms=latency_ms,
                    success=False,
                    provider_error=str(exc),
                    fallback_roles=tuple(
                        role
                        for role, metrics in role_metrics.items()
                        if metrics.failed_calls > 0
                    ),
                    model_routes=_route_identity(route_set.config),
                    role_metrics=role_metrics,
                )
            )
    return tuple(results)


def _summarize_route_set(
    route_set: ProviderRouteSet,
    fixture_results: Sequence[ProviderComparisonFixtureResult],
) -> ProviderComparisonRouteSummary:
    fixture_count = len(fixture_results)
    success_results = [result for result in fixture_results if result.success]
    failure_count = fixture_count - len(success_results)
    fallback_fixture_count = sum(1 for result in fixture_results if result.fallback_roles)
    role_metrics = {
        role: ProviderRoleCallMetrics(
            attempted_calls=sum(
                result.role_metrics.get(role, ProviderRoleCallMetrics()).attempted_calls
                for result in fixture_results
            ),
            failed_calls=sum(
                result.role_metrics.get(role, ProviderRoleCallMetrics()).failed_calls
                for result in fixture_results
            ),
        )
        for role in ("generator", "refiner", "evaluator")
    }
    return ProviderComparisonRouteSummary(
        route_set_id=route_set.route_set_id,
        description=route_set.description,
        fixture_count=fixture_count,
        success_count=len(success_results),
        failure_count=failure_count,
        average_latency_ms=_average(result.latency_ms for result in fixture_results),
        average_quality_fit_score=_average(
            result.quality_fit_score for result in success_results
        ),
        average_overlap_ratio=_average(result.overlap_ratio for result in success_results),
        average_edit_distance=_average(result.edit_distance for result in success_results),
        fallback_fixture_count=fallback_fixture_count,
        routes=_route_identity(route_set.config),
        role_metrics=role_metrics,
    )


def _model_config_from_payload(payload: Mapping[str, object]) -> TrinityModelConfig:
    provider = str(payload.get("provider") or "deterministic").strip().lower()
    return TrinityModelConfig(
        provider=provider,
        ollama_base_url=str(payload.get("ollama_base_url") or "http://127.0.0.1:11434"),
        timeout_seconds=float(payload.get("timeout_seconds") or 45.0),
        generator=_role_route_from_payload(payload, "generator", provider),
        refiner=_role_route_from_payload(payload, "refiner", provider),
        evaluator=_role_route_from_payload(payload, "evaluator", provider),
        mistral_cli_executable=str(payload.get("mistral_cli_executable") or "vibe"),
        mistral_cli_args=tuple(
            str(item).strip()
            for item in payload.get("mistral_cli_args", ())
            if str(item).strip()
        ),
        mistral_cli_mode=str(payload.get("mistral_cli_mode") or "vibe").strip().lower(),
        mistral_cli_model_binding=str(
            payload.get("mistral_cli_model_binding") or "advisory"
        )
        .strip()
        .lower(),
    )


def _role_route_from_payload(
    payload: Mapping[str, object],
    role_name: str,
    provider: str,
) -> TrinityRoleRoute:
    role_payload = payload.get(role_name)
    if not isinstance(role_payload, Mapping):
        raise ValueError(f"Provider route set payload is missing `{role_name}` route config.")
    return TrinityRoleRoute(
        provider=str(role_payload.get("provider") or provider).strip().lower(),
        model=str(role_payload.get("model") or "").strip(),
        temperature=float(role_payload.get("temperature") or 0.0),
        keep_alive=str(role_payload.get("keep_alive") or "10m").strip(),
    )


def _route_identity(config: TrinityModelConfig) -> dict[str, str]:
    return {
        "generator": f"{config.generator.provider}:{config.generator.model}",
        "refiner": f"{config.refiner.provider}:{config.refiner.model}",
        "evaluator": f"{config.evaluator.provider}:{config.evaluator.model}",
    }


def _reference_texts(fixture: ReplyShadowFixture) -> tuple[str, ...]:
    texts = [fixture.legacy_suggestion.strip()]
    texts.extend(
        example.text.strip()
        for example in fixture.thread_snapshot.golden_examples
        if example.text.strip()
    )
    return tuple(text for text in texts if text)


def _quality_fit_score(fixture: ReplyShadowFixture, suggestion: str) -> float:
    return round(
        max(
            (
                (
                    _token_overlap_ratio(reference, suggestion)
                    + (1.0 - _normalized_edit_distance(reference, suggestion))
                )
                / 2.0
            )
            * 100.0
            for reference in _reference_texts(fixture)
        ),
        2,
    )


def _best_reference_overlap(fixture: ReplyShadowFixture, suggestion: str) -> float:
    return round(
        max(_token_overlap_ratio(reference, suggestion) for reference in _reference_texts(fixture)),
        4,
    )


def _best_reference_edit_distance(fixture: ReplyShadowFixture, suggestion: str) -> float:
    return round(
        min(
            _normalized_edit_distance(reference, suggestion)
            for reference in _reference_texts(fixture)
        ),
        4,
    )


def _token_overlap_ratio(left: str, right: str) -> float:
    left_tokens = set(str(left or "").lower().split())
    right_tokens = set(str(right or "").lower().split())
    if not left_tokens and not right_tokens:
        return 1.0
    union = left_tokens | right_tokens
    if not union:
        return 1.0
    overlap = sum(1 for token in union if token in left_tokens and token in right_tokens)
    return overlap / len(union)


def _normalized_edit_distance(left: str, right: str) -> float:
    source = str(left or "")
    target = str(right or "")
    if not source and not target:
        return 0.0
    rows = [[0] * (len(target) + 1) for _ in range(len(source) + 1)]
    for index in range(len(source) + 1):
        rows[index][0] = index
    for index in range(len(target) + 1):
        rows[0][index] = index
    for left_index in range(1, len(source) + 1):
        for right_index in range(1, len(target) + 1):
            cost = 0 if source[left_index - 1] == target[right_index - 1] else 1
            rows[left_index][right_index] = min(
                rows[left_index - 1][right_index] + 1,
                rows[left_index][right_index - 1] + 1,
                rows[left_index - 1][right_index - 1] + cost,
            )
    return rows[len(source)][len(target)] / max(len(source), len(target))


def _average(values: Sequence[float] | Mapping[object, float] | object) -> float:
    resolved = list(values) if not isinstance(values, list) else values
    if not resolved:
        return 0.0
    return round(sum(float(value) for value in resolved) / len(resolved), 2)


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None
