# Evidence Ingestion Contract

## Purpose

This document defines the first concrete runtime contract in `{trinity}`:

- canonical evidence ingestion
- exact-hash duplicate suppression
- provenance retention
- tenant-bound evidence writes

This contract implements the initial delivery target of issue `#3`.

## Contract Objects

The runtime now exposes these evidence-layer objects in `core/trinity_core/`:

- `EvidenceUnit`
- `EvidenceSourceType`
- `EvidenceSourceRef`
- `EvidenceFreshnessWindow`
- `EvidenceProvenance`
- `RawEvidenceInput`
- `EvidenceIngestionResult`
- `DuplicateEvidenceSuppressed`

## Ingestion Rules

### Canonicalization

`canonicalize_content()` currently applies deterministic normalization:

- HTML entities are unescaped
- markup tags are stripped
- carriage returns are normalized
- repeated whitespace is collapsed
- leading and trailing whitespace is removed

If canonicalization produces empty content, ingestion fails closed.

### Hashing

`compute_content_hash()` computes a `sha256` hash of canonical content.

This hash is the exact-deduplication key.

### Deduplication

Duplicate suppression is:

- exact-hash only
- deterministic
- tenant-bound

That means identical canonical content for the same company is suppressed, while identical content across different companies remains valid and separate.

### Provenance

Provenance is explicit.

`EvidenceProvenance` currently requires:

- `collected_at`
- `collector`
- `ingestion_channel`

Optional origin details can still be attached through:

- `raw_origin_uri`
- `ingestion_notes`

### Freshness

Each accepted evidence unit carries an `EvidenceFreshnessWindow` computed from ingestion time plus a provided duration.

## Current Non-Goals

This increment does not yet provide:

- durable persistence
- source-specific adapter collectors
- topic inference logic beyond caller-provided hints
- approximate or semantic deduplication

Those belong in later issues.

## Verification

This contract is verified through deterministic tests covering:

- canonicalization stability
- stable hashing
- same-tenant duplicate suppression
- cross-tenant isolation
- explicit provenance requirements
