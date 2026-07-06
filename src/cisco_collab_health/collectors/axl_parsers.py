"""Backward-compatible AXL parser exports."""

from cisco_collab_health.collectors.axl.parsers import (
    DevicePoolRecord,
    cluster_name_from_nodes,
    find_first_text,
    parse_device_pools,
    parse_device_load_defaults,
    parse_phone_inventory,
    parse_process_nodes,
)

__all__ = [
    "DevicePoolRecord",
    "cluster_name_from_nodes",
    "find_first_text",
    "parse_device_pools",
    "parse_device_load_defaults",
    "parse_phone_inventory",
    "parse_process_nodes",
]
