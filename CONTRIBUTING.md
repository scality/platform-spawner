# Contributing to Platform Spawner

This document provides guidelines for contributing to the MetalK8s Core project.

## Project Layout

```text
├── __main__.py         # Entry point of the Pulumi program
├── providers           # Directory with all cloud providers specific logic
├── Pulumi.yaml         # Project metadata and template configuration
├── tools               # Directory with various development tools
├── Pulumi.<stack>.yaml # Stack-specific configuration (e.g., Pulumi.dev.yaml)
└── pyproject.toml      # Python project configuration
```

## Development Setup

- Python 3.13+
- [Pulumi CLI](https://www.pulumi.com/docs/iac/download-install/)
- [uv](https://docs.astral.sh/uv/)
- [pre-commit](https://pre-commit.com/)

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
