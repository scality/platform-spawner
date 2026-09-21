#! /usr/bin/env python3
"""
Bring the SSH files of a platform back from the stack that holds it.

A spawn writes them where it ran, so another machine, or the same one after a
clean up, has nothing to reach the platform with. Everything needed is in the
stack: the addresses and users are exported, and so is the key a spawn
generated, as a secret.

Nothing deployed is read or touched, only the stack.
"""

import argparse
import os
import pathlib
import sys

import ssh_config
import stack
from pulumi.automation import CommandError

NO_SSH_INFO = "Stack {stack!r} reports no ssh_info, is it spawned?"
KEY_MISSING = "Stack {stack!r} exports no key, was it spawned before they were?"


def __main__() -> int:
    """Write the SSH files of a platform out of its stack."""
    args = _parse_args()
    workspace, stack_name = stack.open_stack(args.stack)

    try:
        outputs = workspace.stack_outputs(stack_name)
    except CommandError as err:
        print(f"Cannot read stack {stack_name!r}:\n{err}", file=sys.stderr)
        return 1

    ssh_info = outputs["ssh_info"].value if "ssh_info" in outputs else {}
    if not ssh_info.get("nodes"):
        print(NO_SSH_INFO.format(stack=stack_name), file=sys.stderr)
        return 1

    # NOTE: The exported path is the one the spawn wrote to, on whatever
    # machine ran it. Only the name of the key carries over, so that the
    # config points at the copy written here rather than at a directory that
    # exists on somebody else's machine.
    key = ssh_info.get("key")
    if key:
        ssh_info["key"] = str((args.directory / pathlib.Path(key).name).resolve())

    path = ssh_config.path_for(args.directory, stack_name)
    ssh_config.generate(ssh_info, path)
    print(f"Wrote {path}")
    print(f"      {ssh_config.bastion_path(path)}")
    print(f"      {path.with_name(ssh_config.LINK_NAME)} -> {path.name}")

    if not key:
        # NOTE: The stack was spawned on a key of its own, which it never held
        print("No key to bring back, the platform runs on one of your own")
        return 0

    if "ssh_private_key" not in outputs:
        print(KEY_MISSING.format(stack=stack_name), file=sys.stderr)
        return 1

    key_path = pathlib.Path(ssh_info["key"])
    _write_private(key_path, outputs["ssh_private_key"].value)
    key_path.with_suffix(".pub").write_text(outputs["ssh_public_key"].value)
    print(f"Wrote {key_path}")
    print(f"      {key_path.with_suffix('.pub')}")

    return 0


def _write_private(path: pathlib.Path, content: str) -> None:
    """
    Write a file nobody else can read, from the moment it exists.

    NOTE: Writing it and narrowing it afterwards leaves it readable by anyone
    on the machine in between, which for a private key is a window worth not
    having.
    """
    path.unlink(missing_ok=True)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as key_file:
        key_file.write(content)


def _parse_args() -> argparse.Namespace:
    """Read the command line."""
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--stack", default=None, help="stack to read (default: current)")
    parser.add_argument(
        "--directory",
        type=pathlib.Path,
        default=pathlib.Path.cwd(),
        help="where to write the files (default: here)",
    )

    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(__main__())
