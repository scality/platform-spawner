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
VOLUME_TYPE = "openstack:blockstorage/volume:Volume"
VOLUME_ATTACH_TYPE = "openstack:compute/volumeAttach:VolumeAttach"
OPENSTACK = "openstack"
AVAILABLE = "available"
VOLUME_ERROR = "error"
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

    failed = _clean_ports(cloud, resources, stack_name)
    failed += _clean_volume_attachments(cloud, resources, stack_name, args.timeout)

    return 1 if failed else 0


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


def _clean_volume_attachments(
    cloud: openstack.connection.Connection,
    resources: list[dict],
    stack_name: str,
    timeout: int,
) -> int:
    """
    Detach the volumes of a stack that the stack holds no attachment for.

    An attachment that went through unanswered holds its volume for good:
    attaching again answers that the volume is already attached, which no
    amount of retrying gets past, and destroying cannot delete a volume that
    is in use.

    The volume is detached rather than taken into the stack, so that the next
    attempt makes the attachment itself and the stack ends up knowing about
    the one it runs on.
    """
    volumes = {r["id"] for r in resources if r.get("type") == VOLUME_TYPE}
    known = {
        volume
        for r in resources
        if r.get("type") == VOLUME_ATTACH_TYPE
        for volume in _attached_volumes(r)
    }
    if not volumes:
        print(f"No attachment to look at, {stack_name} holds no volume")
        return 0

    seen, orphans = _survey_volumes(cloud, volumes, known)
    print(f"{len(seen)} volume(s) of {stack_name}:")
    for line in seen:
        print(f"\t{line}")

    if not orphans:
        return 0

    print(f"{len(orphans)} to detach:")
    detached, failed = [], []
    for volume in orphans:
        name = volume.name or volume.id
        try:
            _detach(cloud, volume, timeout)
        except openstack.exceptions.SDKException as err:
            print(f"{name} could not be detached: {err}", file=sys.stderr)
            failed.append(name)
        else:
            detached.append(f"{name} ({volume.id})")

    if detached:
        step_summary.write(f"Volumes left attached by `{stack_name}`", detached)

    return 1 if failed else 0


def _attached_volumes(resource: dict) -> set[str]:
    """
    Say which volume an attachment of the stack holds.

    NOTE: Read twice, from the output and from the id, which carries the
    instance and the volume it joins. Taking a free volume for an attached
    one only leaves it where it is, where the other way around would pull a
    volume out from under a running instance.
    """
    outputs = resource.get("outputs") or {}
    _, _, from_id = str(resource.get("id") or "").partition("/")

    return {volume for volume in (outputs.get("volumeId"), from_id) if volume}


def _survey_volumes(
    cloud: openstack.connection.Connection,
    volumes: set[str],
    known: set[str],
) -> tuple[list[str], list]:
    """
    Say what holds the volumes of a stack, and which of them are ours to free.

    NOTE: Every volume is reported, like every port is. A spawn that keeps
    failing on one volume says nothing about the others, and whether they are
    attached at all is what tells how far the last attempt got.
    """
    seen, orphans = [], []
    for volume_id in sorted(volumes):
        try:
            volume = cloud.block_storage.get_volume(volume_id)
        except openstack.exceptions.ResourceNotFound:
            seen.append(f"{volume_id:<40} gone from the cloud")
            continue

        servers = ", ".join(a.get("server_id", "?") for a in volume.attachments or [])
        if volume_id in known:
            held = f"in the stack, on {servers}" if servers else "in the stack, attached to nothing"
        elif servers:
            held = f"left attached to {servers}"
            orphans.append(volume)
        else:
            held = volume.status
        seen.append(f"{volume.name or volume_id:<40} {held}")

    return seen, orphans


def _detach(
    cloud: openstack.connection.Connection,
    volume: openstack.block_storage.v3.volume.Volume,
    timeout: int,
) -> None:
    """
    Take a volume off whatever holds it, and wait until it really is off.

    NOTE: Waiting on our own terms rather than through `detach_volume`, which
    waits without a timeout whatever it is handed. A detach that never ends
    would hold the run that called us for as long as the job is given.
    """
    for attachment in volume.attachments or []:
        server_id = attachment.get("server_id")
        print(f"\t{volume.name or volume.id} off {server_id}")
        cloud.compute.delete_volume_attachment(
            server=server_id,
            volume=volume.id,
            ignore_missing=True,
        )

    cloud.block_storage.wait_for_status(
        volume,
        status=AVAILABLE,
        failures=[VOLUME_ERROR],
        wait=timeout,
    )


def _parse_args() -> argparse.Namespace:
    """Read the command line."""
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--stack", default=None, help="stack to clean up (default: current)")
    parser.add_argument("--timeout", type=int, default=600, help="seconds to wait for a detach")

    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(__main__())
