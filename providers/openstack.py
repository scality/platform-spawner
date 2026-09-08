"""OpenStack Spawner for managing Nova instances."""

import functools
import inspect
import ipaddress

import pulumi
import pulumi_openstack
import yaml

from providers import base

# NOTE: Flavor names are not standardized across OpenStack clouds, those ones
# come from the OVH Public Cloud catalog and are matched on the AWS t3 sizes.
# The local disk a flavor comes with is the root disk, see create_instance, so
# picking a flavor also picks how big the root disk is.
#
#   small    d2-2    1 vCPU,   2 GB RAM,   25 GB disk
#   medium   d2-4    2 vCPU,   4 GB RAM,   50 GB disk
#   large    b3-8    2 vCPU,   8 GB RAM,   50 GB disk
#   xlarge   b3-32   8 vCPU,  32 GB RAM,  200 GB disk
_instance_flavor_matching = {
    base.InstanceFlavor.SMALL: "d2-2",
    base.InstanceFlavor.MEDIUM: "d2-4",
    base.InstanceFlavor.LARGE: "b3-8",
    base.InstanceFlavor.XLARGE: "b3-32",
}

# Aliases for the images provided by the cloud itself, any other value is
# looked up in Glance as is, which is what the custom images rely on.
_known_images = {
    "rocky-8": "Rocky Linux 8",
    "rocky-9": "Rocky Linux 9",
}

ANY_CIDR = "0.0.0.0/0"
# NOTE: The provider waits half an hour for an instance to come up, where the
# AWS one waits ten minutes. A machine that is not up by then is not coming,
# and the extra twenty minutes only delay the failure.
INSTANCE_TIMEOUT = "10m"
# What OpenStack takes for a single tag, on a Nova server as on a Neutron
# resource. A name long enough to overflow it would be dropped server side.
MAX_TAG_LENGTH = 60
TAG_SHORTENED = "The tag {tag!r} is {length} characters, cut to the {limit} OpenStack takes."

# cloud-init only reads the payload as cloud-config when it opens with this
CLOUD_CONFIG_HEADER = "#cloud-config"

UNKNOWN_RESOURCE = "Cannot introspect {type_}, the layout of the OpenStack SDK changed."


def _shortened_tags(tags: list[str]) -> list[str]:
    """
    Return the tags, cut to what the cloud takes.

    NOTE: Cut rather than refused. A tag is there to find a platform by, not
    to run it, so losing the tail of one is no reason to turn a spawn away.
    It is said out loud though, or a name that no longer tells platforms
    apart would go unnoticed.
    """
    fitting = []
    for tag in tags:
        if len(tag) > MAX_TAG_LENGTH:
            _warn_once(TAG_SHORTENED.format(tag=tag, length=len(tag), limit=MAX_TAG_LENGTH))
        fitting.append(tag[:MAX_TAG_LENGTH])

    return fitting


@functools.cache
def _warn_once(message: str) -> None:
    """
    Say something once, however many resources run into it.

    NOTE: Every resource of a platform carries the same tags, so what is
    wrong with one of them is wrong forty times over.
    """
    pulumi.log.warn(message)


@functools.cache
def _supported_properties(type_: str) -> frozenset[str]:
    """
    Return the input properties an OpenStack resource type accepts.

    A resource type token such as `openstack:networking/subnet:Subnet` maps to
    the `pulumi_openstack.networking.SubnetArgs` class, whose signature tells
    us which properties the resource supports. Anything that is not an
    OpenStack resource gets an empty set and is left alone.

    NOTE: This reports the Python names while a transform receives the wire
    names, so only look up properties spelled the same in both.
    """
    provider, _, rest = type_.partition(":")
    if provider != "openstack":
        return frozenset()

    module_path, _, class_name = rest.partition(":")
    module = getattr(pulumi_openstack, module_path.split("/")[0], None)
    args_class = getattr(module, f"{class_name}Args", None)
    if args_class is None:
        message = UNKNOWN_RESOURCE.format(type_=type_)
        raise RuntimeError(message)

    parameters = inspect.signature(args_class.__init__).parameters
    return frozenset(parameters) - {"self", "__self__"}


