"""
Scaleway cluster implementation.

This module orchestrates the deployment of complete clusters
on Scaleway infrastructure with any number of worker nodes.

A bastion VM provides SSH access and NAT functionality for accessing
and providing internet connectivity to private worker nodes.
"""

from typing import Any, Dict, List

import pulumi
import pulumiverse_scaleway as scaleway

from core.interfaces import ClusterInterface
from core.models import ClusterConfig, NodeConfig
from config.flavors import get_instance_type
from .network import ScalewayNetwork
from .compute import ScalewayCompute


# Cloud-init configuration for bastion VM with NAT functionality
# Enables IP forwarding and configures iptables masquerading
BASTION_NAT_CLOUDINIT = """#cloud-config
write_files:
  - path: /etc/sysctl.d/99-ip-forward.conf
    content: |
      net.ipv4.ip_forward = 1
    owner: root:root
    permissions: '0644'

runcmd:
  # Enable IP forwarding immediately
  - sysctl -p /etc/sysctl.d/99-ip-forward.conf
  # Configure iptables NAT masquerading
  # eth0 is the public interface, private NIC is attached later
  - iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
  - iptables -A FORWARD -i eth0 -o eth0 -m state --state RELATED,ESTABLISHED -j ACCEPT
  - iptables -A FORWARD -j ACCEPT
  # Make iptables rules persistent (Rocky Linux / RHEL)
  - dnf install -y iptables-services || yum install -y iptables-services || true
  - service iptables save || true
"""


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

        # Create security groups
        # Bastion: SSH access from allowed CIDRs + restricted outbound (NAT to update servers only)
        sg_bastion = self.compute.create_bastion_security_group(
            allowed_cidrs=self.config.network.allowed_ips,
            private_subnet=self.config.network.private_subnet,
            restrict_outbound=True,  # Restrict NAT to DNS and HTTPS only
        )
        # All worker nodes use internal security group (private network access only)
        sg_internal = self.compute.create_internal_security_group(
            private_subnet=self.config.network.private_subnet
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
        )
        pulumi.log.info(f"Deployed bastion VM: {bastion_name}")

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
                "user": "rocky",  # Default user for Rocky Linux bastion image
                "instance_id": bastion["node_output"].id,
            },
        }

        # Deploy instance nodes (private only, accessed via bastion)
        if "node" in nodes_by_role:
            for node_config in nodes_by_role["node"]:
                # All nodes use internal security group
                # Outbound restrictions are handled by the bastion's NAT
                node = self._deploy_internal_node(
                    node_config=node_config,
                    image_id=instance_image,
                    security_group=sg_internal,
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
        )

        # Attach to private network
        nic = self.compute.attach_to_private_network(
            instance=instance_output.resource,
            network=self.network.private_network,
            instance_name=node_config.name,
        )

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
        }
