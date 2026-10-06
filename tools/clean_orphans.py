#! /usr/bin/env python3
"""
Take away what a failed spawn left behind on the cloud.

A cloud that goes down mid-spawn can answer the call that does the work and
then not the one that waits for it. What was asked for exists, the stack
never learned of it, and the next attempt walks straight into it.

Only what belongs to the stack and what the stack does not know about is
taken away. Whatever the cloud itself holds is left alone.

NOTE: OpenStack only, the cloud this has been seen on.
"""

import argparse
import sys

import openstack
import openstack.exceptions

import stack
import step_summary

NETWORK_TYPE = "openstack:networking/network:Network"
PORT_TYPE = "openstack:networking/port:Port"
OPENSTACK = "openstack"
# What the cloud owns on a network it hands us: the DHCP port, the router
# interfaces, the floating IPs. Everything else on a network of ours is ours,
# whether or not it says what it is attached to.
CLOUD_OWNED = "network:"


def __main__() -> int:
    """Take away what the stack owns on the cloud and does not know about."""
    args = _parse_args()
    workspace, stack_name = stack.open_stack(args.stack)

    provider = workspace.get_config(stack_name, "provider").value
    if provider != OPENSTACK:
        print(f"Nothing to do, {stack_name} is spawned on {provider}")
        return 0

    resources = workspace.export_stack(stack_name).deployment.get("resources", [])
    cloud = openstack.connect()

    return _clean_ports(cloud, resources, stack_name)


def _clean_ports(
    cloud: openstack.connection.Connection,
    resources: list[dict],
    stack_name: str,
) -> int:
    """
    Delete the ports of a stack that the stack does not know about.

    Every address here is fixed, so a port left behind holds the one the next
    attempt needs: spawning again answers `IpAddressAlreadyAllocated` for as
    long as it is there, and destroying answers that the subnet still has an
    allocation.
    """
    networks = {r["id"] for r in resources if r.get("type") == NETWORK_TYPE}
    known = {r["id"] for r in resources if r.get("type") == PORT_TYPE}
    if not networks:
        print(f"No port to look at, {stack_name} holds no network")
        return 0

    seen, orphans = _survey_ports(cloud, networks, known)
    print(f"{len(seen)} port(s) on the {len(networks)} network(s) of {stack_name}:")
    for line in seen:
        print(f"\t{line}")

    if not orphans:
        return 0

    print(f"{len(orphans)} to take away:")
    deleted, failed = [], []
    for port in orphans:
        addresses = ", ".join(ip.get("ip_address", "?") for ip in port.fixed_ips or [])
        print(f"\t{port.id} holding {addresses or 'no address'}")
        try:
            cloud.network.delete_port(port, ignore_missing=True)
        except openstack.exceptions.SDKException as err:
            print(f"{port.id} could not be deleted: {err}", file=sys.stderr)
            failed.append(port.id)
        else:
            deleted.append(f"{port.id} ({addresses})")

    if deleted:
        step_summary.write(f"Ports left behind by `{stack_name}`", deleted)

    return 1 if failed else 0


def _survey_ports(
    cloud: openstack.connection.Connection,
    networks: set[str],
    known: set[str],
) -> tuple[list[str], list]:
    """
    Say what sits on the networks of a stack, and what of it is ours to remove.

    NOTE: Everything is reported, not only what is taken away. When a spawn
    keeps failing on an address that is somehow already taken, what holds it
    is the one thing worth reading in the log.
    """
    seen, orphans = [], []
    for network in sorted(networks):
        for port in cloud.network.ports(network_id=network):
            owner = port.device_owner or ""
            addresses = ", ".join(ip.get("ip_address", "?") for ip in port.fixed_ips or [])
            if port.id in known:
                held = "in the stack"
            elif owner.startswith(CLOUD_OWNED):
                held = f"the cloud's own ({owner})"
            else:
                held = f"left behind ({owner or 'attached to nothing'})"
                orphans.append(port)
            seen.append(f"{addresses or 'no address':<40} {held}")

    return seen, orphans


def _parse_args() -> argparse.Namespace:
    """Read the command line."""
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--stack", default=None, help="stack to clean up (default: current)")

    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(__main__())
