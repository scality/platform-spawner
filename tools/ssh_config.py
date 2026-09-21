"""
Write the SSH configuration that reaches a platform.

Shared between the program that spawns a platform and the tool that brings
the files back from a stack, so that a recovered configuration is the one the
spawn would have written rather than something close to it.
"""

import pathlib

LINK_NAME = "ssh_config"
KNOWN_HOSTS_PREFIX = "ssh_known_hosts"
# Where the bastion keeps what it is handed, in its own home
BASTION_KEY = ".ssh/bastion"
BASTION_CONFIG = "ssh_config"


def path_for(directory: pathlib.Path, stack: str) -> pathlib.Path:
    """Return the config written for a stack."""
    return directory / f"{LINK_NAME}-{stack}"


def known_hosts_path(config_path: pathlib.Path) -> pathlib.Path:
    """Return the known_hosts file that goes with a generated config."""
    stack = config_path.name.removeprefix(f"{LINK_NAME}-")

    return config_path.with_name(f"{KNOWN_HOSTS_PREFIX}-{stack}")


def bastion_path(config_path: pathlib.Path) -> pathlib.Path:
    """Return the config written for the bastion itself, next to the local one."""
    return config_path.with_name(f"{config_path.name}-bastion")


def common_options(config_path: pathlib.Path) -> list[str]:
    """Return the options every host block of the config repeats."""
    return [
        "  IdentitiesOnly yes",
        "  StrictHostKeyChecking no",
        # NOTE: A file of its own for each platform. The machines always sit at
        # the same addresses, so a shared one would hold the keys of the
        # platform before this one and get in the way, while a dedicated one
        # still catches a key changing under us within the life of this one.
        f"  UserKnownHostsFile {known_hosts_path(config_path)}",
        "  ServerAliveInterval 15",
    ]


def generate_bastion(ssh_info: dict, path: pathlib.Path) -> None:
    """
    Write the config the bastion uses to reach the nodes.

    It carries no bastion entry: from the bastion there is nothing to jump
    through. It points at the key the bastion is handed rather than at the
    one that stays here. Host keys are left to the default file: the machines are
    as new as the bastion reading it, so nothing stale can get in the way.
    """
    config_lines = []
    for host, info in ssh_info["nodes"].items():
        config_lines.append(f"Host {host}")
        config_lines.append(f"  HostName {info['ip']}")
        config_lines.append("  Port 22")
        if info.get("user"):
            config_lines.append(f"  User {info['user']}")
        config_lines.append(f"  IdentityFile ~/{BASTION_KEY}")
        config_lines.append("  IdentitiesOnly yes")
        config_lines.append("  StrictHostKeyChecking no")
        config_lines.append("  ServerAliveInterval 15")
        config_lines.append("")

    bastion_path(path).write_text("\n".join(config_lines))


def generate(ssh_info: dict, path: pathlib.Path) -> str:
    """Write the config reaching a platform, and point the stable name at it."""
    options = common_options(path)
    config_lines = []
    if "bastion" in ssh_info:
        config_lines.append("Host bastion")
        config_lines.append(f"  HostName {ssh_info['bastion']['ip']}")
        config_lines.append("  Port 22")
        if ssh_info["bastion"].get("user"):
            config_lines.append(f"  User {ssh_info['bastion']['user']}")
        if ssh_info.get("key"):
            config_lines.append(f"  IdentityFile {ssh_info['key']}")
        config_lines.extend(options)
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
        config_lines.extend(options)
        config_lines.append("")

    path.write_text("\n".join(config_lines))
    generate_bastion(ssh_info, path)

    # Point the stable name at the platform this config reaches, so that
    # `ssh -F ssh_config` keeps working while the per stack files pile up
    # next to it.
    link = path.with_name(LINK_NAME)
    link.unlink(missing_ok=True)
    link.symlink_to(path.name)

    return str(path)
