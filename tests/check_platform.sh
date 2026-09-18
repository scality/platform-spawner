#! /usr/bin/env bash
#
# Check that a spawned platform answers, from the outside and from within.
#
# Run from wherever the generated ssh_config is, which is where the platform
# was spawned from.

set -euo pipefail

mapfile -t nodes < <(awk '/^Host node-/ { print $2 }' ssh_config)
if [ "${#nodes[@]}" -eq 0 ]; then
    echo "No node in ssh_config, was anything spawned?" >&2
    exit 1
fi

echo "Reaching every machine"
ssh -F ssh_config bastion hostname
for node in "${nodes[@]}"; do
    ssh -F ssh_config "$node" hostname
done

# The bastion is handed a key and a config of its own, so it reaches the nodes
# without the one that opens the platform ever leaving for it.
#
# NOTE: The list is spelled out as one line, `${nodes[*]}` rather than one name
# per line, or the loop reaches the remote shell split across lines and is read
# as several commands.
echo "Reaching the nodes from the bastion"
ssh -F ssh_config bastion "
    set -eu
    for node in ${nodes[*]}; do
        ssh -F ssh_config \"\$node\" hostname
    done
"
