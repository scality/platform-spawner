"""
Core abstractions for multi-cloud infrastructure deployment.

This package provides provider-agnostic interfaces and models for
deploying infrastructure across multiple cloud providers.
"""

from .models import (
    Topology,
    Provider,
    NodeConfig,
    NetworkConfig,
    ClusterConfig,
    NodeOutput,
    NetworkOutput
)
from .interfaces import (
    NetworkInterface,
    ComputeInterface,
    ClusterInterface
)
from .topology import get_topology_config
from .factory import create_cluster

__all__ = [
    "Topology",
    "Provider",
    "NodeConfig",
    "NetworkConfig",
    "ClusterConfig",
    "NodeOutput",
    "NetworkOutput",
    "NetworkInterface",
    "ComputeInterface",
    "ClusterInterface",
    "get_topology_config",
    "create_cluster",
]

