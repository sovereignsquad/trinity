# {reply} Product Adapter Contract

## Purpose

This document defines the first explicit `{reply}` to `{trinity}` product adapter seam.

The contract is owned by `{trinity}` because `{trinity}` owns the canonical runtime vocabulary for:

- evidence
- candidate generation
- evaluation
- frontier ranking
- feedback memory

`{reply}` may adapt product data into this shape, but it must not redefine the runtime concepts.

## Current Contract Version

- `trinity.reply.v1alpha1`

## Payload Families

### 1. Evidence Into {trinity}

`ReplyEvidenceEnvelope` carries:

- `company_id`
- `conversation_ref`
- `channel`
- `sender_handle`
- `message_text`
- `occurred_at`
- optional `external_message_id`
- optional string metadata

### 2. Draft Candidates Out Of {trinity}

`ReplyDraftCandidate` carries:

- `candidate_id`
- `conversation_ref`
- `recipient_handle`
- `channel`
- `draft_text`
- `rationale`
- canonical `CandidateScores`
- `source_evidence_ids`

### 3. Feedback Back Into {trinity}

`ReplyFeedbackEvent` carries:

- `candidate_id`
- `conversation_ref`
- `disposition`
- `occurred_at`
- optional notes
- optional `edited_text`

## Ownership Rules

- `{reply}` owns channels, operator UX, send flows, and product-local storage.
- `{trinity}` owns candidate vocabulary, ranking semantics, and feedback meaning.
- `{train}` may optimize bounded `{trinity}` artifacts derived from these runtime concepts, but it does not define them.
