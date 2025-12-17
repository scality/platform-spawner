"""
Main entry point for the Pulumi multi-cloud platform spawner.

This module reads configuration from Pulumi, creates the appropriate
cluster configuration, and deploys the requested topology.
"""

import pulumi
import json
from core.models import Topology, Provider, ClusterConfig, VolumeConfig
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
    
    # Optional worker snapshot (if not provided, uses marketplace image)
    worker_snapshot_id = config.get("worker_snapshot_id")
       
    # Optional configuration with defaults
    provider_str = config.get("provider") or "scaleway"
    region = config.get("region") or "fr-par"
    zone = config.get("zone") or "fr-par-1"
    
    # Worker OS configuration (marketplace image if no snapshot provided)
    bastion_os_name = config.get("bastion_os_name") or "rockylinux"
    bastion_os_version = config.get("bastion_os_version") or "9"
    
    # Instance type for worker nodes (default: PRO2-S)
    # Note: No bastion VM - using gateway bastion feature instead
    instance_type = config.get("instance_type") or "PRO2-S"
    
    # Optional: Additional volumes for worker nodes
    # Format: [{"suffix": "service", "size": 120}, {"suffix": "data", "size": 10, "count": 12}]
    additional_volumes_str = config.get("additional_volumes")
    additional_volumes = []
    if additional_volumes_str:
        try:
            volumes_data = json.loads(additional_volumes_str)
            for vol_data in volumes_data:
                volume_config = VolumeConfig(
                    suffix=vol_data["suffix"],
                    size=vol_data["size"],
                    count=vol_data.get("count", 1)  # Default to 1 if not specified
                )
                additional_volumes.append(volume_config)
            pulumi.log.info(f"Additional volumes for worker nodes: {len(additional_volumes)} volume configurations")
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            pulumi.log.warn(f"Failed to parse additional_volumes configuration: {e}")
            additional_volumes = []
    
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
    
    # Inject SSH key into all node configurations if provided
    # SSH keys are needed on all nodes for gateway bastion to access them
    if ssh_user_data:
        for node in topology_config["nodes"]:
            # Merge with existing user_data if any
            if node.user_data:
                node.user_data = node.user_data + "\n" + ssh_user_data
            else:
                node.user_data = ssh_user_data
    
    # Create IAM SSH keys for gateway bastion access (if provided)
    iam_ssh_key_ids = []
    if ssh_keys:
        import pulumiverse_scaleway as scaleway
        for idx, key in enumerate(ssh_keys):
            iam_key = scaleway.IamSshKey(
                f"ssh-key-{idx+1}",
                public_key=key,
                name=f"platform-spawner-key-{idx+1}",
                project_id=project_id,
            )
            iam_ssh_key_ids.append(iam_key.id)
        pulumi.log.info(f"Created {len(iam_ssh_key_ids)} IAM SSH keys for gateway bastion access")
    
    # Prepare SSH key for cloud-init injection (if provided)
    # This is simpler than IAM SSH key resources and works for all providers
    cluster_config = ClusterConfig(
        topology=topology,
        provider=provider,
        region=region,
        zone=zone,
        project_id=project_id,
        worker_snapshot_id=worker_snapshot_id,
        bastion_os_name=bastion_os_name,
        bastion_os_version=bastion_os_version,
        ssh_key_ids=[],  # Not used with cloud-init approach
        nodes=topology_config["nodes"],
        network=topology_config["network"],
        additional_volumes=additional_volumes,
    )
    
    # Log configuration for debugging
    pulumi.log.info(f"Deploying {topology.value} topology on {provider.value}")
    pulumi.log.info(f"Region: {region}, Zone: {zone}")
    pulumi.log.info(f"Using Gateway SSH bastion feature (no bastion VM)")
    if worker_snapshot_id:
        pulumi.log.info(f"Worker nodes: Custom snapshot {worker_snapshot_id}")
    else:
        pulumi.log.info(f"Worker nodes: Marketplace image ({bastion_os_name} {bastion_os_version})")
    pulumi.log.info(f"Instance type for worker nodes: {instance_type}")
    pulumi.log.info(f"Number of worker nodes: {len(cluster_config.nodes)}")
    
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
        "worker_image": worker_snapshot_id if worker_snapshot_id else f"{bastion_os_name} {bastion_os_version} (marketplace)",
        "instance_types": {
            "gateway_bastion": "VPC-GW-S",  # Gateway provides SSH bastion
            "worker_nodes": instance_type,  # Configurable: default PRO2-S
        },
    })


# Execute main function
if __name__ == "__main__":
    main()

