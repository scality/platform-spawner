#! /usr/bin/env python3
"""Update README file based on comment <!-- BEGIN_PULUMI_DOCS -->."""

import pathlib
import re

import yaml

ROOT_DIR = pathlib.Path(__file__).parent.parent

PULUMI_CONFIG_FILE = ROOT_DIR / "Pulumi.yaml"
README_FILE = ROOT_DIR / "README.md"

BEGIN_MARKER = "<!-- BEGIN_PULUMI_DOCS -->"
END_MARKER = "<!-- END_PULUMI_DOCS -->"


def _compute_tab_content(pulumi_config: dict) -> str:
    tab_content = [
        "| Name | Description | Type | Default | Required |",
        "|------|-------------|------|---------|----------|",
    ]
    for key, values in (pulumi_config.get("config") or {}).items():
        name = key
        description = values.get("description", "")
        type_ = values.get("type", "")
        default = (
            "N/A" if values.get("default") is None else f"`{values.get('default')}`"
        )
        required = "yes" if values.get("default") is None else "no"

        tab_content.append(
            f"| {name} | {description} | {type_} | {default} | {required} |",
        )
    return "\n".join(tab_content)


def __main__() -> None:
    pulumi_config = yaml.safe_load(PULUMI_CONFIG_FILE.read_text(encoding="utf-8"))

    readme_content = README_FILE.read_text(encoding="utf-8")

    # Update README content based on Pulumi config
    readme_content = re.sub(
        f"{BEGIN_MARKER}.*{END_MARKER}",
        f"{BEGIN_MARKER}\n{_compute_tab_content(pulumi_config)}\n{END_MARKER}",
        readme_content,
        flags=re.DOTALL,
    )

    README_FILE.write_text(readme_content, encoding="utf-8")


if __name__ == "__main__":
    __main__()
