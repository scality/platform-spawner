"""
Provider-agnostic data models for infrastructure configuration.

These dataclasses define the structure of configurations and outputs
that are shared across all cloud providers.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any
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


@dataclass
class PrivateNetworkConfig:
    """
    Configuration for additional private network interfaces to attach to nodes.

    Each configuration creates a separate private network and attaches a NIC
    to each instance. This allows multi-homed instances with isolated network
    segments for different traffic types (e.g., management, data, storage).

    Attributes:
        suffix: Identifier suffix for the network (e.g., "data", "storage", "mgmt")
        subnet: CIDR block for the private network (e.g., "10.1.0.0/24")
        count: Number of NICs to create per instance (default: 1, typically 1)
    """

    suffix: str
    subnet: str
    count: int = 1


@dataclass
class RouteConfig:
    """
    Configuration for a custom VPC route.

    Attributes:
        destination: CIDR block for the route destination (e.g., "35.241.243.135/32")
        description: Human-readable description (e.g., "artifacts.scality.net")
    """

    destination: str
    description: str = ""


class Provider(Enum):
    """Supported cloud providers."""

    SCALEWAY = "scaleway"
    AWS = "aws"


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
        root_volume_size_gb: Root disk size in GB
    """

    name: str
    role: str
    instance_type: str
    has_public_ip: bool = True
    has_private_ip: bool = False
    user_data: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    storage_size_gb: Optional[int] = None
    root_volume_size_gb: Optional[int] = None


@dataclass
class NetworkConfig:
    """
    Network configuration for the cluster.

    Attributes:
        enable_private_network: Whether to create a private network
        enable_gateway: Whether to create a NAT gateway
        private_subnet: CIDR block for private network
        dns_local_name: Local DNS domain name
        allowed_ips: List of IPs/CIDRs allowed to access the gateway bastion
        custom_routes: List of custom VPC routes (traffic through gateway)
    """

    enable_private_network: bool = False
    enable_gateway: bool = False
    private_subnet: str = "192.168.10.0/24"
    dns_local_name: str = "cluster.local"
    allowed_ips: List[str] = field(default_factory=list)
    custom_routes: List[RouteConfig] = field(default_factory=list)


@dataclass
class ClusterConfig:
    """
    Complete cluster configuration.

    Attributes:
        instance_count: Number of instances to deploy
        provider: Cloud provider to use
        region: Provider region
        zone: Provider availability zone
        project_id: Provider project/account ID
        instance_image: Image for the instances (AMI name for AWS, snapshot ID for Scaleway)

        # Global values
        product: Product name for the resources
        name_prefix: Prefix applied to all resource names (nodes, volumes, VPC, gateway, etc.)

        # Network configs
        offline: If true, the platform will not be connected to the internet
        authorized_tcp_ports: List of authorized TCP ports for ingress to the instances
        authorized_udp_ports: List of authorized UDP ports for ingress to the instances
        authorized_icmp: Whether ICMP traffic is authorized for ingress to the instances
        authorized_cidrs: List of authorized CIDRs for the instances

        # Instance configs
        instance_flavor: Flavor of the instance (small/medium/large)
        instance_root_disk_size: Root disk size for the instance (in GiB)

        # Bastion host configuration
        bastion_image: Image for the bastion host (e.g., "rocky-9")
        bastion_flavor: Flavor of the bastion host
        bastion_root_disk_size: Root disk size for the bastion host (in GiB)

        # SSH information
        ssh_key_name: Name of an existing SSH key in the cloud provider to use (option 2)
        ssh_private_key_create: If true, generate a new SSH keypair and register in IAM (option 3)
        ssh_public_keys: List of SSH public keys to register in the cloud provider (option 3 & 4)

        # Lifecycle
        disable_auto_stop: If true, the instance will not be automatically stopped

        # Extra stuff
        extra_volumes: Additional volumes to attach to the instances
        extra_private_networks: Additional private networks to attach to the instances

        # Internal/computed fields
        network: Network configuration
        nodes: List of node configurations

        # Deprecated fields (kept for backward compatibility)
        bastion_os_name: Operating system name for bastion (derived from bastion_image)
        bastion_os_version: Operating system version for bastion (derived from bastion_image)
    """

    # Required fields
    instance_count: int
    provider: Provider
    region: str
    zone: str
    project_id: str
    instance_image: str

    # Global values
    product: str = "unknown"
    name_prefix: str = ""

    # Network configs
    offline: bool = False
    authorized_tcp_ports: List[int] = field(default_factory=lambda: [22])
    authorized_udp_ports: List[int] = field(default_factory=list)
    authorized_icmp: bool = True
    authorized_cidrs: List[str] = field(default_factory=list)

    # Instance configs
    instance_flavor: str = "medium"
    instance_root_disk_size: int = 50

    # Bastion host configuration
    bastion_image: str = "rocky-9"
    bastion_flavor: str = "small"
    bastion_root_disk_size: int = 30

    # SSH information
    ssh_key_name: str = ""
    ssh_private_key_create: bool = False
    ssh_public_keys: List[str] = field(default_factory=list)

    # Lifecycle
    disable_auto_stop: bool = False

    # Extra stuff
    extra_volumes: List[VolumeConfig] = field(default_factory=list)
    extra_private_networks: List[PrivateNetworkConfig] = field(default_factory=list)

    # Internal/computed fields
    network: NetworkConfig = field(default_factory=NetworkConfig)
    nodes: List[NodeConfig] = field(default_factory=list)

    # Deprecated fields (kept for backward compatibility, derived from bastion_image)
    bastion_os_name: str = "rockylinux"
    bastion_os_version: str = "9"


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
