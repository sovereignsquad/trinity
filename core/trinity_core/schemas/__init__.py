"""Schema contracts for Trinity runtime artifacts."""

from .candidate import (
    CandidateLineage,
    CandidateRecord,
    CandidateScores,
    CandidateState,
    CandidateType,
    ReworkRoute,
)
from .evidence import (
    EvidenceFreshnessWindow,
    EvidenceProvenance,
    EvidenceSourceRef,
    EvidenceSourceType,
    EvidenceUnit,
)
from .integration import (
    REPLY_CONTRACT_VERSION,
    ReplyDraftCandidate,
    ReplyEvidenceEnvelope,
    ReplyFeedbackDisposition,
    ReplyFeedbackEvent,
)

__all__ = [
    "CandidateLineage",
    "CandidateRecord",
    "CandidateScores",
    "CandidateState",
    "CandidateType",
    "EvidenceFreshnessWindow",
    "EvidenceProvenance",
    "EvidenceSourceRef",
    "EvidenceSourceType",
    "EvidenceUnit",
    "REPLY_CONTRACT_VERSION",
    "ReworkRoute",
    "ReplyDraftCandidate",
    "ReplyEvidenceEnvelope",
    "ReplyFeedbackDisposition",
    "ReplyFeedbackEvent",
]
