#! /usr/bin/env bash
#
# Check that a platform is offline: the nodes cannot reach the internet, and
# the bastion still can.
#
# Run from wherever the generated ssh_config is, which is where the platform
# was spawned from.

set -euo pipefail

echo "The platform is offline"
if ssh -F ssh_config node-1 'timeout 15 curl -sS -o /dev/null https://1.1.1.1'; then
    echo "node-1 reached the internet, the platform is not offline" >&2
    exit 1
fi
# the very same reach, from the machine that is meant to have it
ssh -F ssh_config bastion 'timeout 15 curl -sS -o /dev/null https://1.1.1.1'
