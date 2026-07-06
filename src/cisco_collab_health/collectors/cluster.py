"""Cluster node discovery contracts."""

from __future__ import annotations

from typing import Protocol

from cisco_collab_health.models.facts import CollaborationNode
from cisco_collab_health.models.runtime import CollectionContext


class ClusterNodeDiscoveryCollector(Protocol):
    """Collector contract for discovering all nodes in a collaboration cluster."""

    name: str

    def discover_nodes(self, context: CollectionContext) -> list[CollaborationNode]:
        """Discover cluster nodes from the Publisher or another authoritative API source."""
