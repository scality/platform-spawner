"""An AWS Python Pulumi program"""

import pathlib
import requests
from typing import List

import pulumi
import pulumi_local
import pulumi_tls

from providers import aws
from providers import base


def __main__():
    provider = aws.AWSSProvider()

    config = pulumi.Config()

    instance_image = config.require("instance_image")
    instance_flavor = base.InstanceFlavor(config.require("instance_flavor"))

    ssh_key_name = _prepare_ssh_key(config, provider)

    # Create networks
    main_network = provider.create_network(
        name="main",
        cidr="172.30.0.0/16",
    )

    public_subnet = provider.create_subnet(
        name="public",
        network=main_network,
        cidr="172.30.0.0/24",
        gateway_to_internet=True,
    )
    control_plane_subnet = provider.create_subnet(
        name="control-plane",
        network=main_network,
        cidr="172.30.100.0/24",
    )
    workload_plane_subnet = provider.create_subnet(
        name="workload-plane",
        network=main_network,
        cidr="172.30.200.0/24",
        # Workload plane can reach the public subnet
        # if offline mode is disable
        gateway_to_net=public_subnet if not config.require_bool("offline") else None,
    )

    # Create security groups
    internal_sg = provider.create_security_group(
        name="internal",
        network=main_network,
        internal_traffic=True,
        open_egress=True,
    )
    ingress_sg = provider.create_security_group(
        name="ingress",
        network=main_network,
        ingress_tcp_ports=config.require_object("authorized_tcp_ports"),
        ingress_udp_ports=config.require_object("authorized_udp_ports"),
        ingress_icmp=config.require_object("authorized_icmp"),
        ingress_cidrs=_parse_cidrs(config.require_object("authorized_cidrs")),
    )
    egress_sg = provider.create_security_group(
        name="egress",
        network=main_network,
        open_egress=True,
    )

    # Create instances
    bastion_public_iface = provider.create_interface(
        subnet=public_subnet,
        subnet_name="public",
        node_name="bastion",
        ip="172.30.0.99",
        security_groups=[internal_sg, ingress_sg, egress_sg],
        public=True,
    )
    bastion_cp_iface = provider.create_interface(
        subnet=control_plane_subnet,
        subnet_name="control-plane",
        node_name="bastion",
        security_groups=[internal_sg],
        ip="172.30.100.99",
    )
    bastion_wp_iface = provider.create_interface(
        subnet=workload_plane_subnet,
        subnet_name="workload-plane",
        node_name="bastion",
        security_groups=[internal_sg, egress_sg],
        ip="172.30.200.99",
    )
    bastion = provider.create_instance(
        name="bastion",
        image_name=config.require("bastion_image"),
        flavor=base.InstanceFlavor(config.require("bastion_flavor")),
        key_name=ssh_key_name,
        root_disk_size=config.require_int("bastion_root_disk_size"),
        interfaces=[bastion_public_iface, bastion_wp_iface, bastion_cp_iface],
    )
    pulumi.export(
        "bastion",
        {
            "id": bastion.id,
            "public_ip": bastion.public_ip,
            "private_ips": {
                "public": bastion_public_iface.private_ips[0],
                "control-plane": bastion_cp_iface.private_ips[0],
                "workload-plane": bastion_wp_iface.private_ips[0],
            },
        },
    )

    for node_index in range(1, config.require_int("instance_count") + 1):
        cp_iface = provider.create_interface(
            subnet=control_plane_subnet,
            subnet_name="control-plane",
            node_name=f"node-{node_index}",
            security_groups=[internal_sg],
            ip=f"172.30.100.{100 + node_index}",
        )
        wp_iface = provider.create_interface(
            subnet=workload_plane_subnet,
            subnet_name="workload-plane",
            node_name=f"node-{node_index}",
            security_groups=[internal_sg, egress_sg],
            ip=f"172.30.200.{100 + node_index}",
        )
        node = provider.create_instance(
            name=f"node-{node_index}",
            image_name=instance_image,
            flavor=instance_flavor,
            key_name=ssh_key_name,
            root_disk_size=config.require_int("instance_root_disk_size"),
            interfaces=[wp_iface, cp_iface],
        )
        pulumi.export(
            f"node-{node_index}-id",
            {
                "id": node.id,
                "private_ips": {
                    "control-plane": cp_iface.private_ips[0],
                    "workload-plane": wp_iface.private_ips[0],
                },
            },
        )


def _prepare_ssh_key(config: pulumi.Config, provider: base.BaseProvider) -> str:
    if config.require_bool("ssh_private_key_create"):
        path = pathlib.Path(f"~/.ssh/{provider.compute_resource_name()}").expanduser()

        private_key = pulumi_tls.PrivateKey(
            provider.compute_resource_name(), algorithm="ED25519"
        )
        pulumi_local.File(
            "ssh-private-key-file",
            content=private_key.private_key_pem,
            filename=str(path),
            file_permission="0600",
        )
        pulumi_local.File(
            "ssh-public-key-file",
            content=private_key.public_key_pem,
            filename=str(path.with_suffix(".pub")),
        )

        pulumi.export("ssh_private_key_path", str(path))
        return provider.create_key_pair("key", private_key.public_key_openssh).id
    else:
        return config.require("ssh_key_name")


def _parse_cidrs(cidrs: List[str]):
    """Mainly used to replace the `__my_ip__` placeholder."""

    def _get_my_ip():
        response = requests.get("https://api.ipify.org", timeout=5)
        response.raise_for_status()
        return f"{response.text}/32"

    return [
        pulumi.Output.from_input(None).apply(lambda _: _get_my_ip())
        if cidr == "__my_ip__"
        else cidr
        for cidr in cidrs
    ]


if __name__ == "__main__":
    __main__()
