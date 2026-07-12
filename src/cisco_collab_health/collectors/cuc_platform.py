"""Read-only Unity Connection UCOS CLI collection."""

from __future__ import annotations

from collections.abc import Callable

from cisco_collab_health.collectors.base import CollectionResult
from cisco_collab_health.models.facts import AssessmentFacts, PlatformCheckFact
from cisco_collab_health.models.runtime import CollectionContext

CUC_SAFE_CLI_COMMANDS = (
    "show status",
    "show version",
    "show network",
    "show memory",
    "show hardware",
    "utils service list",
)


class CucPlatformCollector:
    """Capture bounded, read-only UCOS health output over SSH."""

    name = "cuc_platform_cli"

    def __init__(self, executor: Callable[[CollectionContext, str], str] | None = None) -> None:
        self.executor = executor or _execute_ssh_command

    def collect(self, context: CollectionContext) -> CollectionResult:
        facts = AssessmentFacts()
        warnings: list[str] = []
        node = context.publisher_ip or context.target
        if not node:
            return CollectionResult(self.name, facts, warnings=["CUC target is missing."])
        for command in CUC_SAFE_CLI_COMMANDS:
            try:
                output = self.executor(context, command)
            except Exception as exc:
                warnings.append(f"CUC CLI '{command}' failed: {exc}")
                continue
            if context.artifact_store is not None:
                context.artifact_store.write_command_output(node, command, output)
            facts.platform_checks.append(
                PlatformCheckFact(
                    node=node,
                    check_name=command,
                    status="collected",
                    details={"output_captured": "true", "output_length": str(len(output))},
                    source="CUC.UCOS.CLI",
                )
            )
        return CollectionResult(self.name, facts, warnings=warnings)


def _execute_ssh_command(context: CollectionContext, command: str) -> str:
    """Execute one CLI command with the configured platform credentials."""

    try:
        import paramiko  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError("paramiko is required for CUC SSH collection") from exc
    host = context.publisher_ip or context.target
    if not host or not context.os_username or context.os_password is None:
        raise RuntimeError("CUC platform SSH credentials are unavailable")
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    try:
        client.connect(
            hostname=host,
            username=context.os_username,
            password=context.os_password,
            timeout=context.timeout_seconds,
            banner_timeout=context.timeout_seconds,
            auth_timeout=context.timeout_seconds,
            look_for_keys=False,
            allow_agent=False,
        )
        _stdin, stdout, stderr = client.exec_command(command, timeout=context.timeout_seconds)
        output = stdout.read().decode("utf-8", errors="replace")
        error_output = stderr.read().decode("utf-8", errors="replace")
        return output if not error_output.strip() else f"{output}\nSTDERR:\n{error_output}"
    finally:
        client.close()
