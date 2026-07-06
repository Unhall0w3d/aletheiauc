"""Collection interfaces and implementations."""

from cisco_collab_health.collectors.base import CollectionResult, Collector
from cisco_collab_health.collectors.cluster import ClusterNodeDiscoveryCollector
from cisco_collab_health.models.runtime import CollectionContext
from cisco_collab_health.transport.tls import TlsPolicy

__all__ = [
    "ClusterNodeDiscoveryCollector",
    "CollectionContext",
    "CollectionResult",
    "Collector",
    "TlsPolicy",
]
