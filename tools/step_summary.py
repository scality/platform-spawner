"""Tell a CI job what a tool did, where it can show it."""

import os
import pathlib


def write(title: str, items: list[str]) -> None:
    """
    Add a section to the step summary of the job running this.

    NOTE: Silent outside a GitHub workflow, where the variable naming the file
    to write simply is not there. Nothing else in these tools knows about the
    CI and this only knows the one thing.
    """
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return

    lines = [f"### {title}", "", *(f"- `{item}`" for item in items), ""]
    with pathlib.Path(path).open("a") as summary:
        summary.write("\n".join(lines) + "\n")
