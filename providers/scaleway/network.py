"""
Scaleway network implementation.

This module handles VPC, Private Network, and Public Gateway creation
for Scaleway infrastructure, implementing the NetworkInterface.
"""

import ipaddress
from typing import Any, Dict, List, Optional, Union

import pulumi
import pulumiverse_scaleway as scaleway

from core.interfaces import NetworkInterface
from core.models import ClusterConfig, NetworkOutput


def compute_static_ip(subnet_cidr: str, role: str, node_index: int = 0) -> str:
    """Compute a deterministic IP address for a node within a subnet.

    Addressing scheme:
        - bastion: x.y.z.2
        - node N:  x.y.z.(10 + N)  (e.g. node 1 -> .11, node 2 -> .12)

    Args:
        subnet_cidr: CIDR block (e.g. "192.168.10.0/24")
        role: "bastion" or "node"
        node_index: 1-based node index (ignored for bastion)

    Returns:
        IPv4 address string (e.g. "192.168.10.11")

    Raises:
        ValueError: If the computed address falls outside the subnet
    """
    network = ipaddress.ip_network(subnet_cidr, strict=False)
    base = int(network.network_address)
    host_offset = 2 if role == "bastion" else 10 + node_index
    addr = ipaddress.ip_address(base + host_offset)
    if addr not in network:
        raise ValueError(
            f"Computed IP {addr} is outside subnet {subnet_cidr} "
            f"(role={role}, node_index={node_index})"
        )
    return str(addr)


