"""A Pulumi program to spawn platforms on a cloud provider."""

import ipaddress
import pathlib

import pulumi
import pulumi_command
import pulumi_tls
import requests

import providers
from providers import base

SSH_ARG_MUTUALLY_EXCLUSIFE = "One of ssh_key_name or ssh_private_key_create can be set."
SSH_USER_UNKNOWN = "No user to reach the {machine} with, set {machine}_ssh_user."
EXTRA_NETWORK_TOO_SMALL = "{name} ({cidr}) has no room left, there are too many instances."
TOO_MANY_EXTRA_NETWORKS = "At most {limit} extra networks can be asked for."
DUPLICATE_EXTRA_NETWORK = "Several extra networks are named {names}."
INSTANCE_IMAGE_MISSING = "One of instance_image or instance_image_file must be set."
# Fallback for the images we know, anything else has to be configured
SSH_USERS = {
    "rocky-8": "rocky",
    "rocky-9": "rocky",
}
# Held until every machine answers SSH and cloud-init is done with it, so that
# a finished update means a platform that can actually be used.
BOOT_WAIT_TIMEOUT = 600
BOOT_WAIT_SCRIPT = """set -eu
for host in {hosts}; do
    give_up=$(( $(date +%s) + {timeout} ))
    until ssh -F {config} -o ConnectTimeout=10 "$host" true 2>/dev/null; do
        if [ "$(date +%s)" -ge "$give_up" ]; then
            echo "$host never answered ssh" >&2
            exit 1
        fi
        sleep 5
    done

    # NOTE: Bounded like the wait above. `cloud-init status --wait` holds for
    # as long as it takes, and a boot that never ends would otherwise hold the
    # update with it. 124 is what the timeout itself exits with.
    booted=0
    timeout {timeout} ssh -F {config} "$host" cloud-init status --wait || booted=$?
    if [ "$booted" -eq 124 ]; then
        echo "$host was still booting after {timeout}s" >&2
        exit 1
    fi
    if [ "$booted" -ne 0 ]; then
        echo "$host booted badly, cloud-init exited $booted" >&2
        exit 1
    fi
done
"""
# Extra networks sit beside the public one, in the space the planes already
# share, and the control plane is what bounds how many of them there can be
EXTRA_NETWORK_CIDR = "172.30.{index}.0/24"
EXTRA_NETWORK_MAX = 99
EXTRA_NETWORK_NAME = "extra-network-{index}"
SSH_CONFIG_DIR = pathlib.Path.cwd()
SSH_CONFIG_LINK_NAME = "ssh_config"
SSH_KNOWN_HOSTS_PREFIX = "ssh_known_hosts"


