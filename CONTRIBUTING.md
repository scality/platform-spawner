# Contributing to Platform Spawner

This document provides guidelines for contributing to the MetalK8s Core project.

## Project Layout

```text
├── __main__.py         # Entry point of the Pulumi program
├── providers           # Directory with all cloud providers specific logic
├── Pulumi.yaml         # Project metadata and template configuration
├── docs                # Documentation, beyond what the README holds
├── tools               # Directory with various development tools
├── tests               # Checks run against a platform once it is up
├── Pulumi.<stack>.yaml # Stack-specific configuration (e.g., Pulumi.dev.yaml)
└── pyproject.toml      # Python project configuration
```

## Development Setup

- Python 3.13+
- [Pulumi CLI](https://www.pulumi.com/docs/iac/download-install/)
- [uv](https://docs.astral.sh/uv/)
- [pre-commit](https://pre-commit.com/)

We recommend using the [devcontainer](https://code.visualstudio.com/docs/devcontainers/containers)
provided here that come with all necessary tools pre-installed.

## Tests

Every pull request spawns a platform on each provider, checks that the
machines answer SSH and that the bastion reaches the nodes on its own, then
destroys them. Two more platforms go up beside them on OpenStack: one asking
for everything at once, offline with extra networks and extra volumes, and one
that is snapshotted and spawned back from its images, carrying a file written
before the snapshot to prove it came back whole. That one takes its images
away afterwards, nothing else ever would.

Each of them is a workflow of its own carrying its spawn, its checks and its
destroy, so a platform goes away as soon as its own test is done rather than
waiting on the others. The end to end workflow only says which ones to run.
What is checked lives in `tests/`, and runs against a platform spawned by hand
just as well:

```bash
./tests/check_platform.sh
```

Whatever the jobs leave behind is picked up by the nightly garbage collection,
which needs to reach both clouds for the same reason. It collects stacks, not
snapshots: the snapshot test takes its images away itself, in a step that runs
whether the test passed or failed.

They run on the repository settings rather than on anything checked in: the
`OS_PASSWORD` secret, and the `OS_AUTH_URL`, `OS_USERNAME`, `OS_PROJECT_ID`,
`OS_PROJECT_NAME` and `OS_REGION` variables. Note that the last one is handed
to the tooling as `OS_REGION_NAME`, which is the name it reads, and that the
domain settings are not configured at all, being the same for every OVH
project.

## Update README

To update the README file with the latest Pulumi configuration, run:

```bash
tools/generate_docs.py
```

> **Note**
> This is automatically run by pre-commit on file changes.

## Run python linting and formatting

### Using pre-commit

```bash
pre-commit run --all-files
```

> **Note**
> To install pre-commit hooks, run:
>
> ```bash
> pre-commit install --install-hooks
> ```

### Using `ruff` with `uv`

```bash
uv run ruff check
uv run ruff format
```
