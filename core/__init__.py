"""
Core abstractions for multi-cloud infrastructure deployment.

This package provides provider-agnostic interfaces and models for
deploying infrastructure across multiple cloud providers.
"""

from .models import (
    Provider,
    NodeConfig,
    NetworkConfig,
    ClusterConfig,
    NodeOutput,
    NetworkOutput,
    VolumeConfig,
    PrivateNetworkConfig,
)
from .interfaces import NetworkInterface, ComputeInterface, ClusterInterface
from .topology import get_cluster_config
from .factory import create_cluster

__all__ = [
    "Provider",
    "NodeConfig",
    "NetworkConfig",
    "ClusterConfig",
    "NodeOutput",
    "NetworkOutput",
    "VolumeConfig",
    "PrivateNetworkConfig",
    "NetworkInterface",
    "ComputeInterface",
    "ClusterInterface",
    "get_cluster_config",
    "create_cluster",
]
