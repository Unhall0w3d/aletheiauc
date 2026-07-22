"""Tests for the bounded CER API scaffold."""

from __future__ import annotations

import unittest

from cisco_collab_health.collectors.cer import CerApiCollector
from cisco_collab_health.models.runtime import CollectionContext
from cisco_collab_health.transport.http import CapturedHttpResponse


class FakeCerClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get(self, endpoint: str, context: CollectionContext, **kwargs: str) -> CapturedHttpResponse:
        del context
        self.calls.append((endpoint, kwargs))
        return CapturedHttpResponse(
            200,
            "OK",
            "<authentication><status>Authentication successful on publisher</status></authentication>",
            None,
        )


class CerApiCollectorTests(unittest.TestCase):
    def test_authentication_status_probe_is_read_only_xml(self) -> None:
        client = FakeCerClient()
        result = CerApiCollector(client).collect(CollectionContext(target="192.0.2.40"))

        self.assertEqual(result.warnings, [])
        self.assertEqual(client.calls[0][0], "https://192.0.2.40/cerappservices/export/authenticate/status")
        self.assertEqual(client.calls[0][1]["accept"], "text/xml")
        self.assertEqual(result.facts.configuration_objects[0].details["http_status"], "200")
