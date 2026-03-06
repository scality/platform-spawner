"""
Scaleway cluster implementation.

This module orchestrates the deployment of complete clusters
on Scaleway infrastructure with any number of worker nodes.

A bastion VM provides SSH access and NAT functionality for accessing
and providing internet connectivity to private worker nodes.
"""

from typing import Any, Dict, List

import yaml
import pulumi
import pulumiverse_scaleway as scaleway

from core.interfaces import ClusterInterface
from core.models import ClusterConfig, NodeConfig
from config.flavors import get_instance_type
from config.defaults import DEFAULT_BASTION_USERS  ### TODO move it to main
from .network import ScalewayNetwork
from .compute import ScalewayCompute

# ---------------------------------------------------------------------------
# Cloud-init helpers
# ---------------------------------------------------------------------------


class _LiteralScalar(str):
    """String subclass that serialises as a YAML literal block scalar (|)."""


class _CloudConfigDumper(yaml.SafeDumper):
    """YAML dumper that renders _LiteralScalar instances with | style."""


_CloudConfigDumper.add_representer(
    _LiteralScalar,
    lambda dumper, data: dumper.represent_scalar(
        "tag:yaml.org,2002:str", data, style="|"
    ),
)


def _to_cloud_config(data: dict) -> str:
    """Serialize *data* to a ``#cloud-config`` YAML string."""
    return "#cloud-config\n" + yaml.dump(
        data, Dumper=_CloudConfigDumper, default_flow_style=False, sort_keys=False
    )


# ---------------------------------------------------------------------------
# Scaleway VPC route-fix — defense in depth
# ---------------------------------------------------------------------------
# Problem: Scaleway DHCP pushes classless static routes (option 121) for
# every private network in the VPC to every interface.  Because the DHCP
# cross-routes can have LOWER metrics than the kernel directly-connected
# routes, traffic takes wrong paths:
#
#   192.168.30.0/24 via 169.254.169.254 dev eth1 proto dhcp metric 50  ← WRONG
#   192.168.30.0/24 dev eth2 proto kernel metric 102                   ← correct
#
# Strategy (defense in depth):
#   Layer 0 — Disable scw-net-reconfig: Stop Scaleway's hot-reconfig agent
#   Layer 1 — NM conf.d:   Aspirational — ignored by current NM versions
#   Layer 2 — NM dispatcher: Clean routes on private iface up/DHCP change
#   Layer 3 — Retroactive runcmd: Fix already-active private connections
#
# The Scaleway VM agent (scaleway-vmagent) + scw-net-reconfig.path/.service
# continuously re-apply DHCP configuration on private interfaces, undoing
# our fixes.  Layer 0 masks the reconfig service to prevent interference.
# See: scaleway.com/en/docs/instances/reference-content/
#      understanding-automatic-network-hot-reconfiguration/
#
# IMPORTANT: eth0 is the public interface (Scaleway uses net.ifnames=0).
# ipv4.ignore-auto-routes suppresses ALL DHCP routes INCLUDING the default
# gateway (option 3), so it MUST NOT be applied to eth0 or the instance
# loses internet connectivity and SSH access.
# ---------------------------------------------------------------------------

# Layer 1 — NetworkManager connection defaults (aspirational)
# NM only supports a limited set of properties as [connection] defaults:
# route-metric, may-fail, link-local, etc.  ipv4.ignore-auto-routes is
# NOT in the supported set, so this has NO real effect today.  We keep
# it as documentation and for forward-compatibility if NM adds support.
_VPC_NM_CONF = """\
# Aspirational: suppress DHCP classless static routes (option 121).
# Currently ignored by NM (not a supported [connection] default).
# The NM dispatcher (Layer 2) is the actual enforcement mechanism.
[connection]
ipv4.ignore-auto-routes=1
ipv6.ignore-auto-routes=1
"""

_VPC_NM_CONF_WRITE_FILE = {
    "path": "/etc/NetworkManager/conf.d/90-scaleway-vpc.conf",
    "content": _LiteralScalar(_VPC_NM_CONF),
    "owner": "root:root",
    "permissions": "0644",
}

