#! /usr/bin/env python3
"""
Take one snapshot image per instance of a platform, so it can be spawned back.

The snapshots outlive the platform they were taken from, which is why this
lives outside the Pulumi program: a destroy would otherwise take them away
with everything else, and a snapshot is worth having precisely because the
platform is not.

NOTE: OpenStack only for the moment. Another cloud would bring its own
`_snapshot_instances`, the rest of the script does not know what a cloud is.
"""

import argparse
import sys
import time

import openstack
import openstack.exceptions
import stack
import step_summary

# Both have to be watched: an image is reported active at times while the
# instance is still uploading it.
UPLOADING_TASK = "image_uploading"
UNFINISHED_IMAGE_STATUSES = frozenset({"", "queued", "saving"})
STOPPED = "SHUTOFF"
RUNNING = "ACTIVE"


def __main__() -> int:
    """Take a snapshot of every instance of a platform."""
    args = _parse_args()

    workspace, stack_name = stack.open_stack(args.stack)
    product = workspace.get_config(stack_name, "product").value
    nodes = workspace.stack_outputs(stack_name).get("nodes")
    nodes = nodes.value if nodes else {}
    instances = {name: node["id"] for name, node in sorted(nodes.items())}
    if not instances:
        print("No instance to snapshot", file=sys.stderr)
        return 1

    snapshots = {
        instance_id: f"{product}-{args.name}-{name}" for name, instance_id in instances.items()
    }
    print(f"{len(snapshots)} snapshot(s) to take:")
    for instance_id, image_name in snapshots.items():
        print(f"\t{image_name} from {instance_id}")

    result = _snapshot_instances(snapshots, args)
    if result == 0:
        step_summary.write(f"Snapshot `{args.name}` taken", sorted(snapshots.values()))

    return result


def _parse_args() -> argparse.Namespace:
    """Read the command line."""
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("name", help="name of the snapshot, spawned back with restore_snapshot")
    parser.add_argument("--stack", default=None, help="stack to snapshot (default: current)")
    parser.add_argument("--retries", type=int, default=3, help="attempts per snapshot")
    parser.add_argument("--timeout", type=int, default=1200, help="seconds to wait for an image")
    parser.add_argument("--poll", type=int, default=5, help="seconds between two checks")

    return parser.parse_args()


def _snapshot_instances(snapshots: dict[str, str], args: argparse.Namespace) -> int:
    """Stop every instance, snapshot it, and start them all back."""
    cloud = openstack.connect()
    stopped: list[str] = []

    result = 0
    try:
        stopped.extend(instance_id for instance_id in snapshots if _stop(cloud, instance_id))
        for instance_id in snapshots:
            _wait_until_stopped(cloud, instance_id, args)

        for instance_id, image_name in snapshots.items():
            if not _take_snapshot(cloud, instance_id, image_name, args):
                result = 1
                break
    finally:
        # Whatever happened, leave the platform as we found it
        if not _start_back(cloud, stopped, args):
            result = 1

    return result


def _start_back(
    cloud: openstack.connection.Connection,
    instance_ids: list[str],
    args: argparse.Namespace,
) -> bool:
    """
    Start the instances back, telling whether they all came up.

    NOTE: Waiting rather than only asking. What this hands back is a platform
    ready to be used again rather than one still on its way up, and an
    instance that never returns is worth hearing about here rather than at
    whatever next tries to reach it.
    """
    for instance_id in instance_ids:
        print(f"Starting {instance_id} back")
        cloud.compute.start_server(instance_id)

    back = True
    for instance_id in instance_ids:
        server = cloud.compute.get_server(instance_id)
        try:
            cloud.compute.wait_for_server(server, status=RUNNING, wait=args.timeout)
        except openstack.exceptions.SDKException as err:
            # NOTE: Reported rather than raised. This runs in the `finally`
            # of whatever went before, where raising would hide it.
            print(f"{instance_id} did not come back up: {err}", file=sys.stderr)
            back = False
        else:
            print(f"{instance_id} is back up")

    return back


def _stop(cloud: openstack.connection.Connection, instance_id: str) -> bool:
    """Ask an instance to stop, telling whether it had to be asked at all."""
    server = cloud.compute.get_server(instance_id)
    if server.status == STOPPED:
        return False

    print(f"Stopping {instance_id}")
    cloud.compute.stop_server(server)

    return True


def _wait_until_stopped(
    cloud: openstack.connection.Connection,
    instance_id: str,
    args: argparse.Namespace,
) -> None:
    """Hold until an instance is down, so that its disk stops moving."""
    server = cloud.compute.get_server(instance_id)
    cloud.compute.wait_for_server(server, status=STOPPED, wait=args.timeout)
    print(f"{instance_id} stopped")


def _take_snapshot(
    cloud: openstack.connection.Connection,
    instance_id: str,
    image_name: str,
    args: argparse.Namespace,
) -> bool:
    """Snapshot one instance, retrying as long as it does not come out active."""
    existing = cloud.image.find_image(image_name)
    if existing is not None and existing.status == "active":
        print(f"{image_name} already exists and is active")
        return True

    for attempt in range(1, args.retries + 1):
        print(f"Taking {image_name} [{attempt}/{args.retries}]")
        image = cloud.compute.create_server_image(instance_id, image_name)

        if _wait_until_active(cloud, instance_id, image.id, args):
            print(f"{image_name} is active")
            return True

        # NOTE: The one that did not make it has to go before asking for
        # another. Glance takes a second image of the same name happily, and
        # from then on nothing can tell the two apart by that name again.
        print(f"{image_name} did not become active in {args.timeout}s, taking it away")
        cloud.image.delete_image(image, ignore_missing=True)

    print(f"{image_name} is still not active after {args.retries} attempts", file=sys.stderr)

    return False


def _wait_until_active(
    cloud: openstack.connection.Connection,
    instance_id: str,
    image_id: str,
    args: argparse.Namespace,
) -> bool:
    """
    Hold until an image is really finished.

    NOTE: An image is reported active at times while the instance is still
    uploading it, so the instance is watched as well as the image.

    The image is followed by its id rather than by its name. A name says
    nothing once a failed attempt has left a second image answering to it.
    """
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        image = cloud.image.find_image(image_id)
        status = "" if image is None else image.status
        task = cloud.compute.get_server(instance_id).task_state

        if status not in UNFINISHED_IMAGE_STATUSES and task != UPLOADING_TASK:
            return status == "active"

        print(f"  not ready yet (image: {status or 'absent'}, instance: {task})")
        time.sleep(args.poll)

    return False


if __name__ == "__main__":
    sys.exit(__main__())
