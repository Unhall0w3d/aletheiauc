"""Collector interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from dataclasses import replace
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
    collector_name: str | None = None
    target_id: str | None = None
    technology: str | None = None


class CollectorExecutionFailure(RuntimeError):
    """An explicitly classified collector failure."""

    def __init__(self, message: str, *, recoverable: bool = True) -> None:
        super().__init__(message)
        self.recoverable = recoverable


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

    @property
    def name(self) -> str:
        """Stable collector name used in evidence and status output."""

    def collect(self, context: CollectionContext) -> CollectionResult:
        """Collect facts from a Cisco Collaboration source."""


def collect_safely(
    collector: Collector,
    context: CollectionContext,
    *,
    target_id: str | None = None,
    technology: str | None = None,
) -> CollectionResult:
    """Convert recoverable collector exceptions into attributed results.

    KeyboardInterrupt and other non-Exception control-flow events intentionally propagate.
    """

    collector_name = getattr(collector, "name", collector.__class__.__name__)
    try:
        return collector.collect(context)
    except CollectorExecutionFailure as exc:
        return CollectionResult(
            collector_name=collector_name,
            facts=AssessmentFacts(),
            errors=[
                CollectorError(
                    message=str(exc),
                    exception_type=exc.__class__.__name__,
                    recoverable=exc.recoverable,
                    collector_name=collector_name,
                    target_id=target_id,
                    technology=technology,
                )
            ],
        )
    except Exception as exc:
        return CollectionResult(
            collector_name=collector_name,
            facts=AssessmentFacts(),
            errors=[
                CollectorError(
                    message=str(exc),
                    exception_type=exc.__class__.__name__,
                    collector_name=collector_name,
                    target_id=target_id,
                    technology=technology,
                )
            ],
        )


@dataclass(frozen=True)
class TargetPipelineCollector:
    """Run a target's collectors with isolated discovery state and credentials."""

    target_id: str
    technology: str
    collectors: tuple[Collector, ...]
    target_context: CollectionContext

    @property
    def name(self) -> str:
        return f"{self.target_id}[{self.technology}]"

    def collect(self, context: CollectionContext) -> CollectionResult:
        del context
        facts = AssessmentFacts()
        warnings: list[str] = []
        errors: list[CollectorError] = []
        evidence: list[EvidenceRef] = []
        notes: list[str] = []
        flags: list[str] = []
        target_context = self.target_context
        for collector in self.collectors:
            result = collect_safely(
                collector,
                target_context,
                target_id=self.target_id,
                technology=self.technology,
            )
            tagged_facts = replace(
                result.facts,
                nodes=[
                    replace(node, technology=self.technology, target_id=self.target_id)
                    for node in result.facts.nodes
                ],
                platform_checks=[
                    replace(check, technology=self.technology, target_id=self.target_id)
                    for check in result.facts.platform_checks
                ],
            )
            facts.merge(tagged_facts)
            warnings.extend(f"{collector.name}: {item}" for item in result.warnings)
            errors.extend(result.errors)
            evidence.extend(result.evidence)
            notes.extend(f"{collector.name}: {item}" for item in result.notes)
            flags.extend(result.status_flags)
            if any(not error.recoverable for error in result.errors):
                break
            target_context = replace(
                target_context,
                discovered_nodes=tuple(
                    dict.fromkeys(node.address or node.name for node in facts.nodes)
                ),
                discovered_device_names=tuple(
                    dict.fromkeys(device.name for device in facts.devices if device.name)
                ),
            )
        return CollectionResult(
            collector_name=self.name,
            facts=facts,
            warnings=warnings,
            errors=errors,
            evidence=evidence,
            notes=notes,
            status_flags=flags,
        )
