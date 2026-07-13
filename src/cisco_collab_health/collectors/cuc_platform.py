"""Read-only Unity Connection UCOS CLI collection."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Protocol

from cisco_collab_health.collectors.base import CollectionResult
from cisco_collab_health.models.facts import (
    AssessmentFacts,
    ClusterIdentity,
    CollaborationNode,
    PlatformCheckFact,
    ServiceStatusFact,
)
from cisco_collab_health.models.runtime import CollectionContext
from cisco_collab_health.transport.ssh import SshCommandResult, SshCommandTimeout, UcosSshSession

@dataclass(frozen=True)
class UcosCommand:
    """Declarative metadata for a bounded, read-only UCOS command."""

    command_id: str
    command: str
    timeout_seconds: int
    diagnostic_only: bool = True
    output_sensitive: bool = True


CUC_COMMAND_CATALOG = (
    UcosCommand("cuc.show_status", "show status", 30),
    UcosCommand("cuc.show_version_active", "show version active", 30),
    UcosCommand("cuc.show_version_inactive", "show version inactive", 30),
    UcosCommand("cuc.show_hardware", "show hardware", 30),
    UcosCommand("cuc.show_network_cluster", "show network cluster", 30),
    UcosCommand("cuc.show_network_eth0_detail", "show network eth0 detail", 30),
    UcosCommand("cuc.utils_diagnose_test", "utils diagnose test", 180),
    UcosCommand("cuc.utils_service_list", "utils service list", 120),
    UcosCommand("cuc.utils_core_active_list", "utils core active list", 120),
    UcosCommand("cuc.show_cluster_status", "show cuc cluster status", 30),
)
CUC_SAFE_CLI_COMMANDS = tuple(item.command for item in CUC_COMMAND_CATALOG)


class CliSession(Protocol):
    def __enter__(self) -> "CliSession": ...
    def __exit__(self, *_: object) -> None: ...
    def execute(
        self, command: str, *, timeout_seconds: int | None = None
    ) -> SshCommandResult: ...


class CucPlatformCollector:
    """Capture bounded, read-only UCOS health output over SSH."""

    name = "cuc_platform_cli"

    def __init__(
        self, session_factory: Callable[[CollectionContext], CliSession] | None = None
    ) -> None:
        self.session_factory = session_factory or UcosSshSession

    def collect(self, context: CollectionContext) -> CollectionResult:
        facts = AssessmentFacts()
        warnings: list[str] = []
        version: str | None = None
        publisher = context.publisher_ip or context.target
        if not publisher:
            return CollectionResult(self.name, facts, warnings=["CUC target is missing."])
        cluster_output = self._collect_cluster_listing(context, publisher, facts, warnings)
        for cluster_node in _cuc_cluster_nodes(cluster_output, target_id=context.target_id):
            facts.add_node(cluster_node)
        nodes = tuple(dict.fromkeys(context.discovered_nodes or tuple(
            item.address or item.name for item in facts.nodes
        ) or (publisher,)))
        for node in filter(None, nodes):
            node_version = self._collect_node(
                replace(context, target=node, publisher_ip=node), node, facts, warnings
            )
            if node == publisher and node_version:
                version = node_version
        if version:
            facts.cluster = ClusterIdentity(publisher, "Cisco Unity Connection", version)
        return CollectionResult(self.name, facts, warnings=warnings)

    def _collect_cluster_listing(
        self, context: CollectionContext, node: str, facts: AssessmentFacts, warnings: list[str]
    ) -> str:
        """Discover CUC members before collecting platform evidence from each member."""

        definition = next(item for item in CUC_COMMAND_CATALOG if item.command == "show network cluster")
        try:
            with self.session_factory(context) as session:
                result = session.execute(definition.command, timeout_seconds=definition.timeout_seconds)
        except Exception as exc:
            warnings.append(f"CUC SSH session failed on {node}: {exc}")
            return ""
        if context.artifact_store is not None:
            context.artifact_store.write_command_output(node, definition.command, result.output)
        facts.platform_checks.append(_cuc_check(node, definition, "collected", result.output, result.paged))
        return result.output

    def _collect_node(
        self, context: CollectionContext, node: str, facts: AssessmentFacts, warnings: list[str]
    ) -> str | None:
        version: str | None = None
        try:
            with self.session_factory(context) as session:
                for definition in CUC_COMMAND_CATALOG:
                    if definition.command == "show network cluster":
                        continue
                    try:
                        result = session.execute(definition.command, timeout_seconds=definition.timeout_seconds)
                    except SshCommandTimeout as exc:
                        if context.artifact_store is not None and exc.output:
                            context.artifact_store.write_command_output(node, definition.command, exc.output)
                        facts.platform_checks.append(_cuc_check(node, definition, "incomplete", exc.output, exc.paged, incomplete=True))
                        warnings.append(f"CUC CLI '{definition.command}' on {node} did not return to the prompt; retained {len(exc.output)} characters of partial output.")
                        continue
                    except Exception as exc:
                        warnings.append(f"CUC CLI '{definition.command}' on {node} failed: {exc}")
                        continue
                    if context.artifact_store is not None:
                        context.artifact_store.write_command_output(node, definition.command, result.output)
                    if definition.command == "show version active":
                        version = _cuc_version(result.output)
                    if definition.command == "utils service list":
                        facts.services.extend(_cuc_service_status(node, result.output))
                    facts.platform_checks.append(_cuc_check(node, definition, "collected", result.output, result.paged))
        except Exception as exc:
            warnings.append(f"CUC SSH session failed on {node}: {exc}")
        return version


def _cuc_check(
    node: str, definition: UcosCommand, status: str, output: str, paged: bool,
    *, incomplete: bool = False,
) -> PlatformCheckFact:
    return PlatformCheckFact(
        node=node, check_name=definition.command, status=status,
        details={
            "output_captured": str(bool(output)).lower(), "output_length": str(len(output)),
            "paged": str(paged).lower(), "completion": "prompt timeout" if incomplete else "complete",
            "command_id": definition.command_id, "timeout_seconds": str(definition.timeout_seconds),
            "diagnostic_only": str(definition.diagnostic_only).lower(),
            **_cuc_cli_summary(definition.command, output),
        }, source="CUC.UCOS.CLI",
    )


def _cuc_cli_summary(command: str, output: str) -> dict[str, str]:
    """Extract conservative health summaries while retaining the full CLI artifact."""

    if command == "utils diagnose test":
        return {
            "passed": str(len(re.findall(r"(?im)^test\s+-.*:\s*Passed", output))),
            "failed": str(len(re.findall(r"(?im)^test\s+-.*:\s*Failed", output))),
            "skipped": str(len(re.findall(r"(?im)^skip\s+-", output))),
        }
    if command == "utils service list":
        return {
            "started": str(len(re.findall(r"\[STARTED\]", output))),
            "stopped": str(len(re.findall(r"\[STOPPED\]", output))),
            "not_activated": str(output.count("Service Not Activated")),
        }
    if command == "show cuc cluster status":
        return {
            "primary_nodes": str(len(re.findall(r"\bPrimary\b", output))),
            "secondary_nodes": str(len(re.findall(r"\bSecondary\b", output))),
            "connected_peers": str(len(re.findall(r"\bConnected\b", output))),
            "unhealthy_states": str(len(re.findall(r"(?im)\b(?:failed|error|inactive)\b", output))),
        }
    if command == "utils core active list":
        return {"core_files": "0" if "No core files found" in output else "present"}
    if command == "show network eth0 detail":
        status = re.search(r"Status\s*:\s*(\w+)", output)
        duplicate = re.search(r"Duplicate IP\s*:\s*(\w+)", output)
        return {
            "link_status": status.group(1).lower() if status else "unknown",
            "duplicate_ip": duplicate.group(1).lower() if duplicate else "unknown",
        }
    if command == "show status":
        disk_usage = [
            int(match.group(1))
            for match in re.finditer(r"(?m)^Disk/\S+.*?\((\d+)%\)", output)
        ]
        uptime = re.search(r"\bup\s+(\d+)\s+days?", output, re.IGNORECASE)
        uptime_days = int(uptime.group(1)) if uptime else None
        return {
            "max_disk_usage_percent": str(max(disk_usage)) if disk_usage else "unknown",
            "disk_warning_count": str(sum(value >= 90 for value in disk_usage)),
            "disk_critical_count": str(sum(value >= 95 for value in disk_usage)),
            "uptime_days": str(uptime_days) if uptime_days is not None else "unknown",
        }
    return {}


def _cuc_service_status(node: str, output: str) -> list[ServiceStatusFact]:
    """Normalize UCOS service-list entries without treating inactive services as failures."""

    services: list[ServiceStatusFact] = []
    pattern = re.compile(r"(?m)^(?P<name>.+?)\[(?P<state>STARTED|STOPPED)\](?P<detail>.*)$")
    for match in pattern.finditer(output):
        detail = match.group("detail").strip()
        services.append(
            ServiceStatusFact(
                node=node,
                service_name=match.group("name").strip(),
                activated="service not activated" not in detail.lower(),
                status=match.group("state").title(),
                uptime_seconds=None,
                source="CUC.UCOS.CLI",
                reason=detail or None,
            )
        )
    return services


def _cuc_version(output: str) -> str | None:
    match = re.search(r"(?im)^Active Master Version:\s*(\S+)", output)
    return match.group(1) if match else None


def _cuc_cluster_nodes(output: str, *, target_id: str | None) -> list[CollaborationNode]:
    """Normalize the bounded UCOS cluster listing into shared report node facts."""

    nodes: list[CollaborationNode] = []
    pattern = re.compile(
        r"(?im)^(?P<address>\S+)\s+(?P<name>\S+)\s+\S+\s+"
        r"(?P<role>Publisher|Subscriber)\b"
    )
    for match in pattern.finditer(output):
        nodes.append(
            CollaborationNode(
                name=match.group("name"),
                address=match.group("address"),
                role=match.group("role").lower(),
                technology="cuc",
                target_id=target_id,
            )
        )
    return nodes