# Layer 2 — NetworkManager dispatcher script (primary defense)
# Fires on every up/dhcp4-change event for PRIVATE interfaces only.
# eth0 is skipped — its DHCP routes include the default gateway which we
# must not suppress (ignore-auto-routes kills ALL DHCP routes including
# the default gw from option 3, not just classless statics from option 121).
#
# nmcli connection modify changes the on-disk profile.
# device reapply is NOT sufficient for ipv4.ignore-auto-routes — a full
# connection down/up cycle is required so NM re-reads the profile and
# does not install DHCP routes.  An idempotency guard prevents the
# down/up from triggering an infinite dispatcher loop.
_VPC_ROUTE_FIX_DISPATCHER = """\
#!/bin/bash
# /etc/NetworkManager/dispatcher.d/10-scaleway-vpc-routes
# Installed by platform-spawner cloud-init.
# Suppresses DHCP cross-network routes on private interfaces only.

case "$2" in
    up|dhcp4-change) ;;
    *) exit 0 ;;
esac

IFACE="$1"
[ "$IFACE" = "lo" ] && exit 0
[ "$IFACE" = "eth0" ] && exit 0   # Public interface — keep its default route
[ -z "$CONNECTION_UUID" ] && exit 0

# Idempotency guard: skip if already configured (prevents down/up loop).
current=$(nmcli -g ipv4.ignore-auto-routes connection show "$CONNECTION_UUID" 2>/dev/null)
[ "$current" = "yes" ] && exit 0

# Suppress DHCP routes and IPv6 on this private interface.
nmcli connection modify "$CONNECTION_UUID" \\
    ipv4.ignore-auto-routes yes \\
    ipv4.ignore-auto-dns yes \\
    ipv6.ignore-auto-routes yes \\
    ipv6.ignore-auto-dns yes \\
    ipv6.method disabled 2>/dev/null || true

# Full reconnect: device reapply is not sufficient for ignore-auto-routes.
# The down/up cycle makes NM re-read the profile and honour the setting
# from the start of DHCP negotiation, so cross-routes are never installed.
nmcli connection down "$CONNECTION_UUID" 2>/dev/null || true
nmcli connection up "$CONNECTION_UUID" 2>/dev/null || true

# Restore Scaleway metadata route (killed by ignore-auto-routes).
# 169.254.42.42 is the Scaleway metadata API used by cloud-init datasource.
ip route replace 169.254.42.42/32 dev "$IFACE" scope link 2>/dev/null || true
"""

_VPC_ROUTE_FIX_WRITE_FILE = {
    "path": "/etc/NetworkManager/dispatcher.d/10-scaleway-vpc-routes",
    "permissions": "0755",
    "owner": "root:root",
    "content": _LiteralScalar(_VPC_ROUTE_FIX_DISPATCHER),
}

# Layer 0 — Disable Scaleway automatic network hot-reconfiguration
# The scw-net-reconfig.path watches for network config changes and
# scw-net-reconfig.service re-applies DHCP routes (including cross-
# network routes), undoing our ignore-auto-routes=yes fix.
# Masking prevents any unit from starting these services again.
_DISABLE_SCW_NET_RECONFIG = """\
# Disable Scaleway network hot-reconfiguration agent.
# It conflicts with our NM dispatcher by re-applying DHCP cross-routes.
systemctl stop scw-net-reconfig.path scw-net-reconfig.service 2>/dev/null || true
systemctl mask scw-net-reconfig.path scw-net-reconfig.service 2>/dev/null || true
"""

