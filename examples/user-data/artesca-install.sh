#!/bin/bash
# Install ARTESCA from an ARTESCA AMI, on one node or three.
#
# Meant for `instance_user_data`. node-1 drives the install and reaches the
# other nodes with the key platform-spawner hands it once they have booted.
#
# NOTE: AWS has no layer 2 between the nodes and checks the source of every
# packet, so there are no virtual IPs and pods speak through IP-in-IP.
set -euo pipefail

# NOTE: The AMI expires the password of its user, and an expired password
# refuses SSH without a TTY to change it, keys included. Every node needs it
# lifted: platform-spawner waits on SSH, and node-1 drives the others with it.
# The AMI expires it from cloud-init, which started this script and may not
# have got there yet.
cloud-init status --wait >/dev/null || true
chage --lastday "$(date +%F)" "$SSH_USER"

[ "$NODE_INDEX" = 1 ] || exit 0

home=$(getent passwd "$SSH_USER" | cut -d: -f6)
key=/etc/metalk8s/pki/bastion

echo "Waiting for the nodes key"
until [ -s "$home/$NODES_KEY" ]; do sleep 10; done
install -D -m 600 "$home/$NODES_KEY" "$key"

nodes=()
for ip in $NODES_CONTROL_PLANE_IPS; do
    index=${ip##*.}
    index=$((index - 100))
    [ "$index" = 1 ] && continue

    echo "Waiting for node-$index ($ip)"
    until ssh -i "$key" -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
        "$SSH_USER@$ip" true; do
        sleep 10
    done
    nodes+=(--node "{name: node-$index, host: $ip, key: $key}")
done

if [ "$NODE_COUNT" = 1 ]; then
    architecture=(--architecture single-node)
else
    architecture=(
        --architecture 3-nodes
        --no-managed-management-vip
        --no-data-vip
    )
fi

cd "$home"
rm -f config.yaml
su "$SSH_USER" -c "$(printf '%q ' sudo ./artesca-installer config generate \
    --output config.yaml \
    "${architecture[@]}" \
    --profile demo \
    --use-case generic \
    --username scality \
    --base-domain workloadplane.scality.local \
    --local-node-name node-1 \
    --ipip-always \
    --workload-plane-cidr "$WORKLOAD_PLANE_CIDR" \
    --control-plane-cidr "$CONTROL_PLANE_CIDR" \
    --management-ip '' \
    "${nodes[@]}")"
su "$SSH_USER" -c "sudo ./artesca-installer config validate --config config.yaml"

echo "Configuration generated, deploying"
su "$SSH_USER" -c "sudo ./artesca-installer deploy --allow-unverified-raid -c config.yaml"
echo "Deployment finished"
