"""Tests for bounded Unity Connection UCOS CLI collection."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cisco_collab_health.artifacts import ArtifactStore
from cisco_collab_health.collectors.cuc_platform import (
    CUC_COMMAND_CATALOG,
    CUC_SAFE_CLI_COMMANDS,
    CucPlatformCollector,
    _cuc_cluster_nodes,
    _cuc_cli_summary,
    _cuc_service_status,
    _cuc_version,
)
from cisco_collab_health.models.runtime import CollectionContext
from cisco_collab_health.transport.ssh import SshCommandResult, SshCommandTimeout


class FakeSession:
    def __init__(self, context: CollectionContext, commands: list[str]) -> None:
        del context
        self.commands = commands

    def __enter__(self) -> "FakeSession":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, command: str, *, timeout_seconds: int | None = None) -> SshCommandResult:
        del timeout_seconds
        self.commands.append(command)
        return SshCommandResult(command, f"output for {command}")


class CucPlatformCollectorTests(unittest.TestCase):
    def test_command_catalog_has_unique_stable_ids_and_bounded_timeouts(self) -> None:
        self.assertEqual(len({item.command_id for item in CUC_COMMAND_CATALOG}), len(CUC_COMMAND_CATALOG))
        self.assertTrue(all(item.timeout_seconds > 0 for item in CUC_COMMAND_CATALOG))
        self.assertEqual(tuple(item.command for item in CUC_COMMAND_CATALOG), CUC_SAFE_CLI_COMMANDS)

    def test_cli_summaries_parse_diagnostics_services_and_core_state(self) -> None:
        self.assertEqual(
            _cuc_cli_summary("utils diagnose test", "test - a : Passed\nskip - b : later")["passed"],
            "1",
        )
        self.assertEqual(
            _cuc_cli_summary("utils service list", "A[STARTED]\nB[STOPPED]  Service Not Activated")["stopped"],
            "1",
        )
        self.assertEqual(_cuc_cli_summary("utils core active list", "No core files found")["core_files"], "0")
        status = _cuc_cli_summary(
            "show status",
            "21:08:27 up 328 days, 5:41\nDisk/active 10K 1K 9K (90%)\nDisk/logging 10K 1K 9K (95%)",
        )
        self.assertEqual(status["max_disk_usage_percent"], "95")
        self.assertEqual(status["disk_warning_count"], "2")
        self.assertEqual(status["disk_critical_count"], "1")
        self.assertEqual(status["uptime_days"], "328")
        self.assertEqual(_cuc_version("Active Master Version: 15.0.1.12900-43"), "15.0.1.12900-43")

    def test_service_list_normalizes_states_and_intentional_inactive_reason(self) -> None:
        services = _cuc_service_status(
            "cuc-pub",
            "A Cisco DB[STARTED]\nCisco DirSync[STOPPED] Service Not Activated",
        )

        self.assertEqual(services[0].status, "Started")
        self.assertTrue(services[0].activated)
        self.assertEqual(services[1].status, "Stopped")
        self.assertFalse(services[1].activated)

    def test_network_cluster_output_normalizes_cuc_members(self) -> None:
        nodes = _cuc_cluster_nodes(
            "\n".join(
                (
                    "10.51.200.9 YT-UCX-PUB.example.org YT-UCX-PUB Publisher connection DBPub authenticated",
                    "10.51.202.14 UCX-SUB.example.org UCX-SUB Subscriber connection DBSub authenticated",
                )
            ),
            target_id="cuc-example",
        )

        self.assertEqual(
            [(node.role, node.address) for node in nodes],
            [("publisher", "10.51.200.9"), ("subscriber", "10.51.202.14")],
        )
        self.assertTrue(all(node.technology == "cuc" for node in nodes))

    def test_collector_records_only_safe_commands_and_artifacts(self) -> None:
        commands: list[str] = []

        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts = ArtifactStore.create(Path(tmpdir), "cuc", None)
            result = CucPlatformCollector(
                session_factory=lambda context: FakeSession(context, commands)
            ).collect(CollectionContext(publisher_ip="192.0.2.20", artifact_store=artifacts))

            self.assertEqual(commands, list(CUC_SAFE_CLI_COMMANDS))
            self.assertEqual(len(result.facts.platform_checks), len(CUC_SAFE_CLI_COMMANDS))
            self.assertEqual(len(list(artifacts.root.rglob("*.txt"))), len(CUC_SAFE_CLI_COMMANDS))

    def test_collector_retains_partial_output_from_long_running_command(self) -> None:
        class PartialSession(FakeSession):
            def execute(
                self, command: str, *, timeout_seconds: int | None = None
            ) -> SshCommandResult:
                if command == "utils diagnose test":
                    self.commands.append(command)
                    if timeout_seconds != 180:
                        raise AssertionError("long-running timeout was not applied")
                    raise SshCommandTimeout("diagnostic output in progress", False)
                return super().execute(command, timeout_seconds=timeout_seconds)

        commands: list[str] = []
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts = ArtifactStore.create(Path(tmpdir), "cuc", None)
            result = CucPlatformCollector(
                session_factory=lambda context: PartialSession(context, commands)
            ).collect(CollectionContext(publisher_ip="192.0.2.20", artifact_store=artifacts))

            check = next(
                item
                for item in result.facts.platform_checks
                if item.check_name == "utils diagnose test"
            )
            self.assertEqual(check.status, "incomplete")
            self.assertEqual(check.details["output_length"], "29")
            self.assertIn("did not return to the prompt", result.warnings[0])
            self.assertIn(
                "diagnostic output in progress",
                (artifacts.root / "nodes" / "192.0.2.20" / "cli" / "utils_diagnose_test.txt").read_text(),
            )
