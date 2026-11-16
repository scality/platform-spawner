#! /usr/bin/env bash
#
# Check that the bastion serves the nodes what they were spawned to get from
# it: names resolved through it (`bastion_dns`) and dnf going through its
# proxy (`bastion_dnf_proxy`).
#
# Run from wherever the generated ssh_config is, which is where the platform
# was spawned from.

set -euo pipefail

mapfile -t nodes < <(awk '/^Host node-/ { print $2 }' ssh_config)
if [ "${#nodes[@]}" -eq 0 ]; then
    echo "No node in ssh_config, was anything spawned?" >&2
    exit 1
fi

for node in "${nodes[@]}"; do
    echo "$node resolves names through the bastion"
    ssh -F ssh_config "$node" '
        set -eu
        grep -qx "nameserver 172.30.100.99" /etc/resolv.conf
        getent hosts github.com
    '

    echo "dnf on $node goes through the bastion"
    ssh -F ssh_config "$node" '
        set -eu
        grep -qx "proxy=http://172.30.100.99:3128" /etc/dnf/dnf.conf
        sudo dnf -q makecache --refresh
    '
done
