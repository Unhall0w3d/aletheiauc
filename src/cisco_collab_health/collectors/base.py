"""Collector interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from cisco_collab_health.models.evidence import EvidenceRef
from cisco_collab_health.models.facts import AssessmentFacts
from cisco_collab_health.models.runtime import CollectionContext


@dataclass(frozen=True)
class CollectorError:
    """Structured error raised by one collector without aborting the assessment."""

    message: str
    exception_type: str
    recoverable: bool = True


@dataclass(frozen=True)
class CollectionResult:
    """Facts and metadata returned by one collector."""

    collector_name: str
    facts: AssessmentFacts
    warnings: list[str] = field(default_factory=list)
    errors: list[CollectorError] = field(default_factory=list)
    evidence: list[EvidenceRef] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    status_flags: list[str] = field(default_factory=list)


class Collector(Protocol):
    """Protocol implemented by all fact collectors."""

    name: str

    def collect(self, context: CollectionContext) -> CollectionResult:
        """Collect facts from a Cisco Collaboration source."""
