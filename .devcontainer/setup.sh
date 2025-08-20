#!/bin/bash

set -xe

echo "Install pre-commit hooks"
pre-commit install --install-hooks

echo "End of setup"
