# platform-spawner

This is a **Pulumi program, written in Python, that spawns test platforms** on
AWS EC2 or on OpenStack (OVH Public Cloud). A platform is one bastion, a
handful of nodes and three networks, at addresses that are the same on every
platform. It is also published as a **composite GitHub Action** that other
Scality repositories call to spawn, update, snapshot and destroy platforms
from their CI.

It contains:

- The Pulumi entry point (`__main__.py`) and the stack configuration schema
  (`Pulumi.yaml`)
- One provider per cloud behind a common interface (`providers/base.py`,
  `providers/aws.py`, `providers/openstack.py`)
- Command line tools run by the action, some of them calling the OpenStack API
  directly through `openstacksdk` (`tools/`)
- Shell checks run against a live platform (`tests/`)
- The composite action (`action.yaml`) and the CI that spawns real platforms
  on both clouds on every pull request (`.github/workflows/`)
- Design notes and user documentation (`DESIGN.md`, `docs/`)

Tooling: Python 3.13 managed with `uv`, `ruff` with every rule enabled,
`pre-commit` running `yamllint`, `actionlint` and `tools/generate_docs.py`.
The configuration table in `README.md` is generated from `Pulumi.yaml`.

The repository is public.
