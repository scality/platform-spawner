"""Base class for all providers."""

import dataclasses
from abc import ABC, abstractmethod
from enum import StrEnum

import pulumi

IMAGE_UPLOAD_UNSUPPORTED = "The {provider} provider cannot upload an image file."


class InstanceFlavor(StrEnum):
    """
    Flavor of an Instance, in the sizes every provider can offer.

    A provider translates these into whatever its catalog calls them, and
    lets any other value through untouched, so that a flavor it has never
    heard of can still be asked for by name.
    """

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    XLARGE = "xlarge"


@dataclasses.dataclass(frozen=True)
class Network:
    """
    A network, in a form that is common to every provider.

    `resource` is the underlying network when the provider has such an object
    to group the subnets under. Some providers have none and build everything
    at the subnet level, in which case only the address space is carried.
    """

    cidr: str
    resource: pulumi.CustomResource | None = None


@dataclasses.dataclass(frozen=True)
class Interface:
    """A network interface, in a form that is common to every provider."""

    resource: pulumi.CustomResource
    ip: pulumi.Output[str]
    public_ip: pulumi.Output[str] | None = None


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
        flavor: InstanceFlavor | str,
        key_name: pulumi.Input[str],
        root_disk_size: int,
        interfaces: list[Interface],
        extra_volumes: list[dict] | None = None,
        disable_auto_stop: bool = False,
    ) -> pulumi.CustomResource:
        """
        Create and return a new instance.

        This method must be implemented by subclasses.
        """

    def create_image(
        self,
        name: str,
        file_path: str,
        file_format: str,
    ) -> str:
        """
        Upload an image file to the cloud and return the name it took.

        NOTE: Not abstract on purpose. Uploading an image is something only
        some clouds make cheap, and a provider has nothing to write here until
        someone needs the capability on it.
        """
        del name, file_path, file_format

        message = IMAGE_UPLOAD_UNSUPPORTED.format(provider=self.provider_name)
        raise NotImplementedError(message)

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
    ) -> Network:
        """
        Create and return a new network.

        This method must be implemented by subclasses.
        """

    @abstractmethod
    def create_subnet(
        self,
        name: str,
        network: Network,
        cidr: str,
        routed: bool = False,
        gateway_to_internet: bool = False,
        gateway_to_net: pulumi.Resource | None = None,
    ) -> pulumi.Resource:
        """
        Create and return a new subnet.

        `routed` tells whether the subnet sits behind a router at all, while
        the two gateway arguments tell whether that router has a way out. They
        are separate because a subnet can be routed and yet reach nothing,
        which is what an offline platform looks like.

        This method must be implemented by subclasses.
        """

    @abstractmethod
    def create_security_group(
        self,
        name: str,
        network: Network,
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
    ) -> Interface:
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
