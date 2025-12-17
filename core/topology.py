"""
Topology configuration factory.

This module provides functions to generate node and network configurations
for different cluster topologies.
"""

from typing import Dict, Any
from .models import Topology, NodeConfig, NetworkConfig


def get_topology_config(
    topology: Topology,
    base_instance_type: str = "PRO2-S"
) -> Dict[str, Any]:
    """
    Generate node and network configurations based on topology.
    
    This factory function creates the appropriate node list and network
    configuration for the requested topology.
    
    Instance Types:
    - Bastion: Always PLAY2-NANO (small machine for SSH access only)
    - Nodes: Uses base_instance_type parameter (default: PRO2-S)
    
    Args:
        topology: The topology to configure
        base_instance_type: Instance type to use for worker nodes (not bastion)
        
    Returns:
        Dictionary with 'nodes' and 'network' keys containing the
        configuration for the topology
        
    Raises:
        ValueError: If topology is not supported
    """
    
    configs = {
        Topology.SINGLE: _get_single_node_config,
        Topology.THREE_NODE: _get_three_node_config,
        Topology.SIX_NODE: _get_six_node_config,
    }
    
    if topology not in configs:
        raise ValueError(f"Unsupported topology: {topology}")
    
    return configs[topology](base_instance_type)


def _get_single_node_config(instance_type: str) -> Dict[str, Any]:
    """
    Generate configuration for single-node topology.
    
    Topology:
    - 1 Node (private only)
    - Gateway with bastion feature for SSH access
    
    Args:
        instance_type: Instance type to use for the node
        
    Returns:
        Configuration dictionary
    """
    return {
        "nodes": [
            NodeConfig(
                name="node-01",
                role="node",
                instance_type=instance_type,  # Worker node uses configured instance type (default: PRO2-S)
                has_public_ip=False,
                has_private_ip=True,
                tags=["role:node", "index:01", "topology:single-node", "os:rocky9"]
            )
        ],
        "network": NetworkConfig(
            enable_private_network=True,
            enable_gateway=True  # Gateway provides SSH bastion + NAT
        )
    }


def _get_three_node_config(instance_type: str) -> Dict[str, Any]:
    """
    Generate configuration for 3-node cluster topology.
    
    Topology:
    - 3 Nodes (private only)
    - Gateway with bastion feature for SSH access + NAT
    
    Args:
        instance_type: Instance type to use for the 3 nodes
        
    Returns:
        Configuration dictionary
    """
    return {
        "nodes": [
            # Worker nodes use configured instance type (default: PRO2-S)
            NodeConfig(name="node-01", role="node", instance_type=instance_type, has_public_ip=False, has_private_ip=True, tags=["role:node", "index:01", "topology:3-nodes", "os:rocky9"]),
            NodeConfig(name="node-02", role="node", instance_type=instance_type, has_public_ip=False, has_private_ip=True, tags=["role:node", "index:02", "topology:3-nodes", "os:rocky9"]),
            NodeConfig(name="node-03", role="node", instance_type=instance_type, has_public_ip=False, has_private_ip=True, tags=["role:node", "index:03", "topology:3-nodes", "os:rocky9"]),
        ],
        "network": NetworkConfig(
            enable_private_network=True,  # Required for internal communication
            enable_gateway=True,  # Gateway provides SSH bastion + NAT
            private_subnet="192.168.10.0/24",
            dns_local_name="cluster.local"
        )
    }


def _get_six_node_config(instance_type: str) -> Dict[str, Any]:
    """
    Generate configuration for 6-node cluster topology.
    
    Topology:
    - 6 Nodes (private only)
    - Gateway with bastion feature for SSH access + NAT
    
    Uses Python list comprehension to generate the 6 nodes
    programmatically, demonstrating the power of using Python for IaC.
    
    Args:
        instance_type: Instance type to use for the 6 nodes
        
    Returns:
        Configuration dictionary
    """
    # Generate 6 worker nodes programmatically (use configured instance type, default: PRO2-S)
    nodes = []
    for i in range(1, 7):
        node_index = f"{i:02d}"  # Format as 01, 02, 03, 04, 05, 06
        nodes.append(
            NodeConfig(
                name=f"node-{node_index}",
                role="node",
                instance_type=instance_type,  # Worker node uses configured instance type (default: PRO2-S)
                has_public_ip=False,  # Private only, accessed via gateway bastion
                has_private_ip=True,
                tags=[
                    "role:node",
                    f"index:{node_index}",
                    "topology:6-node",
                    "os:rocky9"
                ]
            )
        )
    
    return {
        "nodes": nodes,
        "network": NetworkConfig(
            enable_private_network=True,
            enable_gateway=True,  # Gateway provides SSH bastion + NAT
            private_subnet="192.168.10.0/24",
            dns_local_name="cluster.local"
        )
    }


def get_node_by_role(nodes: list[NodeConfig], role: str) -> NodeConfig | None:
    """
    Helper function to find a node by its role.
    
    Args:
        nodes: List of node configurations
        role: Role to search for
        
    Returns:
        First node with the specified role, or None if not found
    """
    for node in nodes:
        if node.role == role:
            return node
    return None


def get_nodes_by_role(nodes: list[NodeConfig], role: str) -> list[NodeConfig]:
    """
    Helper function to find all nodes with a specific role.
    
    Args:
        nodes: List of node configurations
        role: Role to search for
        
    Returns:
        List of nodes with the specified role
    """
    return [node for node in nodes if node.role == role]

