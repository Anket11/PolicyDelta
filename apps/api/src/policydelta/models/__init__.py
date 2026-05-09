"""Single import point for all table models.

Import order matters: ``base`` first (naming convention), then tables.
Alembic's env.py imports this module once — importing models anywhere else
re-uses these definitions, avoiding SQLModel duplicate-table errors.
"""

from policydelta.models import base  # noqa: F401  (naming convention side effect)
from policydelta.models.audit import AuditFinding, AuditRun, RunStatus, RunVerdict
from policydelta.models.jobs import Job, JobKind, JobStatus
from policydelta.models.policy import OrgPolicy, OrgPolicyVersion
from policydelta.models.reference import Jurisdiction
from policydelta.models.regulatory import (
    EMBEDDING_DIMS,
    EffectiveDateSource,
    ExtractionStatus,
    RegulatoryChunk,
    RegulatoryDocument,
    Supersession,
    SupersessionRelation,
)
from policydelta.models.tenant import ApiKey, Organization

__all__ = [
    "EMBEDDING_DIMS",
    "ApiKey",
    "AuditFinding",
    "AuditRun",
    "EffectiveDateSource",
    "ExtractionStatus",
    "Job",
    "JobKind",
    "JobStatus",
    "Jurisdiction",
    "OrgPolicy",
    "OrgPolicyVersion",
    "Organization",
    "RegulatoryChunk",
    "RegulatoryDocument",
    "RunStatus",
    "RunVerdict",
    "Supersession",
    "SupersessionRelation",
]