class OpenStackProvider(base.BaseProvider):
    """OpenStack implementation of BaseProvider using Nova instances."""

    provider_name = "openstack"

    def __init__(self) -> None:
        """Initialize the OpenStack provider."""
        super().__init__()

        config = pulumi.Config()
        self.external_network = config.require("openstack_external_network")
        self.dns_nameservers = config.require_object("openstack_dns_nameservers")

        self._external_network_id: pulumi.Output[str] | None = None
        self._router_interfaces: list[pulumi_openstack.networking.RouterInterface] = []

        pulumi.runtime.register_resource_transform(self._transform_add_common_metadata)

    def create_instance(
        self,
        name: str,
        image_name: str,
        flavor: base.InstanceFlavor,
        key_name: pulumi.Input[str],
        root_disk_size: int,  # noqa: ARG002
        interfaces: list[base.Interface],
        extra_volumes: list[dict] | None = None,
        disable_auto_stop: bool = False,
    ) -> pulumi_openstack.compute.Instance:
        """
        Create a new Nova instance.

        NOTE: `root_disk_size` is unused, the instance boots on the local disk
        the flavor comes with and the catalog fixes its size. Sizing it freely
        would mean booting from a Block Storage volume, which the flavor's
        local disk gets billed on top of rather than instead of.
        """
        image = self._get_image(image_name)

        metadata = {
            "node": name,
        }
        if disable_auto_stop:
            metadata["lifecycle_autostop"] = "no"

        instance = pulumi_openstack.compute.Instance(
            name,
            flavor_name=_instance_flavor_matching[flavor],
            image_id=image.id,
            key_pair=key_name,
            # NOTE: The security groups are held by the ports, setting them
            # here as well would apply them to every interface.
            networks=[
                pulumi_openstack.compute.InstanceNetworkArgs(port=iface.resource.id)
                for iface in interfaces
            ],
            metadata=metadata,
            user_data=self._cloud_config(),
            opts=pulumi.ResourceOptions(
                custom_timeouts=pulumi.CustomTimeouts(
                    create=INSTANCE_TIMEOUT,
                    update=INSTANCE_TIMEOUT,
                ),
            ),
        )

        volume_index = 1
        attached = None
        for vol in extra_volumes or []:
            for _ in range(vol.get("count", 1)):
                volume_name = f"{name}-extra-volume-{volume_index}"
                volume = pulumi_openstack.blockstorage.Volume(
                    volume_name,
                    size=vol["size"],
                )
                # NOTE: The device is left to the hypervisor. Asking for one it
                # does not honour makes the attachment drift on every refresh,
                # detaching and reattaching the volume indefinitely.
                #
                # One after another, each waiting on the last. An instance
                # takes its volumes one at a time whatever is asked of it, so
                # handing it a dozen at once only stacks them behind one
                # another while every one of them counts the same ten minutes:
                # the last of the queue runs out of them waiting for its turn.
                attached = pulumi_openstack.compute.VolumeAttach(
                    volume_name,
                    instance_id=instance.id,
                    volume_id=volume.id,
                    opts=pulumi.ResourceOptions(depends_on=[attached] if attached else None),
                )
                volume_index += 1

        return instance

    def create_key_pair(
        self,
        name: str,
        public_key: pulumi.Input[str],
    ) -> pulumi.Output[str]:
        """Create a new key pair and return its name."""
        return pulumi_openstack.compute.Keypair(
            name,
            public_key=public_key,
            name=self.compute_resource_name(name),
        ).name

    def create_network(
        self,
        name: str,  # noqa: ARG002
        cidr: str,
    ) -> base.Network:
        """
        Return the address space of the platform, with nothing to create.

        NOTE: Neutron has no object grouping subnets together, see
        create_subnet, so there is nothing to build at this level.
        """
        return base.Network(cidr=cidr)

    def create_subnet(
        self,
        name: str,
        network: base.Network,  # noqa: ARG002
        cidr: str,
        routed: bool = False,
        gateway_to_internet: bool = False,
        gateway_to_net: pulumi_openstack.networking.Subnet | None = None,
    ) -> pulumi_openstack.networking.Subnet:
        """
        Create and return a new subnet, along with the network holding it.

        NOTE: A Neutron network is a broadcast domain where an AWS VPC is a
        routing one. Several subnets under a single network would sit on the
        same wire and reach each other without ever crossing the router, so
        each subnet gets a network of its own and the router is what joins
        them. This makes `network` useless here.
        """
        subnet_network = pulumi_openstack.networking.Network(name)

        # NOTE: Neutron reserves a gateway address on every subnet and its DHCP
        # agent advertises it as a default route, whether or not a router
        # answers at that address. Only the routed subnets get to hand one out,
        # and they keep it whether or not a router is plugged in at the time.
        #
        # The address is spelled out rather than left to Neutron because
        # turning `no_gateway` back off does not make it hand one out again,
        # and a subnet without a gateway cannot join a router.
        #
        # The allocation pool has to be spelled out for the same reason: a
        # subnet born without a gateway hands its first address to the pool,
        # and that address is the one a gateway would need later on.
        addresses = ipaddress.ip_network(cidr)
        gateway = addresses.network_address + 1

        subnet = pulumi_openstack.networking.Subnet(
            name,
            network_id=subnet_network.id,
            cidr=cidr,
            gateway_ip=str(gateway) if routed else None,
            no_gateway=None if routed else True,
            allocation_pools=[
                pulumi_openstack.networking.SubnetAllocationPoolArgs(
                    start=str(gateway + 1),
                    end=str(addresses.broadcast_address - 1),
                )
            ],
            # NOTE: Left empty, Neutron hands out the DHCP agent itself as the
            # resolver. Whether that agent forwards queries upstream is up to
            # the operator, and OVH does not, so the instances would end up
            # with a resolver that answers nothing.
            dns_nameservers=self.dns_nameservers,
        )

        if gateway_to_internet or gateway_to_net is not None:
            # NOTE: Every subnet reaching out gets a router of its own rather
            # than sharing one. A router routes between everything it is
            # plugged into, so a shared one would carry traffic from a subnet
            # to another behind the back of the interfaces meant to carry it,
            # and taking an interface down would not cut anything off.
            #
            # The router and its interface are what `offline` adds and
            # removes. The subnet itself never changes, which is what keeps
            # the switch from disturbing a single instance: a gateway cannot
            # be taken off a subnet while a router still holds the address,
            # and Pulumi runs its deletions last.
            router = pulumi_openstack.networking.Router(
                name,
                external_network_id=self._get_external_network_id(),
            )
            self._router_interfaces.append(
                pulumi_openstack.networking.RouterInterface(
                    name,
                    router_id=router.id,
                    subnet_id=subnet.id,
                )
            )

        return subnet

    def create_security_group(
        self,
        name: str,
        network: base.Network,  # noqa: ARG002
        ingress_tcp_ports: list[int] | None = None,
        ingress_udp_ports: list[int] | None = None,
        ingress_icmp: bool = False,
        ingress_cidrs: list[str] | None = None,
        open_egress: bool = False,
        internal_traffic: bool = False,
    ) -> pulumi_openstack.networking.SecGroup:
        """
        Create a new security group.

        NOTE: OpenStack security groups are not bound to a network, so
        `network` is unused here.
        """
        if ingress_cidrs is None:
            ingress_cidrs = [ANY_CIDR]

        # NOTE: OpenStack fills every new security group with a pair of allow
        # all egress rules. Drop them so the rules below are the only ones,
        # which is what a freshly created AWS security group looks like.
        sec_group = pulumi_openstack.networking.SecGroup(
            name,
            delete_default_rules=True,
        )

        for protocol, ports in {
            "tcp": ingress_tcp_ports,
            "udp": ingress_udp_ports,
        }.items():
            for port in ports or []:
                for cidr in ingress_cidrs:
                    cidr_name = cidr if isinstance(cidr, str) else "my_ip"
                    pulumi_openstack.networking.SecGroupRule(
                        f"{name}-allow-{protocol}-{port}-{cidr_name}",
                        security_group_id=sec_group.id,
                        direction="ingress",
                        ethertype="IPv4",
                        protocol=protocol,
                        port_range_min=port,
                        port_range_max=port,
                        remote_ip_prefix=cidr,
                    )

        if ingress_icmp:
            for cidr in ingress_cidrs:
                cidr_name = cidr if isinstance(cidr, str) else "my_ip"
                pulumi_openstack.networking.SecGroupRule(
                    f"{name}-allow-icmp-{cidr_name}",
                    security_group_id=sec_group.id,
                    direction="ingress",
                    ethertype="IPv4",
                    protocol="icmp",
                    remote_ip_prefix=cidr,
                )

        if open_egress:
            # NOTE: Leaving the protocol out means any protocol
            pulumi_openstack.networking.SecGroupRule(
                f"{name}-allow-egress",
                security_group_id=sec_group.id,
                direction="egress",
                ethertype="IPv4",
                remote_ip_prefix=ANY_CIDR,
            )

        if internal_traffic:
            pulumi_openstack.networking.SecGroupRule(
                f"{name}-allow-internal",
                security_group_id=sec_group.id,
                direction="ingress",
                ethertype="IPv4",
                remote_group_id=sec_group.id,
            )

        return sec_group

    def create_interface(
        self,
        subnet: pulumi_openstack.networking.Subnet,
        subnet_name: str,
        node_name: str,
        ip: str,
        security_groups: list[pulumi_openstack.networking.SecGroup] | None = None,
        public: bool = False,
    ) -> base.Interface:
        """Create a new network interface."""
        name = f"{node_name}-{subnet_name}"

        port = pulumi_openstack.networking.Port(
            name,
            network_id=subnet.network_id,
            fixed_ips=[
                pulumi_openstack.networking.PortFixedIpArgs(
                    subnet_id=subnet.id,
                    ip_address=ip,
                )
            ],
            security_group_ids=[sec_group.id for sec_group in security_groups or []],
            # NOTE: Stands for disabling the AWS source/destination check on
            # the private interfaces, so that a node can forward traffic it
            # is not the endpoint of.
            allowed_address_pairs=(
                []
                if public
                else [
                    pulumi_openstack.networking.PortAllowedAddressPairArgs(
                        ip_address=ANY_CIDR,
                    )
                ]
            ),
        )

        public_ip = None
        if public:
            public_ip = pulumi_openstack.networking.FloatingIp(
                name,
                pool=self.external_network,
                port_id=port.id,
                # A floating IP is only routable once the subnet it points to
                # is plugged into the router
                opts=pulumi.ResourceOptions(depends_on=self._router_interfaces),
            ).address

        return base.Interface(
            resource=port,
            ip=port.all_fixed_ips[0],
            public_ip=public_ip,
        )

    def _get_external_network_id(self) -> pulumi.Output[str]:
        """Resolve the external network once, then hand the same id around."""
        if self._external_network_id is None:
            self._external_network_id = pulumi_openstack.networking.get_network(
                name=self.external_network,
            ).id

        return self._external_network_id

    def _cloud_config(self) -> str:
        """
        Render the cloud-init configuration handed to every instance.

        NOTE: The images OVH publishes carry the `/etc/resolv.conf` of the
        machine they were built on, whose resolver does not exist here.
        Nothing rewrites that file as a whole at boot, so the stale nameserver
        stays first and every lookup waits for it to time out. We write the
        file ourselves, from the resolvers the subnets are already handed.

        The `resolv_conf` module would be the obvious tool for the job, but
        those images do not enable it and it fails silently when asked. Hence
        `write_files`, deferred to the end of the boot so that whatever
        NetworkManager writes comes first. This is not a transitional
        workaround, we do not build those images.
        """
        resolv_conf = "\n".join(
            [
                f"# Written by {self.project} through cloud-init",
                *(f"nameserver {nameserver}" for nameserver in self.dns_nameservers),
                "",
            ]
        )

        config = {
            "write_files": [
                {
                    "path": "/etc/resolv.conf",
                    "defer": True,
                    "content": resolv_conf,
                }
            ]
        }

        return f"{CLOUD_CONFIG_HEADER}\n{yaml.safe_dump(config)}"

    def _get_image(self, image_name: str) -> pulumi_openstack.images.GetImageResult:
        """Retrieve the image for a given image name."""
        return pulumi_openstack.images.get_image(
            name=_known_images.get(image_name, image_name),
            most_recent=True,
        )

    def _transform_add_common_metadata(
        self,
        args: pulumi.ResourceTransformArgs,
    ) -> pulumi.ResourceTransformResult:
        """Transform function to name resources and add common metadata."""
        supported = _supported_properties(args.type_)
        common_metadata = {
            "stack": self.stack,
            "product": self.product,
            "spawner": self.project,
        }

        if "name" in supported and not args.props.get("name"):
            args.props["name"] = self.compute_resource_name(args.name)

        if "metadata" in supported:
            args.props["metadata"] = {
                **common_metadata,
                **(args.props.get("metadata") or {}),
            }

        # NOTE: A Nova instance carries both, and they are not interchangeable:
        # only the tags can be filtered on server side.
        if "tags" in supported:
            # NOTE: Neutron tags are a flat list of strings, not a mapping
            args.props["tags"] = _shortened_tags(
                [
                    *(f"{key}={value}" for key, value in common_metadata.items()),
                    *(args.props.get("tags") or []),
                ]
            )

        return pulumi.ResourceTransformResult(
            props=args.props,
            opts=args.opts,
        )
