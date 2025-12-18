"""
Provider-agnostic data models for infrastructure configuration.

These dataclasses define the structure of configurations and outputs
that are shared across all cloud providers.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


@dataclass
class VolumeConfig:
    """
    Configuration for additional volumes to attach to nodes.
    
    Attributes:
        suffix: Identifier suffix for the volume (e.g., "service", "data")
        size: Volume size in GB
        count: Number of volumes to create with this configuration (default: 1)
    """
    suffix: str
    size: int
    count: int = 1


class Provider(Enum):
    """Supported cloud providers."""
    SCALEWAY = "scaleway"
    AWS = "aws"
    OVH = "ovh"


@dataclass
class NodeConfig:
    """
    Configuration for a single node/instance.
    
    Attributes:
        name: Unique identifier for the node
        role: Node role (bastion, node)
        instance_type: Provider-specific instance type
        has_public_ip: Whether the node should have a public IP
        has_private_ip: Whether the node should be on private network
        user_data: Cloud-init or startup script
        tags: List of tags for resource management
        storage_size_gb: Optional additional storage in GB
    """
    name: str
    role: str
    instance_type: str
    has_public_ip: bool = True
    has_private_ip: bool = False
    user_data: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    storage_size_gb: Optional[int] = None


@dataclass
class NetworkConfig:
    """
    Network configuration for the cluster.
    
    Attributes:
        enable_private_network: Whether to create a private network
        enable_gateway: Whether to create a NAT gateway
        private_subnet: CIDR block for private network
        dns_local_name: Local DNS domain name
    """
    enable_private_network: bool = False
    enable_gateway: bool = False
    private_subnet: str = "192.168.10.0/24"
    dns_local_name: str = "cluster.local"


@dataclass
class ClusterConfig:
    """
    Complete cluster configuration.
    
    Attributes:
        worker_count: Number of worker nodes to deploy
        provider: Cloud provider to use
        region: Provider region
        zone: Provider availability zone
        project_id: Provider project/account ID
        name_prefix: Prefix applied to all resource names (nodes, volumes, VPC, gateway, etc.)
        worker_snapshot_id: Custom snapshot/image ID for worker nodes (required)
        bastion_os_name: Operating system name for bastion node (marketplace image)
        bastion_os_version: Operating system version for bastion node
        ssh_key_ids: List of SSH key IDs to attach to instances (for CI/CD)
        network: Network configuration
        nodes: List of node configurations
        additional_volumes: List of additional volume configurations for worker nodes
    """
    worker_count: int
    provider: Provider
    region: str
    zone: str
    project_id: str
    name_prefix: str = ""
    worker_snapshot_id: Optional[str] = None
    bastion_os_name: str = "rockylinux"
    bastion_os_version: str = "9"
    ssh_key_ids: List[str] = field(default_factory=list)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    nodes: List[NodeConfig] = field(default_factory=list)
    additional_volumes: List[VolumeConfig] = field(default_factory=list)


@dataclass
class NodeOutput:
    """
    Output information for a deployed node.
    
    Attributes:
        id: Provider resource ID
        name: Node name
        public_ip: Public IP address (if any)
        private_ip: Private IP address (if any)
        resource: Provider-specific resource object
    """
    id: str
    name: str
    public_ip: Optional[str] = None
    private_ip: Optional[str] = None
    resource: Any = None


@dataclass
class NetworkOutput:
    """
    Output information for deployed network resources.
    
    Attributes:
        vpc_id: VPC/Network ID
        private_network_id: Private network ID
        gateway_id: Gateway ID (if any)
        gateway_ip: Gateway public IP (if any)
        subnet: Private subnet CIDR
    """
    vpc_id: Optional[str] = None
    private_network_id: Optional[str] = None
    gateway_id: Optional[str] = None
    gateway_ip: Optional[str] = None
    subnet: Optional[str] = None

