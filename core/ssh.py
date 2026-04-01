"""
SSH key and configuration management utilities.

This module provides functions for generating SSH keys and creating
SSH config files for accessing deployed infrastructure.
"""

import os
import subprocess
import tempfile
from typing import Dict, Any, Optional
import pulumi


def generate_ssh_key_pair(key_name: str, output_dir: str = None) -> Dict[str, str]:
    """
    Generate an SSH key pair (ED25519).

    Args:
        key_name: Base name for the key files (e.g., "platform-spawner")
        output_dir: Directory to store keys (default: temp directory)

    Returns:
        Dictionary with:
        - private_key_path: Path to private key file
        - public_key_path: Path to public key file
        - public_key_content: Content of public key

    Raises:
        Exception: If ssh-keygen fails
    """
    if output_dir is None:
        output_dir = tempfile.gettempdir()

    # Ensure directory exists with proper permissions
    os.makedirs(output_dir, mode=0o755, exist_ok=True)

    private_key_path = os.path.join(output_dir, f"{key_name}")
    public_key_path = f"{private_key_path}.pub"

    # Check if key already exists
    if os.path.exists(private_key_path):
        pulumi.log.warn(
            f"SSH key already exists: {private_key_path}, using existing key"
        )
        with open(public_key_path, "r") as f:
            public_key_content = f.read().strip()

        return {
            "private_key_path": private_key_path,
            "public_key_path": public_key_path,
            "public_key_content": public_key_content,
        }

    # Generate ED25519 key (modern, secure, small)
    try:
        subprocess.run(
            [
                "ssh-keygen",
                "-t",
                "ed25519",
                "-f",
                private_key_path,
                "-N",
                "",  # No passphrase
                "-C",
                f"{key_name}@platform-spawner",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        pulumi.log.info(f"Generated SSH key pair: {private_key_path}")

        # Read public key content
        with open(public_key_path, "r") as f:
            public_key_content = f.read().strip()

        # Set proper permissions on private key
        os.chmod(private_key_path, 0o600)

        return {
            "private_key_path": private_key_path,
            "public_key_path": public_key_path,
            "public_key_content": public_key_content,
        }

    except subprocess.CalledProcessError as e:
        error_msg = (
            f"Failed to generate SSH key: {e.stderr if e.stderr else 'No error output'}"
        )
        error_msg += f"\nCommand: {' '.join(e.cmd)}"
        error_msg += f"\nReturn code: {e.returncode}"
        error_msg += f"\nOutput dir: {output_dir}"
        pulumi.log.error(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"Error generating SSH key: {e}"
        pulumi.log.error(error_msg)
        raise Exception(error_msg)


def generate_ssh_config(
    bastion_ip: str,
    bastion_port: int = 22,
    bastion_user: str = "rocky",
    node_user: str = "spawner",
    nodes: Dict[str, Dict[str, Any]] = None,
    private_key_path: Optional[str] = None,
    output_path: str = None,
) -> str:
    """
    Generate an SSH config file for accessing nodes via bastion VM.

    Args:
        bastion_ip: Bastion VM public IP address
        bastion_port: Bastion SSH port (default: 22)
        bastion_user: Bastion SSH user (default: "rocky" for Rocky Linux bastion)
        node_user: SSH user for worker nodes (default: "spawner")
        nodes: Dictionary of nodes with their connection info
        private_key_path: Path to private key (optional)
        output_path: Path to write config file (default: temp file)

    Returns:
        Path to the generated SSH config file

    Example nodes dict:
        {
            "node-01": {
                "name": "node-01",
                "private_ip": "192.168.10.2"
            }
        }

    Generated config allows:
        ssh bastion           # Connect to bastion
        ssh node-01           # Connect to node via bastion (ProxyJump)
    """
    if nodes is None:
        nodes = {}
    if output_path is None:
        output_dir = tempfile.gettempdir()
        output_path = os.path.join(output_dir, "ssh_config")

    config_lines = [
        "# SSH Config for Platform Spawner",
        "# Generated automatically - do not edit manually",
        "",
        "# Bastion/Jump Host",
        "Host bastion",
        f"  HostName {bastion_ip}",
        f"  Port {bastion_port}",
        f"  User {bastion_user}",
        "  StrictHostKeyChecking no",
        "  UserKnownHostsFile /dev/null",
    ]

    # If private key is provided, add it to node config as well (optional)
    # IdentityOnly ensures SSH uses the specified key
    # and doesn't try other keys from the agent or default locations
    if private_key_path:
        config_lines.append(f"  IdentityFile {private_key_path}")
        config_lines.append("  IdentitiesOnly yes")

    config_lines.extend(
        [
            "",
            "# Cluster Nodes (accessed via bastion)",
        ]
    )

    # Add configuration for each node
    for node_name, node_info in nodes.items():
        # Extract hostname from FQDN or use name
        if "fqdn" in node_info:
            hostname = node_info["fqdn"]
        elif "private_ip" in node_info:
            hostname = node_info["private_ip"]
        else:
            pulumi.log.warn(f"Node {node_name} has no fqdn or private_ip, skipping")
            continue

        config_lines.extend(
            [
                "",
                f"Host {node_name}",
                f"  HostName {hostname}",
                f"  User {node_user}",
                "  ProxyJump bastion",
                "  StrictHostKeyChecking no",
                "  UserKnownHostsFile /dev/null",
            ]
        )

        # If private key is provided, add it to node config as well (optional)
        # IdentityOnly ensures SSH uses the specified key
        # and doesn't try other keys from the agent or default locations
        if private_key_path:
            config_lines.append(f"  IdentityFile {private_key_path}")
            config_lines.append("  IdentitiesOnly yes")

    # Write config file
    os.makedirs(
        os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
        exist_ok=True,
    )

    with open(output_path, "w") as f:
        f.write("\n".join(config_lines))
        f.write("\n")

    # Set proper permissions
    os.chmod(output_path, 0o644)

    pulumi.log.info(f"Generated SSH config: {output_path}")

    return output_path


def extract_node_info_for_ssh_config(
    nodes_output: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """
    Extract relevant node information from Pulumi outputs for SSH config generation.

    Args:
        nodes_output: Dictionary of node outputs from cluster deployment

    Returns:
        Dictionary suitable for generate_ssh_config()

    Note:
        SSH command format: ssh -J {bastion_user}@{bastion_ip} {node_user}@{private_ip}
    """
    ssh_nodes = {}

    for node_name, node_data in nodes_output.items():
        ssh_nodes[node_name] = {
            "name": node_name,
            "private_ip": node_data.get("private_ip"),
        }

        # Extract target host from ssh_command if available
        if "ssh_command" in node_data:
            ssh_cmd = node_data["ssh_command"]
            # SSH command format: ssh -J {bastion_user}@{bastion_ip} {node_user}@{target}
            if "@" in ssh_cmd:
                parts = ssh_cmd.split("@")
                if len(parts) >= 3:
                    # Last part after @ is the target (private IP or FQDN)
                    target = parts[-1].strip()
                    # Only set fqdn if it looks like a hostname (contains dots but isn't just an IP)
                    if "." in target and not target.replace(".", "").isdigit():
                        ssh_nodes[node_name]["fqdn"] = target

    return ssh_nodes
