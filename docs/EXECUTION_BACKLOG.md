# {trinity} Execution Backlog

## Objective

Deliver a reusable runtime with explicit product adapters while keeping current Reply integrations stable.

## Milestones

### M1. Core Runtime Foundations

- [x] Establish deterministic workflow core.
- [x] Add explicit Reply integration contracts.
- [x] Persist runtime cycles, exports, and training bundles.

### M2. Policy Loop Foundations

- [x] Add `ReplyBehaviorPolicy` schema.
- [x] Add accepted-artifact registry.
- [x] Add replay-gated acceptance workflow.
- [x] Add Reply shadow fixtures and summary tooling.

### M3. Adapter Extraction

- [x] Add adapter helpers and generic runtime facade.
- [x] Add generic CLI commands with `--adapter`.
- [x] Add adapter-scoped runtime storage for new installs.
- [x] Preserve Reply compatibility aliases and legacy storage fallback.

### M4. Multi-Project Proof

- [ ] Add a second real product adapter.
- [ ] Move Reply-owned mapping and policy behavior deeper into dedicated adapter modules.
- [ ] Generalize policy envelopes where two adapters demonstrably need shared behavior.

## Active Issue Queue

### Closed

- `TRINITY-001` Missing first-class `{reply}` adapter contract
  Fixed by adding explicit Reply integration schemas and adapter-facing runtime artifacts.

- `TRINITY-002` Frontier ranking lived only in prose
  Fixed by adding deterministic frontier selection in workflow core.

- `TRINITY-003` Missing feedback-memory application logic
  Fixed by adding deterministic feedback application for Reply-originated outcomes.

- `TRINITY-POLICY-001` Missing bounded Reply behavior policy schema
  Fixed by adding `ReplyBehaviorPolicy` and deterministic scope precedence rules.

- `TRINITY-POLICY-002` Missing accepted artifact registry
  Fixed by adding immutable version storage plus explicit promote and rollback semantics.

- `TRINITY-POLICY-003` Missing training bundle export
  Fixed by adding bounded bundle export from persisted runtime cycles.

- `TRINITY-POLICY-004` Missing runtime policy resolution
  Fixed by adding accepted policy resolution and accepted-artifact provenance in runtime output.

- `TRINITY-POLICY-005` Missing acceptance gate workflow
  Fixed by adding replay-gated policy acceptance and incumbent-regression checks.

- `TRINITY-005` Missing Reply shadow comparison fixtures
  Fixed by adding deterministic fixture replay and aggregate comparison summaries.

- `TRINITY-ADAPTER-001` Runtime shell still hard-wired to Reply
  Fixed by adding adapter helpers, `TrinityRuntime`, adapter-scoped storage, and generic CLI commands while preserving Reply compatibility aliases.

### Open

- `TRINITY-ADAPTER-002` No second adapter proving the abstraction
  The runtime now has an adapter seam, but the abstraction is not yet proven by a second real product integration.

- `TRINITY-ADAPTER-003` Reply policy artifacts remain adapter-specific
  This is acceptable today, but future shared policy abstractions should be introduced only when a second adapter demonstrates overlap.

## Dependencies

- depends on `{reply}` to keep the existing production adapter contract stable
- depends on a second downstream project to validate the new adapter architecture
- continues feeding `{train}` with bounded runtime artifacts while retaining runtime ownership