# Layer 3 — Retroactive fix for private connections active at cloud-init time
# Scaleway may hot-plug NICs before or after cloud-init runs.  A full NM
# restart ensures our dispatcher script is loaded and fires on every
# connection that comes up.  The loop afterwards is belt-and-suspenders
# for any connection the dispatcher might have missed.
_VPC_ROUTE_FIX_RETROACTIVE = """\
# Full restart so NM picks up our dispatcher + conf.d (reload is not enough).
systemctl restart NetworkManager 2>/dev/null || true
sleep 10  # wait for NM to re-establish connections

for uuid in $(nmcli -t -f UUID connection show --active 2>/dev/null); do
    device=$(nmcli -g GENERAL.DEVICE connection show "$uuid" 2>/dev/null)
    [ -z "$device" ] || [ "$device" = "lo" ] && continue
    [ "$device" = "eth0" ] && continue   # Public interface — keep its routes
    current=$(nmcli -g ipv4.ignore-auto-routes connection show "$uuid" 2>/dev/null)
    [ "$current" = "yes" ] && continue   # Already fixed by dispatcher
    nmcli connection modify "$uuid" \\
        ipv4.ignore-auto-routes yes \\
        ipv4.ignore-auto-dns yes \\
        ipv6.ignore-auto-routes yes \\
        ipv6.ignore-auto-dns yes \\
        ipv6.method disabled 2>/dev/null || true
    nmcli connection down "$uuid" 2>/dev/null || true
    nmcli connection up "$uuid" 2>/dev/null || true
    ip route replace 169.254.42.42/32 dev "$device" scope link 2>/dev/null || true
done
"""

# ---------------------------------------------------------------------------
# Bastion NAT configuration
# ---------------------------------------------------------------------------
# Install iptables first, then configure NAT, then persist rules for reboots.
_BASTION_NAT_SETUP = """\
# Install iptables if not present (Rocky 9 ships without it)
if ! command -v iptables &>/dev/null; then
    dnf install -y iptables-nft 2>/dev/null || \\
    yum install -y iptables-nft 2>/dev/null || \\
    apt-get install -y iptables 2>/dev/null || true
fi

# Configure NAT masquerading
iptables -t nat -C POSTROUTING -o eth0 -j MASQUERADE 2>/dev/null || \\
    iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
iptables -P FORWARD ACCEPT

# Persist iptables rules across reboots (RHEL/Rocky or Debian/Ubuntu)
if command -v dnf &>/dev/null || command -v yum &>/dev/null; then
    dnf install -y iptables-services 2>/dev/null || yum install -y iptables-services 2>/dev/null || true
    systemctl enable iptables 2>/dev/null || true
    service iptables save 2>/dev/null || true
elif command -v apt-get &>/dev/null; then
    DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent 2>/dev/null || true
    netfilter-persistent save 2>/dev/null || true
fi
"""

# ---------------------------------------------------------------------------
# Bastion NTP server (chrony)
# ---------------------------------------------------------------------------
# The bastion acts as the NTP server for all worker nodes.
# Workers point their chrony to the bastion's private IP.
_BASTION_CHRONY_CONF = """\
pool pool.ntp.org iburst
local stratum 10
allow 192.168.0.0/16
makestep 1.0 3
rtcsync
leapsectz right/UTC
driftfile /var/lib/chrony/drift
keyfile /etc/chrony.keys
logdir /var/log/chrony
"""

_BASTION_NTP_SETUP = """\
command -v chronyd &>/dev/null || dnf install -y chrony

if systemctl is-active firewalld &>/dev/null; then
  firewall-cmd --permanent --add-service=ntp || true
  firewall-cmd --reload || true
fi

systemctl enable --now chronyd
systemctl restart chronyd

for i in $(seq 1 10); do
  chronyc waitsync 1 0.1 0 0 -t 10 &>/dev/null && { chronyc sources; break; }
  [ "$i" -eq 10 ] && { chronyc burst 1/1; sleep 5; chronyc makestep; chronyc sources; } || sleep 5
done
echo "cloud-init: bastion NTP server configured"
"""

