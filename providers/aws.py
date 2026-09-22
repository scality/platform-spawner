"""AWS Spawner for managing EC2 instances."""

import pulumi
import pulumi_aws

from providers import base

_instance_flavor_matching = {
    base.InstanceFlavor.SMALL: pulumi_aws.ec2.InstanceType.T3_SMALL,
    base.InstanceFlavor.MEDIUM: pulumi_aws.ec2.InstanceType.T3_MEDIUM,
    base.InstanceFlavor.LARGE: pulumi_aws.ec2.InstanceType.T3_LARGE,
    base.InstanceFlavor.XLARGE: pulumi_aws.ec2.InstanceType.T3_2_X_LARGE,
}

_known_images = {
    "eu-north-1": {
        "rocky-9": "ami-0853aa90ccfad6064",
    },
    "us-west-2": {"rocky-9": "ami-03b6c12852a6ec38a"},
}

DEFAULT_DISK_TYPE = "gp3"


class AWSProvider(base.BaseProvider):
    """AWS implementation of BaseProvider using EC2 instances."""

    provider_name = "aws"

    _availability_zone = ""

    def __init__(self) -> None:
        """Initialize the AWS provider."""
        super().__init__()

        self.aws_config = pulumi.Config("aws")
        self.region = pulumi_aws.get_region().region

        pulumi.runtime.register_resource_transform(self._transform_add_common_tags)

    def create_instance(
        self,
        name: str,
        image_name: str,
        flavor: base.InstanceFlavor | str,
        key_name: pulumi.Input[str],
        root_disk_size: int,
        interfaces: list[base.Interface],
        extra_volumes: list[dict] | None = None,
        disable_auto_stop: bool = False,
        cloud_config: dict | None = None,
    ) -> pulumi_aws.ec2.Instance:
        """Create a new EC2 instance."""
        ami = self._get_ami(image_name)

        tags = {
            "node": name,
        }
        if disable_auto_stop:
            tags["lifecycle_autostop"] = "no"

        volumes = []
        device_id = 1
        for vol in extra_volumes or []:
            for _ in range(vol.get("count", 1)):
                volumes.append(
                    pulumi_aws.ec2.InstanceEbsBlockDeviceArgs(
                        device_name=f"/dev/sd{chr(ord('b') + device_id)}",
                        volume_size=vol["size"],
                        volume_type=DEFAULT_DISK_TYPE,
                    )
                )
                device_id += 1

        return pulumi_aws.ec2.Instance(
            name,
            instance_type=_instance_flavor_matching.get(flavor, flavor),
            ami=ami,
            key_name=key_name,
            root_block_device=pulumi_aws.ec2.InstanceRootBlockDeviceArgs(
                volume_size=root_disk_size,
                volume_type=DEFAULT_DISK_TYPE,
            ),
            network_interfaces=[
                pulumi_aws.ec2.InstanceNetworkInterfaceArgs(
                    network_interface_id=iface.resource.id,
                    device_index=index,
                )
                for index, iface in enumerate(interfaces)
            ],
            ebs_block_devices=volumes,
            user_data=(
                pulumi.Output.from_input(cloud_config).apply(base.render_cloud_config)
                if cloud_config
                else None
            ),
            tags=tags,
        )

    def create_key_pair(
        self,
        name: str,
        public_key: pulumi.Input[str],
    ) -> pulumi.Output[str]:
        """Create a new key pair and return its name."""
        return pulumi_aws.ec2.KeyPair(
            name,
            public_key=public_key,
            key_name=self.compute_resource_name(name),
        ).key_name

    def create_network(
        self,
        name: str,
        cidr: str,
    ) -> base.Network:
        """Create and return a new VPC."""
        return base.Network(
            cidr=cidr,
            resource=pulumi_aws.ec2.Vpc(
                name,
                cidr_block=cidr,
            ),
        )

    def create_subnet(
        self,
        name: str,
        network: base.Network,
        cidr: str,
        routed: bool = False,  # noqa: ARG002
        gateway_to_internet: bool = False,
        gateway_to_net: pulumi_aws.ec2.Subnet | None = None,
        filtered: bool = True,  # noqa: ARG002
    ) -> pulumi_aws.ec2.Subnet:
        """
        Create and return a new subnet.

        NOTE: `routed` is unused, a VPC carries a local route reaching every
        subnet it holds and there is no way to opt out of it.
        """
        tags = {
            "network": name,
        }

        subnet = pulumi_aws.ec2.Subnet(
            name,
            vpc_id=network.resource.id,
            cidr_block=cidr,
            availability_zone=self._get_availability_zone(),
            tags=tags,
        )

        route_table = pulumi_aws.ec2.RouteTable(
            name,
            vpc_id=network.resource.id,
            tags=tags,
        )

        pulumi_aws.ec2.RouteTableAssociation(
            name,
            subnet_id=subnet.id,
            route_table_id=route_table.id,
        )

        if gateway_to_internet:
            internet_gateway = pulumi_aws.ec2.InternetGateway(
                name,
                vpc_id=network.resource.id,
                tags=tags,
            )

            pulumi_aws.ec2.Route(
                f"{name}-to-internet",
                route_table_id=route_table.id,
                destination_cidr_block="0.0.0.0/0",
                gateway_id=internet_gateway.id,
            )

        if gateway_to_net:
            eip = pulumi_aws.ec2.Eip(
                f"{name}-gw",
                domain="vpc",
                tags=dict(tags, type="NAT gateway"),
            )

            nat_gateway = pulumi_aws.ec2.NatGateway(
                name,
                allocation_id=eip.id,
                subnet_id=gateway_to_net.id,
                tags=tags,
            )

            pulumi_aws.ec2.Route(
                f"{name}-to-nat",
                route_table_id=route_table.id,
                destination_cidr_block="0.0.0.0/0",
                gateway_id=nat_gateway.id,
            )

        return subnet

    def create_security_group(
        self,
        name: str,
        network: base.Network,
        ingress_tcp_ports: list[int] | None = None,
        ingress_udp_ports: list[int] | None = None,
        ingress_icmp: bool = False,
        ingress_cidrs: list[str] | None = None,
        open_egress: bool = False,
        internal_traffic: bool = False,
    ) -> pulumi_aws.ec2.SecurityGroup:
        """Create a new security group."""
        if ingress_cidrs is None:
            ingress_cidrs = ["0.0.0.0/0"]

        sg = pulumi_aws.ec2.SecurityGroup(
            name,
            vpc_id=network.resource.id,
            tags={
                "type": name,
            },
        )

        for protocol, ports in {
            "tcp": ingress_tcp_ports,
            "udp": ingress_udp_ports,
        }.items():
            for port in ports or []:
                for cidr in ingress_cidrs:
                    cidr_name = cidr if isinstance(cidr, str) else "my_ip"
                    pulumi_aws.vpc.SecurityGroupIngressRule(
                        f"{name}-allow-{protocol}-{port}-{cidr_name}",
                        security_group_id=sg.id,
                        from_port=port,
                        to_port=port,
                        ip_protocol=protocol,
                        cidr_ipv4=cidr,
                    )
        if ingress_icmp:
            for cidr in ingress_cidrs:
                cidr_name = cidr if isinstance(cidr, str) else "my_ip"
                pulumi_aws.vpc.SecurityGroupIngressRule(
                    f"{name}-allow-icmp-{cidr_name}",
                    security_group_id=sg.id,
                    from_port=0,
                    to_port=0,
                    ip_protocol="icmp",
                    cidr_ipv4=cidr,
                )

        if open_egress:
            pulumi_aws.vpc.SecurityGroupEgressRule(
                f"{name}-allow-egress",
                security_group_id=sg.id,
                from_port=0,
                to_port=0,
                ip_protocol="-1",
                cidr_ipv4="0.0.0.0/0",
            )

        if internal_traffic:
            pulumi_aws.vpc.SecurityGroupIngressRule(
                f"{name}-allow-internal",
                security_group_id=sg.id,
                from_port=0,
                to_port=0,
                ip_protocol="-1",
                referenced_security_group_id=sg.id,
            )

        return sg

    def create_interface(
        self,
        subnet: pulumi_aws.ec2.Subnet,
        subnet_name: str,
        node_name: str,
        ip: str,
        security_groups: list[pulumi_aws.ec2.SecurityGroup] | None = None,
        public: bool = False,
    ) -> base.Interface:
        """Create a new network interface."""
        name = f"{node_name}-{subnet_name}"
        tags = {
            "network": subnet_name,
            "node": node_name,
        }

        iface = pulumi_aws.ec2.NetworkInterface(
            name,
            subnet_id=subnet.id,
            private_ips=[ip],
            security_groups=[sg.id for sg in security_groups or []],
            # Only enable source/destination checking for public interfaces
            source_dest_check=public,
            tags=tags,
        )

        public_ip = None
        if public:
            public_ip = pulumi_aws.ec2.Eip(
                name,
                domain="vpc",
                network_interface=iface.id,
                tags=tags,
            ).public_ip

        return base.Interface(
            resource=iface,
            ip=iface.private_ips[0],
            public_ip=public_ip,
        )

    def _get_ami(self, image_name: str) -> str:
        """Retrieve the AMI ID for a given image name."""
        # Try to find the AMI in known one
        known = _known_images.get(self.region, {}).get(image_name)
        if known:
            return known

        # NOTE: The ids rather than the AMI itself, so that finding none is
        # ours to report. Asking for the AMI answers that no such thing was
        # found, which never says what was looked for.
        found = pulumi_aws.ec2.get_ami_ids(
            # NOTE: We may want to support other owners in the future
            owners=["self"],
            filters=[{"name": "name", "values": [image_name]}],
            sort_ascending=False,
        )
        if not found.ids:
            message = base.IMAGE_NOT_FOUND.format(provider=self.provider_name, name=image_name)
            raise ValueError(message)

        return found.ids[0]

    def _get_availability_zone(self) -> str:
        if not self._availability_zone:
            self._availability_zone = pulumi_aws.get_availability_zones(
                state="available",
            ).names[0]
        return self._availability_zone

    def _transform_add_common_tags(
        self,
        args: pulumi.ResourceTransformArgs,
    ) -> pulumi.ResourceTransformResult:
        """Transform function to add common tags to resources."""
        common_tags = {
            "Name": self.compute_resource_name(args.name),
            "stack": self.stack,
            "product": self.product,
            "spawner": self.project,
        }

        # List of resources that cannot be tagged
        non_tagged_types = {
            "aws:ec2/routeTableAssociation:RouteTableAssociation",
            "aws:ec2/route:Route",
            "command:local:Command",
        }

        if args.type_ not in non_tagged_types:
            args.props["tags"] = {**common_tags, **(args.props.get("tags") or {})}

        return pulumi.ResourceTransformResult(
            props=args.props,
            opts=args.opts,
        )
