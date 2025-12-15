"""
Scaleway network implementation.

This module handles VPC, Private Network, and Public Gateway creation
for Scaleway infrastructure, implementing the NetworkInterface.
"""

import pulumi
import pulumiverse_scaleway as scaleway
from typing import Any, Dict, Optional
from core.interfaces import NetworkInterface
from core.models import ClusterConfig, NetworkOutput


class ScalewayNetwork(NetworkInterface):
    """
    Scaleway-specific implementation of network provisioning.
    
    Handles creation of:
    - VPC (Virtual Private Cloud)
    - Private Networks (Layer 2 VLAN within region)
    - Public Gateways (NAT and DHCP services)
    - Gateway Networks (attachment of gateway to private network)
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
        tags = kwargs.get("tags", ["managed-by:pulumi", f"topology:{self.config.topology.value}"])
        
        self._vpc = scaleway.network.Vpc(
            f"vpc-{name}",
            name=name,
            region=self.config.region,
            project_id=self.config.project_id,
            tags=tags,
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
        )
        
        return self._private_network
    
    def create_gateway(
        self,
        network_ref: scaleway.network.PrivateNetwork,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a Public Gateway for NAT and DHCP services.
        
        The Public Gateway provides:
        - NAT/Masquerading for outbound internet access
        - DHCP server for IP assignment
        - Optional bastion/jump host functionality
        
        This method creates three resources:
        1. PublicGatewayIp - The public IP for the gateway
        2. PublicGateway - The gateway appliance
        3. GatewayNetwork - Attachment to the private network
        
        Args:
            network_ref: Private network to attach gateway to
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with gateway resources
        """
        gateway_type = kwargs.get("gateway_type", "VPC-GW-S")
        enable_bastion = kwargs.get("enable_bastion", False)
        
        # 1. Allocate a public IP for the gateway
        self._gateway_ip = scaleway.network.PublicGatewayIp(
            "gateway-ip",
            project_id=self.config.project_id,
            zone=self.config.zone,
        )
        
        # 2. Create the Public Gateway appliance
        self._gateway = scaleway.network.PublicGateway(
            "gateway",
            name=f"{self.config.topology.value}-gateway",
            type=gateway_type,
            ip_id=self._gateway_ip.id,
            bastion_enabled=enable_bastion,
            project_id=self.config.project_id,
            zone=self.config.zone,
            tags=["managed-by:pulumi", "service:nat-gateway"],
        )
        
        # 3. Attach the gateway to the private network with IPAM/DHCP
        # Note: Using ipam_configs (modern approach, not deprecated dhcp_id/enable_dhcp)
        self._gateway_network = scaleway.network.GatewayNetwork(
            "gateway-network",
            gateway_id=self._gateway.id,
            private_network_id=network_ref.id,
            ipam_configs=[
                scaleway.network.GatewayNetworkIpamConfigArgs(
                    push_default_route=False,  # Do NOT push route - breaks public SSH
                )
            ],
            enable_masquerade=True,  # Critical: enables NAT
            zone=self.config.zone,
        )
        
        return {
            "gateway": self._gateway,
            "gateway_ip": self._gateway_ip,
            "gateway_network": self._gateway_network,
        }
    
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
        vpc = self.create_vpc(
            name=f"{self.config.topology.value}-vpc",
            tags=[
                "managed-by:pulumi",
                f"topology:{self.config.topology.value}",
            ]
        )
        
        # Create Private Network
        private_network = self.create_private_network(
            vpc_ref=vpc,
            name=f"{self.config.topology.value}-internal",
            tags=["internal", "managed-by:pulumi"]
        )
        
        # Create Gateway if needed
        gateway_resources = None
        if self.config.network.enable_gateway:
            gateway_resources = self.create_gateway(
                network_ref=private_network,
                enable_bastion=False,  # We create our own bastion node
            )
        
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

