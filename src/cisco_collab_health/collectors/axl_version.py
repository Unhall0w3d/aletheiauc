"""Backward-compatible AXL version exports."""

from cisco_collab_health.collectors.axl.version import (
    AxlVersionPolicy,
    DEFAULT_AXL_VERSION,
    SUPPORTED_AXL_VERSIONS,
    is_incorrect_axl_version_response,
    response_summary,
    supported_axl_versions,
)

__all__ = [
    "AxlVersionPolicy",
    "DEFAULT_AXL_VERSION",
    "SUPPORTED_AXL_VERSIONS",
    "is_incorrect_axl_version_response",
    "response_summary",
    "supported_axl_versions",
]
