"""
Main entry point for the Pulumi multi-cloud platform spawner.

This module reads configuration from Pulumi, creates the appropriate
cluster configuration, and deploys the requested topology.
"""

import pulumi
import pulumiverse_scaleway as scaleway
from core.models import Topology, Provider, ClusterConfig
from core.topology import get_topology_config
from core.factory import create_cluster


def main():
    """
    Main orchestration function.
    
    Reads Pulumi configuration, validates it, creates the cluster
    configuration, and deploys the infrastructure.
    """
    # Read Pulumi configuration
    config = pulumi.Config()
    
    # Required configuration
    topology_str = config.require("topology")
    project_id = config.require("project_id")
    
    # Optional configuration with defaults
    provider_str = config.get("provider") or "scaleway"
    region = config.get("region") or "fr-par"
    zone = config.get("zone") or "fr-par-1"
    os_name = config.get("os_name") or "rockylinux"
    os_version = config.get("os_version") or "9"
    # Instance type for worker nodes (default: PRO2-S)
    # Note: Bastion always uses PLAY2-NANO (small machine for SSH only)
    instance_type = config.get("instance_type") or "PRO2-S"
    
    # Optional: Custom image/snapshot ID (overrides os_name/os_version)
    image_id = config.get("image_id")  # If set, uses this snapshot instead of marketplace image
    
    # Optional: SSH public keys for instance access (recommended for CI/CD)
    # Supports both single key (sshPublicKey) and multiple keys (sshPublicKeys - comma-separated)
    ssh_public_key = config.get("sshPublicKey")
    ssh_public_keys_str = config.get("sshPublicKeys")  # Comma-separated list
    
    # Build list of SSH keys
    ssh_keys = []
    if ssh_public_key:
        ssh_keys.append(ssh_public_key)
    if ssh_public_keys_str:
        ssh_keys.extend([key.strip() for key in ssh_public_keys_str.split(',') if key.strip()])
    
    # Prepare SSH key for cloud-init injection (if provided)
    ssh_user_data = None
    if ssh_keys:
        # Format SSH keys for cloud-init
        ssh_keys_yaml = "\n".join([f"      - {key}" for key in ssh_keys])
        ssh_user_data = f"""#cloud-config
users:
  - name: artesca-os
    sudo: ALL=(ALL) NOPASSWD:ALL
    groups: wheel
    shell: /bin/bash
    ssh_authorized_keys:
{ssh_keys_yaml}
"""
        pulumi.log.info(f"SSH keys ({len(ssh_keys)}) will be injected via cloud-init for user 'artesca-os'")
    
    # Parse and validate topology
    try:
        topology = Topology(topology_str)
    except ValueError:
        valid_topologies = [t.value for t in Topology]
        raise ValueError(
            f"Invalid topology '{topology_str}'. "
            f"Valid options: {', '.join(valid_topologies)}"
        )
    
    # Parse and validate provider
    try:
        provider = Provider(provider_str)
    except ValueError:
        valid_providers = [p.value for p in Provider]
        raise ValueError(
            f"Invalid provider '{provider_str}'. "
            f"Valid options: {', '.join(valid_providers)}"
        )
    
    # Generate topology-specific node and network configuration
    topology_config = get_topology_config(topology, instance_type)
    
    # Inject SSH key into node configurations if provided
    if ssh_user_data:
        for node in topology_config["nodes"]:
            if node.has_public_ip:  # Only add SSH to nodes with public IPs
                # Merge with existing user_data if any
                if node.user_data:
                    node.user_data = node.user_data + "\n" + ssh_user_data
                else:
                    node.user_data = ssh_user_data
    
    # Prepare SSH key for cloud-init injection (if provided)
    # This is simpler than IAM SSH key resources and works for all providers
    cluster_config = ClusterConfig(
        topology=topology,
        provider=provider,
        region=region,
        zone=zone,
        project_id=project_id,
        os_name=os_name,
        os_version=os_version,
        image_id=image_id,
        ssh_key_ids=[],  # Not used with cloud-init approach
        nodes=topology_config["nodes"],
        network=topology_config["network"],
    )
    
    # Log configuration for debugging
    pulumi.log.info(f"Deploying {topology.value} topology on {provider.value}")
    pulumi.log.info(f"Region: {region}, Zone: {zone}")
    if image_id:
        pulumi.log.info(f"Using custom image/snapshot: {image_id}")
    else:
        pulumi.log.info(f"Using marketplace image: {os_name} {os_version}")
    pulumi.log.info(f"Instance type for worker nodes: {instance_type}")
    pulumi.log.info(f"Instance type for bastion: PLAY2-NANO (fixed)")
    pulumi.log.info(f"Number of nodes: {len(cluster_config.nodes)}")
    
    # Create cluster implementation via factory
    cluster = create_cluster(cluster_config)
    
    # Deploy the infrastructure
    outputs = cluster.deploy()
    
    # Export all outputs
    for key, value in outputs.items():
        pulumi.export(key, value)
    
    # Additional helpful exports
    pulumi.export("config", {
        "topology": topology.value,
        "provider": provider.value,
        "region": region,
        "zone": zone,
        "os": f"{os_name} {os_version}",
        "instance_types": {
            "bastion": "PLAY2-NANO",  # Fixed: small machine for SSH access
            "worker_nodes": instance_type,  # Configurable: default PRO2-S
        },
    })


# Execute main function
if __name__ == "__main__":
    main()

