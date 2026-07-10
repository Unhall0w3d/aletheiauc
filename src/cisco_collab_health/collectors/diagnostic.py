"""Bounded read-only diagnostic capture across CUCM service interfaces."""

from __future__ import annotations

from collections.abc import Iterable
from xml.sax.saxutils import escape

from cisco_collab_health.collectors.base import CollectionResult
from cisco_collab_health.models.evidence import EvidenceRef
from cisco_collab_health.models.facts import AssessmentFacts
from cisco_collab_health.models.runtime import CollectionContext
from cisco_collab_health.transport.http import CapturedHttpClient, CapturedHttpError
from cisco_collab_health.transport.soap import (
    SoapClient,
    SoapRequest,
    SoapResponse,
    SoapTransportError,
)

AST_NAMESPACE = "http://schemas.cisco.com/ast/soap"


class DiagnosticCaptureCollector:
    """Capture bounded discovery responses for future parser and collector work."""

    name = "diagnostic_capture"

    def __init__(
        self,
        available_interfaces: Iterable[str],
        *,
        soap_client: SoapClient | None = None,
        http_client: CapturedHttpClient | None = None,
    ) -> None:
        self.available_interfaces = frozenset(available_interfaces)
        self.soap_client = soap_client or SoapClient()
        self.http_client = http_client or CapturedHttpClient()

    def collect(self, context: CollectionContext) -> CollectionResult:
        facts = AssessmentFacts()
        warnings: list[str] = []
        notes: list[str] = []
        evidence: list[EvidenceRef] = []
        status_flags = ["diagnostic_capture.enabled"]

        if context.artifact_store is None:
            return CollectionResult(
                collector_name=self.name,
                facts=facts,
                warnings=[
                    "Diagnostic capture skipped because local artifact storage is disabled."
                ],
                status_flags=[*status_flags, "diagnostic_capture.skipped_no_artifacts"],
            )
        if not context.publisher_ip:
            return CollectionResult(
                collector_name=self.name,
                facts=facts,
                warnings=["Diagnostic capture skipped because Publisher IP is missing."],
                status_flags=[*status_flags, "diagnostic_capture.skipped_no_publisher"],
            )

        nodes = tuple(dict.fromkeys(context.discovered_nodes or (context.publisher_ip,)))
        self._capture_wsdls(context, nodes, evidence, warnings)

        if "risport70" in self.available_interfaces:
            self._capture_risport(context, evidence, warnings)
        if "control_center" in self.available_interfaces:
            self._capture_control_center(context, nodes, evidence, warnings)
        if "perfmon" in self.available_interfaces:
            self._capture_perfmon(context, nodes, evidence, warnings)

        notes.append(
            "Diagnostic capture is raw, bounded discovery evidence; responses are not yet "
            "treated as normalized health facts."
        )
        notes.append(
            f"Diagnostic node scope: {len(nodes)} node(s). RISPort device cap: "
            f"{context.diagnostic_max_devices}."
        )
        return CollectionResult(
            collector_name=self.name,
            facts=facts,
            warnings=warnings,
            evidence=evidence,
            notes=notes,
            status_flags=status_flags,
        )

    def _capture_wsdls(
        self,
        context: CollectionContext,
        nodes: tuple[str, ...],
        evidence: list[EvidenceRef],
        warnings: list[str],
    ) -> None:
        definitions = []
        if "risport70" in self.available_interfaces:
            definitions.append(
                (
                    "risport70",
                    context.risport_port,
                    "/realtimeservice2/services/RISService70?wsdl",
                    "wsdl",
                )
            )
        if "control_center" in self.available_interfaces:
            definitions.extend(
                [
                    (
                        "control_center",
                        context.control_center_port,
                        "/controlcenterservice2/services/ControlCenterServices?wsdl",
                        "wsdl",
                    ),
                    (
                        "control_center_ex",
                        context.control_center_port,
                        "/controlcenterservice2/services/ControlCenterServicesEx?wsdl",
                        "wsdl",
                    ),
                ]
            )
        if "perfmon" in self.available_interfaces:
            definitions.append(
                (
                    "perfmon",
                    context.perfmon_port,
                    "/perfmonservice2/services/PerfmonService?wsdl",
                    "wsdl",
                )
            )

        for node in nodes:
            for interface, port, path, operation in definitions:
                endpoint = f"https://{node}:{port}{path}"
                try:
                    response = self.http_client.get(
                        endpoint,
                        context,
                        node=node,
                        interface=interface,
                        operation=operation,
                    )
                except CapturedHttpError as exc:
                    warnings.append(f"{interface} WSDL capture failed on {node}: {exc}")
                    continue
                evidence.append(
                    EvidenceRef(
                        source=interface.upper(),
                        operation="wsdl",
                        node=node,
                        artifact_path=response.response_artifact_path,
                        parser="raw_diagnostic_capture",
                        confidence="high",
                    )
                )

    def _capture_risport(
        self,
        context: CollectionContext,
        evidence: list[EvidenceRef],
        warnings: list[str],
    ) -> None:
        assert context.publisher_ip is not None
        device_names = context.discovered_device_names[: context.diagnostic_max_devices]
        if device_names:
            select_items = "".join(
                "<ast:item><ast:Item>"
                f"{escape(device_name)}"
                "</ast:Item></ast:item>"
                for device_name in device_names
            )
            operation = "selectCmDeviceExt"
        else:
            select_items = "<ast:item><ast:Item>*</ast:Item></ast:item>"
            operation = "selectCmDevice"
            warnings.append(
                "RISPort diagnostic capture is using a wildcard SelectCmDevice fallback "
                "because no AXL device names were available."
            )
        body = f"""<ast:{operation}>
          <ast:StateInfo></ast:StateInfo>
          <ast:CmSelectionCriteria>
            <ast:MaxReturnedDevices>{min(context.diagnostic_max_devices, 2000)}</ast:MaxReturnedDevices>
            <ast:DeviceClass>Any</ast:DeviceClass>
            <ast:Model>255</ast:Model>
            <ast:Status>Any</ast:Status>
            <ast:NodeName></ast:NodeName>
            <ast:SelectBy>Name</ast:SelectBy>
            <ast:SelectItems>{select_items}</ast:SelectItems>
            <ast:Protocol>Any</ast:Protocol>
            <ast:DownloadStatus>Any</ast:DownloadStatus>
          </ast:CmSelectionCriteria>
        </ast:{operation}>"""
        self._capture_soap(
            context,
            node=context.publisher_ip,
            endpoint=(
                f"https://{context.publisher_ip}:{context.risport_port}"
                "/realtimeservice2/services/RISService70"
            ),
            interface="risport70",
            operation=operation,
            body=body,
            evidence=evidence,
            warnings=warnings,
        )

    def _capture_control_center(
        self,
        context: CollectionContext,
        nodes: tuple[str, ...],
        evidence: list[EvidenceRef],
        warnings: list[str],
    ) -> None:
        operations = (
            (
                "getProductInformationList",
                "<ast:getProductInformationList><ast:ServiceInfo></ast:ServiceInfo>"
                "</ast:getProductInformationList>",
            ),
            (
                "soapGetServiceStatus",
                "<ast:soapGetServiceStatus><ast:ServiceStatus></ast:ServiceStatus>"
                "</ast:soapGetServiceStatus>",
            ),
        )
        for node in nodes:
            endpoint = (
                f"https://{node}:{context.control_center_port}"
                "/controlcenterservice2/services/ControlCenterServices"
            )
            for operation, body in operations:
                self._capture_soap(
                    context,
                    node=node,
                    endpoint=endpoint,
                    interface="control_center",
                    operation=operation,
                    body=body,
                    evidence=evidence,
                    warnings=warnings,
                )

    def _capture_perfmon(
        self,
        context: CollectionContext,
        nodes: tuple[str, ...],
        evidence: list[EvidenceRef],
        warnings: list[str],
    ) -> None:
        baseline_objects = ("Processor", "Memory", "Cisco CallManager")
        for node in nodes:
            escaped_node = escape(node)
            endpoint = (
                f"https://{node}:{context.perfmon_port}"
                "/perfmonservice2/services/PerfmonService"
            )
            self._capture_soap(
                context,
                node=node,
                endpoint=endpoint,
                interface="perfmon",
                operation="perfmonListCounter",
                body=(
                    "<ast:perfmonListCounter>"
                    f"<ast:Host>{escaped_node}</ast:Host>"
                    "</ast:perfmonListCounter>"
                ),
                evidence=evidence,
                warnings=warnings,
            )
            for object_name in baseline_objects:
                artifact_operation = "perfmonCollectCounterData_" + _safe_operation(object_name)
                body = (
                    "<ast:perfmonCollectCounterData>"
                    f"<ast:Host>{escaped_node}</ast:Host>"
                    f"<ast:Object>{object_name}</ast:Object>"
                    "</ast:perfmonCollectCounterData>"
                )
                self._capture_soap(
                    context,
                    node=node,
                    endpoint=endpoint,
                    interface="perfmon",
                    operation="perfmonCollectCounterData",
                    artifact_operation=artifact_operation,
                    body=body,
                    evidence=evidence,
                    warnings=warnings,
                )

    def _capture_soap(
        self,
        context: CollectionContext,
        *,
        node: str,
        endpoint: str,
        interface: str,
        operation: str,
        body: str,
        evidence: list[EvidenceRef],
        warnings: list[str],
        artifact_operation: str | None = None,
    ) -> None:
        request = SoapRequest(
            endpoint=endpoint,
            body=body,
            operation=operation,
            interface=interface,
            node=node,
            namespace=AST_NAMESPACE,
            namespace_prefix="ast",
            action=operation,
            artifact_operation=artifact_operation,
        )
        try:
            response = self.soap_client.send(request, context)
        except SoapTransportError as exc:
            warnings.append(f"{interface} {operation} failed on {node}: {exc}")
            return
        evidence.append(_soap_evidence(response, node))


def _soap_evidence(response: SoapResponse, node: str) -> EvidenceRef:
    return EvidenceRef(
        source=response.interface.upper(),
        operation=response.operation,
        node=node,
        artifact_path=response.response_artifact_path,
        parser="raw_diagnostic_capture",
        confidence="high",
    )


def _safe_operation(value: str) -> str:
    return "_".join(value.lower().split())
