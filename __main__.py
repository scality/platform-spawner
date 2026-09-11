"""A Pulumi program to spawn platforms on a cloud provider."""

import pathlib

import pulumi
import pulumi_command
import pulumi_tls
import requests

import providers
from providers import base

SSH_ARG_MUTUALLY_EXCLUSIFE = "One of ssh_key_name or ssh_private_key_create can be set."
SSH_USERS = {
    "rocky-8": "rocky",
    "rocky-9": "rocky",
}
SSH_CONFIG_DIR = pathlib.Path.cwd()
SSH_CONFIG_LINK_NAME = "ssh_config"


def __main__() -> None:
    provider = providers.get_provider()

    config = pulumi.Config()

    instance_image = config.require("instance_image")
    instance_flavor = base.InstanceFlavor(config.require("instance_flavor"))

    ssh_info = {
        "bastion": {},
        "nodes": {},
    }
    ssh_key_name = _prepare_ssh_key(config, provider, ssh_info)

    # Create networks
    main_network = provider.create_network(
        name="main",
        cidr="172.30.0.0/16",
    )

    public_subnet = provider.create_subnet(
        name="public",
        network=main_network,
        cidr="172.30.0.0/24",
        routed=True,
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
        routed=True,
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
        disable_auto_stop=config.require_bool("disable_auto_stop"),
    )
    pulumi.export(
        "bastion",
        {
            "id": bastion.id,
            "public_ip": bastion_public_iface.public_ip,
            "private_ips": {
                "public": bastion_public_iface.ip,
                "control-plane": bastion_cp_iface.ip,
                "workload-plane": bastion_wp_iface.ip,
            },
        },
    )
    ssh_info["bastion"] = {
        "ip": bastion_public_iface.public_ip,
        "user": SSH_USERS.get(config.require("bastion_image")),
    }
    nodes_info = {}

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
            extra_volumes=config.require_object("extra_volumes"),
            disable_auto_stop=config.require_bool("disable_auto_stop"),
        )
        nodes_info[f"node-{node_index}"] = {
            "id": node.id,
            "private_ips": {
                "control-plane": cp_iface.ip,
                "workload-plane": wp_iface.ip,
            },
        }
        ssh_info["nodes"][f"node-{node_index}"] = {
            "ip": cp_iface.ip,
            "user": SSH_USERS.get(config.require("instance_image")),
        }

    pulumi.export("nodes", nodes_info)
    pulumi.export("ssh_info", ssh_info)

    ssh_config_file = SSH_CONFIG_DIR / f"{SSH_CONFIG_LINK_NAME}-{provider.stack}"
    pulumi.export("ssh_config", str(ssh_config_file))
    pulumi.Output.all(ssh_info).apply(lambda info: _generate_ssh_config(info, ssh_config_file))


def _prepare_ssh_key(
    config: pulumi.Config,
    provider: base.BaseProvider,
    ssh_info: dict,
) -> pulumi.Input[str]:
    if config.require_bool("ssh_private_key_create"):
        path = pathlib.Path(f"./ssh_{provider.compute_resource_name()}").resolve()

        private_key = pulumi_tls.PrivateKey(
            provider.compute_resource_name(),
            algorithm="ED25519",
        )
        pulumi_command.local.Command(
            "ssh-private-key-file",
            create=pulumi.Output.from_input(private_key.private_key_openssh).apply(
                lambda pk: f"echo -n '{pk}' > {path!s} && chmod 600 {path!s}"
            ),
        )
        pulumi_command.local.Command(
            "ssh-public-key-file",
            create=pulumi.Output.from_input(private_key.public_key_openssh).apply(
                lambda pk: f"echo -n '{pk}' > {path.with_suffix('.pub')!s}"
            ),
        )

        ssh_info["key"] = str(path)
        return provider.create_key_pair("key", private_key.public_key_openssh)

    ssh_key_name = config.require("ssh_key_name")
    if not ssh_key_name:
        raise ValueError(SSH_ARG_MUTUALLY_EXCLUSIFE)
    return ssh_key_name


def _parse_cidrs(cidrs: list[str]) -> list[pulumi.Output[str]]:
    """Mainly used to replace the `__my_ip__` placeholder."""

    def _get_my_ip() -> str:
        response = requests.get("https://api.ipify.org", timeout=5)
        response.raise_for_status()
        return f"{response.text}/32"

    return [
        pulumi.Output.from_input(None).apply(lambda _: _get_my_ip())
        if cidr == "__my_ip__"
        else cidr
        for cidr in cidrs
    ]


def _parse_extra_volumes(extra_volumes: list[dict]) -> dict:
    """Parse the extra volumes configuration."""
    volumes = {}
    for index, vol in enumerate(extra_volumes):
        volumes[vol.get("name", f"extra-volume-{index + 1}")] = {
            "size": vol["size"],
            "count": vol.get("count", 1),
        }
    return volumes


def _generate_ssh_config(ssh_info_list: list[dict], path: pathlib.Path) -> None:
    ssh_info = ssh_info_list[0]
    config_lines = []
    if "bastion" in ssh_info:
        config_lines.append("Host bastion")
        config_lines.append(f"  HostName {ssh_info['bastion']['ip']}")
        config_lines.append("  Port 22")
        if ssh_info["bastion"].get("user"):
            config_lines.append(f"  User {ssh_info['bastion']['user']}")
        if ssh_info.get("key"):
            config_lines.append(f"  IdentityFile {ssh_info['key']}")
        config_lines.append("  IdentitiesOnly yes")
        config_lines.append("  StrictHostKeyChecking no")
        config_lines.append("  ServerAliveInterval 15")
        config_lines.append("")

    for host, info in ssh_info["nodes"].items():
        config_lines.append(f"Host {host}")
        if "bastion" in ssh_info:
            config_lines.append("  ProxyJump bastion")
        config_lines.append(f"  HostName {info['ip']}")
        config_lines.append("  Port 22")
        if info.get("user"):
            config_lines.append(f"  User {info['user']}")
        if ssh_info.get("key"):
            config_lines.append(f"  IdentityFile {ssh_info['key']}")
        config_lines.append("  IdentitiesOnly yes")
        config_lines.append("  StrictHostKeyChecking no")
        config_lines.append("  ServerAliveInterval 15")
        config_lines.append("")

    path.write_text("\n".join(config_lines))

    # Point the stable name at the stack we just spawned, so that `ssh -F
    # ssh_config` keeps working while the per stack files pile up next to it.
    link = path.with_name(SSH_CONFIG_LINK_NAME)
    link.unlink(missing_ok=True)
    link.symlink_to(path.name)


if __name__ == "__main__":
    __main__()
