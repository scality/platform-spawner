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

## Update README

To update the README file with the latest Pulumi configuration, run:

```bash
tools/generate_docs.py
```