# ---------------------------------------------------------------------------
# Bastion DNS resolver (dnsmasq)
# ---------------------------------------------------------------------------
# The bastion runs dnsmasq to provide DNS resolution for all worker nodes.
# It captures upstream DNS servers before overwriting resolv.conf.
_BASTION_DNS_SETUP = """\
command -v dnsmasq &>/dev/null || dnf install -y dnsmasq bind-utils

# Capture upstream DNS before we overwrite resolv.conf
UPSTREAM=$(grep -E '^nameserver' /etc/resolv.conf | awk '{print $2}' | grep -v '127.0.0.1' | head -3)
[ -z "$UPSTREAM" ] && UPSTREAM="1.1.1.1 8.8.8.8"

cat > /etc/dnsmasq.conf <<CONF
bind-dynamic
no-resolv
no-hosts
cache-size=1000
domain-needed
bogus-priv
CONF

for dns in $UPSTREAM; do echo "server=$dns" >> /etc/dnsmasq.conf; done

if systemctl is-active firewalld &>/dev/null; then
  firewall-cmd --permanent --add-service=dns || true
  firewall-cmd --reload || true
fi

systemctl enable --now dnsmasq
systemctl restart dnsmasq

# Prevent NetworkManager from overwriting resolv.conf
if systemctl is-active NetworkManager &>/dev/null; then
  mkdir -p /etc/NetworkManager/conf.d
  printf '[main]\ndns=none\n' > /etc/NetworkManager/conf.d/90-dns-none.conf
  systemctl reload NetworkManager
fi

# Point bastion itself to local dnsmasq
printf 'nameserver 127.0.0.1\n' > /etc/resolv.conf

dig @127.0.0.1 pool.ntp.org +short +timeout=5 &>/dev/null \\
  && echo "cloud-init: dnsmasq working" \\
  || echo "cloud-init: DNS test failed (may succeed later)"
"""

# ---------------------------------------------------------------------------
# Cloud-init configurations (dicts serialised at point of use)
# ---------------------------------------------------------------------------

# VPC route fix data (for worker nodes — merged with SSH user_data)
_SCALEWAY_VPC_FIX_DATA: Dict[str, Any] = {
    "write_files": [_VPC_NM_CONF_WRITE_FILE, _VPC_ROUTE_FIX_WRITE_FILE],
    "runcmd": [
        _LiteralScalar(_DISABLE_SCW_NET_RECONFIG),
        _LiteralScalar(_VPC_ROUTE_FIX_RETROACTIVE),
    ],
}

# Bastion: IP forwarding + NAT + VPC route fix + NTP server + DNS resolver
BASTION_NAT_CLOUDINIT = _to_cloud_config(
    {
        "write_files": [
            {
                "path": "/etc/sysctl.d/99-ip-forward.conf",
                "content": _LiteralScalar("net.ipv4.ip_forward = 1\n"),
                "owner": "root:root",
                "permissions": "0644",
            },
            {
                "path": "/etc/chrony.conf",
                "content": _LiteralScalar(_BASTION_CHRONY_CONF),
                "owner": "root:root",
                "permissions": "0644",
            },
            _VPC_NM_CONF_WRITE_FILE,
            _VPC_ROUTE_FIX_WRITE_FILE,
        ],
        "runcmd": [
            "sysctl -p /etc/sysctl.d/99-ip-forward.conf",
            _LiteralScalar(_DISABLE_SCW_NET_RECONFIG),
            _LiteralScalar(_VPC_ROUTE_FIX_RETROACTIVE),
            _LiteralScalar(_BASTION_NAT_SETUP),
            _LiteralScalar(_BASTION_NTP_SETUP),
            _LiteralScalar(_BASTION_DNS_SETUP),
        ],
    }
)


