"""
Scaleway image lookup utilities.

This module provides dynamic image lookup functionality to ensure
deployments always use the latest security-patched OS images.
"""

import pulumiverse_scaleway as scaleway
from typing import Optional


def get_rocky_linux_image(version: str, zone: str) -> str:
    """
    Look up the latest Rocky Linux image for the specified version.
    
    Uses Scaleway's marketplace image lookup to find the current
    UUID for Rocky Linux. This ensures deployments always use the
    latest patched version without hardcoding image IDs.
    
    Args:
        version: Rocky Linux version (e.g., "9")
        zone: Scaleway zone (e.g., "fr-par-1")
        
    Returns:
        Image ID (UUID)
        
    Example:
        >>> image_id = get_rocky_linux_image("9", "fr-par-1")
        >>> # Returns current UUID for rockylinux_9
    """
    label = f"rockylinux_{version}"
    
    image = scaleway.get_marketplace_image(
        label=label,
        zone=zone,
    )
    
    return image.id


def get_ubuntu_image(version: str, zone: str) -> str:
    """
    Look up the latest Ubuntu image for the specified version.
    
    Args:
        version: Ubuntu version (e.g., "22.04", "jammy")
        zone: Scaleway zone
        
    Returns:
        Image ID (UUID)
    """
    # Scaleway uses codenames like "ubuntu_jammy" or version-based labels
    if "." in version:
        # Convert version to codename mapping
        version_map = {
            "22.04": "jammy",
            "20.04": "focal",
        }
        label = f"ubuntu_{version_map.get(version, version)}"
    else:
        label = f"ubuntu_{version}"
    
    image = scaleway.get_marketplace_image(
        label=label,
        zone=zone,
    )
    
    return image.id


def get_debian_image(version: str, zone: str) -> str:
    """
    Look up the latest Debian image for the specified version.
    
    Args:
        version: Debian version (e.g., "11", "bullseye")
        zone: Scaleway zone
        
    Returns:
        Image ID (UUID)
    """
    label = f"debian_{version}"
    
    image = scaleway.get_marketplace_image(
        label=label,
        zone=zone,
    )
    
    return image.id


def get_os_image(os_name: str, version: str, zone: str, custom_image_id: Optional[str] = None) -> str:
    """
    Generic OS image lookup that routes to the appropriate function.
    
    If custom_image_id is provided, it returns that directly (useful for snapshots).
    Otherwise, it looks up the marketplace image for the specified OS.
    
    Args:
        os_name: OS name (rockylinux, ubuntu, debian)
        version: OS version
        zone: Scaleway zone
        custom_image_id: Custom image or snapshot ID (overrides marketplace lookup)
        
    Returns:
        Image ID (UUID)
        
    Raises:
        ValueError: If OS name is not supported
        
    Example:
        # Use marketplace image
        >>> get_os_image("rockylinux", "9", "fr-par-1")
        
        # Use custom snapshot
        >>> get_os_image("rockylinux", "9", "fr-par-1", 
        ...              custom_image_id="11111111-2222-3333-4444-555555555555")
    """
    # If custom image ID provided, use it directly
    if custom_image_id:
        return custom_image_id
    
    # Otherwise, lookup marketplace image
    os_name_lower = os_name.lower()
    
    if os_name_lower in ["rocky", "rockylinux", "rocky-linux"]:
        return get_rocky_linux_image(version, zone)
    elif os_name_lower == "ubuntu":
        return get_ubuntu_image(version, zone)
    elif os_name_lower == "debian":
        return get_debian_image(version, zone)
    else:
        raise ValueError(
            f"Unsupported OS: {os_name}. "
            f"Supported: rockylinux, ubuntu, debian"
        )

