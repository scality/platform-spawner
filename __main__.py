"""
Main entry point for the Pulumi multi-cloud platform spawner.

This module reads configuration from Pulumi, creates the appropriate
cluster configuration, and deploys the requested cluster.
"""

import pulumi
import json
import os
from core.models import Provider, ClusterConfig, VolumeConfig
from core.topology import get_cluster_config
from core.factory import create_cluster
from core.ssh import generate_ssh_key_pair, generate_ssh_config, extract_node_info_for_ssh_config


def main():
    """
    Main orchestration function.
    
    Reads Pulumi configuration, validates it, creates the cluster
    configuration, and deploys the infrastructure.
    """
    # Read Pulumi configuration
    config = pulumi.Config()
    
    # Required configuration
    instance_count = config.require_int("instance_count")
    project_id = config.require("project_id")
    instance_image = config.require("instance_image")
    
    # Validate instance count
    if instance_count < 1:
        raise ValueError(f"instance_count must be at least 1, got {instance_count}")
    
    # Global values
    product = config.get("product") or "unknown"
    
    # Network configuration
    offline = config.get_bool("offline") or False
    authorized_tcp_ports = config.get_object("authorized_tcp_ports") or [22]
    authorized_udp_ports = config.get_object("authorized_udp_ports") or []
    authorized_icmp = config.get_bool("authorized_icmp")
    if authorized_icmp is None:
        authorized_icmp = True
    authorized_cidrs = config.get_object("authorized_cidrs") or []
    
    # Instance configuration
    instance_flavor = config.get("instance_flavor") or "medium"
    instance_root_disk_size = config.get_int("instance_root_disk_size") or 50
    
    # Bastion host configuration
    bastion_image = config.get("bastion_image") or "rocky-9"
    bastion_flavor = config.get("bastion_flavor") or "small"
    bastion_root_disk_size = config.get_int("bastion_root_disk_size") or 30
    
    # Parse bastion_image (e.g., "rocky-9") into name and version
    # Format: "os-version" or "os_version"
    bastion_parts = bastion_image.replace("_", "-").split("-")
    if len(bastion_parts) >= 2:
        bastion_os_name = "-".join(bastion_parts[:-1])
        bastion_os_version = bastion_parts[-1]
    else:
        bastion_os_name = bastion_image
        bastion_os_version = "9"  # Default version
    
    # SSH information
    ssh_key_name = config.get("ssh_key_name") or ""
    ssh_private_key_create = config.get_bool("ssh_private_key_create") or False
    
    # Lifecycle
    disable_auto_stop = config.get_bool("disable_auto_stop") or False
    
    # Optional configuration with defaults
    provider_str = config.get("provider") or "scaleway"
    region = config.get("region") or "fr-par"
    zone = config.get("zone") or "fr-par-1"
    
    # Parse and validate provider
    try:
        provider = Provider(provider_str)
    except ValueError:
        valid_providers = [p.value for p in Provider]
        raise ValueError(
            f"Invalid provider '{provider_str}'. "
            f"Valid options: {', '.join(valid_providers)}"
        )
    
    # Map abstract flavors to provider-specific instance types
    from config.flavors import get_instance_type
    instance_type = get_instance_type(provider, instance_flavor)
    bastion_instance_type = get_instance_type(provider, bastion_flavor)
    
    pulumi.log.info(f"Instance flavor '{instance_flavor}' mapped to {instance_type}")
    pulumi.log.info(f"Bastion flavor '{bastion_flavor}' mapped to {bastion_instance_type}")
    
    # If authorized_cidrs is empty, use default
    if not authorized_cidrs:
        authorized_cidrs = ["0.0.0.0/0"]
        pulumi.log.warn("No authorized_cidrs specified. Using 0.0.0.0/0 (open to all). Set 'authorized_cidrs' config to restrict access for production.")
    else:
        pulumi.log.info(f"Gateway bastion restricted to CIDRs: {', '.join(authorized_cidrs)}")
    
    # Optional: Extra volumes for worker nodes
    # Format: JSON string like '[{"size": 120, "count": 1}, {"size": 10, "count": 12}]'
    extra_volumes_str = config.get("extra_volumes")
    extra_volumes = []
    
    if extra_volumes_str:
        try:
            extra_volumes_obj = json.loads(extra_volumes_str)
            for vol_data in extra_volumes_obj:
                volume_config = VolumeConfig(
                    suffix=vol_data.get("suffix", "data"),  # Default suffix
                    size=vol_data["size"],
                    count=vol_data.get("count", 1)  # Default to 1 if not specified
                )
                extra_volumes.append(volume_config)
            pulumi.log.info(f"Extra volumes for worker nodes: {len(extra_volumes)} volume configurations")
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            pulumi.log.warn(f"Failed to parse extra_volumes configuration: {e}")
            extra_volumes = []

    # SSH key management
    ssh_key_info = None
    
    # If ssh_private_key_create is true, generate a new SSH key pair
    if ssh_private_key_create:
        pulumi.log.info("Generating new SSH key pair...")
        stack_name = pulumi.get_stack()
        key_name = f"platform-spawner-{stack_name}"
        
         # Generate in .ssh directory under project root
        # Use absolute path to ensure it works regardless of where Pulumi runs from
        project_root = os.path.abspath(os.path.dirname(__file__))
        key_dir = os.path.join(project_root, ".ssh")
        
        pulumi.log.info(f"Creating SSH keys in: {key_dir}")
        ssh_key_info = generate_ssh_key_pair(key_name, output_dir=key_dir)
        
        pulumi.log.info(f"SSH key generated: {ssh_key_info['private_key_path']}")
    
    # Support both ssh_public_key and ssh_public_keys for backward compatibility
    ssh_public_key = config.get("ssh_public_key")
    ssh_public_keys_str = config.get("ssh_public_keys")  # Comma-separated list
    
    # Build list of SSH keys
    ssh_keys = []
    
    # If we generated a key, add its public key
    if ssh_key_info:
        ssh_keys.append(ssh_key_info["public_key_content"])
    
    # Also add any explicitly provided keys
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
    
    # Generate cluster node and network configuration based on instance count
    cluster_topology = get_cluster_config(instance_count, instance_type, product)
    
    # Add authorized CIDRs to network configuration
    cluster_topology["network"].allowed_ips = authorized_cidrs
    
    # Inject SSH key into all node configurations if provided
    # SSH keys are needed on all nodes for gateway bastion to access them
    if ssh_user_data:
        for node in cluster_topology["nodes"]:
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
    
    # Create cluster configuration
    cluster_config = ClusterConfig(
        # Required fields
        instance_count=instance_count,
        provider=provider,
        region=region,
        zone=zone,
        project_id=project_id,
        instance_image=instance_image,
        
        # Global values
        product=product,
        
        # Network configs
        offline=offline,
        authorized_tcp_ports=authorized_tcp_ports,
        authorized_udp_ports=authorized_udp_ports,
        authorized_icmp=authorized_icmp,
        authorized_cidrs=authorized_cidrs,
        
        # Instance configs
        instance_flavor=instance_flavor,
        instance_root_disk_size=instance_root_disk_size,
        
        # Bastion host configuration
        bastion_image=bastion_image,
        bastion_flavor=bastion_flavor,
        bastion_root_disk_size=bastion_root_disk_size,
        bastion_os_name=bastion_os_name,
        bastion_os_version=bastion_os_version,
        
        # SSH information
        ssh_key_name=ssh_key_name,
        ssh_private_key_create=ssh_private_key_create,
        
        # Lifecycle
        disable_auto_stop=disable_auto_stop,
        
        # Extra stuff
        extra_volumes=extra_volumes,
        
        # Internal/computed fields
        nodes=cluster_topology["nodes"],
        network=cluster_topology["network"],
    )
    
    # Log configuration for debugging
    pulumi.log.info(f"Deploying {instance_count}-node cluster on {provider.value}")
    pulumi.log.info(f"Product: {product}")
    pulumi.log.info(f"Region: {region}, Zone: {zone}")
    pulumi.log.info(f"Using Gateway SSH bastion feature (no bastion VM)")
    pulumi.log.info(f"Instance image: {instance_image}")
    pulumi.log.info(f"Instance type: {instance_type} (flavor: {instance_flavor})")
    pulumi.log.info(f"Instance root disk size: {instance_root_disk_size} GiB")
    pulumi.log.info(f"Number of instances: {instance_count}")
    if offline:
        pulumi.log.info("Offline mode: instances will not have internet access")
    pulumi.log.info(f"Authorized TCP ports: {authorized_tcp_ports}")
    pulumi.log.info(f"Authorized UDP ports: {authorized_udp_ports}")
    pulumi.log.info(f"ICMP authorized: {authorized_icmp}")
    
    # Create cluster implementation via factory
    cluster = create_cluster(cluster_config)
    
    # Deploy the infrastructure
    outputs = cluster.deploy()
    
    # Generate SSH config file after deployment
    ssh_config_path = None
    if outputs.get("bastion") and outputs.get("nodes"):
        # Extract bastion info
        bastion_info = outputs.get("bastion", {})
        
        # Use Pulumi Output.all to wait for all values to be available
        def generate_config(values):
            bastion_ip, bastion_port, bastion_user, nodes = values
            
            # Extract node info for SSH config
            ssh_nodes = extract_node_info_for_ssh_config(nodes)
            
            # Generate SSH config
            private_key = ssh_key_info["private_key_path"] if ssh_key_info else None
            project_root = os.path.abspath(os.path.dirname(__file__))
            config_dir = os.path.join(project_root, ".ssh")
            output_path = os.path.join(config_dir, f"ssh_config_{pulumi.get_stack()}")
            
            ssh_config_path = generate_ssh_config(
                bastion_ip=bastion_ip,
                bastion_port=bastion_port,
                bastion_user=bastion_user,
                nodes=ssh_nodes,
                private_key_path=private_key,
                output_path=output_path,
            )
            
            return ssh_config_path
        
        # Wait for all values and generate config
        ssh_config_path = pulumi.Output.all(
            bastion_info.get("ip"),
            bastion_info.get("port"),
            bastion_info.get("user"),
            outputs.get("nodes"),
        ).apply(generate_config)
    
    # Export all outputs
    for key, value in outputs.items():
        pulumi.export(key, value)
    
    # Export SSH config path
    if ssh_config_path:
        pulumi.export("ssh_config", ssh_config_path)
    
    # Export SSH key info if we created one
    if ssh_key_info:
        pulumi.export("ssh_info", {
            "key": ssh_key_info["private_key_path"],
            "key_pub": ssh_key_info["public_key_path"],
            "generated": True,
        })
    
    # Additional helpful exports
    pulumi.export("config", {
        "product": product,
        "instance_count": instance_count,
        "provider": provider.value,
        "region": region,
        "zone": zone,
        "instance_image": instance_image,
        "instance_flavor": instance_flavor,
        "instance_type": instance_type,
        "instance_root_disk_size": instance_root_disk_size,
        "bastion_flavor": bastion_flavor,
        "bastion_instance_type": bastion_instance_type,
        "offline": offline,
        "disable_auto_stop": disable_auto_stop,
    })


# Execute main function
if __name__ == "__main__":
    main()