def _node_ntp_dns_cloud_config(bastion_ip: str) -> dict:
    """Return a cloud-config *dict* that configures a worker node to use
    the bastion as its NTP server (chrony) and DNS resolver.

    Args:
        bastion_ip: The bastion's private IPv4 address.
    """
    chrony_conf = f"""\
server {bastion_ip} iburst
makestep 1.0 3
maxdistance 16.0
rtcsync
leapsectz right/UTC
driftfile /var/lib/chrony/drift
keyfile /etc/chrony.keys
logdir /var/log/chrony
"""

    dns_and_ntp_setup = f"""\
# --- DNS: point to bastion ---
if systemctl is-active NetworkManager &>/dev/null; then
  mkdir -p /etc/NetworkManager/conf.d
  printf '[main]\\ndns=none\\n' > /etc/NetworkManager/conf.d/90-dns-none.conf
  systemctl reload NetworkManager
fi
printf 'nameserver {bastion_ip}\\n' > /etc/resolv.conf

for i in $(seq 1 5); do
  dig @{bastion_ip} pool.ntp.org +short +timeout=5 &>/dev/null \
    && {{ echo "cloud-init: DNS OK"; break; }}
  [ "$i" -eq 5 ] && echo "cloud-init: DNS test failed" || sleep 3
done

# --- NTP: point to bastion ---
command -v chronyd &>/dev/null || dnf install -y chrony
systemctl enable --now chronyd
systemctl restart chronyd

for i in $(seq 1 10); do
  chronyc waitsync 1 0.1 0 0 -t 10 &>/dev/null && {{ chronyc sources; break; }}
  [ "$i" -eq 10 ] && {{ chronyc burst 1/1; sleep 5; chronyc makestep; chronyc sources; }} || sleep 5
done
"""

    return {
        "write_files": [
            {
                "path": "/etc/chrony.conf",
                "content": _LiteralScalar(chrony_conf),
                "owner": "root:root",
                "permissions": "0644",
            },
        ],
        "runcmd": [
            _LiteralScalar(dns_and_ntp_setup),
        ],
    }


