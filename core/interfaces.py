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
    Main interface for deploying complete clusters with worker nodes.

    This is the primary interface that orchestrates network and compute
    resources to deploy the requested cluster configuration.
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
    def deploy_cluster(self) -> Dict[str, Any]:
        """
        Deploy a cluster with the configured number of worker nodes.

        Returns:
            Dictionary with deployment outputs
        """
        pass

    def register_ssh_keys(self, ssh_keys: List[str]) -> List[str]:
        """
        Register SSH public keys in the cloud provider.

        Override this method in provider implementations to register
        SSH keys in the provider's IAM/key management system.

        Args:
            ssh_keys: List of SSH public key strings to register

        Returns:
            List of registered key IDs
        """
        # Default implementation does nothing - provider must override
        return []

    def deploy(self) -> Dict[str, Any]:
        """
        Deploy the configured cluster.

        This method calls the deploy_cluster implementation.

        Returns:
            Dictionary with deployment outputs
        """
        return self.deploy_cluster()

