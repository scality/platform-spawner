#! /usr/bin/env python3
"""
Merge configuration keys, read as YAML on stdin, into the file of a stack.

A live platform is updated on the configuration it was last deployed with,
plus whatever it is handed. The keys go straight into the file rather than
through `pulumi config set`. That command takes a string, sets a list or an
object one leaf at a time, and has no way to say that a list is now empty.
"""

import argparse
import pathlib
import sys

import yaml

PROJECT_FILE = pathlib.Path(__file__).resolve().parent.parent / "Pulumi.yaml"
NOT_A_MAPPING = "The configuration must be a mapping of keys to values."


def __main__() -> int:
    """Merge the keys read on stdin into the file of a stack."""
    args = _parse_args()

    keys = yaml.safe_load(sys.stdin) or {}
    if not isinstance(keys, dict):
        print(NOT_A_MAPPING, file=sys.stderr)
        return 1

    project = yaml.safe_load(PROJECT_FILE.read_text(encoding="utf-8"))["name"]
    content = {}
    if args.stack_file.exists():
        content = yaml.safe_load(args.stack_file.read_text(encoding="utf-8")) or {}
    config = content.get("config") or {}

    merged = {}
    for key, value in keys.items():
        # NOTE: A key of the project can be spelled with or without its
        # namespace, and Pulumi refuses a file holding both spellings. The
        # one it writes itself is the namespaced one, so that is the one kept.
        name = key.removeprefix(f"{project}:")
        if ":" not in name:
            config.pop(name, None)
            name = f"{project}:{name}"

        merged[name] = value

    config.update(merged)
    print(yaml.safe_dump(merged, sort_keys=False), end="")

    content["config"] = config
    args.stack_file.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")

    return 0


def _parse_args() -> argparse.Namespace:
    """Read the command line."""
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("stack_file", type=pathlib.Path, help="file of the stack to merge into")

    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(__main__())
