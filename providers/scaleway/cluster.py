"""
Scaleway cluster implementation.

This module orchestrates the deployment of complete cluster topologies
on Scaleway infrastructure:
- Single-node: 1 bastion (PLAY2-NANO) + 1 node
- 3-node: 1 bastion (PLAY2-NANO) + 3 nodes
- 6-node: 1 bastion (PLAY2-NANO) + 6 nodes

The bastion is always a small machine for SSH access. No bootstrap node.
"""

import pulumi
from typing import Dict, Any, List
from core.interfaces import ClusterInterface
from core.models import ClusterConfig, NodeConfig, Topology
from .network import ScalewayNetwork
from .compute import ScalewayCompute


class ScalewayCluster(ClusterInterface):
    """
    Scaleway-specific cluster implementation.
    
    Orchestrates network and compute resources to deploy:
    - Single-node topology: 1 bastion (PLAY2-NANO) + 1 node
    - 3-node topology: 1 bastion (PLAY2-NANO) + 3 nodes
    - 6-node topology: 1 bastion (PLAY2-NANO) + 6 nodes
    
    The bastion is always a small machine (PLAY2-NANO) for SSH access.
    No bootstrap node is needed in any topology.
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
    
    def deploy_single_node(self) -> Dict[str, Any]:
        """
        Deploy a single-node topology (Scenario I).
        
        Creates:
        - VPC and Private Network
        - 2 Security Groups (bastion and internal)
        - 1 Bastion node (public + private, small machine PLAY2-NANO)
        - 1 Node (private only)
        
        This is the simplest topology, suitable for development
        or standalone applications.
        
        Returns:
            Dictionary with deployment outputs
        """
        # Get node configurations
        nodes_by_role = self._organize_nodes_by_role()
        
        # Get images for different node types
        bastion_image = self.compute.get_bastion_os_image()
        worker_image = self.compute.get_worker_image()
        
        # Create network infrastructure
        network_output = self.network.create_full_network()
        
        # Create security groups
        sg_bastion = self.compute.create_bastion_security_group()
        sg_internal = self.compute.create_internal_security_group(
            private_subnet=self.config.network.private_subnet
        )
        
        # Deploy nodes
        outputs = {
            "topology": Topology.SINGLE.value,
            "network": {
                "vpc_id": network_output.vpc_id,
                "private_network_id": network_output.private_network_id,
                "subnet": network_output.subnet,
            },
            "nodes": {},
        }
        
        # Deploy Bastion node (small machine for SSH access)
        if "bastion" in nodes_by_role:
            bastion_config = nodes_by_role["bastion"][0]
            bastion = self._deploy_bastion_node(
                node_config=bastion_config,
                image_id=bastion_image,
                security_group=sg_bastion,
            )
            outputs["nodes"]["bastion"] = {
                "id": bastion["node_output"].id,
                "name": bastion_config.name,
                "instance_type": bastion_config.instance_type,
                "public_ip": bastion["node_output"].public_ip,
                "private_ip": bastion["node_output"].private_ip,
            }
            outputs["bastion_public_ip"] = bastion["node_output"].public_ip
        
        # Deploy Node (private only, accessed via bastion)
        if "node" in nodes_by_role:
            node_config = nodes_by_role["node"][0]
            node_item = self._deploy_internal_node(
                node_config=node_config,
                image_id=worker_image,
                security_group=sg_internal,
            )
            outputs["nodes"]["node-01"] = {
                "id": node_item["node_output"].id,
                "name": node_config.name,
                "instance_type": node_config.instance_type,
                "private_ip": node_item["node_output"].private_ip,
            }
        
        return outputs
    
    def deploy_three_node(self) -> Dict[str, Any]:
        """
        Deploy a 3-node cluster topology (Scenario II).
        
        Creates:
        - VPC and Private Network
        - Public Gateway with NAT and DHCP
        - 2 Security Groups (bastion and internal)
        - 1 Bastion node (public + private, small machine PLAY2-NANO)
        - 3 Nodes (private only)
        
        The bastion provides SSH access to the private nodes.
        The gateway provides outbound internet for private nodes.
        
        Returns:
            Dictionary with deployment outputs
        """
        # Get node configurations
        nodes_by_role = self._organize_nodes_by_role()
        
        # Get images for different node types
        bastion_image = self.compute.get_bastion_os_image()
        worker_image = self.compute.get_worker_image()
        
        # Create network infrastructure
        network_output = self.network.create_full_network()
        
        # Create security groups
        sg_bastion = self.compute.create_bastion_security_group()
        sg_internal = self.compute.create_internal_security_group(
            private_subnet=self.config.network.private_subnet
        )
        
        # Deploy nodes
        outputs = {
            "topology": Topology.THREE_NODE.value,
            "network": {
                "vpc_id": network_output.vpc_id,
                "private_network_id": network_output.private_network_id,
                "subnet": network_output.subnet,
            },
            "nodes": {},
        }
        
        # Deploy Bastion node (small machine for SSH access)
        if "bastion" in nodes_by_role:
            bastion_config = nodes_by_role["bastion"][0]
            bastion = self._deploy_bastion_node(
                node_config=bastion_config,
                image_id=bastion_image,
                security_group=sg_bastion,
            )
            outputs["nodes"]["bastion"] = {
                "id": bastion["node_output"].id,
                "name": bastion_config.name,
                "instance_type": bastion_config.instance_type,
                "public_ip": bastion["node_output"].public_ip,
                "private_ip": bastion["node_output"].private_ip,
            }
            outputs["bastion_public_ip"] = bastion["node_output"].public_ip
        
        # Deploy 3 Nodes (private only, accessed via bastion)
        if "node" in nodes_by_role:
            for node_config in nodes_by_role["node"]:
                node_item = self._deploy_internal_node(
                    node_config=node_config,
                    image_id=worker_image,
                    security_group=sg_internal,
                )
                outputs["nodes"][node_config.name] = {
                    "id": node_item["node_output"].id,
                    "name": node_config.name,
                    "instance_type": node_config.instance_type,
                    "private_ip": node_item["node_output"].private_ip,
                }
        
        return outputs
    
    def deploy_six_node(self) -> Dict[str, Any]:
        """
        Deploy a 6-node cluster topology (Scenario III).
        
        Creates:
        - VPC and Private Network
        - Public Gateway with NAT and DHCP
        - 2 Security Groups (bastion and internal)
        - 1 Bastion node (public + private, small machine PLAY2-NANO)
        - 6 Nodes (private only)
        
        This demonstrates the power of Python loops for infrastructure
        provisioning - the 6 nodes are created programmatically.
        
        Returns:
            Dictionary with deployment outputs
        """
        # Get node configurations
        nodes_by_role = self._organize_nodes_by_role()
        
        # Get images for different node types
        bastion_image = self.compute.get_bastion_os_image()
        worker_image = self.compute.get_worker_image()
        
        # Create network infrastructure
        network_output = self.network.create_full_network()
        
        # Create security groups
        sg_bastion = self.compute.create_bastion_security_group()
        sg_internal = self.compute.create_internal_security_group(
            private_subnet=self.config.network.private_subnet
        )
        
        # Deploy nodes
        outputs = {
            "topology": Topology.SIX_NODE.value,
            "network": {
                "vpc_id": network_output.vpc_id,
                "private_network_id": network_output.private_network_id,
                "subnet": network_output.subnet,
            },
            "nodes": {},
            "node_ids": [],
        }

        # Deploy Bastion node (small machine for SSH access)
        if "bastion" in nodes_by_role:
            bastion_config = nodes_by_role["bastion"][0]
            bastion = self._deploy_bastion_node(
                node_config=bastion_config,
                image_id=bastion_image,
                security_group=sg_bastion,
            )
            outputs["nodes"]["bastion"] = {
                "id": bastion["node_output"].id,
                "name": bastion_config.name,
                "instance_type": bastion_config.instance_type,
                "public_ip": bastion["node_output"].public_ip,
                "private_ip": bastion["node_output"].private_ip,
            }
            outputs["bastion_public_ip"] = bastion["node_output"].public_ip
        
        # Deploy 6 Nodes (private only, accessed via bastion)
        if "node" in nodes_by_role:
            for node_config in nodes_by_role["node"]:
                node = self._deploy_internal_node(
                    node_config=node_config,
                    image_id=worker_image,
                    security_group=sg_internal,
                )
                outputs["nodes"][node_config.name] = {
                    "id": node["node_output"].id,
                    "name": node_config.name,
                    "instance_type": node_config.instance_type,
                    "private_ip": node["node_output"].private_ip,
                }
                outputs["node_ids"].append(node["node_output"].id)
        
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
        
        Args:
            node_config: Node configuration
            image_id: OS image ID
            security_group: Security group resource
            
        Returns:
            Dictionary with instance and NIC resources
        """
        # Create instance without public IP (private only)
        instance_output = self.compute.create_instance(
            name=node_config.name,
            image=image_id,
            instance_type=node_config.instance_type,
            security_group=security_group,
            tags=node_config.tags,
            user_data=node_config.user_data,
            create_public_ip=False,  # Private only, no public IP
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

