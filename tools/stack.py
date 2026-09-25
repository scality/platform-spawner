"""Reach the Pulumi stack a tool works beside."""

import os
import pathlib

from pulumi.automation import LocalWorkspace

# The tools sit one level under the project the stacks belong to
PROJECT_DIR = pathlib.Path(__file__).resolve().parent.parent
NO_STACK = "No stack to work on, name one with --stack"


def open_stack(name: str | None) -> tuple[LocalWorkspace, str]:
    """
    Return the workspace of the project, and the stack to work on.

    NOTE: The workspace goes through the Pulumi CLI like everything else, but
    it is the one asking for the flags and reading back what comes out, so a
    tool says what it wants rather than how to ask for it.

    An unset passphrase is taken for an empty one. Pulumi would rather refuse
    to open the stack than assume that, which is right of it and unhelpful
    here: these tools read a stack someone else spawned, and a spawn through
    the action leaves the passphrase empty.
    """
    if "PULUMI_CONFIG_PASSPHRASE_FILE" not in os.environ:
        os.environ.setdefault("PULUMI_CONFIG_PASSPHRASE", "")

    workspace = LocalWorkspace(work_dir=str(PROJECT_DIR))
    if name is not None:
        return workspace, name

    current = workspace.stack()
    if current is None:
        raise SystemExit(NO_STACK)

    return workspace, current.name
