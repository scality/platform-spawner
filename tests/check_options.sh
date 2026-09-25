#! /usr/bin/env bash
#
# Check a platform spawned with everything at once: offline, extra networks
# and extra volumes.
#
# Run from wherever the generated ssh_config is, which is where the platform
# was spawned from.

set -euo pipefail

echo "Extra networks are addressed as they should"
# storage is the first one asked for, bonded the second and redundant
ssh -F ssh_config node-1 '
    set -eu
    ip -brief -4 addr show | grep -q "172.30.1.101/24"
    ip -brief -4 addr show | grep -q "172.30.2.101/24"
    ip -brief -4 addr show | grep -q "172.30.2.201/24"
'
ssh -F ssh_config bastion '
    set -eu
    # the bastion sits on them once, whatever redundant says
    ip -brief -4 addr show | grep -q "172.30.1.99/24"
    ip -brief -4 addr show | grep -q "172.30.2.99/24"
    ! ip -brief -4 addr show | grep -q "172.30.2.199/24"
'

echo "Extra volumes are attached"
disks=$(ssh -F ssh_config node-1 'lsblk --nodeps --noheadings --output TYPE | grep -c disk')
echo "  node-1 carries $disks disk(s)"
# the one it boots on, plus the two asked for
[ "$disks" -eq 3 ]

echo "The platform is offline"
if ssh -F ssh_config node-1 'timeout 15 curl -sS -o /dev/null https://1.1.1.1'; then
    echo "node-1 reached the internet, the platform is not offline" >&2
    exit 1
fi
# the very same reach, from the machine that is meant to have it
ssh -F ssh_config bastion 'timeout 15 curl -sS -o /dev/null https://1.1.1.1'