def _merge_cloud_config(base: dict, extra_user_data: str | None = None) -> str:
    """Merge *base* cloud-config dict with an optional YAML user-data string.

    List-valued keys (``write_files``, ``runcmd``, ...) are concatenated;
    everything else is taken from *extra_user_data* when present.
    """
    if not extra_user_data:
        return _to_cloud_config(base)
    text = extra_user_data
    if text.startswith("#cloud-config"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
    extra = yaml.safe_load(text) or {}
    merged = dict(base)
    for key, value in extra.items():
        if key in merged and isinstance(merged[key], list) and isinstance(value, list):
            merged[key] = list(merged[key]) + value
        else:
            merged[key] = value
    return _to_cloud_config(merged)


class ScalewayCluster(ClusterInterface):
    """
    Scaleway-specific cluster implementation.

    Orchestrates network and compute resources to deploy clusters
    with any number of worker nodes. All worker nodes are on a private
    network and accessed via a bastion VM that also provides NAT.
    """

    def __init__(self, config: ClusterConfig):
        """
        Initialize Scaleway cluster deployer.

        Args:
            config: Cluster configuration
        """
        super().__init__(config)
        self.network = ScalewayNetwork(config)
        self.compute = ScalewayCompute(config)

    def register_ssh_keys(self, ssh_keys: List[str]) -> List[str]:
        """
        Register SSH public keys in Scaleway IAM.

        Creates IAM SSH keys that will be available for instances
        and the bastion VM.

        Args:
            ssh_keys: List of SSH public key strings to register

        Returns:
            List of registered key IDs
        """
        if not ssh_keys:
            return []

        key_ids = []
        # Include product name in IAM key name for better identification
        if self.config.product and self.config.product != "unknown":
            key_prefix = self.config.product
        else:
            key_prefix = "platform-spawner"

        for idx, key in enumerate(ssh_keys):
            iam_key = scaleway.iam.SshKey(
                f"ssh-key-{idx+1}",
                public_key=key,
                name=f"{key_prefix}-key-{idx+1}",
                project_id=self.config.project_id,
            )
            key_ids.append(iam_key.id)

        pulumi.log.info(f"Registered {len(key_ids)} SSH keys in Scaleway IAM")
        return key_ids

    def deploy_cluster(self) -> Dict[str, Any]:
        """
        Deploy a cluster with the configured number of instances.

        Creates:
        - VPC and Private Network
        - Bastion VM (SSH jump host + NAT gateway)
        - Security Groups (bastion, first-node, internal)
        - N Instance Nodes (private only, accessed via bastion)

        Returns:
            Dictionary with deployment outputs
        """
        # Get node configurations
        nodes_by_role = self._organize_nodes_by_role()

        # Get instance images
        instance_image = self.compute.get_worker_image()
        bastion_image = self.compute.get_bastion_os_image()

        # Create network infrastructure (VPC + Private Network, no gateway)
        network_output = self.network.create_full_network()

        # Collect extra private network subnets for security group rules
        extra_subnets = [nc.subnet for nc in self.config.extra_private_networks]

        # Create security groups
        # Bastion: SSH access from allowed CIDRs + restricted outbound (NAT to update servers only)
        sg_bastion = self.compute.create_bastion_security_group(
            allowed_cidrs=self.config.network.allowed_ips,
            private_subnet=self.config.network.private_subnet,
            restrict_outbound=True,  # Restrict NAT to DNS and HTTPS only
            extra_subnets=extra_subnets,
        )
        # All worker nodes use internal security group (private network access only)
        sg_internal = self.compute.create_internal_security_group(
            private_subnet=self.config.network.private_subnet,
            extra_subnets=extra_subnets,
        )

        # Create placement group for co-locating all instances
        pg_name = (
            f"{self.config.product}-pg" if self.config.product else "placement-group"
        )
        placement_group = self.compute.create_placement_group(
            name=pg_name, policy_mode=self.config.placement_group_policy_mode
        )

        # Build extra networks info for outputs
        extra_networks_info = {}
        for suffix, extra_net in self.network.extra_private_networks.items():
            # Find the subnet from config
            net_config = next(
                (
                    nc
                    for nc in self.config.extra_private_networks
                    if nc.suffix == suffix
                ),
                None,
            )
            extra_networks_info[suffix] = {
                "id": extra_net.id,
                "subnet": net_config.subnet if net_config else "unknown",
            }

        # Deploy bastion VM first (provides SSH access + NAT for worker nodes)
        bastion_name = (
            f"{self.config.product}-bastion" if self.config.product else "bastion"
        )
        bastion_instance_type = get_instance_type(
            self.config.provider, self.config.bastion_flavor
        )
        bastion_config = NodeConfig(
            name=bastion_name,
            role="bastion",
            instance_type=bastion_instance_type,
            tags=["bastion", "nat-gateway", "managed-by:pulumi"],
            user_data=BASTION_NAT_CLOUDINIT,
            root_volume_size_gb=self.config.bastion_root_disk_size,
        )
        bastion = self._deploy_bastion_node(
            node_config=bastion_config,
            image_id=bastion_image,
            security_group=sg_bastion,
            placement_group_id=placement_group.id,
        )
        pulumi.log.info(f"Deployed bastion VM: {bastion_name}")
        pulumi.log.info(
            "VPC route fix: NM dispatcher will be deployed via cloud-init "
            "on all instances to prevent DHCP cross-network route conflicts"
        )

        # Initialize outputs
        outputs = {
            "instance_count": self.config.instance_count,
            "network": {
                "vpc_id": network_output.vpc_id,
                "private_network_id": network_output.private_network_id,
                "subnet": network_output.subnet,
                "extra_networks": extra_networks_info,
            },
            "nodes": {},
            "bastion": {
                "type": "vm",
                "ip": bastion["node_output"].public_ip,
                "private_ip": bastion["node_output"].private_ip,
                "port": 22,
                "user": DEFAULT_BASTION_USERS.get(self.config.bastion_os_name, "rocky"),
                "instance_id": bastion["node_output"].id,
                "extra_nics": {
                    suffix: {
                        "private_ip": extra_nic.private_ips.apply(
                            lambda ips: (
                                next(
                                    (ip.address for ip in ips if ":" not in ip.address),
                                    None,
                                )
                                if ips
                                else None
                            )
                        ),
                    }
                    for suffix, extra_nic in bastion["extra_nics"].items()
                },
            },
        }

        # Deploy instance nodes (private only, accessed via bastion)
        bastion_private_ip = bastion["node_output"].private_ip
        if "node" in nodes_by_role:
            for node_config in nodes_by_role["node"]:
                # Inject VPC route fix into worker cloud-init to prevent
                # cross-network DHCP route conflicts on multi-homed nodes.
                base_user_data = _merge_cloud_config(
                    _SCALEWAY_VPC_FIX_DATA, node_config.user_data
                )

                # Build final user_data as a Pulumi Output that includes
                # DNS + NTP configuration pointing to the bastion.
                node_config.user_data = bastion_private_ip.apply(
                    lambda ip, _base=base_user_data: _merge_cloud_config(
                        _node_ntp_dns_cloud_config(ip), _base
                    )
                )

                # All nodes use internal security group
                # Outbound restrictions are handled by the bastion's NAT
                node = self._deploy_internal_node(
                    node_config=node_config,
                    image_id=instance_image,
                    security_group=sg_internal,
                    placement_group_id=placement_group.id,
                )

                # Generate SSH jump command for accessing the node via bastion
                # Use bastion's public IP and private IP of the node
                ssh_command = pulumi.Output.all(
                    bastion["node_output"].public_ip, node["node_output"].private_ip
                ).apply(
                    lambda args, name=node_config.name: (
                        f"ssh -J rocky@{args[0]} artesca-os@{args[1]}"
                    )
                )

                # Prepare volume information if volumes exist
                volumes_info = []
                if node.get("volumes"):
                    for vol_data in node["volumes"]:
                        volumes_info.append(
                            {
                                "id": vol_data["resource"].id,
                                "urn": vol_data["resource"].urn,
                                "name": vol_data["resource"].name,
                                "size_gb": vol_data["size_gb"],
                            }
                        )

                # Prepare extra NICs information if extra networks were attached
                extra_nics_info = {}
                if node.get("extra_nics"):
                    for suffix, extra_nic in node["extra_nics"].items():
                        # Get the private IP from the extra NIC (filter out IPv6)
                        extra_nics_info[suffix] = {
                            "private_ip": extra_nic.private_ips.apply(
                                lambda ips: (
                                    next(
                                        (
                                            ip.address
                                            for ip in ips
                                            if ":" not in ip.address
                                        ),
                                        None,
                                    )
                                    if ips
                                    else None
                                )
                            ),
                        }

                outputs["nodes"][node_config.name] = {
                    "id": node["node_output"].id,
                    "name": node_config.name,
                    "instance_type": node_config.instance_type,
                    "private_ip": node["node_output"].private_ip,
                    "ssh_command": ssh_command,
                    "urn": node["instance"].urn,
                    "volumes": volumes_info,
                    "extra_nics": extra_nics_info,
                }

        return outputs

    def _organize_nodes_by_role(self) -> Dict[str, List[NodeConfig]]:
        """
        Organize node configurations by role for easier processing.

        Returns:
            Dictionary mapping role names to lists of node configs
        """
        nodes_by_role: Dict[str, List[NodeConfig]] = {}
        for node in self.config.nodes:
            if node.role not in nodes_by_role:
                nodes_by_role[node.role] = []
            nodes_by_role[node.role].append(node)
        return nodes_by_role

    def _deploy_internal_node(
        self,
        node_config: NodeConfig,
        image_id: str,
        security_group: Any,
        placement_group_id: Any = None,
    ) -> Dict[str, Any]:
        """
        Deploy an internal node (private network only).

        Creates an instance and attaches it to the private network(s).
        Also creates and attaches additional volumes if configured.

        Args:
            node_config: Node configuration
            image_id: OS image ID
            security_group: Security group resource

        Returns:
            Dictionary with instance, volumes, NIC, and extra_nics resources
        """
        # Create extra volumes for instance nodes only (not bastion)
        volume_ids = []
        volumes = []
        if node_config.role == "node" and self.config.extra_volumes:
            for vol_config in self.config.extra_volumes:
                # Create 'count' volumes for this configuration
                for i in range(vol_config.count):
                    # Generate unique volume name
                    if vol_config.count == 1:
                        volume_name = f"{node_config.name}-{vol_config.suffix}"
                    else:
                        volume_name = (
                            f"{node_config.name}-{vol_config.suffix}-{i+1:02d}"
                        )

                    # Create the volume
                    volume = self.compute.create_volume(
                        name=volume_name,
                        size_gb=vol_config.size,
                    )
                    # Store volume with metadata for later reference
                    volumes.append(
                        {
                            "resource": volume,
                            "size_gb": vol_config.size,
                        }
                    )
                    volume_ids.append(volume.id)

        # Create instance without public IP (private only)
        instance_output = self.compute.create_instance(
            name=node_config.name,
            image=image_id,
            instance_type=node_config.instance_type,
            security_group=security_group,
            tags=node_config.tags,
            user_data=node_config.user_data,
            create_public_ip=False,  # Private only, no public IP
            additional_volume_ids=volume_ids if volume_ids else None,
            root_volume_size_gb=node_config.root_volume_size_gb,
            placement_group_id=placement_group_id,
        )

        # Attach to primary private network
        nic = self.compute.attach_to_private_network(
            instance=instance_output.resource,
            network=self.network.private_network,
            instance_name=node_config.name,
        )

        # Attach to extra private networks if configured (for multi-homed instances)
        extra_nics = {}
        if node_config.role == "node" and self.config.extra_private_networks:
            for net_config in self.config.extra_private_networks:
                extra_network = self.network.extra_private_networks.get(
                    net_config.suffix
                )
                if extra_network:
                    extra_nic = self.compute.attach_to_private_network(
                        instance=instance_output.resource,
                        network=extra_network,
                        instance_name=f"{node_config.name}-{net_config.suffix}",
                    )
                    extra_nics[net_config.suffix] = extra_nic

        # Update node_output with private IPv4 address from NIC (filter out IPv6)
        # IPv4 addresses don't contain ':' character, IPv6 do
        instance_output.private_ip = nic.private_ips.apply(
            lambda ips: (
                next((ip.address for ip in ips if ":" not in ip.address), None)
                if ips
                else None
            )
        )

        return {
            "instance": instance_output.resource,
            "node_output": instance_output,
            "nic": nic,
            "extra_nics": extra_nics,
            "volumes": volumes,
        }

    def _deploy_bastion_node(
        self,
        node_config: NodeConfig,
        image_id: str,
        security_group: Any,
        placement_group_id: Any = None,
    ) -> Dict[str, Any]:
        """
        Deploy a bastion node (public + private network) with NAT capabilities.

        Creates an instance with public IP and attaches it to the private network.
        The bastion serves two purposes:
        1. SSH jump host for accessing internal nodes
        2. NAT gateway for worker nodes' outbound internet access

        NAT is configured via cloud-init (BASTION_NAT_CLOUDINIT) which enables
        IP forwarding and sets up iptables masquerading.

        Args:
            node_config: Node configuration (should include user_data for NAT setup)
            image_id: OS image ID (Scaleway marketplace label, e.g., "rockylinux_9")
            security_group: Security group resource

        Returns:
            Dictionary with instance, node_output, and NIC resources
        """
        # Create instance (has public IP by default)
        instance_output = self.compute.create_instance(
            name=node_config.name,
            image=image_id,
            instance_type=node_config.instance_type,
            security_group=security_group,
            tags=node_config.tags,
            user_data=node_config.user_data,
            create_public_ip=True,  # Bastion needs public IP for SSH access
            root_volume_size_gb=node_config.root_volume_size_gb,
            placement_group_id=placement_group_id,
        )

        # Attach to private network
        nic = self.compute.attach_to_private_network(
            instance=instance_output.resource,
            network=self.network.private_network,
            instance_name=node_config.name,
        )

        # Attach to extra private networks if configured (bastion is multi-homed like workers)
        extra_nics = {}
        if self.config.extra_private_networks:
            for net_config in self.config.extra_private_networks:
                extra_network = self.network.extra_private_networks.get(
                    net_config.suffix
                )
                if extra_network:
                    extra_nic = self.compute.attach_to_private_network(
                        instance=instance_output.resource,
                        network=extra_network,
                        instance_name=f"{node_config.name}-{net_config.suffix}",
                    )
                    extra_nics[net_config.suffix] = extra_nic

        # Update node_output with private IPv4 address from NIC (filter out IPv6)
        # IPv4 addresses don't contain ':' character, IPv6 do
        instance_output.private_ip = nic.private_ips.apply(
            lambda ips: (
                next((ip.address for ip in ips if ":" not in ip.address), None)
                if ips
                else None
            )
        )

        return {
            "instance": instance_output.resource,
            "node_output": instance_output,
            "nic": nic,
            "extra_nics": extra_nics,
        }
