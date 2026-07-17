"""Tests for bounded CUCM UCOS CLI summaries."""

from __future__ import annotations

import unittest

from cisco_collab_health.collectors.cucm_platform import CucmPlatformCollector, _summary
from cisco_collab_health.models.runtime import CollectionContext
from cisco_collab_health.transport.ssh import SshCommandResult


class CucmPlatformSummaryTests(unittest.TestCase):
    def test_ntp_and_replication_summaries(self) -> None:
        ntp = _summary(
            "utils ntp status",
            "synchronized to NTP server (10.0.0.10) at stratum 3\n^? bad-source",
        )
        replication = _summary(
            "utils dbreplication runtimestate",
            "pub 10.0.0.1 0.01 Y/Y/Y 0 (g_2) (2) Setup Completed\n"
            "sub 10.0.0.2 0.01 Y/Y/Y 0 (g_2) (1) Setup Failed",
        )

        self.assertEqual(ntp["synchronized"], "true")
        self.assertEqual(ntp["stratum"], "3")
        self.assertEqual(ntp["bad_sources"], "1")
        self.assertEqual(replication["replication_rows"], "2")
        self.assertEqual(replication["replication_bad_rows"], "1")

    def test_replication_summary_accepts_completed_subscriber_rows_without_status_code(self) -> None:
        replication = _summary(
            "utils dbreplication runtimestate",
            "pub 10.0.0.1 0.01 Y/Y/Y 0 (g_2) (2) Setup Completed\n"
            "sub-a 10.0.0.2 0.01 Y/Y/Y 0 (g_2) (-) Setup Completed\n"
            "sub-b 10.0.0.3 0.01 Y/Y/Y 0 (g_2) (2) Setup Completed",
        )

        self.assertEqual(replication["replication_rows"], "3")
        self.assertEqual(replication["replication_bad_rows"], "0")

    def test_version_and_partition_summaries_are_normalized(self) -> None:
        version = _summary(
            "show version active",
            "Active Master Version: 15.0.1.12900-234\n"
            "Active Version Installed Software Options:\nsecurity_patch.cop\nfeature.cop\n",
        )
        disk = _summary(
            "show status",
            "Disk/active 100K 5K 95K (5%)\nDisk/logging 100K 8K 92K (92%)\n",
        )

        self.assertEqual(version["active_version"], "15.0.1.12900-234")
        self.assertEqual(version["installed_software_options"], "security_patch.cop|feature.cop")
        self.assertEqual(disk["active_partition_usage_percent"], "5")
        self.assertEqual(disk["common_partition_usage_percent"], "92")

    def test_drs_history_summary_keeps_only_an_unambiguous_success_date(self) -> None:
        history = _summary(
            "utils disaster_recovery history backup",
            "2025-01-01 01:02:03 FAILED\n"
            "2025-01-03 04:05:06 SUCCESS\n",
        )

        self.assertEqual(history["successful_backup_entries"], "1")
        self.assertEqual(history["latest_successful_backup"], "2025-01-03")
        self.assertIn("latest_successful_backup_age_days", history)

    def test_collection_reuses_preflighted_node_context_without_opening_a_second_preflight_shell(self) -> None:
        opened: list[str] = []

        class FakeSession:
            def __init__(self, context: CollectionContext) -> None:
                self.context = context

            def __enter__(self) -> "FakeSession":
                opened.append(self.context.publisher_ip or "")
                return self

            def __exit__(self, *_: object) -> None:
                return None

            def execute(self, command: str, *, timeout_seconds: int | None = None) -> SshCommandResult:
                del timeout_seconds
                return SshCommandResult(command, "complete", False)

        preflighted = CollectionContext(publisher_ip="cucm-sub.example", target="cucm-sub.example")
        context = CollectionContext(
            publisher_ip="cucm-pub.example",
            discovered_nodes=("cucm-sub.example",),
            ssh_preflight_contexts={"cucm-sub.example": preflighted},
        )

        result = CucmPlatformCollector(FakeSession).collect(context)

        self.assertFalse(result.warnings)
        self.assertEqual(opened, ["cucm-sub.example"])
        self.assertEqual(len(result.facts.platform_checks), 9)
