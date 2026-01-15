"""
Scaleway cluster implementation.

This module orchestrates the deployment of complete clusters
on Scaleway infrastructure with any number of worker nodes.

The gateway provides SSH bastion functionality for accessing private worker nodes.
"""

import pulumi
import pulumiverse_scaleway as scaleway
from typing import Dict, Any, List
from core.interfaces import ClusterInterface
from core.models import ClusterConfig, NodeConfig
from .network import ScalewayNetwork
from .compute import ScalewayCompute


class ScalewayCluster(ClusterInterface):
    """
    Scaleway-specific cluster implementation.

    Orchestrates network and compute resources to deploy clusters
    with any number of worker nodes. All worker nodes are on a private
    network and accessed via a gateway with SSH bastion functionality.
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
        and the gateway bastion.

        Args:
            ssh_keys: List of SSH public key strings to register

        Returns:
            List of registered key IDs
        """
        if not ssh_keys:
            return []

        key_ids = []
        for idx, key in enumerate(ssh_keys):
            iam_key = scaleway.iam.SshKey(
                f"ssh-key-{idx+1}",
                public_key=key,
                name=f"platform-spawner-key-{idx+1}",
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
        - Public Gateway with SSH bastion, NAT and DHCP
        - Security Groups (first-node with restricted outbound, internal for others)
        - N Instance Nodes (private only, accessed via gateway bastion)

        Returns:
            Dictionary with deployment outputs
        """
        # Get node configurations
        nodes_by_role = self._organize_nodes_by_role()

        # Get instance image
        instance_image = self.compute.get_worker_image()

        # Create network infrastructure (includes gateway with bastion)
        network_output = self.network.create_full_network()

        # Create security groups
        # First node gets restricted outbound (for application updates from specific IPs)
        sg_first_node = self.compute.create_first_node_security_group(
            private_subnet=self.config.network.private_subnet
        )
        # Other nodes get standard internal security group (permissive outbound)
        sg_internal = self.compute.create_internal_security_group(
            private_subnet=self.config.network.private_subnet
        )

        # Deploy nodes
        outputs = {
            "instance_count": self.config.instance_count,
            "network": {
                "vpc_id": network_output.vpc_id,
                "private_network_id": network_output.private_network_id,
                "subnet": network_output.subnet,
                "gateway_id": network_output.gateway_id,
            },
            "nodes": {},
            "bastion": {},
        }

        # Add gateway bastion info to outputs (action.yaml expects 'bastion' output)
        if network_output.gateway_ip:
            outputs["bastion"] = {
                "type": "gateway",
                "ip": network_output.gateway_ip,
                "port": 61000,
                "user": "bastion",
                "gateway_id": network_output.gateway_id,
            }
            # Also keep gateway_bastion_ip for backward compatibility
            outputs["gateway_bastion_ip"] = network_output.gateway_ip

        # Deploy instance nodes (private only, accessed via gateway bastion)
        if "node" in nodes_by_role:
            # Get the actual private network name (includes product prefix)
            private_network_name = f"{self.config.product}-internal" if self.config.product else "internal"
            for idx, node_config in enumerate(nodes_by_role["node"]):
                # First node (idx=0) gets restricted outbound security group
                # Other nodes get standard internal security group
                security_group = sg_first_node if idx == 0 else sg_internal
                
                node = self._deploy_internal_node(
                    node_config=node_config,
                    image_id=instance_image,
                    security_group=security_group,
                )

                # Generate SSH jump command for accessing the node via bastion
                # Scaleway internal DNS format: {hostname}.{private_network_name}.internal
                ssh_command = network_output.gateway_ip.apply(
                    lambda ip, name=node_config.name, net=private_network_name: f"ssh -J bastion@{ip}:61000 artesca-os@{name}.{net}.internal"
                )

                # Prepare volume information if volumes exist
                volumes_info = []
                if node.get("volumes"):
                    for vol_data in node["volumes"]:
                        volumes_info.append({
                            "id": vol_data["resource"].id,
                            "urn": vol_data["resource"].urn,
                            "name": vol_data["resource"].name,
                            "size_gb": vol_data["size_gb"],
                        })

                outputs["nodes"][node_config.name] = {
                    "id": node["node_output"].id,
                    "name": node_config.name,
                    "instance_type": node_config.instance_type,
                    "private_ip": node["node_output"].private_ip,
                    "ssh_command": ssh_command,
                    "urn": node["instance"].urn,
                    "volumes": volumes_info,
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

        Creates an instance and attaches it to the private network.
        Also creates and attaches additional volumes if configured.

        Args:
            node_config: Node configuration
            image_id: OS image ID
            security_group: Security group resource

        Returns:
            Dictionary with instance, volumes, and NIC resources
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
                        volume_name = f"{node_config.name}-{vol_config.suffix}-{i+1:02d}"

                    # Create the volume
                    volume = self.compute.create_volume(
                        name=volume_name,
                        size_gb=vol_config.size,
                    )
                    # Store volume with metadata for later reference
                    volumes.append({
                        "resource": volume,
                        "size_gb": vol_config.size,
                    })
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

        # Attach to private network
        nic = self.compute.attach_to_private_network(
            instance=instance_output.resource,
            network=self.network.private_network,
            instance_name=node_config.name,
        )

        # Update node_output with private IPv4 address from NIC (filter out IPv6)
        # IPv4 addresses don't contain ':' character, IPv6 do
        instance_output.private_ip = nic.private_ips.apply(
            lambda ips: next((ip.address for ip in ips if ':' not in ip.address), None) if ips else None
        )

        return {
            "instance": instance_output.resource,
            "node_output": instance_output,
            "nic": nic,
            "volumes": volumes,
        }

    def _deploy_bastion_node(
        self,
        node_config: NodeConfig,
        image_id: str,
        security_group: Any,
    ) -> Dict[str, Any]:
        """
        Deploy a bastion node (public + private network).

        Creates an instance with public IP and attaches it to
        the private network for accessing internal nodes.

        Args:
            node_config: Node configuration
            image_id: OS image ID
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
            lambda ips: next((ip.address for ip in ips if ':' not in ip.address), None) if ips else None
        )

        return {
            "instance": instance_output.resource,
            "node_output": instance_output,
            "nic": nic,
        }

