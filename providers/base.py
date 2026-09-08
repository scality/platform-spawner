"""Base class for all providers."""

from abc import ABC, abstractmethod
from enum import StrEnum

import pulumi


class InstanceFlavor(StrEnum):
    """Flavor of an Instance."""

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    XLARGE = "xlarge"


class BaseProvider(ABC):
    """Abstract base class for providers that create instances."""

    provider_name = "none"

    def __init__(self) -> None:
        """Initialize the provider with the product name and configuration."""
        config = pulumi.Config()
        self.project = pulumi.get_project()
        self.stack = pulumi.get_stack()
        self.product = config.require("product")

    @abstractmethod
    def create_instance(
        self,
        name: str,
        image_name: str,
        flavor: InstanceFlavor,
        key_name: pulumi.Input[str],
        root_disk_size: int,
        interfaces: list[pulumi.Resource],
        extra_volumes: list[dict] | None = None,
        disable_auto_stop: bool = False,
    ) -> pulumi.Resource:
        """
        Create and return a new instance.

        This method must be implemented by subclasses.
        """

    @abstractmethod
    def create_key_pair(
        self,
        name: str,
        public_key: pulumi.Input[str],
    ) -> pulumi.Output[str]:
        """
        Create a new key pair and return its name.

        This method must be implemented by subclasses.
        """

    @abstractmethod
    def create_network(
        self,
        name: str,
        cidr: str,
    ) -> pulumi.Resource:
        """
        Create and return a new network.

        This method must be implemented by subclasses.
        """

    @abstractmethod
    def create_subnet(
        self,
        name: str,
        network: pulumi.Resource,
        cidr: str,
        gateway_to_internet: bool = False,
        gateway_to_net: pulumi.Resource | None = None,
    ) -> pulumi.Resource:
        """
        Create and return a new subnet.

        This method must be implemented by subclasses.
        """

    @abstractmethod
    def create_security_group(
        self,
        name: str,
        network: pulumi.Resource,
        ingress_tcp_ports: list[int] | None = None,
        ingress_udp_ports: list[int] | None = None,
        ingress_icmp: bool = False,
        ingress_cidrs: list[str] | None = None,
        open_egress: bool = False,
        internal_traffic: bool = False,
    ) -> pulumi.Resource:
        """
        Create and return a new security group.

        This method must be implemented by subclasses.
        """

    @abstractmethod
    def create_interface(
        self,
        subnet: pulumi.Resource,
        subnet_name: str,
        node_name: str,
        ip: str,
        security_groups: list[pulumi.Resource] | None = None,
        public: bool = False,
    ) -> pulumi.Resource:
        """
        Create and return a new network interface.

        This method must be implemented by subclasses.
        """

    def compute_resource_name(self, name: str = "") -> str:
        """Add the product and stack as a prefix to the resource name."""
        res = f"{self.product}_{self.stack}"
        if name:
            res += f"_{name}"
        return res
