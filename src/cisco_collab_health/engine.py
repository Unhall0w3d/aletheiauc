"""Assessment orchestration."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from dataclasses import replace

from cisco_collab_health.collectors.base import Collector, collect_safely
from cisco_collab_health.models.assessment import AssessmentReport
from cisco_collab_health.models.facts import AssessmentFacts, CollectorIssueFact
from cisco_collab_health.models.runtime import CollectionContext
from cisco_collab_health.rules.base import HealthRule


@dataclass(frozen=True)
class AssessmentEngine:
    """Runs collectors, applies rules, and returns a structured assessment."""

    collectors: Iterable[Collector]
    rules: Iterable[HealthRule]

    def run(self, context: CollectionContext | None = None) -> AssessmentReport:
        collection_context = context or CollectionContext()
        facts = AssessmentFacts()
        collector_results = []

        for collector in self.collectors:
            result = collect_safely(collector, collection_context)
            collector_results.append(result)
            facts.merge(result.facts)
            discovered_nodes = tuple(
                dict.fromkeys(node.address or node.name for node in facts.nodes)
            )
            discovered_device_names = tuple(
                dict.fromkeys(device.name for device in facts.devices if device.name)
            )
            collection_context = replace(
                collection_context,
                discovered_nodes=discovered_nodes,
                discovered_device_names=discovered_device_names,
            )
            for warning in result.warnings:
                facts.collector_issues.append(
                    CollectorIssueFact(
                        collector_name=result.collector_name,
                        issue_type="warning",
                        message=warning,
                    )
                )
            for error in result.errors:
                facts.collector_issues.append(
                    CollectorIssueFact(
                        collector_name=result.collector_name,
                        issue_type="error",
                        message=error.message,
                        exception_type=error.exception_type,
                    )
                )

        findings = []
        for rule in self.rules:
            findings.extend(rule.evaluate(facts))

        return AssessmentReport(
            facts=facts,
            collector_results=collector_results,
            findings=findings,
        )
