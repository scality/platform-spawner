"""
Scaleway network implementation.

This module handles VPC, Private Network, and Public Gateway creation
for Scaleway infrastructure, implementing the NetworkInterface.
"""

import pulumi
import pulumiverse_scaleway as scaleway
from typing import Any, Dict, List, Optional, Union
from core.interfaces import NetworkInterface
from core.models import ClusterConfig, NetworkOutput, RouteConfig


class ScalewayNetwork(NetworkInterface):
    """
    Scaleway-specific implementation of network provisioning.
    
    Handles creation of:
    - VPC (Virtual Private Cloud)
    - Private Networks (Layer 2 VLAN within region)
    - Public Gateways (NAT and DHCP services)
    - Gateway Networks (attachment of gateway to private network)
    - Custom Routes (for routing traffic to specific destinations via gateway)
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
        self,
        vpc_ref: scaleway.network.Vpc,
        name: str,
        **kwargs
    ) -> scaleway.network.PrivateNetwork:
        """
        Create a Private Network within the VPC.
        
        A Private Network is a Layer 2 VLAN that spans the entire region,
        allowing instances in different zones to communicate privately.
        
        Args:
            vpc_ref: VPC resource reference
            name: Private network name
            **kwargs: Additional Scaleway PrivateNetwork arguments
            
        Returns:
            Scaleway PrivateNetwork resource
        """
        tags = kwargs.get("tags", ["internal", "managed-by:pulumi"])
        
        self._private_network = scaleway.network.PrivateNetwork(
            f"pn-{name}",
            name=name,
            vpc_id=vpc_ref.id,
            project_id=self.config.project_id,
            region=self.config.region,
            tags=tags,
            # Configure the IPv4 subnet for this private network
            ipv4_subnet=scaleway.network.PrivateNetworkIpv4SubnetArgs(
                subnet=self.config.network.private_subnet,
            ),
            enable_default_route_propagation=True,
        )
        
        return self._private_network
    
    def create_gateway(
        self,
        network_ref: scaleway.network.PrivateNetwork,
        **kwargs
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
        gateway_type = kwargs.get("gateway_type", "VPC-GW-S")
        enable_bastion = kwargs.get("enable_bastion", True)  # Default to enabled
        allowed_ips = self.config.network.allowed_ips or ["0.0.0.0/0"]
        
        # Log IP restriction configuration
        if allowed_ips != ["0.0.0.0/0"]:
            pulumi.log.info(f"Gateway bastion access restricted to IPs: {', '.join(allowed_ips)}")
        else:
            pulumi.log.info("Gateway bastion access open to all IPs (0.0.0.0/0)")
        
        # 1. Allocate a public IP for the gateway
        self._gateway_ip = scaleway.network.PublicGatewayIp(
            "gateway-ip",
            project_id=self.config.project_id,
            zone=self.config.zone,
        )
        
        # 2. Create the Public Gateway appliance with SSH bastion enabled
        gateway_name = f"{self.config.product}-gateway" if self.config.product else "gateway"
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
            pulumi.log.info("Offline mode: NAT/masquerade disabled - instances will have no internet access")
        
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
            destination: CIDR block for the destination (e.g., "35.241.243.135/32")
            description: Human-readable description (e.g., "artifacts.scality.net")
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
        Create complete network stack (VPC + Private Network + Gateway).
        
        This is a convenience method that creates all network resources
        in the correct order based on the cluster configuration.
        
        Returns:
            NetworkOutput with all network resource information
        """
        if not self.config.network.enable_private_network:
            # No private network needed for single-node topology
            return NetworkOutput()
        
        # Create VPC
        vpc_name = f"{self.config.product}-vpc" if self.config.product else "vpc"
        vpc = self.create_vpc(
            name=vpc_name,
            tags=["managed-by:pulumi"]
        )
        
        # Create Private Network
        pn_name = f"{self.config.product}-internal" if self.config.product else "internal"
        private_network = self.create_private_network(
            vpc_ref=vpc,
            name=pn_name,
            tags=["internal", "managed-by:pulumi"]
        )
        
        # Create Gateway if needed
        gateway_resources = None
        if self.config.network.enable_gateway:
            gateway_resources = self.create_gateway(
                network_ref=private_network,
                enable_bastion=True,  # Enable built-in SSH bastion feature
            )
        
        # Create custom routes if configured (requires gateway)
        if gateway_resources and self.config.network.custom_routes:
            for i, route_config in enumerate(self.config.network.custom_routes):
                # Generate a safe name from the description or use index
                route_suffix = route_config.description.replace(".", "-").replace(" ", "-") if route_config.description else f"custom-{i}"
                route_name = f"{self.config.product}-{route_suffix}" if self.config.product else route_suffix
                
                # Log the private network ID being passed
                private_network.id.apply(lambda pn_id: pulumi.log.info(f"Creating route linked with private_network_id={pn_id}"))
                
                self.create_route(
                    name=route_name,
                    destination=route_config.destination,
                    description=route_config.description,
                    private_network_id=private_network.id,
                )
                pulumi.log.info(f"Created route for {route_config.destination} ({route_config.description})")
        
        # Build output
        output = NetworkOutput(
            vpc_id=vpc.id,
            private_network_id=private_network.id,
            subnet=self.config.network.private_subnet,
        )
        
        if gateway_resources:
            output.gateway_id = gateway_resources["gateway"].id
            output.gateway_ip = gateway_resources["gateway_ip"].address
        
        return output
    
    @property
    def vpc(self) -> Optional[scaleway.network.Vpc]:
        """Get the created VPC resource."""
        return self._vpc
    
    @property
    def private_network(self) -> Optional[scaleway.network.PrivateNetwork]:
        """Get the created private network resource."""
        return self._private_network
    
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

