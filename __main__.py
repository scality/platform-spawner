"""
Main entry point for the Pulumi multi-cloud platform spawner.

This module reads configuration from Pulumi, creates the appropriate
cluster configuration, and deploys the requested cluster.
"""

import pulumi
import json
import yaml
import os
from core.models import Provider, ClusterConfig, VolumeConfig, RouteConfig, PrivateNetworkConfig
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
    
    # Custom routes configuration
    # Format: JSON array like '[{"destination": "35.241.243.135/32", "description": "artifacts.scality.net"}]'
    custom_routes_str = config.get("custom_routes")
    custom_routes = []
    
    if custom_routes_str:
        try:
            custom_routes_obj = json.loads(custom_routes_str)
            for route_data in custom_routes_obj:
                route_config = RouteConfig(
                    destination=route_data["destination"],
                    description=route_data.get("description", ""),
                )
                custom_routes.append(route_config)
            pulumi.log.info(f"Custom routes configured: {len(custom_routes)} route(s)")
            for route in custom_routes:
                pulumi.log.info(f"  - {route.destination} ({route.description})")
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            pulumi.log.warn(f"Failed to parse custom_routes configuration: {e}")
            custom_routes = []
    
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
    
    # Map common OS name aliases to Scaleway marketplace label names
    os_name_map = {
        "rocky": "rockylinux",
        "rocky-linux": "rockylinux",
    }
    bastion_os_name = os_name_map.get(bastion_os_name, bastion_os_name)
    
    # SSH information
    ssh_key_name = config.get("ssh_key_name") or ""
    ssh_public_keys = config.get_object("ssh_public_keys") or []
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
    # Or native YAML list (when quotes are stripped in CI environments)
    extra_volumes_str = config.get("extra_volumes")
    extra_volumes = []
    
    # Try string first, then fall back to object (for native YAML arrays)
    if extra_volumes_str:
        # Non-empty string - parse as JSON
        try:
            extra_volumes_obj = json.loads(extra_volumes_str)
            for vol_data in extra_volumes_obj:
                volume_config = VolumeConfig(
                    suffix=vol_data.get("suffix", "data"),
                    size=vol_data["size"],
                    count=vol_data.get("count", 1)
                )
                extra_volumes.append(volume_config)
            pulumi.log.info(f"Extra volumes for worker nodes: {len(extra_volumes)} volume configurations")
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            pulumi.log.warn(f"Failed to parse extra_volumes configuration: {e}")
    else:
        # Not set, None, or empty string - try as native YAML array
        extra_volumes_obj = config.get_object("extra_volumes")
        if extra_volumes_obj and isinstance(extra_volumes_obj, list):
            try:
                for vol_data in extra_volumes_obj:
                    volume_config = VolumeConfig(
                        suffix=vol_data.get("suffix", "data"),
                        size=vol_data["size"],
                        count=vol_data.get("count", 1)
                    )
                    extra_volumes.append(volume_config)
                pulumi.log.info(f"Extra volumes for worker nodes: {len(extra_volumes)} volume configurations")
            except (KeyError, TypeError) as e:
                pulumi.log.warn(f"Failed to parse extra_volumes configuration: {e}")

    # Optional: Extra private networks for worker nodes (multi-homed instances)
    # Format: JSON string like '[{"suffix": "data", "subnet": "10.1.0.0/24"}]'
    # Or native YAML list (when quotes are stripped in CI environments)
    # Each entry creates a separate private network and attaches a NIC to each instance
    extra_private_networks_str = config.get("extra_private_networks")
    extra_private_networks = []
    
    # Try string first, then fall back to object (for native YAML arrays)
    # Note: config.get() may return "" (default) if schema type mismatch (e.g., list instead of string)
    if extra_private_networks_str:
        # Non-empty string - parse as JSON
        try:
            extra_private_networks_obj = json.loads(extra_private_networks_str)
            for net_data in extra_private_networks_obj:
                network_config = PrivateNetworkConfig(
                    suffix=net_data.get("suffix", "extra"),
                    subnet=net_data["subnet"],
                    count=net_data.get("count", 1)
                )
                extra_private_networks.append(network_config)
            pulumi.log.info(f"Extra private networks for worker nodes: {len(extra_private_networks)} network(s)")
            for net_cfg in extra_private_networks:
                pulumi.log.info(f"  - {net_cfg.suffix}: {net_cfg.subnet}")
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            pulumi.log.warn(f"Failed to parse extra_private_networks configuration: {e}")
    else:
        # Not set, None, or empty string - try as native YAML array
        # This handles cases where YAML parses the value as a list (quotes stripped)
        extra_private_networks_obj = config.get_object("extra_private_networks")
        if extra_private_networks_obj and isinstance(extra_private_networks_obj, list):
            try:
                for net_data in extra_private_networks_obj:
                    network_config = PrivateNetworkConfig(
                        suffix=net_data.get("suffix", "extra"),
                        subnet=net_data["subnet"],
                        count=net_data.get("count", 1)
                    )
                    extra_private_networks.append(network_config)
                pulumi.log.info(f"Extra private networks for worker nodes: {len(extra_private_networks)} network(s)")
                for net_cfg in extra_private_networks:
                    pulumi.log.info(f"  - {net_cfg.suffix}: {net_cfg.subnet}")
            except (KeyError, TypeError) as e:
                pulumi.log.warn(f"Failed to parse extra_private_networks configuration: {e}")

    # SSH key management
    # Four options are supported:
    # 1. Default (no config): No cloud-init config, Scaleway provides all IAM keys to instance
    # 2. ssh_key_name: Use an existing SSH key already registered in the cloud provider (by name)
    # 3. ssh_private_key_create: Generate a new SSH keypair (registered in IAM + cloud-init)
    # 4. ssh_public_key: Provide an SSH public key to add (registered in IAM + cloud-init)
    # 
    # Options 3 and 4 will register the key in IAM AND inject via cloud-init for artesca-os user
    # Options 1 and 2 rely on Scaleway's automatic SSH key injection (no cloud-init override)
    
    ssh_key_info = None
    ssh_keys_to_register = []  # Keys to register in IAM
    ssh_keys_for_cloud_init = []  # Keys to inject via cloud-init
    
    # Option 2: Use existing SSH key by name (no cloud-init, just use provider's default)
    if ssh_key_name:
        pulumi.log.info(f"Using existing SSH key from provider: {ssh_key_name}")
        # No need to register or inject - Scaleway will use this key automatically
    
    # Option 3: Generate a new SSH keypair
    if ssh_private_key_create:
        pulumi.log.info("Generating new SSH key pair...")
        stack_name = pulumi.get_stack()
        # Include product name in key name for better identification
        key_name = f"{product}-{stack_name}" if product and product != "unknown" else f"platform-spawner-{stack_name}"
        
        # Generate in .ssh directory under project root
        project_root = os.path.abspath(os.path.dirname(__file__))
        key_dir = os.path.join(project_root, ".ssh")
        
        pulumi.log.info(f"Creating SSH keys in: {key_dir}")
        ssh_key_info = generate_ssh_key_pair(key_name, output_dir=key_dir)
        
        pulumi.log.info(f"SSH key generated: {ssh_key_info['private_key_path']}")
        ssh_keys_to_register.append(ssh_key_info["public_key_content"])
        ssh_keys_for_cloud_init.append(ssh_key_info["public_key_content"])
    
    # Option 4: Use provided SSH public keys
    if ssh_public_keys:
        pulumi.log.info(f"Adding {len(ssh_public_keys)} SSH public key(s) to cloud provider and cloud-init")
        for idx, key in enumerate(ssh_public_keys, 1):
            if key and key.strip():  # Skip empty keys
                ssh_keys_to_register.append(key)
                ssh_keys_for_cloud_init.append(key)
                pulumi.log.info(f"  - SSH public key {idx} added")
    
    # Prepare SSH key for cloud-init injection ONLY if explicitly provided (options 3 or 4)
    # If no ssh_keys specified, rely on Scaleway's automatic IAM SSH key injection
    ssh_user_data = None
    if ssh_keys_for_cloud_init:
        # Format SSH keys for cloud-init
        cloud_config = {
            "users": [
                {
                    "name": "artesca-os",
                    "lock_passwd": False,
                    "ssh_authorized_keys": ssh_keys_for_cloud_init
                }
            ]
        }

        # Ensure the output starts with #cloud-config
        ssh_user_data = "#cloud-config\n" + yaml.dump(cloud_config)

        pulumi.log.info(f"SSH keys ({len(ssh_keys_for_cloud_init)}) will be injected via cloud-init for user 'artesca-os'")
    else:
        pulumi.log.info("No SSH key specified - using default Scaleway IAM SSH keys (all keys registered in project)")
    
    # Load network configuration cloud-init if extra private networks are configured
    network_config_user_data = None
    if extra_private_networks:
        network_config_path = os.path.join(os.path.dirname(__file__), "config", "cloud-init-network.yaml")
        if os.path.exists(network_config_path):
            with open(network_config_path, 'r') as f:
                network_config_user_data = f.read()
            pulumi.log.info("Loaded network configuration from config/cloud-init-network.yaml")
        else:
            pulumi.log.warn(f"Network config file not found: {network_config_path}")
    
    # Generate cluster node and network configuration based on instance count
    cluster_topology = get_cluster_config(instance_count, instance_type, product)
    
    # Add authorized CIDRs to network configuration
    cluster_topology["network"].allowed_ips = authorized_cidrs
    
    # Set custom routes
    cluster_topology["network"].custom_routes = custom_routes
    
    # Inject SSH key into all node configurations if provided
    # Only inject if explicitly configured - otherwise rely on Scaleway defaults
    if ssh_user_data:
        for node in cluster_topology["nodes"]:
            # Merge with existing user_data if any
            if node.user_data:
                node.user_data = node.user_data + "\n" + ssh_user_data
            else:
                node.user_data = ssh_user_data
    
    # Inject network configuration for nodes with extra private networks
    if network_config_user_data:
        for node in cluster_topology["nodes"]:
            # Only apply to worker nodes, not bastion
            if node.role == "node":
                if node.user_data:
                    node.user_data = node.user_data + "\n" + network_config_user_data
                else:
                    node.user_data = network_config_user_data
        
        pulumi.log.info("Network configuration applied to worker nodes")
    
    # Set root volume size on all nodes
    for node in cluster_topology["nodes"]:
        node.root_volume_size_gb = instance_root_disk_size
    
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
        ssh_public_keys=ssh_keys_to_register,
        
        # Lifecycle
        disable_auto_stop=disable_auto_stop,
        
        # Extra stuff
        extra_volumes=extra_volumes,
        extra_private_networks=extra_private_networks,
        
        # Internal/computed fields
        nodes=cluster_topology["nodes"],
        network=cluster_topology["network"],
    )
    
    # Log configuration for debugging
    pulumi.log.info(f"Deploying {instance_count}-node cluster on {provider.value}")
    pulumi.log.info(f"Product: {product}")
    pulumi.log.info(f"Region: {region}, Zone: {zone}")
    pulumi.log.info("Using Gateway SSH bastion feature (no bastion VM)")
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
    
    # Register SSH keys in the cloud provider (delegated to provider implementation)
    if ssh_keys_to_register:
        cluster.register_ssh_keys(ssh_keys_to_register)
    
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
            # Include private key path if we generated one
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
    
    # Export SSH key info if we generated one
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

