"""Shared bounded UCOS CLI collector for technology-specific platform scaffolding."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from cisco_collab_health.collectors.base import CollectionResult
from cisco_collab_health.collectors.ssh_preflight import preflight_ssh_nodes
from cisco_collab_health.collectors.ucos_summary import disk_usage_summary, version_summary
from cisco_collab_health.models.facts import AssessmentFacts, ClusterIdentity, PlatformCheckFact, ServiceStatusFact
from cisco_collab_health.models.runtime import CollectionContext
from cisco_collab_health.transport.ssh import SshCommandResult, SshCommandTimeout, UcosSshSession


@dataclass(frozen=True)
class UcosPlatformCommand:
    """One read-only command with an explicit prompt-return timeout."""

    command_id: str
    command: str
    timeout_seconds: int


IM_PRESENCE_COMMAND_CATALOG = (
    UcosPlatformCommand("imp.show_status", "show status", 30),
    UcosPlatformCommand("imp.show_version_active", "show version active", 30),
    UcosPlatformCommand("imp.show_version_inactive", "show version inactive", 30),
    UcosPlatformCommand("imp.show_network_cluster", "show network cluster", 30),
    UcosPlatformCommand("imp.show_network_eth0_detail", "show network eth0 detail", 30),
    UcosPlatformCommand("imp.utils_ntp_status", "utils ntp status", 45),
    UcosPlatformCommand("imp.utils_service_list", "utils service list", 120),
    UcosPlatformCommand("imp.utils_core_active_list", "utils core active list", 120),
    UcosPlatformCommand("imp.utils_diagnose_test", "utils diagnose test", 300),
)

CER_COMMAND_CATALOG = (
    UcosPlatformCommand("cer.show_status", "show status", 30),
    UcosPlatformCommand("cer.show_version_active", "show version active", 30),
    UcosPlatformCommand("cer.show_version_inactive", "show version inactive", 30),
    UcosPlatformCommand("cer.show_network_cluster", "show network cluster", 30),
    UcosPlatformCommand("cer.show_network_eth0_detail", "show network eth0 detail", 30),
    UcosPlatformCommand("cer.utils_ntp_status", "utils ntp status", 45),
    UcosPlatformCommand("cer.utils_service_list", "utils service list", 120),
    UcosPlatformCommand("cer.utils_core_active_list", "utils core active list", 120),
    UcosPlatformCommand("cer.utils_diagnose_test", "utils diagnose test", 300),
)


class CliSession(Protocol):
    def __enter__(self) -> "CliSession": ...
    def __exit__(self, *_: object) -> None: ...
    def execute(self, command: str, *, timeout_seconds: int | None = None) -> SshCommandResult: ...


class UcosPlatformCollector:
    """Collect a bounded, publisher-only UCOS baseline for an emerging technology."""

    def __init__(
        self,
        *,
        technology: str,
        product_label: str,
        catalog: tuple[UcosPlatformCommand, ...],
        session_factory: Callable[[CollectionContext], CliSession] | None = None,
    ) -> None:
        self.technology = technology
        self.product_label = product_label
        self.catalog = catalog
        self.name = f"{technology}_platform_cli"
        self.session_factory = session_factory or UcosSshSession

    def collect(self, context: CollectionContext) -> CollectionResult:
        facts = AssessmentFacts()
        warnings: list[str] = []
        node = context.publisher_ip or context.target
        if not node:
            return CollectionResult(self.name, facts, warnings=["No publisher address configured for UCOS collection."])
        ready, preflight_warnings = preflight_ssh_nodes(context, [node], self.session_factory)
        warnings.extend(preflight_warnings)
        if not ready:
            return CollectionResult(self.name, facts, warnings=warnings)
        try:
            with self.session_factory(ready[0]) as session:
                for definition in self.catalog:
                    _progress(context, f"{self.technology.upper()} CLI {node}: running '{definition.command}' (up to {definition.timeout_seconds}s)")
                    try:
                        result = session.execute(definition.command, timeout_seconds=definition.timeout_seconds)
                    except SshCommandTimeout as exc:
                        _write_output(context, node, definition.command, exc.output)
                        facts.platform_checks.append(_check(node, definition, "incomplete", exc.output, self.technology))
                        warnings.append(f"{self.technology.upper()} CLI '{definition.command}' on {node} did not return to the prompt.")
                        continue
                    except Exception as exc:
                        warnings.append(f"{self.technology.upper()} CLI '{definition.command}' on {node} failed: {exc}")
                        continue
                    _write_output(context, node, definition.command, result.output)
                    facts.platform_checks.append(_check(node, definition, "collected", result.output, self.technology))
                    if definition.command == "show version active":
                        version = version_summary(result.output, active=True).get("active_version", "unknown")
                        facts.clusters.append(ClusterIdentity(node, self.product_label, version))
                    if definition.command == "utils service list":
                        facts.services.extend(_service_status(node, result.output, self.technology))
                    _progress(context, f"{self.technology.upper()} CLI {node}: completed '{definition.command}'")
        except Exception as exc:
            warnings.append(f"{self.technology.upper()} SSH session failed on {node}: {exc}")
        return CollectionResult(self.name, facts, warnings=warnings)


def _check(node: str, definition: UcosPlatformCommand, status: str, output: str, technology: str) -> PlatformCheckFact:
    summary = _summary(definition.command, output)
    return PlatformCheckFact(
        node=node,
        check_name=definition.command,
        status=status,
        details={
            "command_id": definition.command_id,
            "timeout_seconds": str(definition.timeout_seconds),
            "output_length": str(len(output)),
            "completion": "complete" if status == "collected" else "prompt timeout",
            **summary,
        },
        source=f"{technology.upper()}.UCOS.CLI",
    )


def _summary(command: str, output: str) -> dict[str, str]:
    if command == "show status":
        return disk_usage_summary(output)
    if command == "show version active":
        return version_summary(output, active=True)
    if command == "show version inactive":
        return version_summary(output, active=False)
    if command == "utils ntp status":
        match = re.search(r"synchroni[sz]ed to NTP server \(([^)]+)\) at stratum (\d+)", output, re.I)
        return {"synchronized": str(bool(match)).lower(), "server": match.group(1) if match else "unknown"}
    if command == "utils core active list":
        return {"core_files": "0" if "No core files found" in output else "present"}
    return {}


def _service_status(node: str, output: str, technology: str) -> list[ServiceStatusFact]:
    pattern = re.compile(r"(?m)^(?P<name>.+?)\[(?P<state>STARTED|STOPPED)\](?P<detail>.*)$")
    return [
        ServiceStatusFact(
            node=node,
            service_name=match.group("name").strip(),
            activated="service not activated" not in match.group("detail").lower(),
            status=match.group("state").title(),
            uptime_seconds=None,
            source=f"{technology.upper()}.UCOS.CLI",
            reason=match.group("detail").strip() or None,
        )
        for match in pattern.finditer(output)
    ]


def _write_output(context: CollectionContext, node: str, command: str, output: str) -> None:
    if context.artifact_store is not None:
        context.artifact_store.write_command_output(node, command, output)


def _progress(context: CollectionContext, message: str) -> None:
    if context.progress is not None:
        context.progress(message)
