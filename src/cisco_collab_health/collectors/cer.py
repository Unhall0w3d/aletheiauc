"""Bounded read-only Cisco Emergency Responder API evidence."""

from __future__ import annotations

import re

from cisco_collab_health.collectors.base import CollectionResult
from cisco_collab_health.models.facts import AssessmentFacts, ConfigurationObjectFact
from cisco_collab_health.models.runtime import CollectionContext
from cisco_collab_health.transport.http import CapturedHttpClient, CapturedHttpError


class CerApiCollector:
    """Call CER's documented read-only authentication-status endpoint only."""

    name = "cer_api"

    def __init__(self, client: CapturedHttpClient | None = None) -> None:
        self.client = client or CapturedHttpClient()

    def collect(self, context: CollectionContext) -> CollectionResult:
        facts = AssessmentFacts()
        node = context.publisher_ip or context.target
        if not node:
            return CollectionResult(self.name, facts, warnings=["No CER publisher address configured."])
        endpoint = f"https://{node}/cerappservices/export/authenticate/status"
        try:
            response = self.client.get(
                endpoint, context, node=node, interface="cer_export_api",
                operation="authenticate_status", accept="text/xml",
            )
        except CapturedHttpError as exc:
            return CollectionResult(self.name, facts, warnings=[f"CER API authentication-status probe failed: {exc}"])
        status = re.sub(r"\s+", " ", " ".join(re.findall(r"<status>(.*?)</status>", response.body, re.I | re.S))).strip()
        facts.configuration_objects.append(
            ConfigurationObjectFact(
                "CerApiAuthenticationStatus", node,
                {"http_status": str(response.status), "status": status or "response received"},
                "CER.EXPORT.API",
            )
        )
        return CollectionResult(self.name, facts)
