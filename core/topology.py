"""
Topology configuration factory.

This module provides functions to generate node and network configurations
based on the number of worker nodes.
"""

from typing import Dict, Any
from .models import NodeConfig, NetworkConfig


def get_cluster_config(
    worker_count: int,
    base_instance_type: str = "PRO2-S",
    name_prefix: str = ""
) -> Dict[str, Any]:
    """
    Generate node and network configurations based on worker count.
    
    This factory function creates the appropriate node list and network
    configuration for the requested number of worker nodes.
    
    Instance Types:
    - Worker Nodes: Uses base_instance_type parameter (default: PRO2-S)
    
    Args:
        worker_count: Number of worker nodes to deploy (must be >= 1)
        base_instance_type: Instance type to use for worker nodes
        name_prefix: Prefix to apply to all resource names (optional)
        
    Returns:
        Dictionary with 'nodes' and 'network' keys containing the
        configuration for the cluster
        
    Raises:
        ValueError: If worker_count is less than 1
    """
    if worker_count < 1:
        raise ValueError(f"Worker count must be at least 1, got {worker_count}")
    
    # Prepare node name prefix
    node_prefix = f"{name_prefix}-" if name_prefix else ""
    
    # Generate worker nodes programmatically
    nodes = []
    for i in range(1, worker_count + 1):
        node_index = f"{i:02d}"  # Format as 01, 02, 03, etc.
        nodes.append(
            NodeConfig(
                name=f"{node_prefix}node-{node_index}",
                role="node",
                instance_type=base_instance_type,
                has_public_ip=False,  # Private only, accessed via gateway bastion
                has_private_ip=True,
                tags=[
                    "role:node",
                    f"index:{node_index}",
                    f"cluster:{worker_count}-nodes",
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