class ScalewayNetwork(NetworkInterface):
    """
    Scaleway-specific implementation of network provisioning.

    Handles creation of:
    - VPC (Virtual Private Cloud)
    - Private Networks (Layer 2 VLAN within region)
    - Extra Private Networks (for multi-homed instances)

    Note: Public Gateway is no longer used. NAT is handled by the bastion VM.
    Gateway code is preserved but disabled by default.
    """

    def __init__(self, config: ClusterConfig):
        """
        Initialize Scaleway network provider.

        Args:
            config: Cluster configuration
        """
        super().__init__(config)
        self._vpc: Optional[scaleway.network.Vpc] = None
        self._private_network: Optional[scaleway.network.PrivateNetwork] = None
        self._extra_private_networks: Dict[str, scaleway.network.PrivateNetwork] = {}
        self._gateway: Optional[scaleway.network.PublicGateway] = None
        self._gateway_ip: Optional[scaleway.network.PublicGatewayIp] = None
        self._gateway_network: Optional[scaleway.network.GatewayNetwork] = None
        self._routes: List[scaleway.network.Route] = []

    def create_vpc(self, name: str, **kwargs) -> scaleway.network.Vpc:
        """
        Create a Scaleway VPC.

        A VPC in Scaleway is a container for regional network resources.
        It provides isolation and organization for Private Networks.

        Args:
            name: VPC name
            **kwargs: Additional Scaleway VPC arguments

        Returns:
            Scaleway VPC resource
        """
        tags = kwargs.get("tags", ["managed-by:pulumi"])

        self._vpc = scaleway.network.Vpc(
            f"vpc-{name}",
            name=name,
            region=self.config.region,
            project_id=self.config.project_id,
            tags=tags,
            enable_routing=True,  # Required for custom routes
            enable_custom_routes_propagation=True,  # Advertise routes to all PNs
        )

        return self._vpc

    def create_private_network(
        self, vpc_ref: scaleway.network.Vpc, name: str, **kwargs
    ) -> scaleway.network.PrivateNetwork:
        """
        Create a Private Network within the VPC.

        A Private Network is a Layer 2 VLAN that spans the entire region,
        allowing instances in different zones to communicate privately.

        Args:
            vpc_ref: VPC resource reference
            name: Private network name
            **kwargs: Additional Scaleway PrivateNetwork arguments
                - subnet: CIDR block for the network (default: uses config.network.private_subnet)

        Returns:
            Scaleway PrivateNetwork resource
        """
        tags = kwargs.get("tags", ["internal", "managed-by:pulumi"])
        subnet = kwargs.get("subnet", self.config.network.private_subnet)

        self._private_network = scaleway.network.PrivateNetwork(
            f"pn-{name}",
            name=name,
            vpc_id=vpc_ref.id,
            project_id=self.config.project_id,
            region=self.config.region,
            tags=tags,
            # Configure the IPv4 subnet for this private network
            ipv4_subnet=scaleway.network.PrivateNetworkIpv4SubnetArgs(
                subnet=subnet,
            ),
            enable_default_route_propagation=True,
        )

        return self._private_network

    def create_extra_private_network(
        self,
        vpc_ref: scaleway.network.Vpc,
        name: str,
        suffix: str,
        subnet: str,
        **kwargs,
    ) -> scaleway.network.PrivateNetwork:
        """
        Create an extra Private Network within the VPC for multi-homed instances.

        Unlike the main private network, this creates additional isolated networks
        that can be attached to instances for different traffic types (e.g., data,
        storage, management).

        Args:
            vpc_ref: VPC resource reference
            name: Private network name
            suffix: Suffix identifier (used as key in _extra_private_networks dict)
            subnet: CIDR block for the network (e.g., "10.1.0.0/24")
            **kwargs: Additional Scaleway PrivateNetwork arguments

        Returns:
            Scaleway PrivateNetwork resource
        """
        tags = kwargs.get("tags", [f"extra-{suffix}", "managed-by:pulumi"])

        extra_network = scaleway.network.PrivateNetwork(
            f"pn-extra-{suffix}-{name}",
            name=name,
            vpc_id=vpc_ref.id,
            project_id=self.config.project_id,
            region=self.config.region,
            tags=tags,
            # Configure the IPv4 subnet for this extra private network
            ipv4_subnet=scaleway.network.PrivateNetworkIpv4SubnetArgs(
                subnet=subnet,
            ),
            enable_default_route_propagation=False,  # Extra networks don't need default route
        )

        # Store in dict by suffix for easy lookup
        self._extra_private_networks[suffix] = extra_network
        pulumi.log.info(f"Created extra private network '{name}' with subnet {subnet}")

        return extra_network

    def create_gateway(
        self, network_ref: scaleway.network.PrivateNetwork, **kwargs
    ) -> Dict[str, Any]:
        """
        Create a Public Gateway for NAT, DHCP, and SSH bastion services.

        The Public Gateway provides:
        - NAT/Masquerading for outbound internet access
        - DHCP server for IP assignment
        - SSH bastion/jump host functionality for accessing private instances
        - IP-based access control for SSH bastion (via allowed_ip_ranges)

        This method creates three resources:
        1. PublicGatewayIp - The public IP for the gateway
        2. PublicGateway - The gateway appliance with bastion enabled and IP restrictions
        3. GatewayNetwork - Attachment to the private network

        Args:
            network_ref: Private network to attach gateway to
            **kwargs: Additional parameters:
                - gateway_type: Gateway instance type (default: VPC-GW-S)
                - enable_bastion: Enable SSH bastion feature (default: True)

        Returns:
            Dictionary with gateway resources
        """
        gateway_type = kwargs.get("gateway_type", "VPC-GW-M")
        enable_bastion = kwargs.get("enable_bastion", True)  # Default to enabled
        allowed_ips = self.config.network.allowed_ips or ["0.0.0.0/0"]

        # Log IP restriction configuration
        if allowed_ips != ["0.0.0.0/0"]:
            pulumi.log.info(
                f"Gateway bastion access restricted to IPs: {', '.join(allowed_ips)}"
            )
        else:
            pulumi.log.info("Gateway bastion access open to all IPs (0.0.0.0/0)")

        # 1. Allocate a public IP for the gateway
        self._gateway_ip = scaleway.network.PublicGatewayIp(
            "gateway-ip",
            project_id=self.config.project_id,
            zone=self.config.zone,
        )

        # 2. Create the Public Gateway appliance with SSH bastion enabled
        gateway_name = (
            f"{self.config.product}-gateway" if self.config.product else "gateway"
        )
        self._gateway = scaleway.network.PublicGateway(
            gateway_name,
            name=gateway_name,
            type=gateway_type,
            ip_id=self._gateway_ip.id,
            bastion_enabled=enable_bastion,  # Enable SSH bastion functionality
            bastion_port=61000,  # Non-standard SSH port for bastion
            allowed_ip_ranges=allowed_ips,  # IP-based access control for SSH bastion
            refresh_ssh_keys="always",  # Automatically refresh SSH keys from IAM
            project_id=self.config.project_id,
            zone=self.config.zone,
            tags=["managed-by:pulumi", "service:nat-gateway", "service:ssh-bastion"],
        )

        # 3. Attach the gateway to the private network with IPAM/DHCP
        # Note: Using ipam_configs (modern approach, not deprecated dhcp_id/enable_dhcp)
        # The subnet is configured on the PrivateNetwork itself, not here
        #
        # enable_masquerade controls NAT for outbound internet access:
        # - True (default): instances can reach internet via gateway NAT
        # - False (offline mode): instances have no internet access
        enable_nat = not self.config.offline
        if self.config.offline:
            pulumi.log.info(
                "Offline mode: NAT/masquerade disabled - no internet access"
            )

        self._gateway_network = scaleway.network.GatewayNetwork(
            "gateway-network",
            gateway_id=self._gateway.id,
            private_network_id=network_ref.id,
            ipam_configs=[
                scaleway.network.GatewayNetworkIpamConfigArgs(
                    push_default_route=False,  # Do NOT push route - breaks public SSH
                )
            ],
            enable_masquerade=enable_nat,  # Disabled in offline mode
            zone=self.config.zone,
        )

        return {
            "gateway": self._gateway,
            "gateway_ip": self._gateway_ip,
            "gateway_network": self._gateway_network,
        }

    def create_route(
        self,
        name: str,
        destination: str,
        private_network_id: Union[str, pulumi.Output[str]],
        description: Optional[str] = None,
    ) -> scaleway.network.Route:
        """
        Create a VPC route for a specific destination via the gateway.

        This allows private-only nodes to reach specific external hosts
        through the Public Gateway's NAT functionality.

        Args:
            name: Unique name for the route resource
            destination: CIDR block for the destination (e.g., "203.0.113.10/32")
            description: Human-readable description (e.g., "my-server")
            private_network_id: Optional private network ID to scope the route to.
                              If not provided, uses the GatewayNetwork's private_network_id

        Returns:
            Scaleway Route resource

        Raises:
            ValueError: If VPC, private network, or gateway network are not created yet
        """
        if not self._vpc:
            raise ValueError("VPC must be created before creating routes")
        if not self._private_network:
            raise ValueError("Private network must be created before creating routes")
        if not self._gateway_network:
            raise ValueError("Gateway network must be created before creating routes")
        if not self._gateway:
            raise ValueError("Gateway must be created before creating routes")

        # For Public Gateway routes, use the GatewayNetwork ID
        # GatewayNetwork is the connection resource (like PrivateNic for instances)
        # This is the correct nexthop_resource_id for gateway-based routes
        route = scaleway.network.Route(
            f"route-{name}",
            vpc_id=self._vpc.id,
            destination=destination,
            nexthop_resource_id=self._gateway_network.id,
            nexthop_private_network_id=private_network_id,
            description=description,
            region=self.config.region,
            tags=["managed-by:pulumi"],
            opts=pulumi.ResourceOptions(depends_on=[self._gateway_network]),
        )

        self._routes.append(route)
        return route

    def create_full_network(self) -> NetworkOutput:
        """
        Create complete network stack (VPC + Private Network + Extra Networks).

        This is a convenience method that creates all network resources
        in the correct order based on the cluster configuration.

        Note: Gateway is no longer created here. NAT is handled by the bastion VM.

        Returns:
            NetworkOutput with all network resource information
        """
        if not self.config.network.enable_private_network:
            # No private network needed for single-node topology
            return NetworkOutput()

        # Create VPC
        vpc_name = f"{self.config.product}-vpc" if self.config.product else "vpc"
        vpc = self.create_vpc(name=vpc_name, tags=["managed-by:pulumi"])

        # Create Primary Private Network
        pn_name = (
            f"{self.config.product}-internal" if self.config.product else "internal"
        )
        private_network = self.create_private_network(
            vpc_ref=vpc, name=pn_name, tags=["internal", "managed-by:pulumi"]
        )

        # Create Extra Private Networks if configured (for multi-homed instances)
        if self.config.extra_private_networks:
            count = len(self.config.extra_private_networks)
            pulumi.log.info(f"Creating {count} extra private network(s)")
            for net_config in self.config.extra_private_networks:
                # Generate network name with product prefix
                if self.config.product:
                    extra_pn_name = f"{self.config.product}-{net_config.suffix}"
                else:
                    extra_pn_name = net_config.suffix
                self.create_extra_private_network(
                    vpc_ref=vpc,
                    name=extra_pn_name,
                    suffix=net_config.suffix,
                    subnet=net_config.subnet,
                    tags=[f"extra-{net_config.suffix}", "managed-by:pulumi"],
                )

        # Note: Gateway is no longer created here.
        # NAT functionality is provided by the bastion VM instead.
        # The bastion VM is deployed in cluster.py with IP forwarding and iptables masquerading.

        # Build output
        output = NetworkOutput(
            vpc_id=vpc.id,
            private_network_id=private_network.id,
            subnet=self.config.network.private_subnet,
        )

        return output

    def create_ipam_ip(
        self,
        name: str,
        address: str,
        private_network: scaleway.network.PrivateNetwork,
    ) -> scaleway.ipam.Ip:
        """Book a static IPAM IP on a private network.

        Args:
            name: Unique resource name suffix
            address: IPv4 address to reserve (e.g. "192.168.10.2")
            private_network: Target private network resource

        Returns:
            scaleway.ipam.Ip resource
        """
        return scaleway.ipam.Ip(
            f"ipam-{name}",
            address=address,
            sources=[scaleway.ipam.IpSourceArgs(
                private_network_id=private_network.id,
            )],
            region=self.config.region,
            project_id=self.config.project_id,
            tags=["managed-by:pulumi"],
        )

    @property
    def vpc(self) -> Optional[scaleway.network.Vpc]:
        """Get the created VPC resource."""
        return self._vpc

    @property
    def private_network(self) -> Optional[scaleway.network.PrivateNetwork]:
        """Get the created primary private network resource."""
        return self._private_network

    @property
    def extra_private_networks(self) -> Dict[str, scaleway.network.PrivateNetwork]:
        """Get the created extra private networks by suffix."""
        return self._extra_private_networks

    @property
    def gateway(self) -> Optional[scaleway.network.PublicGateway]:
        """Get the created gateway resource."""
        return self._gateway

    @property
    def gateway_ip(self) -> Optional[scaleway.network.PublicGatewayIp]:
        """Get the gateway IP resource."""
        return self._gateway_ip

    @property
    def routes(self) -> List[scaleway.network.Route]:
        """Get the created route resources."""
        return self._routes
