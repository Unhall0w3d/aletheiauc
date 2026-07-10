"""Tests for bounded cross-interface diagnostic capture."""

from __future__ import annotations

import unittest
from pathlib import Path

from cisco_collab_health.collectors.diagnostic import DiagnosticCaptureCollector
from cisco_collab_health.models.runtime import CollectionContext
from cisco_collab_health.transport.http import CapturedHttpResponse
from cisco_collab_health.transport.soap import SoapResponse


class FakeHttpClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def get(self, endpoint, context, *, node, interface, operation):
        del context
        self.calls.append((node, interface, endpoint))
        return CapturedHttpResponse(
            200,
            "OK",
            "<wsdl />",
            Path(f"{node}/{interface}/{operation}/response.txt"),
        )


class FakeSoapClient:
    def __init__(self) -> None:
        self.requests = []

    def send(self, request, context):
        del context
        self.requests.append(request)
        return SoapResponse(
            status=200,
            reason="OK",
            headers={},
            body="<response />",
            operation=request.operation,
            interface=request.interface,
            artifact_request="request",
            artifact_response="response",
            response_artifact_path=Path(
                f"{request.node}/{request.interface}/"
                f"{request.artifact_operation or request.operation}/response.txt"
            ),
        )


class DiagnosticCaptureCollectorTests(unittest.TestCase):
    def test_capture_queries_all_discovered_nodes_with_bounded_operations(self) -> None:
        http = FakeHttpClient()
        soap = FakeSoapClient()
        collector = DiagnosticCaptureCollector(
            ["risport70", "control_center", "perfmon"],
            soap_client=soap,
            http_client=http,
        )
        context = CollectionContext(
            publisher_ip="192.0.2.10",
            gui_username="apiuser",
            gui_password="secret",
            artifact_store=object(),
            discovered_nodes=("192.0.2.10", "192.0.2.11"),
            discovered_device_names=("SEP001", "SEP002"),
            diagnostic_max_devices=321,
        )

        result = collector.collect(context)

        self.assertEqual(result.warnings, [])
        self.assertIn("diagnostic_capture.enabled", result.status_flags)
        self.assertEqual(len(http.calls), 8)
        self.assertEqual(len(soap.requests), 13)
        risport = next(
            request for request in soap.requests if request.operation == "selectCmDeviceExt"
        )
        self.assertIn("<ast:MaxReturnedDevices>321</ast:MaxReturnedDevices>", risport.body)
        self.assertIn("<ast:Item>SEP001</ast:Item>", risport.body)
        control_nodes = {
            request.node
            for request in soap.requests
            if request.operation == "soapGetServiceStatus"
        }
        self.assertEqual(control_nodes, {"192.0.2.10", "192.0.2.11"})
        self.assertTrue(
            any(
                request.artifact_operation == "perfmonCollectCounterData_processor"
                for request in soap.requests
            )
        )

    def test_capture_skips_network_calls_when_artifacts_are_disabled(self) -> None:
        http = FakeHttpClient()
        soap = FakeSoapClient()
        collector = DiagnosticCaptureCollector(
            ["risport70"],
            soap_client=soap,
            http_client=http,
        )

        result = collector.collect(CollectionContext(publisher_ip="192.0.2.10"))

        self.assertEqual(http.calls, [])
        self.assertEqual(soap.requests, [])
        self.assertIn("artifact storage is disabled", result.warnings[0])


if __name__ == "__main__":
    unittest.main()
