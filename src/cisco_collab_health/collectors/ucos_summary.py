"""Shared parsers for read-only UCOS platform command output."""

from __future__ import annotations

import re


def version_summary(output: str, *, active: bool) -> dict[str, str]:
    """Normalize a UCOS active/inactive version and installed software options."""

    state = "Active" if active else "Inactive"
    key = "active_version" if active else "inactive_version"
    match = re.search(rf"(?im)^{state} Master Version:\s*(\S+)", output)
    summary = {key: match.group(1) if match else "unknown"}
    if active:
        options_match = re.search(
            r"(?ims)^Active Version Installed Software Options:\s*(.*)$", output
        )
        option_text = options_match.group(1) if options_match else ""
        options = [
            line.strip()
            for line in option_text.splitlines()
            if line.strip() and "no installed software options found" not in line.lower()
        ]
        summary["installed_software_options"] = "|".join(options)
    return summary


def disk_usage_summary(output: str) -> dict[str, str]:
    """Extract explicit UCOS active and common/logging partition utilization."""

    partitions = {
        match.group("partition").lower(): int(match.group("usage"))
        for match in re.finditer(
            r"(?im)^Disk/(?P<partition>\S+).*?\((?P<usage>\d+)%\)", output
        )
    }
    values = list(partitions.values())
    summary = {
        "max_disk_usage_percent": str(max(values)) if values else "unknown",
        "active_partition_usage_percent": str(partitions.get("active", "unknown")),
        "common_partition_usage_percent": str(partitions.get("logging", "unknown")),
        "disk_warning_count": str(sum(value >= 90 for value in values)),
        "disk_critical_count": str(sum(value >= 95 for value in values)),
    }
    return summary
