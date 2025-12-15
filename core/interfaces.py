"""
Abstract interfaces for provider-agnostic infrastructure operations.

These abstract base classes define the contracts that each cloud provider
must implement to support the platform spawner.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from .models import ClusterConfig, NetworkOutput, NodeOutput


class NetworkInterface(ABC):
    """
    Abstract interface for network provisioning.
    
    Implementations must handle VPC/network creation, private networks,
    and NAT gateways appropriate for their cloud provider.
    """
    
    def __init__(self, config: ClusterConfig):
        """
        Initialize the network interface.
        
        Args:
            config: Cluster configuration
        """
        self.config = config
    
    @abstractmethod
    def create_vpc(self, name: str, **kwargs) -> Any:
        """
        Create a VPC or equivalent network container.
        
        Args:
            name: Name for the VPC
            **kwargs: Provider-specific parameters
            
        Returns:
            Provider-specific VPC resource
        """
        pass
    
    @abstractmethod
    def create_private_network(self, vpc_ref: Any, name: str, **kwargs) -> Any:
        """
        Create a private network within the VPC.
        
        Args:
            vpc_ref: Reference to the VPC resource
            name: Name for the private network
            **kwargs: Provider-specific parameters
            
        Returns:
            Provider-specific private network resource
        """
        pass
    
    @abstractmethod
    def create_gateway(self, network_ref: Any, **kwargs) -> Dict[str, Any]:
        """
        Create a NAT gateway for outbound internet access.
        
        Args:
            network_ref: Reference to the private network
            **kwargs: Provider-specific parameters
            
        Returns:
            Dictionary containing gateway resources
        """
        pass
    
    @abstractmethod
    def create_full_network(self) -> NetworkOutput:
        """
        Create complete network stack (VPC + Private Network + Gateway).
        
        Returns:
            NetworkOutput with all network resource information
        """
        pass


class ComputeInterface(ABC):
    """
    Abstract interface for compute resource provisioning.
    
    Implementations must handle instance creation, security groups,
    and OS image lookups for their cloud provider.
    """
    
    def __init__(self, config: ClusterConfig):
        """
        Initialize the compute interface.
        
        Args:
            config: Cluster configuration
        """
        self.config = config
    
    @abstractmethod
    def get_bastion_os_image(self) -> str:
        """
        Get the OS image for the bastion node.
        
        Uses the bastion OS configuration from ClusterConfig to get
        the appropriate marketplace image.
        
        Returns:
            Provider-specific image ID or label
        """
        pass
    
    @abstractmethod
    def get_worker_image(self) -> str:
        """
        Get the snapshot/image ID for worker nodes.
        
        Returns the worker snapshot ID from ClusterConfig.
        
        Returns:
            Provider-specific snapshot/image ID
        """
        pass
    
    @abstractmethod
    def create_security_group(
        self,
        name: str,
        rules: List[Dict[str, Any]],
        **kwargs
    ) -> Any:
        """
        Create a security group with specified rules.
        
        Args:
            name: Security group name
            rules: List of security rules
            **kwargs: Provider-specific parameters
            
        Returns:
            Provider-specific security group resource
        """
        pass
    
    @abstractmethod
    def create_instance(
        self,
        name: str,
        image: str,
        instance_type: str,
        security_group: Any,
        tags: List[str],
        **kwargs
    ) -> NodeOutput:
        """
        Create a compute instance.
        
        Args:
            name: Instance name
            image: Image ID
            instance_type: Instance type/size
            security_group: Security group resource
            tags: List of tags
            **kwargs: Provider-specific parameters
            
        Returns:
            NodeOutput with instance information
        """
        pass
    
    @abstractmethod
    def attach_to_private_network(
        self,
        instance: Any,
        network: Any,
        **kwargs
    ) -> Any:
        """
        Attach an instance to a private network.
        
        Args:
            instance: Instance resource
            network: Private network resource
            **kwargs: Provider-specific parameters
            
        Returns:
            Network interface resource
        """
        pass


class ClusterInterface(ABC):
    """
    Main interface for deploying complete cluster topologies.
    
    This is the primary interface that orchestrates network and compute
    resources to deploy the requested topology.
    """
    
    def __init__(self, config: ClusterConfig):
        """
        Initialize the cluster interface.
        
        Args:
            config: Cluster configuration
        """
        self.config = config
        self.network: Optional[NetworkInterface] = None
        self.compute: Optional[ComputeInterface] = None
    
    @abstractmethod
    def deploy_single_node(self) -> Dict[str, Any]:
        """
        Deploy a single-node topology.
        
        Returns:
            Dictionary with deployment outputs
        """
        pass
    
    @abstractmethod
    def deploy_three_node(self) -> Dict[str, Any]:
        """
        Deploy a 3-node cluster (bootstrap, bastion, slave).
        
        Returns:
            Dictionary with deployment outputs
        """
        pass
    
    @abstractmethod
    def deploy_six_node(self) -> Dict[str, Any]:
        """
        Deploy a 6-node cluster (bootstrap, bastion, 4 slaves).
        
        Returns:
            Dictionary with deployment outputs
        """
        pass
    
    def deploy(self) -> Dict[str, Any]:
        """
        Deploy the configured topology.
        
        This method routes to the appropriate deployment method based
        on the configured topology.
        
        Returns:
            Dictionary with deployment outputs
        """
        from .models import Topology
        
        if self.config.topology == Topology.SINGLE:
            return self.deploy_single_node()
        elif self.config.topology == Topology.THREE_NODE:
            return self.deploy_three_node()
        elif self.config.topology == Topology.SIX_NODE:
            return self.deploy_six_node()
        else:
            raise ValueError(f"Unknown topology: {self.config.topology}")