def __main__() -> None:
    provider = providers.get_provider()

    config = pulumi.Config()

    instance_image = _instance_image(config, provider)
    instance_flavor = config.require("instance_flavor")

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

    extra_networks = config.require_object("extra_networks")
    extra_subnets = [
        (
            extra,
            name,
            provider.create_subnet(
                name=name,
                network=main_network,
                cidr=_extra_network_cidr(index),
            ),
        )
        for index, (extra, name) in enumerate(
            zip(extra_networks, _extra_network_names(extra_networks), strict=True),
            start=1,
        )
    ]

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
    instances = []
    bastion_extra_ifaces = _create_extra_interfaces(
        provider, extra_subnets, "bastion", 99, [internal_sg], max_interfaces=1
    )

    bastion = provider.create_instance(
        name="bastion",
        image_name=config.require("bastion_image"),
        flavor=config.require("bastion_flavor"),
        key_name=ssh_key_name,
        root_disk_size=config.require_int("bastion_root_disk_size"),
        interfaces=[
            bastion_public_iface,
            bastion_wp_iface,
            bastion_cp_iface,
            *(iface for _, iface in bastion_extra_ifaces),
        ],
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
                **{name: iface.ip for name, iface in bastion_extra_ifaces},
            },
        },
    )
    instances.append(bastion)
    ssh_info["bastion"] = {
        "ip": bastion_public_iface.public_ip,
        "user": _ssh_user(config, "bastion"),
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
        extra_ifaces = _create_extra_interfaces(
            provider, extra_subnets, f"node-{node_index}", 100 + node_index, [internal_sg]
        )

        node = provider.create_instance(
            name=f"node-{node_index}",
            image_name=instance_image,
            flavor=instance_flavor,
            key_name=ssh_key_name,
            root_disk_size=config.require_int("instance_root_disk_size"),
            interfaces=[wp_iface, cp_iface, *(iface for _, iface in extra_ifaces)],
            extra_volumes=config.require_object("extra_volumes"),
            disable_auto_stop=config.require_bool("disable_auto_stop"),
        )
        instances.append(node)
        nodes_info[f"node-{node_index}"] = {
            "id": node.id,
            "private_ips": {
                "control-plane": cp_iface.ip,
                "workload-plane": wp_iface.ip,
                **{name: iface.ip for name, iface in extra_ifaces},
            },
        }
        ssh_info["nodes"][f"node-{node_index}"] = {
            "ip": cp_iface.ip,
            "user": _ssh_user(config, "instance"),
        }

    pulumi.export("nodes", nodes_info)
    pulumi.export("ssh_info", ssh_info)

    ssh_config_file = SSH_CONFIG_DIR / f"{SSH_CONFIG_LINK_NAME}-{provider.stack}"
    pulumi.export("ssh_config", str(ssh_config_file))
    ssh_config_ready = pulumi.Output.all(ssh_info).apply(
        lambda info: _generate_ssh_config(info, ssh_config_file)
    )

    _wait_for_boot(ssh_config_ready, ["bastion", *nodes_info], instances)
    _clean_up_ssh_files(ssh_config_file)


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


def _extra_network_cidr(index: int) -> str:
    """
    Return the address space of the `index`th extra network.

    NOTE: Derived rather than configured. An extra network is the same kind
    of isolated private network as the planes, whose address spaces are
    spelled out here too, so there is nothing for a caller to decide. Letting
    it decide would mean checking that what it picks overlaps neither the
    planes nor another extra network, which nothing did.
    """
    if index > EXTRA_NETWORK_MAX:
        message = TOO_MANY_EXTRA_NETWORKS.format(limit=EXTRA_NETWORK_MAX)
        raise ValueError(message)

    return EXTRA_NETWORK_CIDR.format(index=index)


def _extra_network_names(extra_networks: list[dict]) -> list[str]:
    """
    Return the name of every extra network, in order.

    NOTE: A name is a label and nothing else. The address space comes from
    the position in the list, so renaming a network leaves it exactly where
    it was and reordering the list moves it, whatever the names say.
    """
    names = [
        extra.get("name") or EXTRA_NETWORK_NAME.format(index=index)
        for index, extra in enumerate(extra_networks, start=1)
    ]

    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        message = DUPLICATE_EXTRA_NETWORK.format(names=", ".join(duplicates))
        raise ValueError(message)

    return names


def _create_extra_interfaces(
    provider: base.BaseProvider,
    extra_subnets: list[tuple[dict, str, pulumi.Resource]],
    machine: str,
    host: int,
    security_groups: list[pulumi.Resource],
    max_interfaces: int = 2,
) -> list[tuple[str, base.Interface]]:
    """
    Attach a machine to every extra network, possibly more than once.

    `host` is the address the machine takes on each of them, the same one it
    holds on the other networks. A second interface is what makes a bonding
    setup testable, and it sits a hundred further so that addresses stay
    readable: node 3 at `.103` also answers at `.203`. The bastion only ever
    takes the first one.
    """
    interfaces = []
    for network_index, (extra, network_name, subnet) in enumerate(extra_subnets, start=1):
        cidr = _extra_network_cidr(network_index)
        addresses = ipaddress.ip_network(cidr)
        count = min(2 if extra.get("redundant") else 1, max_interfaces)

        for iface_index in range(1, count + 1):
            offset = host + 100 * (iface_index - 1)
            if offset >= addresses.num_addresses:
                message = EXTRA_NETWORK_TOO_SMALL.format(cidr=cidr, name=network_name)
                raise ValueError(message)

            name = f"{network_name}-{iface_index}"
            interfaces.append(
                (
                    name,
                    provider.create_interface(
                        subnet=subnet,
                        subnet_name=name,
                        node_name=machine,
                        security_groups=security_groups,
                        ip=str(addresses[offset]),
                    ),
                )
            )

    return interfaces


def _clean_up_ssh_files(ssh_config_path: pathlib.Path) -> None:
    """Take the files generated for a platform away with it."""
    known_hosts = _known_hosts_path(ssh_config_path)
    link = ssh_config_path.with_name(SSH_CONFIG_LINK_NAME)

    pulumi_command.local.Command(
        "ssh-files",
        # NOTE: The files are written by the program itself, this only sees to
        # their removal. The stable name is a link to whichever platform was
        # spawned last, so it only goes if it still points at this one.
        #
        # The SSH key is left behind on purpose, throwing a private key away
        # is for someone to decide, not for a destroy to do on its own.
        delete=(
            f"rm -f {known_hosts} {ssh_config_path};"
            f' [ "$(readlink {link} 2>/dev/null)" = "{ssh_config_path.name}" ]'
            f" && rm -f {link} || true"
        ),
    )


def _known_hosts_path(ssh_config_path: pathlib.Path) -> pathlib.Path:
    """Return the known_hosts file that goes with a generated config."""
    stack = ssh_config_path.name.removeprefix(f"{SSH_CONFIG_LINK_NAME}-")

    return ssh_config_path.with_name(f"{SSH_KNOWN_HOSTS_PREFIX}-{stack}")


def _ssh_common_options(ssh_config_path: pathlib.Path) -> list[str]:
    """Return the options every host block of the config repeats."""
    return [
        "  IdentitiesOnly yes",
        "  StrictHostKeyChecking no",
        # NOTE: A file of its own for each platform. The machines always sit at
        # the same addresses, so a shared one would hold the keys of the
        # platform before this one and get in the way, while a dedicated one
        # still catches a key changing under us within the life of this one.
        f"  UserKnownHostsFile {_known_hosts_path(ssh_config_path)}",
        "  ServerAliveInterval 15",
    ]


def _instance_image(config: pulumi.Config, provider: base.BaseProvider) -> str:
    """
    Return the image the instances boot on, uploading a file first if asked.

    NOTE: The bastion is left out, it keeps running whatever `bastion_image`
    names. An image handed over is the one under test, and the bastion is not
    what is being tested.
    """
    image_file = config.require("instance_image_file")
    if not image_file:
        image = config.require("instance_image")
        if not image:
            raise ValueError(INSTANCE_IMAGE_MISSING)

        return image

    return provider.create_image(
        "image",
        image_file,
        config.require("instance_image_file_format"),
    )


def _ssh_user(config: pulumi.Config, machine: str) -> str:
    """
    Return the user to reach a machine with, configured or taken from its image.

    NOTE: An image nobody here has heard of has to be told about rather than
    left to whatever account happens to be running the spawn. A machine
    nothing can log into is worth saying so about now rather than ten minutes
    later, when it turns out never to have answered.
    """
    configured = config.require(f"{machine}_ssh_user")
    if configured:
        return configured

    user = SSH_USERS.get(config.require(f"{machine}_image"))
    if user is None:
        message = SSH_USER_UNKNOWN.format(machine=machine)
        raise ValueError(message)

    return user


def _wait_for_boot(
    ssh_config: pulumi.Output[str],
    hosts: list[str],
    instances: list[pulumi.CustomResource],
) -> None:
    """Hold the update until every machine is done booting."""
    pulumi_command.local.Command(
        "wait-for-boot",
        create=ssh_config.apply(
            lambda config: BOOT_WAIT_SCRIPT.format(
                hosts=" ".join(hosts),
                config=config,
                timeout=BOOT_WAIT_TIMEOUT,
            )
        ),
        # Wait again whenever a machine is replaced under us
        triggers=[instance.id for instance in instances],
        opts=pulumi.ResourceOptions(depends_on=instances),
    )


def _generate_ssh_config(ssh_info_list: list[dict], path: pathlib.Path) -> str:
    ssh_info = ssh_info_list[0]
    common_options = _ssh_common_options(path)
    config_lines = []
    if "bastion" in ssh_info:
        config_lines.append("Host bastion")
        config_lines.append(f"  HostName {ssh_info['bastion']['ip']}")
        config_lines.append("  Port 22")
        if ssh_info["bastion"].get("user"):
            config_lines.append(f"  User {ssh_info['bastion']['user']}")
        if ssh_info.get("key"):
            config_lines.append(f"  IdentityFile {ssh_info['key']}")
        config_lines.extend(common_options)
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
        config_lines.extend(common_options)
        config_lines.append("")

    path.write_text("\n".join(config_lines))

    # Point the stable name at the stack we just spawned, so that `ssh -F
    # ssh_config` keeps working while the per stack files pile up next to it.
    link = path.with_name(SSH_CONFIG_LINK_NAME)
    link.unlink(missing_ok=True)
    link.symlink_to(path.name)

    return str(path)


if __name__ == "__main__":
    __main__()
