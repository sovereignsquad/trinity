# Changelog

All notable release-facing changes to `{trinity}` are recorded here.

## Unreleased documentation — 2026-10-19

### New Features
- No runtime features added; existing navigation is usable from GitHub and other clone locations.

### Fixed Bugs
- Replace machine-specific Markdown link destinations in README, Status and Handover with source-checked repository-relative links.

### Known Issues
- Machine-local shell examples remain examples. Existing dated provider and downstream-health observations are not revalidated by this documentation repair.
- Other documents may still contain machine-specific links; this scope covers the three entry points above. The application release remains 0.1.4.

### Future Roadmap
- Continue the separate portfolio destination, identity and documentation coverage review.

## 0.1.4 - 2026-05-19

This release tightens the live Reply compose contract so prepared drafts are treated as a hot-path runtime responsibility instead of a best-effort background artifact only.

### Added

- explicit documentation that the Reply adapter may be forced to return a prepared draft on conversation open
- release notes and handover coverage for the Reply hot-path prepared-draft contract

### Changed

- the effective Reply prepared-draft contract is now: reuse a fresh prepared draft when present, otherwise generate and return a best-available Trinity draft immediately for the opened thread
- local docs now describe that Reply should no longer seed compose from product-owned fallback drafts on the hot path

### Compatibility

- the generic CLI surface is unchanged
- existing prepared-draft storage and refresh planning remain valid; this release tightens the consumption contract rather than replacing the stored artifact format

## 0.1.3 - 2026-05-13

This release turns the scoring lane into an operational governance workflow while preserving downstream adapter compatibility.

### Added

- factorized score profiles for `impact`, `confidence`, and delivery-difficulty semantics
- deterministic memory-derived similarity signals and per-dimension rationale persistence
- score calibration, score audit, and trace-level `runtime_score_audit` exports
- score-health reports, review decisions, trend reports, and operator review surfaces
- workflow integration for governance-aware acceptance, release-governance reporting, triage queues, triage resolution, and release-decision lineage
- score-bearing persisted Spot reasoning candidates so new Spot traces can participate in ICE and priority inspection

### Changed

- `ease` is now explicitly treated as a compatibility-preserving field whose runtime meaning is delivery difficulty
- acceptance flows can now fail closed on unresolved governance risk unless an operator explicitly overrides with notes
- release and triage workflows now consume persisted governance artifacts instead of ad hoc review
- installation, README, contributor, CLI/API, and architecture docs now describe the governance-enabled runtime contract

### Compatibility

- Reply remains the first full downstream workflow and keeps legacy compatibility aliases
- Spot remains a bounded reasoning adapter slice, now with persisted score fields for new traces
- downstream consumers were revalidated through repo integration coverage, repo lint, and the macOS shell build
