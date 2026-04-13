"""
Topology configuration factory.

This module provides functions to generate node and network configurations
based on the number of worker nodes.
"""

from typing import Dict, Any
from .models import NodeConfig, NetworkConfig


def get_cluster_config(
    instance_count: int, base_instance_type: str = "STANDARD3-X8C-32G", product: str = ""
) -> Dict[str, Any]:
    """
    Generate node and network configurations based on instance count.

    This factory function creates the appropriate node list and network
    configuration for the requested number of instances.

    Instance Types:
    - Instances: Uses base_instance_type parameter (default: STANDARD3-X8C-32G)

    Args:
        instance_count: Number of instances to deploy (must be >= 1)
        base_instance_type: Instance type to use for instances

    Returns:
        Dictionary with 'nodes' and 'network' keys containing the
        configuration for the cluster

    Raises:
        ValueError: If instance_count is less than 1
    """
    if instance_count < 1:
        raise ValueError(f"Instance count must be at least 1, got {instance_count}")

    # Generate instance nodes programmatically
    nodes = []
    for i in range(1, instance_count + 1):
        node_index = f"{i:02d}"  # Format as 01, 02, 03, etc.
        hostname = f"node-{node_index}"
        nodes.append(
            NodeConfig(
                name=f"{product}-node-{node_index}",
                role="node",
                instance_type=base_instance_type,
                has_public_ip=False,  # Private only, accessed via gateway bastion
                has_private_ip=True,
                hostname=hostname,
                tags=[
                    "role:node",
                    f"index:{node_index}",
                    f"cluster:{instance_count}-nodes",
                ],
            )
        )

    return {
        "nodes": nodes,
        "network": NetworkConfig(
            enable_private_network=True,
            enable_gateway=True,  # Gateway provides SSH bastion + NAT
        ),
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
