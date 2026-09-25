#! /usr/bin/env python3
"""
Delete the images a snapshot is made of.

A snapshot outlives the platform it was taken from, which is what makes it
worth having and also what makes them pile up: nothing in the Pulumi program
knows they exist, so destroying a platform leaves its snapshots behind.
Whoever took one says when it goes.

The product is asked for rather than read from the stack, the platform being
usually gone by the time its snapshots are. `pulumi config get product` tells
what it was while the stack is still around.

NOTE: OpenStack only for the moment, like the tool that takes them.
"""

import argparse
import sys

import openstack
import openstack.exceptions

import step_summary


def __main__() -> int:
    """Delete every image a snapshot is made of."""
    args = _parse_args()
    prefix = f"{args.product}-{args.name}-"

    cloud = openstack.connect()
    images = sorted(
        (image for image in cloud.image.images() if (image.name or "").startswith(prefix)),
        key=lambda image: image.name,
    )
    if not images:
        # NOTE: Not a failure. This runs to clean up after whoever took the
        # snapshot, which may well have fallen over before taking anything.
        print(f"No image named {prefix}*, nothing to delete")
        return 0

    print(f"{len(images)} image(s) to delete:")
    deleted, failed = [], []
    for image in images:
        print(f"\t{image.name}")
        try:
            cloud.image.delete_image(image, ignore_missing=True)
        except openstack.exceptions.SDKException as err:
            print(f"{image.name} could not be deleted: {err}", file=sys.stderr)
            failed.append(image.name)
        else:
            deleted.append(image.name)

    if deleted:
        step_summary.write(f"Snapshot `{args.name}` taken away", deleted)

    return 1 if failed else 0


def _parse_args() -> argparse.Namespace:
    """Read the command line."""
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("name", help="name the snapshot was taken under")
    parser.add_argument(
        "--product",
        required=True,
        help="product the platform was spawned for",
    )

    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(__main__())
